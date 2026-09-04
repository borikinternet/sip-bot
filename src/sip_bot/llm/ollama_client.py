"""The existing local Ollama HTTP IPC, hidden behind typed facade methods."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import constants
from sip_bot.prompt.manager import LlmRequest
from sip_bot.retrieval.contracts import EmbeddingRequest, EmbeddingResponse


class OllamaError(RuntimeError):
    """Base error mapped from the existing local HTTP process."""


class MalformedResponseError(OllamaError):
    """The process returned invalid or schema-incompatible JSON."""


class OllamaTimeoutError(OllamaError):
    """The HTTP operation exceeded its configured timeout."""


class OllamaTransportError(OllamaError):
    """The HTTP process could not be reached or closed unexpectedly."""


class ResponseLike(Protocol):
    def read(self, amount: int = -1) -> bytes: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


def _default_opener(url: str, body: bytes, timeout: float) -> ResponseLike:
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    return urlopen(request, timeout=timeout)  # noqa: S310 - endpoint is configured local IPC


def _map_transport_error(error: BaseException) -> OllamaError:
    if isinstance(error, (TimeoutError, socket.timeout)):
        return OllamaTimeoutError("Ollama HTTP operation timed out")
    if isinstance(error, URLError) and isinstance(error.reason, (TimeoutError, socket.timeout)):
        return OllamaTimeoutError("Ollama HTTP operation timed out")
    return OllamaTransportError(str(error) or error.__class__.__name__)


@dataclass(slots=True)
class OllamaNdjsonStream:
    response: ResponseLike
    closed: bool = False

    def __iter__(self) -> Iterator[dict[str, Any]]:
        while not self.closed:
            try:
                raw = self.response.readline()
            except OllamaError:
                raise
            except BaseException as error:
                raise _map_transport_error(error) from error
            if not raw:
                return
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise MalformedResponseError("invalid Ollama NDJSON line") from error
            if not isinstance(value, dict):
                raise MalformedResponseError("Ollama NDJSON item must be an object")
            yield value

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.response.close()


class OllamaHttpClient:
    """Small stdlib client; consumers only see facade-owned typed values."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        *,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        timeout_s: float = 30.0,
        thinking: bool = constants.LLM_THINKING_ENABLED,
        temperature: float = constants.LLM_TEMPERATURE,
        max_generation_tokens: int = constants.LLM_MAX_GENERATION_TOKENS,
        opener: Callable[[str, bytes, float], ResponseLike] | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.chat_model = constants.LLM_CHAT_MODEL if chat_model is None else chat_model
        self.embedding_model = constants.LLM_EMBEDDING_MODEL if embedding_model is None else embedding_model
        self.timeout_s = timeout_s
        self.thinking = thinking
        self.temperature = temperature
        self.max_generation_tokens = max_generation_tokens
        self._opener = _default_opener if opener is None else opener

    def open_chat(self, request: LlmRequest) -> OllamaNdjsonStream:
        allowed_actions = tuple(dict.fromkeys(request.allowed_actions))
        if not allowed_actions:
            raise ValueError("LLM request must declare at least one allowed action")
        output_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "text"],
            "properties": {
                "action": {"type": "string", "enum": list(allowed_actions)},
                "text": {"type": "string", "minLength": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        }
        payload = {
            "model": self.chat_model,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": True,
            "format": output_schema,
            "think": self.thinking,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_generation_tokens,
            },
        }
        try:
            response = self._opener(
                f"{self.endpoint}/api/chat",
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                self.timeout_s,
            )
        except BaseException as error:
            raise _map_transport_error(error) from error
        return OllamaNdjsonStream(response)

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        payload = {"model": request.model or self.embedding_model, "input": request.text}
        try:
            response = self._opener(
                f"{self.endpoint}/api/embed",
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                self.timeout_s,
            )
            raw = response.read()
        except BaseException as error:
            raise _map_transport_error(error) from error
        finally:
            if "response" in locals():
                response.close()
        try:
            value = json.loads(raw.decode("utf-8"))
            vectors = value["embeddings"]
            vector = vectors[0]
            if not isinstance(vector, list) or not vector or not all(isinstance(item, (int, float)) for item in vector):
                raise TypeError("embedding vector is invalid")
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise MalformedResponseError("invalid Ollama embedding response") from error
        return EmbeddingResponse(request.request_id, tuple(float(item) for item in vector), request.model)
