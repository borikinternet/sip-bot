"""Deterministic fake operator for the local J integration scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field

from sip_bot.dialogue.events import TransferResult, TransferStatus

from .contracts import TransferCommand, TransferOperator


@dataclass(slots=True)
class FakeOperator(TransferOperator):
    """A deliberately small stand adapter; no SIP or external service calls."""

    target: str
    available: bool = True
    accepted: list[TransferCommand] = field(default_factory=list)

    def transfer(self, command: TransferCommand) -> TransferResult:
        if command.target != self.target:
            return TransferResult(command.call_id, TransferStatus.FAILED, "operator_target_unavailable")
        if not self.available:
            return TransferResult(command.call_id, TransferStatus.FAILED, "operator_unavailable")
        self.accepted.append(command)
        return TransferResult(command.call_id, TransferStatus.COMPLETED, "operator_connected")


class TransferOrchestrator:
    """Adapt the existing FSM command to the fake/local operator boundary."""

    def __init__(self, operator: TransferOperator) -> None:
        self.operator = operator

    def execute(self, command: object) -> TransferResult:
        from .contracts import TransferCommand

        typed = TransferCommand.from_dialogue_command(command)  # type: ignore[arg-type]
        return self.operator.transfer(typed)

