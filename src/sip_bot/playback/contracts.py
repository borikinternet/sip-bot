"""Typed control/status contracts for the direct playback channel."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlaybackEventKind(StrEnum):
    OPENED = "opened"
    STARTED = "started"
    FRAME_SENT = "frame_sent"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    STALE_DROPPED = "stale_dropped"
    FAILED = "failed"


class PlaybackCloseReason(StrEnum):
    COMPLETED = "completed"
    BARGE_IN = "barge_in"
    CALL_ENDED = "call_ended"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PlaybackCommand:
    call_id: str
    channel_id: str
    generation: int
    action: str
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.call_id or not self.channel_id or self.generation < 1:
            raise ValueError("playback command identity is required")
        if self.action not in {"open", "close", "cancel", "barge_in"}:
            raise ValueError("unsupported playback action")


@dataclass(frozen=True, slots=True)
class PlaybackEvent:
    call_id: str
    channel_id: str
    generation: int
    kind: PlaybackEventKind | str
    timestamp_ns: int
    reason: str = ""
    sequence: int | None = None

    def __post_init__(self) -> None:
        if not self.call_id or not self.channel_id or self.generation < 1:
            raise ValueError("playback event identity is required")
        if self.timestamp_ns < 0:
            raise ValueError("playback event timestamp must be non-negative")
        object.__setattr__(self, "kind", PlaybackEventKind(self.kind))
        if self.sequence is not None and self.sequence < 1:
            raise ValueError("playback sequence must be positive")


__all__ = ["PlaybackCloseReason", "PlaybackCommand", "PlaybackEvent", "PlaybackEventKind"]
