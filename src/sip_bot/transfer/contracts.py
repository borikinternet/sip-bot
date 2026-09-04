"""Typed transfer seam over the existing DialogueFSM/SIP boundary.

The application FSM remains the only owner that can authorize a transfer.  A
transfer adapter may consume only the already-approved ``DialogueCommand``
and returns the existing typed ``TransferResult``; it cannot manufacture a
dialogue decision or call SIP directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sip_bot.dialogue.actions import CommandKind, DialogueCommand
from sip_bot.dialogue.events import TransferResult


class TransferContractError(ValueError):
    """A command did not cross the approved FSM transfer boundary."""


@dataclass(frozen=True, slots=True)
class TransferCommand:
    """Validated view of an existing FSM ``TRANSFER`` command."""

    call_id: str
    target: str
    reason: str
    operation_id: int | None = None

    def __post_init__(self) -> None:
        if not self.call_id or not self.target or not self.reason:
            raise ValueError("transfer command requires call_id, target and reason")
        if self.operation_id is not None and self.operation_id < 1:
            raise ValueError("transfer operation_id must be positive")

    @classmethod
    def from_dialogue_command(cls, command: DialogueCommand) -> "TransferCommand":
        if not isinstance(command, DialogueCommand):
            raise TransferContractError("transfer input must be a DialogueCommand")
        if command.kind is not CommandKind.TRANSFER:
            raise TransferContractError("only an FSM TRANSFER command may reach the operator adapter")
        if not command.target:
            raise TransferContractError("FSM transfer command must contain an operator target")
        return cls(
            call_id=command.call_id,
            target=command.target,
            reason=command.reason or "transfer",
            operation_id=command.operation_id,
        )


class TransferOperator(Protocol):
    """Local operator boundary used by the production adapter and fake stand."""

    def transfer(self, command: TransferCommand) -> TransferResult:
        """Execute one already-authorized transfer and return its typed result."""

