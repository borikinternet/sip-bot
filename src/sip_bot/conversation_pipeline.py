"""Direct data-plane orchestration for one composed conversation.

The dispatcher remains a fast control-plane serializer.  This module owns the
long-running work that follows an authoritative final user turn: retrieval,
prompt preparation, LLM streaming, TTS streaming and transfer execution.  It
uses short-lived worker threads and returns only compact typed decisions and
status events to the existing ``CallComposition``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any, Protocol

from .control import SessionLease
from .dialogue import DialogueAction, DialogueCommand
from .dialogue.events import PlaybackEvent, PlaybackStatus, StructuredDecision, TransferResult
from .llm import LlmFacade
from .llm.types import LlmStreamEvent, StreamEventKind
from .prompt import SkillPromptManager
from .retrieval import KnowledgeContext, KnowledgeQuery, LocalKnowledgeIndex
from .sip_media.models import NegotiatedMediaProfile
from .speech import FinalUserTurn
from .transfer import TransferOrchestrator
from .tts import ApprovedTextChunk, TtsPcmChunk

from .runtime_composition import CallComposition


class TtsStreamPort(Protocol):
    def stream_approved_text(
        self,
        chunks: Iterable[ApprovedTextChunk],
        *,
        channel_id: str,
        profile: NegotiatedMediaProfile,
        cancel: Event | None = None,
    ) -> Iterator[TtsPcmChunk]:
        """Stream approved text into normalized PCM chunks."""


class PipelineError(RuntimeError):
    """A pipeline owner or boundary failed outside the FSM."""


class ConversationPipeline:
    """Connect accepted A--H owners without moving payload through Dispatcher.

    The pipeline deliberately accepts only ``FinalUserTurn`` as its input.
    Retrieval and LLM/TTS work are never run by the dispatcher thread.  The
    caller supplies a main-loop ``drain_control`` call (or runs the existing
    Dispatcher thread) to apply the compact decisions and playback events.
    """

    def __init__(
        self,
        composition: CallComposition,
        *,
        query_builder: Any,
        retrieval: LocalKnowledgeIndex,
        prompt: SkillPromptManager,
        llm: LlmFacade,
        tts: TtsStreamPort | None = None,
        media_profile: NegotiatedMediaProfile | Callable[[], NegotiatedMediaProfile] | None = None,
        audio_sink: Callable[[TtsPcmChunk], None] | None = None,
        transfer: TransferOrchestrator | None = None,
        top_k: int = 3,
        threshold: float = 0.35,
    ) -> None:
        if not isinstance(composition, CallComposition):
            raise TypeError("conversation pipeline requires CallComposition")
        if not isinstance(retrieval, LocalKnowledgeIndex):
            raise TypeError("retrieval must be LocalKnowledgeIndex")
        if not isinstance(prompt, SkillPromptManager):
            raise TypeError("prompt must be SkillPromptManager")
        if not isinstance(llm, LlmFacade):
            raise TypeError("llm must be LlmFacade")
        if top_k < 1 or not 0.0 <= threshold <= 1.0:
            raise ValueError("top_k and threshold are invalid")
        if tts is not None and media_profile is None:
            raise ValueError("media_profile is required when TTS is configured")
        self.composition = composition
        self.query_builder = query_builder
        self.retrieval = retrieval
        self.prompt = prompt
        self.llm = llm
        self.tts = tts
        self.media_profile = media_profile
        self.audio_sink = audio_sink or (lambda _chunk: None)
        self.transfer = transfer
        self.top_k = top_k
        self.threshold = threshold
        self.errors: list[str] = []
        self._lock = RLock()
        self._closed = False
        self._threads: set[Thread] = set()
        self._turns: dict[int, FinalUserTurn] = {}
        self._operations: dict[int, Any] = {}
        self._cancel_events: dict[int, Event] = {}
        self._decisions: dict[int, StructuredDecision] = {}
        self._knowledge: dict[int, KnowledgeContext] = {}
        self.composition.add_command_observer(self._on_command)

    @property
    def active_workers(self) -> int:
        with self._lock:
            self._discard_finished_threads_locked()
            return len(self._threads)

    def submit_final_turn(self, turn: FinalUserTurn) -> bool:
        """Accept one authoritative turn and start non-blocking preparation."""

        if not isinstance(turn, FinalUserTurn):
            raise TypeError("pipeline accepts FinalUserTurn only")
        with self._lock:
            if self._closed:
                return False
            self._turns[self.composition.fsm.active_operation_id + 1] = turn
        accepted = self.composition.accept_final_turn(turn)
        if not accepted:
            with self._lock:
                self._remove_turn_locked(turn)
        return accepted

    def drain_control(self, limit: int | None = None) -> int:
        """Apply compact worker results on the existing Dispatcher path."""

        return self.composition.drain_control(limit)

    def wait(self, timeout: float = 1.0) -> bool:
        """Wait for current worker threads; useful for deterministic tests."""

        deadline = None if timeout is None else monotonic() + max(0.0, timeout)
        while True:
            with self._lock:
                threads = tuple(self._threads)
            if not threads:
                return True
            for thread in threads:
                remaining = None if deadline is None else max(0.0, deadline - monotonic())
                thread.join(remaining)
            with self._lock:
                self._discard_finished_threads_locked()
                if not self._threads:
                    return True
            if deadline is not None and monotonic() >= deadline:
                return False

    def close(self, reason: str = "pipeline_close") -> None:
        with self._lock:
            self._closed = True
            operations = tuple(self._operations.values())
            cancel_events = tuple(self._cancel_events.values())
        for cancel_event in cancel_events:
            cancel_event.set()
        for operation in operations:
            cancel = getattr(operation, "cancel", None)
            if callable(cancel):
                try:
                    cancel(reason=reason)
                except BaseException as exc:  # cleanup must not block call close
                    self._record_error(exc)

    def _on_command(self, command: DialogueCommand) -> None:
        if command.kind.value == "start_inference":
            self._start_inference(command)
        elif command.kind.value == "cancel":
            self._cancel_active(command.reason or "control_cancel")
        elif command.kind.value == "approve_answer":
            self._start_tts(command)
        elif command.kind.value == "transfer":
            self._start_transfer(command)

    def _start_inference(self, command: DialogueCommand) -> None:
        with self._lock:
            turn = self._turns.get(command.operation_id or 0)
            if self._closed or turn is None:
                return
            cancel_event = Event()
            self._cancel_events[command.operation_id or 0] = cancel_event
        thread = Thread(
            target=self._run_inference,
            args=(turn, command.operation_id or 0, cancel_event),
            name=f"sip-bot-inference-{command.operation_id}",
            daemon=True,
        )
        with self._lock:
            self._threads.add(thread)
        thread.start()

    def _run_inference(self, turn: FinalUserTurn, operation_id: int, cancel_event: Event) -> None:
        try:
            if not self._current(turn):
                return
            snapshot = self.composition.owners.context.snapshot()
            context = tuple((item.turn_id, item.text) for item in snapshot.turns[:-1])
            query: KnowledgeQuery = self.query_builder.build(turn.text, context=context)
            knowledge = self._retrieve(query, turn)
            if not self._current(turn) or cancel_event.is_set():
                return
            with self._lock:
                self._knowledge[operation_id] = knowledge
            self.composition.record_rag_context(knowledge)
            request = self.prompt.prepare_for_turn(
                final_turn=turn,
                snapshot=snapshot,
                knowledge_context=knowledge,
            )
            operation = self.llm.start_chat(request, final_user_turn_ns=turn.finalized_at_ns)
            with self._lock:
                self._operations[operation_id] = operation
            for event in operation:
                if cancel_event.is_set() or not self._current(turn):
                    return
                self._consume_llm_event(event, turn, operation_id)
        except BaseException as exc:  # typed control path records failure and preserves call liveness
            self._record_error(exc)
            self._recover_failed_inference(turn, operation_id)
        finally:
            with self._lock:
                self._operations.pop(operation_id, None)
                self._cancel_events.pop(operation_id, None)
                self._discard_finished_threads_locked()

    def _retrieve(self, query: KnowledgeQuery, turn: FinalUserTurn) -> KnowledgeContext:
        try:
            return self.retrieval.query(
                query,
                self.llm,
                top_k=self.top_k,
                threshold=self.threshold,
                context_id=f"knowledge-context-{turn.turn_id}",
            )
        except BaseException as exc:
            # This is an explicit source-unavailable context, not a lexical or
            # model-only fallback.  Prompt policy will produce offer_transfer.
            model = getattr(self.retrieval, "embedding_model", "unknown")
            version = getattr(self.retrieval, "index_version", "unavailable")
            return KnowledgeContext(
                context_id=f"knowledge-context-{turn.turn_id}",
                query_text=query.authoritative_text,
                hits=(),
                sufficient=False,
                threshold=self.threshold,
                top_k=self.top_k,
                index_version=version,
                embedding_model=model,
                failure=f"{type(exc).__name__}: {exc}",
            )

    def _consume_llm_event(self, event: LlmStreamEvent, turn: FinalUserTurn, operation_id: int) -> None:
        if not isinstance(event, LlmStreamEvent):
            raise PipelineError("LLM facade returned an untyped stream event")
        if event.kind is StreamEventKind.ERROR:
            with self._lock:
                operation = self._operations.get(operation_id)
            detail = getattr(operation, "error_detail", None)
            suffix = f": {detail}" if detail else ""
            raise PipelineError(f"LLM operation failed: {event.error_code}{suffix}")
        if event.kind is not StreamEventKind.DECISION or event.decision is None:
            return
        raw = event.decision
        decision = StructuredDecision(
            action=raw.action,
            text=raw.text,
            call_id=turn.call_id,
            operation_id=operation_id,
            confidence=raw.confidence,
        )
        with self._lock:
            if not self._current_locked(turn):
                return
            self._decisions[operation_id] = decision
        if not self.composition.submit_control(decision):
            raise PipelineError("dispatcher rejected structured LLM decision")

    def _recover_failed_inference(self, turn: FinalUserTurn, operation_id: int) -> None:
        """Return a failed THINKING state to the FSM without inventing an answer."""

        if not self._current(turn):
            return
        self.composition.submit_control(
            StructuredDecision(
                action="backend_failure",
                call_id=turn.call_id,
                operation_id=operation_id,
            )
        )

    def _start_tts(self, command: DialogueCommand) -> None:
        operation_id = command.operation_id or 0
        try:
            if self.tts is None:
                raise PipelineError("approved answer has no configured TTS owner")
            with self._lock:
                decision = self._decisions.get(operation_id)
                turn = self._turns.get(operation_id)
                knowledge = self._knowledge.get(operation_id)
                if self._closed or decision is None or turn is None or not self._current_locked(turn):
                    return
                cancel_event = self._cancel_events.setdefault(operation_id, Event())
            if decision.text is None or decision.action not in {
                DialogueAction.ANSWER.value,
                DialogueAction.CLARIFY.value,
                DialogueAction.OFFER_TRANSFER.value,
            }:
                raise PipelineError("approved playback has no answer text")
            self.composition.append_assistant_text(
                f"{turn.turn_id}:answer",
                decision.text,
                source_ids=knowledge.source_ids if knowledge is not None else (),
                knowledge_context_id=knowledge.context_id if knowledge is not None else None,
            )
            profile = self._resolve_profile()
            generation = command.generation or 1
            channel_id = command.channel_id or "playback"
            thread = Thread(
                target=self._run_tts,
                args=(turn, operation_id, generation, channel_id, decision.text, cancel_event, profile),
                name=f"sip-bot-tts-{operation_id}",
                daemon=True,
            )
            with self._lock:
                self._threads.add(thread)
            thread.start()
        except BaseException as exc:
            self._record_error(exc)
            turn = self._turns.get(operation_id)
            if turn is not None and self._current(turn):
                self.composition.submit_control(
                    PlaybackEvent(
                        turn.call_id,
                        PlaybackStatus.FAILED,
                        channel_id=command.channel_id or "playback",
                        channel_generation=command.generation,
                        operation_id=operation_id,
                        reason=type(exc).__name__,
                    )
                )

    def _run_tts(
        self,
        turn: FinalUserTurn,
        operation_id: int,
        generation: int,
        channel_id: str,
        text: str,
        cancel_event: Event,
        profile: NegotiatedMediaProfile,
    ) -> None:
        try:
            approved = ApprovedTextChunk(
                operation_id=f"llm-{operation_id}",
                call_id=turn.call_id,
                turn_id=turn.turn_id,
                generation=generation,
                sequence=1,
                text=text,
                is_final=True,
            )
            for chunk in self.tts.stream_approved_text(
                (approved,),
                channel_id=channel_id,
                profile=profile,
                cancel=cancel_event,
            ):
                if cancel_event.is_set() or not self._current(turn):
                    return
                if not isinstance(chunk, TtsPcmChunk):
                    raise PipelineError("TTS returned an untyped PCM chunk")
                self.audio_sink(chunk)
            if cancel_event.is_set() or not self._current(turn):
                return
            self.composition.submit_control(
                PlaybackEvent(
                    turn.call_id,
                    PlaybackStatus.COMPLETED,
                    channel_id=channel_id,
                    channel_generation=generation,
                    operation_id=operation_id,
                )
            )
        except BaseException as exc:
            self._record_error(exc)
            if self._current(turn):
                self.composition.submit_control(
                    PlaybackEvent(
                        turn.call_id,
                        PlaybackStatus.FAILED,
                        channel_id=channel_id,
                        channel_generation=generation,
                        operation_id=operation_id,
                        reason=type(exc).__name__,
                    )
                )
        finally:
            with self._lock:
                self._discard_finished_threads_locked()

    def _start_transfer(self, command: DialogueCommand) -> None:
        if self.transfer is None:
            self._record_error(PipelineError("transfer command has no configured transfer owner"))
            return
        thread = Thread(
            target=self._run_transfer,
            args=(command,),
            name="sip-bot-transfer",
            daemon=True,
        )
        with self._lock:
            self._threads.add(thread)
        thread.start()

    def _run_transfer(self, command: DialogueCommand) -> None:
        try:
            result = self.transfer.execute(command)
            if not isinstance(result, TransferResult):
                raise PipelineError("transfer owner returned an untyped result")
            self.composition.submit_control(result)
        except BaseException as exc:
            self._record_error(exc)
        finally:
            with self._lock:
                self._discard_finished_threads_locked()

    def _cancel_active(self, reason: str) -> None:
        with self._lock:
            operations = tuple(self._operations.values())
            for cancel_event in self._cancel_events.values():
                cancel_event.set()
        for operation in operations:
            cancel = getattr(operation, "cancel", None)
            if callable(cancel):
                try:
                    cancel(reason=reason)
                except BaseException as exc:
                    self._record_error(exc)

    def _resolve_profile(self) -> NegotiatedMediaProfile:
        profile = self.media_profile() if callable(self.media_profile) else self.media_profile
        if not isinstance(profile, NegotiatedMediaProfile):
            raise PipelineError("TTS playback requires the negotiated media profile")
        return profile

    def _current(self, turn: FinalUserTurn) -> bool:
        with self._lock:
            return self._current_locked(turn)

    def _current_locked(self, turn: FinalUserTurn) -> bool:
        return not self._closed and self.composition.session.accepts(SessionLease(turn.call_id, turn.generation))

    def _remove_turn_locked(self, turn: FinalUserTurn) -> None:
        for operation_id, candidate in tuple(self._turns.items()):
            if candidate is turn:
                self._turns.pop(operation_id, None)

    def _discard_finished_threads_locked(self) -> None:
        self._threads = {thread for thread in self._threads if thread.is_alive()}

    def _record_error(self, error: BaseException) -> None:
        with self._lock:
            self.errors.append(f"{type(error).__name__}: {error}")


__all__ = ["ConversationPipeline", "PipelineError", "TtsStreamPort"]
