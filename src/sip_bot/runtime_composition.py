"""One-call application composition over the accepted component contracts.

This module is deliberately an orchestration boundary, not a second FSM or
dispatcher.  It connects the existing owners, keeps large data-plane values
out of the Dispatcher, and provides the report closeout hook required by the
MVP.  Heavy ASR/LLM/TTS work is supplied through owner callbacks and never
runs synchronously in a control transition.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .context import ContextStore
from .control import (
    CallSession,
    Dispatcher,
    SessionBindings,
    SessionLease,
)
from .dialogue import DialogueCommand, DialogueFSM
from .dialogue.events import PlaybackEvent, StructuredDecision, TransferResult
from .report import ReportFinalizer, ReportInput
from .retrieval import KnowledgeContext
from .understanding import SemanticActTrace, SemanticTurn


@dataclass(frozen=True, slots=True)
class CallOwners:
    """Named component references for one call.

    Only lifecycle ownership is represented here.  Data-plane methods remain
    on the respective component and are called through direct callbacks.
    """

    context: ContextStore
    report: ReportFinalizer
    sip_media: object | None = None
    speech: object | None = None
    retrieval: object | None = None
    prompt: object | None = None
    llm: object | None = None
    tts: object | None = None
    transfer: object | None = None

    def bindings(self) -> SessionBindings:
        return SessionBindings(
            sip_media=self.sip_media,
            speech=self.speech,
            context=self.context,
            retrieval=self.retrieval,
            prompt=self.prompt,
            llm=self.llm,
            tts=self.tts,
            transfer=self.transfer,
            report=self.report,
        )


class CallComposition:
    """Compose one existing Dispatcher/FSM pair with per-call owners."""

    __slots__ = (
        "_command_sink",
        "_control_observers",
        "_previous_command_sink",
        "_pending_report_reason",
        "_report_finalized",
        "_rag_contexts",
        "_semantic_traces",
        "_transfer_result",
        "commands",
        "dispatcher",
        "fsm",
        "owners",
        "session",
    )

    def __init__(
        self,
        dispatcher: Dispatcher,
        session: CallSession,
        owners: CallOwners,
        *,
        command_sink: Callable[[DialogueCommand], None] | None = None,
    ) -> None:
        if not isinstance(dispatcher, Dispatcher):
            raise TypeError("call composition requires the existing Dispatcher")
        if not isinstance(session.fsm, DialogueFSM):
            raise TypeError("call composition requires the existing DialogueFSM")
        if session.fsm is not dispatcher.fsm:
            raise ValueError("session FSM must be the Dispatcher FSM")
        if owners.context.call_id != session.call_id:
            raise ValueError("context owner call_id must match session call_id")
        self.dispatcher = dispatcher
        self.session = session
        self.fsm = session.fsm
        self.owners = owners
        self.commands: list[DialogueCommand] = []
        self._rag_contexts: list[KnowledgeContext] = []
        self._semantic_traces: list[SemanticActTrace] = []
        self._transfer_result: TransferResult | None = None
        self._report_finalized = False
        self._pending_report_reason: str | None = None
        self._command_sink = command_sink
        self._control_observers: list[Callable[[object, bool], None]] = []
        self._previous_command_sink = self.fsm.command_sink
        self.fsm.command_sink = self._on_command

    @property
    def report_finalized(self) -> bool:
        return self._report_finalized

    @property
    def report_path(self) -> Path | None:
        if not self._report_finalized:
            return None
        return self.owners.report.root / self.session.call_id / "report.md"

    @property
    def rag_contexts(self) -> tuple[KnowledgeContext, ...]:
        return tuple(self._rag_contexts)

    @property
    def semantic_traces(self) -> tuple[SemanticActTrace, ...]:
        return tuple(self._semantic_traces)

    def accept_semantic_turn(self, turn: SemanticTurn) -> bool:
        """Persist raw text once, then apply ordered typed acts to the FSM."""

        if not isinstance(turn, SemanticTurn):
            raise TypeError("composition accepts SemanticTurn only")
        source = turn.source
        lease = SessionLease(source.call_id, source.generation)

        def consume() -> None:
            self.owners.context.append_user(source.turn_id, source.text, revision=source.revision)
            for act_index, act in enumerate(turn.acts, start=1):
                if self.fsm.is_terminal:
                    break
                state_before = self.fsm.state.value
                ignored_before = len(self.fsm.ignored_events)
                self.fsm.handle(act)
                ignored = len(self.fsm.ignored_events) > ignored_before
                reason = self.fsm.ignored_events[-1][1] if ignored else None
                self._semantic_traces.append(
                    SemanticActTrace(
                        turn_id=source.turn_id,
                        act_index=act_index,
                        kind=act.kind,
                        span=act.span,
                        outcome="ignored" if ignored else "applied",
                        state_before=state_before,
                        state_after=self.fsm.state.value,
                        reason=reason,
                    )
                )

        accepted = self.session.dispatch_data(
            lease,
            consume,
        )
        if not accepted:
            return False
        self._flush_pending_report()
        return True

    def submit_control(self, event: object) -> bool:
        """Queue a compact typed control event; payload stays on direct paths."""

        if isinstance(event, TransferResult):
            if event.call_id != self.session.call_id:
                return False
            self._transfer_result = event
        accepted = self.dispatcher.submit(event)
        for observer in tuple(self._control_observers):
            observer(event, accepted)
        return accepted

    def drain_control(self, limit: int | None = None) -> int:
        processed = self.dispatcher.drain(limit)
        self._flush_pending_report()
        return processed

    def record_rag_context(self, context: KnowledgeContext) -> None:
        if not isinstance(context, KnowledgeContext):
            raise TypeError("composition accepts KnowledgeContext only")
        self._rag_contexts.append(context)

    def add_command_observer(self, observer: Callable[[DialogueCommand], None]) -> None:
        """Add a non-blocking command observer without replacing an owner hook."""

        if not callable(observer):
            raise TypeError("command observer must be callable")
        previous = self._command_sink

        def chained(command: DialogueCommand) -> None:
            if previous is not None:
                previous(command)
            observer(command)

        self._command_sink = chained

    def add_control_observer(self, observer: Callable[[object, bool], None]) -> None:
        """Observe control submission without routing payload through it.

        The observer is a procedural integration hook.  It receives the
        already-typed compact event and whether the Dispatcher accepted it;
        it must not perform a blocking operation or mutate FSM state.
        """

        if not callable(observer):
            raise TypeError("control observer must be callable")
        self._control_observers.append(observer)

    def append_assistant_text(
        self,
        turn_id: str,
        text: str,
        *,
        source_ids: tuple[str, ...] = (),
        knowledge_context_id: str | None = None,
    ) -> None:
        """Persist answer text directly; this is not a Dispatcher payload."""

        if not self.session.is_open:
            raise RuntimeError("cannot append assistant text after call close")
        self.owners.context.append_assistant(
            turn_id,
            text,
            source_ids=source_ids,
            knowledge_context_id=knowledge_context_id,
        )

    def finalize_report(self, terminal_reason: str) -> Path:
        """Finalize the sole required call artifact exactly once."""

        if not terminal_reason:
            raise ValueError("terminal_reason must be non-empty")
        if self._report_finalized:
            path = self.report_path
            assert path is not None
            return path
        if not self.fsm.is_terminal:
            raise RuntimeError("report can be finalized only after terminal FSM state")
        result = self.owners.report.finalize(
            ReportInput(
                call_id=self.session.call_id,
                terminal_state=self.fsm.state.value,
                terminal_reason=terminal_reason,
                context=self.owners.context.snapshot(),
                rag_contexts=tuple(self._rag_contexts),
                transitions=tuple(self.fsm.trace),
                semantic_traces=tuple(self._semantic_traces),
                transfer_result=self._transfer_result,
            )
        )
        self._report_finalized = True
        return result

    def close(self, reason: str) -> bool:
        return self.session.close(reason)

    def _on_command(self, command: DialogueCommand) -> None:
        self.commands.append(command)
        if self._previous_command_sink is not None:
            self._previous_command_sink(command)
        if self._command_sink is not None:
            self._command_sink(command)
        if command.kind.value == "report":
            # DialogueFSM emits REPORT while it is still inside _terminate;
            # wait until the state transition has returned before building the
            # report snapshot.
            self._pending_report_reason = command.reason or "dialogue_terminal"

    def _flush_pending_report(self) -> None:
        if self._pending_report_reason is not None and self.fsm.is_terminal:
            reason = self._pending_report_reason
            self._pending_report_reason = None
            self.finalize_report(reason)


__all__ = ["CallComposition", "CallOwners"]
