"""Allowlisted dialogue decisions and side-effect commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..control.lifecycle import CallScope, ChannelHandle, LifecycleError
from .events import StructuredDecision


class DialogueAction(StrEnum):
    ANSWER = "answer"
    CLARIFY = "clarify"
    OFFER_TRANSFER = "offer_transfer"
    TRANSFER = "transfer"
    HANGUP = "hangup"


DecisionAction = DialogueAction


class ActionValidationError(ValueError):
    """A structured decision is malformed or not legal in the current state."""


@dataclass(frozen=True, slots=True)
class ApprovedAction:
    action: DialogueAction
    text: str | None = None
    operation_id: int | None = None


class ActionValidator:
    """Validate the finite action schema and state-specific allowlist."""

    def __init__(self, *, max_text_chars: int = 1000) -> None:
        self.max_text_chars = max_text_chars

    def validate(self, decision: StructuredDecision, state: object) -> ApprovedAction:
        try:
            action = DialogueAction(decision.action)
        except ValueError as exc:
            raise ActionValidationError(f"unsupported dialogue action: {decision.action!r}") from exc
        text_required = action in {
            DialogueAction.ANSWER,
            DialogueAction.CLARIFY,
            DialogueAction.OFFER_TRANSFER,
        }
        if text_required and not decision.text:
            raise ActionValidationError(f"action {action.value!r} requires text")
        if decision.text is not None and len(decision.text) > self.max_text_chars:
            raise ActionValidationError("decision text exceeds configured limit")
        state_value = getattr(state, "value", str(state))
        allowed = {
            "thinking": {DialogueAction.ANSWER, DialogueAction.CLARIFY, DialogueAction.OFFER_TRANSFER, DialogueAction.TRANSFER, DialogueAction.HANGUP},
            "connected": {DialogueAction.ANSWER, DialogueAction.CLARIFY, DialogueAction.OFFER_TRANSFER, DialogueAction.TRANSFER, DialogueAction.HANGUP},
            "listening": {DialogueAction.TRANSFER, DialogueAction.HANGUP},
            "awaiting_transfer_confirmation": {DialogueAction.TRANSFER, DialogueAction.HANGUP},
            "playing": {DialogueAction.TRANSFER, DialogueAction.HANGUP},
        }
        if action not in allowed.get(state_value, set()):
            raise ActionValidationError(f"action {action.value!r} is not allowed in state {state_value!r}")
        return ApprovedAction(action, decision.text, decision.operation_id)


class CommandKind(StrEnum):
    ANSWER = "answer"
    HANGUP = "hangup"
    TRANSFER = "transfer"
    OPEN_CHANNEL = "open_channel"
    CLOSE_CHANNEL = "close_channel"
    CANCEL = "cancel"
    START_INFERENCE = "start_inference"
    APPROVE_ANSWER = "approve_answer"
    PLAY_GREETING = "play_greeting"
    PLAY_TRANSFER_CONFIRMATION = "play_transfer_confirmation"
    REPORT = "report"


@dataclass(frozen=True, slots=True)
class DialogueCommand:
    """Control command; answer text remains on the direct TTS data plane."""

    kind: CommandKind | str
    call_id: str
    reason: str | None = None
    action: DialogueAction | None = None
    channel_id: str | None = None
    channel_kind: str | None = None
    generation: int | None = None
    operation_id: int | None = None
    target: str | None = None

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ValueError("command call_id must be non-empty")
        object.__setattr__(self, "kind", CommandKind(self.kind))
        if self.generation is not None and self.generation < 1:
            raise ValueError("command generation must be positive")


ControlCommand = DialogueCommand


class ChannelOrchestrator:
    """Own scoped channel handles and cancellation for the dialogue FSM."""

    def __init__(self) -> None:
        self.scopes: dict[str, CallScope] = {}

    def bind_scope(self, scope: CallScope) -> None:
        """Bind a session-owned scope before the FSM opens its channels.

        Application composition supplies the same ``CallScope`` that belongs
        to ``CallSession``.  The orchestrator may still create a scope for
        standalone FSM tests, but it must never replace an open application
        scope with an unrelated one.
        """

        current = self.scopes.get(scope.call_id)
        if current is not None and current is not scope and current.is_open:
            raise LifecycleError(f"a different open scope is already bound: {scope.call_id}")
        self.scopes[scope.call_id] = scope

    def open(self, call_id: str, channel_id: str, channel_kind: str) -> ChannelHandle:
        scope = self.scopes.get(call_id)
        if scope is None:
            scope = CallScope(call_id)
            self.scopes[call_id] = scope
        try:
            return scope.open_channel(channel_id, channel_kind)
        except LifecycleError:
            current = scope.get_channel(channel_id)
            if current.is_open:
                raise
            return scope.open_channel(channel_id, channel_kind)

    def close(self, call_id: str, channel_id: str, reason: str) -> tuple[ChannelHandle | None, bool]:
        scope = self.scopes.get(call_id)
        if scope is None:
            return None, False
        try:
            return scope.close_channel(channel_id, reason)
        except LifecycleError:
            return None, False

    def close_all(self, call_id: str, reason: str) -> tuple[ChannelHandle, ...]:
        scope = self.scopes.get(call_id)
        return scope.close(reason) if scope is not None else ()

    def cancel_all(self, call_id: str) -> int:
        scope = self.scopes.get(call_id)
        if scope is None:
            return 0
        changed = 0
        for handle in scope.channels():
            if handle.cancel_token.cancel():
                changed += 1
        return changed
