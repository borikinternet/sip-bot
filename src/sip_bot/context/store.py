"""Bounded, text-only conversation context persistence.

The store is deliberately independent from the control event bus.  It accepts
authoritative text payloads and appends JSONL snapshots for a single call.
Audio is never accepted or persisted here.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _check_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} must be a safe non-empty identifier")
    return value


@dataclass(frozen=True, slots=True)
class ContextTurn:
    call_id: str
    turn_id: str
    role: str
    text: str
    revision: int
    source_ids: tuple[str, ...] = ()
    knowledge_context_id: str | None = None

    def __post_init__(self) -> None:
        _check_id(self.call_id, "call_id")
        _check_id(self.turn_id, "turn_id")
        if self.role not in {"user", "assistant", "system"}:
            raise ValueError("role must be user, assistant or system")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("context text must be non-empty")
        if self.revision < 1:
            raise ValueError("revision must be positive")


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    call_id: str
    revision: int
    turns: tuple[ContextTurn, ...]

    @property
    def text_chars(self) -> int:
        return sum(len(turn.text) for turn in self.turns)


class ContextStore:
    """Append-only bounded store for one conversation."""

    def __init__(self, root: Path, call_id: str, *, max_turns: int = 8, max_chars: int = 6000) -> None:
        self.call_id = _check_id(call_id, "call_id")
        if max_turns < 1 or max_chars < 1:
            raise ValueError("context limits must be positive")
        self.root = Path(root) / self.call_id
        self.max_turns = max_turns
        self.max_chars = max_chars
        self.path = self.root / "conversation.jsonl"
        self._turns: list[ContextTurn] = []
        self._revision = 0

    def append(self, turn: ContextTurn) -> ContextSnapshot:
        if turn.call_id != self.call_id:
            raise ValueError("turn call_id does not match store")
        self._revision += 1
        self._turns.append(turn)
        self._trim()
        self.root.mkdir(parents=True, exist_ok=True)
        record = {"store_revision": self._revision, "turn": asdict(turn)}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return self.snapshot()

    def append_user(self, turn_id: str, text: str, *, revision: int = 1) -> ContextSnapshot:
        return self.append(ContextTurn(self.call_id, turn_id, "user", text, revision))

    def append_assistant(
        self,
        turn_id: str,
        text: str,
        *,
        revision: int = 1,
        source_ids: Iterable[str] = (),
        knowledge_context_id: str | None = None,
    ) -> ContextSnapshot:
        return self.append(
            ContextTurn(
                self.call_id,
                turn_id,
                "assistant",
                text,
                revision,
                tuple(source_ids),
                knowledge_context_id,
            )
        )

    def snapshot(self) -> ContextSnapshot:
        return ContextSnapshot(self.call_id, self._revision, tuple(self._turns))

    def _trim(self) -> None:
        while len(self._turns) > self.max_turns or sum(len(item.text) for item in self._turns) > self.max_chars:
            self._turns.pop(0)
