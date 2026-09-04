"""Deterministic one-call Dialogue FSM and channel orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..control.events import ControlEvent, ControlEventKind
from ..control.lifecycle import CallScope
from ..sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from ..speech.contracts import FinalUserTurn
from .actions import (
    ActionValidationError,
    ActionValidator,
    ApprovedAction,
    ChannelOrchestrator,
    CommandKind,
    DialogueAction,
    DialogueCommand,
)
from .events import (
    PlaybackEvent,
    PlaybackStatus,
    SpeechEvent,
    SpeechEventKind,
    StructuredDecision,
    TransferResult,
    TransferStatus,
)


class DialogueState(StrEnum):
    IDLE = "idle"
    CALL_OPEN = "call_open"
    CONNECTED = "connected"
    LISTENING = "listening"
    THINKING = "thinking"
    PLAYING = "playing"
    OFFERING_TRANSFER = "offering_transfer"
    AWAITING_TRANSFER_CONFIRMATION = "awaiting_transfer_confirmation"
    TRANSFERRING = "transferring"
    TERMINAL = "terminal"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class Transition:
    sequence: int
    event: str
    previous: DialogueState
    current: DialogueState
    reason: str | None = None


class DialogueFSM:
    """FSM owner; all methods are fast and do not call external components."""

    def __init__(
        self,
        *,
        operator_target: str = "sip:operator@127.0.0.1:5090",
        command_sink: Callable[[DialogueCommand], None] | None = None,
        validator: ActionValidator | None = None,
        channels: ChannelOrchestrator | None = None,
    ) -> None:
        self.operator_target = operator_target
        self.command_sink = command_sink
        self.validator = validator or ActionValidator()
        self.channels = channels or ChannelOrchestrator()
        self.state = DialogueState.IDLE
        self.call_id: str | None = None
        self.operation_id = 0
        self._sequence = 0
        self._input_generation: int | None = None
        self._playback_generation: int | None = None
        self._pending_playback_action: DialogueAction | None = None
        self._terminalized = False
        self.trace: list[Transition] = []
        self.commands: list[DialogueCommand] = []
        self.ignored_events: list[tuple[str, str]] = []

    def bind_scope(self, scope: CallScope) -> None:
        """Use the application CallSession scope for dialogue channels."""

        self.channels.bind_scope(scope)

    @property
    def active_operation_id(self) -> int:
        return self.operation_id

    @property
    def is_terminal(self) -> bool:
        return self.state in {DialogueState.TERMINAL, DialogueState.CLOSED}

    @property
    def active_channels(self) -> tuple[tuple[str, int], ...]:
        """Current channel generations, exposed for diagnostics and adapters."""

        if self.call_id is None:
            return ()
        scope = self.channels.scopes.get(self.call_id)
        if scope is None:
            return ()
        return tuple((handle.channel_id, handle.generation) for handle in scope.channels(open_only=True))

    def handle(self, event: Any) -> None:
        if isinstance(event, ControlEvent):
            self._handle_control(event)
        elif isinstance(event, NormalizedSipEvent):
            self._handle_sip(event)
        elif isinstance(event, SpeechEvent):
            self._handle_speech(event)
        elif isinstance(event, FinalUserTurn):
            self._handle_turn(event)
        elif isinstance(event, StructuredDecision):
            self._handle_decision(event)
        elif isinstance(event, PlaybackEvent):
            self._handle_playback(event)
        elif isinstance(event, TransferResult):
            self._handle_transfer(event)
        else:
            self.ignored_events.append((type(event).__name__, "unsupported event"))

    dispatch = handle

    def _handle_control(self, event: ControlEvent) -> None:
        if event.kind is ControlEventKind.CALL_OPEN:
            self._open_call(event.call_id)
        elif event.kind is ControlEventKind.CALL_CLOSE:
            self._terminate(event.payload.reason, "call_close")
        elif event.kind is ControlEventKind.TERMINAL:
            self._terminate(event.payload.reason, "terminal")
        elif (
            event.kind is ControlEventKind.CHANNEL_CLOSE
            and self.call_id == event.call_id
            and event.channel_id == "playback"
        ):
            self._playback_generation = None
            if self.state in {DialogueState.PLAYING, DialogueState.OFFERING_TRANSFER}:
                self._transition(DialogueState.LISTENING, "channel_close")

    def _handle_sip(self, event: NormalizedSipEvent) -> None:
        if event.kind is SipEventKind.CALL_STARTED:
            self._open_call(event.call_id)
            return
        if self.is_terminal:
            self.ignored_events.append((event.kind.value, "terminal call"))
            return
        if self.call_id is not None and event.call_id != self.call_id:
            self.ignored_events.append((event.kind.value, "call mismatch"))
            return
        if event.kind is SipEventKind.CALL_ANSWERED:
            self._ensure_call(event.call_id)
            self._open_input_channel()
            self._transition(DialogueState.LISTENING, "call_answered")
        elif event.kind in {
            SipEventKind.REMOTE_HANGUP,
            SipEventKind.REMOTE_CANCEL,
            SipEventKind.CALL_ENDED,
            SipEventKind.MEDIA_FAILED,
            SipEventKind.RTP_TIMEOUT,
        }:
            self._terminate(event.reason or event.kind.value, event.kind.value)
        elif event.kind is SipEventKind.REMOTE_HOLD_STARTED:
            if self.state not in {DialogueState.TERMINAL, DialogueState.CLOSED}:
                self._transition(DialogueState.CONNECTED, "remote_hold")
        elif event.kind is SipEventKind.REMOTE_RESUMED:
            if self.state is DialogueState.CONNECTED:
                self._transition(DialogueState.LISTENING, "remote_resumed")

    def _handle_speech(self, event: SpeechEvent) -> None:
        if not self._matches_call(event.call_id) or self.is_terminal:
            return
        if event.kind in {SpeechEventKind.SPEECH_STARTED, SpeechEventKind.BARGE_IN, SpeechEventKind.SPEECH_RESUMED}:
            if self.state in {DialogueState.PLAYING, DialogueState.OFFERING_TRANSFER}:
                self._cancel_playback("barge_in")
            if self.state is DialogueState.THINKING:
                self._cancel_inference("speech_resumed")
            if self.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION:
                # The confirmation turn is already owned by the FSM. Keep the
                # state until its authoritative FinalUserTurn arrives; moving
                # to LISTENING here would route "Да." back through LLM and
                # repeat the offer instead of executing the approved transfer.
                return
            if self.state not in {DialogueState.CALL_OPEN, DialogueState.CONNECTED}:
                self._transition(DialogueState.LISTENING, event.kind.value)
        elif event.kind is SpeechEventKind.HARD_ENDPOINT:
            # Final text arrives separately from the assembler; no inference is started here.
            self.ignored_events.append((event.kind.value, "awaiting authoritative final turn"))

    def _handle_turn(self, event: FinalUserTurn) -> None:
        if not self._matches_call(event.call_id) or self.is_terminal:
            return
        if self.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION:
            if self._is_positive(event.text):
                self._start_transfer("user_confirmed")
            elif self._is_negative(event.text):
                self._transition(DialogueState.LISTENING, "transfer_declined")
            else:
                self._transition(DialogueState.LISTENING, "confirmation_unclear")
            return
        if self.state not in {
            DialogueState.LISTENING,
            DialogueState.CONNECTED,
            DialogueState.CALL_OPEN,
        }:
            self.ignored_events.append(("utterance_final", f"not accepted in {self.state.value}"))
            return
        self.operation_id += 1
        self._transition(DialogueState.THINKING, "utterance_final")
        self._emit(DialogueCommand(CommandKind.START_INFERENCE, event.call_id, operation_id=self.operation_id))

    def _handle_decision(self, decision: StructuredDecision) -> None:
        if self.call_id is None or self.is_terminal:
            return
        if decision.call_id is not None and decision.call_id != self.call_id:
            self.ignored_events.append(("decision", "call mismatch"))
            return
        if decision.operation_id is not None and decision.operation_id != self.operation_id:
            self.ignored_events.append(("decision", "stale operation"))
            return
        try:
            approved = self.validator.validate(decision, self.state)
        except ActionValidationError as exc:
            self.ignored_events.append(("decision", str(exc)))
            self._cancel_inference("invalid_decision")
            self._transition(DialogueState.LISTENING, "invalid_decision")
            return
        self._execute(approved)

    def _execute(self, approved: ApprovedAction) -> None:
        assert self.call_id is not None
        if approved.action in {DialogueAction.ANSWER, DialogueAction.CLARIFY} or approved.action is DialogueAction.OFFER_TRANSFER:
            self._start_playback(approved.action)
        elif approved.action is DialogueAction.TRANSFER:
            self._start_transfer("explicit_transfer")
        elif approved.action is DialogueAction.HANGUP:
            self._terminate("llm_hangup", "decision", emit_hangup=True)

    def _handle_playback(self, event: PlaybackEvent) -> None:
        if not self._matches_call(event.call_id) or self.is_terminal:
            return
        if event.operation_id is not None and event.operation_id != self.operation_id:
            self.ignored_events.append(("playback", "stale operation"))
            return
        if event.channel_generation is not None and event.channel_generation != self._playback_generation:
            self.ignored_events.append(("playback", "stale generation"))
            return
        if event.status is PlaybackStatus.STARTED:
            if self._pending_playback_action is DialogueAction.OFFER_TRANSFER:
                self._transition(DialogueState.OFFERING_TRANSFER, "playback_started")
            else:
                self._transition(DialogueState.PLAYING, "playback_started")
        elif event.status in {PlaybackStatus.COMPLETED, PlaybackStatus.STOPPED}:
            generation = self._playback_generation
            if generation is not None and self.call_id is not None:
                self.channels.close(self.call_id, "playback", event.status.value)
                self._emit(
                    DialogueCommand(
                        CommandKind.CLOSE_CHANNEL,
                        self.call_id,
                        reason=event.status.value,
                        channel_id="playback",
                        generation=generation,
                    )
                )
            pending = self._pending_playback_action
            self._playback_generation = None
            self._pending_playback_action = None
            if pending is DialogueAction.OFFER_TRANSFER and event.status is PlaybackStatus.COMPLETED:
                self._transition(DialogueState.AWAITING_TRANSFER_CONFIRMATION, "offer_played")
            else:
                self._transition(DialogueState.LISTENING, "playback_finished")
        elif event.status in {PlaybackStatus.CANCELLED, PlaybackStatus.FAILED}:
            generation = self._playback_generation
            if generation is not None and self.call_id is not None:
                self.channels.close(self.call_id, "playback", event.status.value)
                self._emit(
                    DialogueCommand(
                        CommandKind.CLOSE_CHANNEL,
                        self.call_id,
                        reason=event.status.value,
                        channel_id="playback",
                        generation=generation,
                    )
                )
            self._playback_generation = None
            self._pending_playback_action = None
            self._transition(DialogueState.LISTENING, event.status.value)

    def _handle_transfer(self, event: TransferResult) -> None:
        if not self._matches_call(event.call_id) or self.is_terminal:
            return
        if self.state is not DialogueState.TRANSFERRING:
            self.ignored_events.append(("transfer", "result outside transfer"))
            return
        if event.status is TransferStatus.COMPLETED:
            self._terminate("transfer_completed", "transfer_result")
        else:
            self._transition(DialogueState.LISTENING, event.reason or event.status.value)

    def _open_call(self, call_id: str) -> None:
        if not call_id:
            return
        if self.call_id == call_id:
            if self.is_terminal:
                self.ignored_events.append(("call_open", "call identity cannot be reused"))
            return
            return
        if self.call_id is not None and not self.is_terminal:
            self._terminate("replaced_by_new_call", "re-entry")
        self.call_id = call_id
        self.operation_id = 0
        self._input_generation = None
        self._playback_generation = None
        self._pending_playback_action = None
        self._terminalized = False
        self._transition(DialogueState.CALL_OPEN, "call_open")
        self._emit(DialogueCommand(CommandKind.ANSWER, call_id))

    def _ensure_call(self, call_id: str) -> None:
        if self.call_id is None or self.call_id != call_id:
            self._open_call(call_id)

    def _matches_call(self, call_id: str) -> bool:
        return self.call_id == call_id

    def _start_playback(self, action: DialogueAction) -> None:
        assert self.call_id is not None
        self._cancel_inference("decision_accepted", invalidate=False)
        handle = self.channels.open(self.call_id, "playback", "tts_playback")
        self._playback_generation = handle.generation
        self._pending_playback_action = action
        self._transition(DialogueState.OFFERING_TRANSFER if action is DialogueAction.OFFER_TRANSFER else DialogueState.PLAYING, "answer_approved")
        self._emit(DialogueCommand(CommandKind.OPEN_CHANNEL, self.call_id, channel_id="playback", channel_kind="tts_playback", generation=handle.generation))
        self._emit(DialogueCommand(CommandKind.APPROVE_ANSWER, self.call_id, action=action, channel_id="playback", generation=handle.generation, operation_id=self.operation_id))

    def _open_input_channel(self) -> None:
        assert self.call_id is not None
        if self._input_generation is not None:
            return
        handle = self.channels.open(self.call_id, "speech_ingress", "audio_input")
        self._input_generation = handle.generation
        self._emit(DialogueCommand(CommandKind.OPEN_CHANNEL, self.call_id, channel_id="speech_ingress", channel_kind="audio_input", generation=handle.generation))

    def _cancel_playback(self, reason: str) -> None:
        if self.call_id is None or self._playback_generation is None:
            return
        generation = self._playback_generation
        self.channels.close(self.call_id, "playback", reason)
        self._emit(DialogueCommand(CommandKind.CANCEL, self.call_id, reason=reason, channel_id="playback", generation=generation, operation_id=self.operation_id))
        self._emit(DialogueCommand(CommandKind.CLOSE_CHANNEL, self.call_id, reason=reason, channel_id="playback", generation=generation))
        self._playback_generation = None
        self._pending_playback_action = None

    def _cancel_inference(self, reason: str, *, invalidate: bool = True) -> None:
        if self.call_id is None or self.state is not DialogueState.THINKING:
            return
        cancelled_operation = self.operation_id
        if invalidate:
            self.operation_id += 1
        self._emit(DialogueCommand(CommandKind.CANCEL, self.call_id, reason=reason, operation_id=cancelled_operation))

    def _start_transfer(self, reason: str) -> None:
        assert self.call_id is not None
        self._cancel_playback(reason)
        self._cancel_inference(reason)
        self._transition(DialogueState.TRANSFERRING, reason)
        self._emit(DialogueCommand(CommandKind.TRANSFER, self.call_id, reason=reason, target=self.operator_target, operation_id=self.operation_id))

    def _terminate(self, reason: str, event_name: str, *, emit_hangup: bool = False) -> None:
        if self._terminalized:
            return
        self._terminalized = True
        if self.call_id is not None:
            self.operation_id += 1
            if emit_hangup:
                self._emit(DialogueCommand(CommandKind.HANGUP, self.call_id, reason=reason))
            self._emit(DialogueCommand(CommandKind.CANCEL, self.call_id, reason=reason, operation_id=self.operation_id))
            for handle in self.channels.close_all(self.call_id, reason):
                self._emit(DialogueCommand(CommandKind.CLOSE_CHANNEL, self.call_id, reason=reason, channel_id=handle.channel_id, channel_kind=handle.channel_kind, generation=handle.generation))
            self._emit(DialogueCommand(CommandKind.REPORT, self.call_id, reason=reason))
        self._transition(DialogueState.TERMINAL, event_name, reason)

    def _transition(self, state: DialogueState, event: str, reason: str | None = None) -> None:
        previous = self.state
        if previous is state:
            return
        self._sequence += 1
        self.state = state
        self.trace.append(Transition(self._sequence, event, previous, state, reason))

    def _emit(self, command: DialogueCommand) -> None:
        self.commands.append(command)
        if self.command_sink is not None:
            self.command_sink(command)

    @staticmethod
    def _is_positive(text: str) -> bool:
        normalized = text.strip().casefold().strip(" \t\r\n.,!?;:")
        return normalized in {"да", "так", "конечно", "подтверждаю", "соедините", "yes"}

    @staticmethod
    def _is_negative(text: str) -> bool:
        normalized = text.strip().casefold().strip(" \t\r\n.,!?;:")
        return normalized in {"нет", "не надо", "не нужно", "отмена", "no"}


DialogueStateMachine = DialogueFSM
