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
from time import monotonic, monotonic_ns
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
from .tts import ApprovedTextChunk, TtsLatencyEvent, TtsLatencySink, TtsLatencyStage, TtsPcmChunk
from .understanding import KnowledgeRequestAct, SemanticTurn

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

    The pipeline deliberately accepts only ``SemanticTurn`` as its input.
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
        greeting_text: str | None = None,
        transfer_confirmation_text: str | None = None,
        top_k: int = 3,
        threshold: float = 0.35,
        latency_sink: TtsLatencySink | None = None,
        clock_ns: Callable[[], int] = monotonic_ns,
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
        self.greeting_text = greeting_text.strip() if greeting_text is not None else ""
        self.transfer_confirmation_text = (
            transfer_confirmation_text.strip() if transfer_confirmation_text is not None else ""
        )
        self.top_k = top_k
        self.threshold = threshold
        self.latency_sink = latency_sink
        self.clock_ns = clock_ns
        self.errors: list[str] = []
        self._lock = RLock()
        self._closed = False
        self._threads: set[Thread] = set()
        self._turns: dict[int, FinalUserTurn] = {}
        self._contents: dict[int, KnowledgeRequestAct] = {}
        self._pending_submission: tuple[FinalUserTurn, list[KnowledgeRequestAct]] | None = None
        self._operations: dict[int, Any] = {}
        self._cancel_events: dict[int, Event] = {}
        self._decisions: dict[int, StructuredDecision] = {}
        self._llm_final_result_ns: dict[int, int] = {}
        self._knowledge: dict[int, KnowledgeContext] = {}
        self.composition.add_command_observer(self._on_command)

    @property
    def active_workers(self) -> int:
        with self._lock:
            self._discard_finished_threads_locked()
            return len(self._threads)

    def submit_semantic_turn(self, turn: SemanticTurn) -> bool:
        """Accept one parsed turn and start non-blocking content preparation."""

        if not isinstance(turn, SemanticTurn):
            raise TypeError("pipeline accepts SemanticTurn only")
        with self._lock:
            if self._closed:
                return False
            if self._pending_submission is not None:
                raise PipelineError("semantic turn submission is not re-entrant")
            self._pending_submission = (
                turn.source,
                [act for act in turn.acts if isinstance(act, KnowledgeRequestAct)],
            )
        try:
            return self.composition.accept_semantic_turn(turn)
        finally:
            with self._lock:
                self._pending_submission = None

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
        elif command.kind.value == "play_greeting":
            self._start_greeting(command)
        elif command.kind.value == "play_transfer_confirmation":
            self._start_transfer_confirmation(command)
        elif command.kind.value == "transfer":
            self._start_transfer(command)

    def _start_inference(self, command: DialogueCommand) -> None:
        with self._lock:
            operation_id = command.operation_id or 0
            pending = self._pending_submission
            if self._closed or pending is None or not pending[1]:
                return
            turn = pending[0]
            content = pending[1].pop(0)
            self._turns[operation_id] = turn
            self._contents[operation_id] = content
            cancel_event = Event()
            self._cancel_events[operation_id] = cancel_event
        thread = Thread(
            target=self._run_inference,
            args=(turn, content, operation_id, cancel_event),
            name=f"sip-bot-inference-{command.operation_id}",
            daemon=True,
        )
        with self._lock:
            self._threads.add(thread)
        thread.start()

    def _run_inference(
        self,
        turn: FinalUserTurn,
        content: KnowledgeRequestAct,
        operation_id: int,
        cancel_event: Event,
    ) -> None:
        try:
            if not self._current(turn):
                return
            snapshot = self.composition.owners.context.snapshot()
            context = (
                tuple((item.turn_id, item.text) for item in snapshot.turns[:-1])
                if self.query_builder.requires_dialogue_context(content.content)
                else ()
            )
            query: KnowledgeQuery = self.query_builder.build(content.content, context=context)
            knowledge = self._retrieve(query, turn)
            if not self._current(turn) or cancel_event.is_set():
                return
            with self._lock:
                self._knowledge[operation_id] = knowledge
            self.composition.record_rag_context(knowledge)
            request = self.prompt.prepare(
                call_id=turn.call_id,
                turn_id=turn.turn_id,
                final_user_text=content.content,
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
                self._contents.pop(operation_id, None)
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
            self._llm_final_result_ns[operation_id] = event.timestamp_ns
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
            final_result_ns = self._llm_final_result_ns.get(operation_id)
            if final_result_ns is not None:
                self._emit_tts_latency(
                    operation_id=f"llm-{operation_id}",
                    call_id=turn.call_id,
                    turn_id=turn.turn_id,
                    channel_id=channel_id,
                    generation=generation,
                    stage=TtsLatencyStage.LLM_FINAL_RESULT,
                    timestamp_ns=final_result_ns,
                )
            self._emit_tts_latency(
                operation_id=f"llm-{operation_id}",
                call_id=turn.call_id,
                turn_id=turn.turn_id,
                channel_id=channel_id,
                generation=generation,
                stage=TtsLatencyStage.TTS_COMMAND_ACCEPTED,
            )
            thread = Thread(
                target=self._run_tts_payload,
                args=(
                    turn.call_id,
                    turn.turn_id,
                    f"llm-{operation_id}",
                    operation_id,
                    generation,
                    channel_id,
                    decision.text,
                    cancel_event,
                    profile,
                    lambda: self._current(turn),
                ),
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

    def _start_greeting(self, command: DialogueCommand) -> None:
        self._start_static_playback(
            command,
            text=self.greeting_text,
            turn_id=f"{self.composition.session.call_id}:greeting",
            operation_key="call-greeting",
            label="greeting",
        )

    def _start_transfer_confirmation(self, command: DialogueCommand) -> None:
        self._start_static_playback(
            command,
            text=self.transfer_confirmation_text,
            turn_id=f"{self.composition.session.call_id}:transfer-confirmation:{command.operation_id or 0}",
            operation_key=f"transfer-confirmation-{command.operation_id or 0}",
            label="transfer confirmation",
        )

    def _start_static_playback(
        self,
        command: DialogueCommand,
        *,
        text: str,
        turn_id: str,
        operation_key: str,
        label: str,
    ) -> None:
        operation_id = command.operation_id or 0
        try:
            if self.tts is None:
                raise PipelineError(f"configured {label} has no TTS owner")
            if not text:
                raise PipelineError(f"configured {label} text must be non-empty")
            with self._lock:
                if self._closed or not self._session_current():
                    return
                cancel_event = self._cancel_events.setdefault(operation_id, Event())
            self.composition.append_assistant_text(
                turn_id,
                text,
            )
            profile = self._resolve_profile()
            generation = command.generation or 1
            channel_id = command.channel_id or "playback"
            thread = Thread(
                target=self._run_tts_payload,
                args=(
                    self.composition.session.call_id,
                    turn_id,
                    operation_key,
                    operation_id,
                    generation,
                    channel_id,
                    text,
                    cancel_event,
                    profile,
                    self._session_current,
                ),
                name=f"sip-bot-tts-{operation_key}",
                daemon=True,
            )
            with self._lock:
                self._threads.add(thread)
            thread.start()
        except BaseException as exc:
            self._record_error(exc)
            if self._session_current():
                self.composition.submit_control(
                    PlaybackEvent(
                        self.composition.session.call_id,
                        PlaybackStatus.FAILED,
                        channel_id=command.channel_id or "playback",
                        channel_generation=command.generation,
                        operation_id=operation_id,
                        reason=type(exc).__name__,
                    )
                )

    def _run_tts_payload(
        self,
        call_id: str,
        turn_id: str,
        operation_key: str,
        operation_id: int,
        generation: int,
        channel_id: str,
        text: str,
        cancel_event: Event,
        profile: NegotiatedMediaProfile,
        current: Callable[[], bool],
    ) -> None:
        try:
            self._emit_tts_latency(
                operation_id=operation_key,
                call_id=call_id,
                turn_id=turn_id,
                channel_id=channel_id,
                generation=generation,
                stage=TtsLatencyStage.TTS_WORKER_STARTED,
            )
            approved = ApprovedTextChunk(
                operation_id=operation_key,
                call_id=call_id,
                turn_id=turn_id,
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
                if cancel_event.is_set() or not current():
                    return
                if not isinstance(chunk, TtsPcmChunk):
                    raise PipelineError("TTS returned an untyped PCM chunk")
                self.audio_sink(chunk)
            if cancel_event.is_set() or not current():
                return
            self.composition.submit_control(
                PlaybackEvent(
                    call_id,
                    PlaybackStatus.PRODUCER_COMPLETED,
                    channel_id=channel_id,
                    channel_generation=generation,
                    operation_id=operation_id,
                )
            )
        except BaseException as exc:
            self._record_error(exc)
            if current():
                self.composition.submit_control(
                    PlaybackEvent(
                        call_id,
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

    def _emit_tts_latency(
        self,
        *,
        operation_id: str,
        call_id: str,
        turn_id: str,
        channel_id: str,
        generation: int,
        stage: TtsLatencyStage,
        timestamp_ns: int | None = None,
    ) -> None:
        sink = self.latency_sink
        if sink is None:
            return
        try:
            sink(
                TtsLatencyEvent(
                    operation_id=operation_id,
                    call_id=call_id,
                    turn_id=turn_id,
                    channel_id=channel_id,
                    generation=generation,
                    stage=stage,
                    timestamp_ns=self.clock_ns() if timestamp_ns is None else timestamp_ns,
                )
            )
        except Exception:
            # Timing evidence is observational and cannot fail the dialogue.
            return

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

    def _session_current(self) -> bool:
        with self._lock:
            return not self._closed and self.composition.session.accepts(self.composition.session.lease())

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
