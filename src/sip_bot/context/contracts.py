"""Typed context-facing boundary values."""

from __future__ import annotations

from dataclasses import dataclass

from sip_bot.speech.contracts import FinalUserTurn
from .store import ContextSnapshot


# Backward-compatible name for callers that used the initial F draft.  The
# speech contract is authoritative; context must not define a second turn type.
FinalTurnContext = FinalUserTurn


@dataclass(frozen=True, slots=True)
class ContextInput:
    final_turn: FinalTurnContext
    snapshot: ContextSnapshot


__all__ = ["ContextInput", "ContextSnapshot", "FinalTurnContext", "FinalUserTurn"]
