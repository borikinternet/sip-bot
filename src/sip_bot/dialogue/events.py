"""Small control-plane event values used by the dialogue boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SpeechEventKind(StrEnum):
    SPEECH_STARTED = "speech_started"
    PAUSE_CANDIDATE = "pause_candidate"
    SOFT_ENDPOINT = "soft_endpoint"
    SPEECH_RESUMED = "speech_resumed"
    HARD_ENDPOINT = "hard_endpoint"
    UTTERANCE_FINAL = "utterance_final"
    BARGE_IN = "barge_in"
    AUDIO_OVERRUN = "audio_overrun"
    AUDIO_UNDERRUN = "audio_underrun"


@dataclass(frozen=True, slots=True)
class SpeechEvent:
    call_id: str
    kind: SpeechEventKind | str
    sequence: int = 1
    channel_id: str | None = None
    channel_generation: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ValueError("call_id must be non-empty")
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        object.__setattr__(self, "kind", SpeechEventKind(self.kind))


class PlaybackStatus(StrEnum):
    STARTED = "started"
    STOPPED = "stopped"
    PRODUCER_COMPLETED = "producer_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PlaybackEvent:
    call_id: str
    status: PlaybackStatus | str
    channel_id: str = "playback"
    channel_generation: int | None = None
    operation_id: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ValueError("call_id must be non-empty")
        object.__setattr__(self, "status", PlaybackStatus(self.status))


class TransferStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TransferResult:
    call_id: str
    status: TransferStatus | str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ValueError("call_id must be non-empty")
        object.__setattr__(self, "status", TransferStatus(self.status))


@dataclass(frozen=True, slots=True)
class StructuredDecision:
    """LLM result after JSON/schema decoding, before FSM approval."""

    action: str
    text: str | None = None
    call_id: str | None = None
    operation_id: int | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("decision action must be non-empty")
        if self.text is not None and len(self.text) > 1000:
            raise ValueError("decision text exceeds the MVP answer limit")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, call_id: str | None = None, operation_id: int | None = None) -> StructuredDecision:
        allowed = {"action", "text", "confidence"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown structured decision fields: {sorted(unknown)!r}")
        return cls(
            action=value.get("action", ""),
            text=value.get("text"),
            call_id=call_id,
            operation_id=operation_id,
            confidence=value.get("confidence"),
        )

    from_dict = from_mapping


DialogueEvent = SpeechEvent | PlaybackEvent | TransferResult | StructuredDecision
