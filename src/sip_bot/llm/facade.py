"""Typed facade lifecycle, structured output mapping and stale suppression."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterator
from time import monotonic_ns

from sip_bot.dialogue.events import StructuredDecision
from sip_bot.prompt.manager import LlmRequest
from sip_bot.retrieval.contracts import EmbeddingRequest, EmbeddingResponse

from .ollama_client import (
    MalformedResponseError,
    OllamaError,
    OllamaHttpClient,
    OllamaTimeoutError,
    OllamaTransportError,
)
from .telemetry import LatencyTrace
from .types import CancelRequest, InferenceStatus, InferenceStatusKind, LlmStreamEvent, StreamEventKind


class ChatOperation:
    """One authoritative request and its cancellable HTTP stream."""

    def __init__(self, client: OllamaHttpClient, request: LlmRequest, final_user_turn_ns: int | None) -> None:
        self.client = client
        self.request = request
        self.operation_id = uuid.uuid4().hex
        self.trace = LatencyTrace.start(final_user_turn_ns)
        self.status = InferenceStatus(self.operation_id, request.call_id, InferenceStatusKind.CREATED, monotonic_ns())
        self._cancelled = threading.Event()
        self._cancel_request: CancelRequest | None = None
        self._stream = None
        self._lock = threading.Lock()
        self._iterated = False
        self.error_detail: str | None = None

    def cancel(self, request: CancelRequest | None = None, *, reason: str = "caller_cancelled") -> None:
        cancel_request = request or CancelRequest(self.operation_id, self.request.call_id, reason)
        if cancel_request.operation_id != self.operation_id or cancel_request.call_id != self.request.call_id:
            raise ValueError("cancel request does not match operation")
        with self._lock:
            if self._cancelled.is_set():
                return
            self._cancel_request = cancel_request
            self.trace.mark_cancel_requested()
            self._cancelled.set()
            if self._stream is not None:
                self._stream.close()

    def __iter__(self) -> Iterator[LlmStreamEvent]:
        with self._lock:
            if self._iterated:
                raise RuntimeError("chat operation can be consumed only once")
            self._iterated = True
        if self._cancelled.is_set():
            yield self._cancelled_event()
            return

        self.trace.mark_request_started()
        self.status = InferenceStatus(self.operation_id, self.request.call_id, InferenceStatusKind.RUNNING, monotonic_ns())
        yield self._event(StreamEventKind.STARTED)
        accumulated = ""
        try:
            self._stream = self.client.open_chat(self.request)
            if self._cancelled.is_set():
                self._stream.close()
            for payload in self._stream:
                if self._cancelled.is_set():
                    continue
                now = monotonic_ns()
                self.trace.mark_first_stream_event(now)
                delta, done = self._decode_payload(payload)
                if delta:
                    accumulated += delta
                    self.trace.mark_first_usable_output(now)
                    yield self._event(StreamEventKind.DELTA, timestamp_ns=now, text_delta=delta, text=accumulated)
                if done:
                    decision = self._decode_decision(accumulated)
                    self.trace.mark_final_result(now)
                    yield self._event(StreamEventKind.DECISION, timestamp_ns=now, decision=decision, text=accumulated)
                    yield self._event(StreamEventKind.COMPLETED, timestamp_ns=now, text=accumulated)
                    self.status = InferenceStatus(
                        self.operation_id, self.request.call_id, InferenceStatusKind.COMPLETED, now
                    )
                    return
            if self._cancelled.is_set():
                yield self._cancelled_event()
            else:
                raise MalformedResponseError("Ollama stream ended before done=true")
        except OllamaError as error:
            if self._cancelled.is_set():
                yield self._cancelled_event()
                return
            self.error_detail = str(error) or error.__class__.__name__
            code = self._error_code(error)
            self.status = InferenceStatus(self.operation_id, self.request.call_id, InferenceStatusKind.FAILED, monotonic_ns(), code)
            yield self._event(StreamEventKind.ERROR, error_code=code)
        finally:
            if self._stream is not None:
                self._stream.close()

    def _decode_payload(self, payload: dict[str, object]) -> tuple[str, bool]:
        if "error" in payload:
            raise OllamaTransportError(str(payload["error"]))
        message = payload.get("message")
        if message is not None:
            if not isinstance(message, dict):
                raise MalformedResponseError("message must be an object")
            content = message.get("content", "")
        else:
            content = payload.get("response", "")
        if not isinstance(content, str):
            raise MalformedResponseError("response content must be a string")
        done = payload.get("done", False)
        if not isinstance(done, bool):
            raise MalformedResponseError("done must be boolean")
        return content, done

    @staticmethod
    def _decode_decision(text: str) -> StructuredDecision:
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, TypeError) as error:
            sample = text.strip().replace("\n", "\\n")[:512]
            raise MalformedResponseError(
                f"final response is not structured JSON; raw={sample!r}"
            ) from error
        if not isinstance(value, dict):
            raise MalformedResponseError("final response must be a JSON object")
        try:
            return StructuredDecision.from_mapping(value)
        except (TypeError, ValueError) as error:
            raise MalformedResponseError("final response violates structured decision schema") from error

    def _cancelled_event(self) -> LlmStreamEvent:
        now = monotonic_ns()
        self.status = InferenceStatus(self.operation_id, self.request.call_id, InferenceStatusKind.CANCELLED, now)
        return self._event(StreamEventKind.CANCELLED, timestamp_ns=now)

    def _event(self, kind: StreamEventKind, *, timestamp_ns: int | None = None, **kwargs: object) -> LlmStreamEvent:
        return LlmStreamEvent(
            self.operation_id,
            self.request.call_id,
            self.request.turn_id,
            kind,
            monotonic_ns() if timestamp_ns is None else timestamp_ns,
            **kwargs,
        )

    @staticmethod
    def _error_code(error: OllamaError) -> str:
        if isinstance(error, MalformedResponseError):
            return "malformed_response"
        if isinstance(error, OllamaTimeoutError):
            return "timeout"
        if isinstance(error, OllamaTransportError):
            return "transport_error"
        return "inference_error"


class LlmFacade:
    """Application-facing facade; no consumer needs Ollama JSON or URLs."""

    def __init__(self, client: OllamaHttpClient) -> None:
        self.client = client

    def start_chat(self, request: LlmRequest, *, final_user_turn_ns: int | None = None) -> ChatOperation:
        return ChatOperation(self.client, request, final_user_turn_ns)

    def warmup(self, request: LlmRequest) -> LatencyTrace:
        """Force one complete structured chat before the first live call.

        Ollama loads the chat model lazily.  This method deliberately uses the
        same typed request/facade path as a real turn, consumes the stream to
        ``done=true`` and refuses to declare readiness on a partial or failed
        response.
        """

        if not isinstance(request, LlmRequest):
            raise TypeError("LLM warmup requires LlmRequest")
        operation = self.start_chat(request)
        events = list(operation)
        if operation.status.status is not InferenceStatusKind.COMPLETED:
            error = next((event.error_code for event in events if event.kind is StreamEventKind.ERROR), None)
            raise OllamaError(f"LLM warmup did not complete{': ' + error if error else ''}")
        if not any(event.kind is StreamEventKind.DECISION for event in events):
            raise OllamaError("LLM warmup completed without a structured decision")
        return operation.trace

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        response = self.client.embed(request)
        if response.request_id != request.request_id or response.model != request.model:
            raise ValueError("embedding response does not match request")
        return response
