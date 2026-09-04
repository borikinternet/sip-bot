"""Typed data-plane contracts for the speech ingress boundary.

The contracts carry lifecycle metadata on every value.  They are immutable so
that a stale result cannot be amended in place and accidentally reused by a
new call generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

from sip_bot.media.asr_chunker import AsrAudioChunk


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"{name} must be a non-empty string of at most 128 characters")
    return value


def _generation(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("generation must be a positive integer")
    return value


def _timestamp(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("timestamp_ns must be a non-negative integer")
    return value


class EndpointEventKind(StrEnum):
    """Observable lifecycle boundaries owned by ``TurnDetector``."""

    SPEECH_STARTED = "speech_started"
    PAUSE_CANDIDATE = "pause_candidate"
    SOFT_ENDPOINT = "soft_endpoint"
    SPEECH_RESUMED = "speech_resumed"
    HARD_ENDPOINT = "hard_endpoint"


class TranscriptUpdateKind(StrEnum):
    """Observable transcript states emitted by ``TranscriptAssembler``."""

    PARTIAL = "partial"
    STABLE = "stable"
    FINAL = "final"


@dataclass(frozen=True, slots=True)
class VadDecision:
    """One frame-level VAD result, tied to one call generation."""

    call_id: str
    channel_id: str
    generation: int
    sequence: int
    timestamp_ns: int
    frame_duration_ms: int
    is_speech: bool
    confidence: float | None = None
    source: str = "webrtc-vad"

    def __post_init__(self) -> None:
        _identifier(self.call_id, "call_id")
        _identifier(self.channel_id, "channel_id")
        _generation(self.generation)
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        _timestamp(self.timestamp_ns)
        if self.frame_duration_ms not in (10, 20, 30):
            raise ValueError("frame_duration_ms must be 10, 20 or 30")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def end_timestamp_ns(self) -> int:
        return self.timestamp_ns + self.frame_duration_ms * 1_000_000


@dataclass(frozen=True, slots=True)
class EndpointEvent:
    """Turn boundary event; hard endpoint is the authoritative final boundary."""

    kind: EndpointEventKind
    call_id: str
    channel_id: str
    generation: int
    turn_id: str
    timestamp_ns: int
    silence_ms: int
    reason: str
    authoritative: bool = False

    def __post_init__(self) -> None:
        _identifier(self.call_id, "call_id")
        _identifier(self.channel_id, "channel_id")
        _generation(self.generation)
        _identifier(self.turn_id, "turn_id")
        _timestamp(self.timestamp_ns)
        if self.silence_ms < 0:
            raise ValueError("silence_ms must not be negative")
        if not self.reason:
            raise ValueError("reason must not be empty")
        if self.kind is EndpointEventKind.HARD_ENDPOINT and not self.authoritative:
            raise ValueError("hard_endpoint must be authoritative")


@dataclass(frozen=True, slots=True)
class AsrHypothesis:
    """A revision of the text hypothesis for one active turn."""

    call_id: str
    channel_id: str
    generation: int
    revision: int
    timestamp_ns: int
    text: str
    is_final: bool = False
    stable_prefix: str | None = None
    confidence: float | None = None
    source: str = "streaming-asr"

    def __post_init__(self) -> None:
        _identifier(self.call_id, "call_id")
        _identifier(self.channel_id, "channel_id")
        _generation(self.generation)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        _timestamp(self.timestamp_ns)
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if self.stable_prefix is not None:
            if not isinstance(self.stable_prefix, str) or not self.text.startswith(self.stable_prefix):
                raise ValueError("stable_prefix must be a prefix of text")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def normalized_text(self) -> str:
        return " ".join(self.text.split())


@dataclass(frozen=True, slots=True)
class TranscriptUpdate:
    """Assembler snapshot; only a hard-boundary ``FINAL`` is authoritative."""

    kind: TranscriptUpdateKind
    call_id: str
    channel_id: str
    generation: int
    revision: int
    timestamp_ns: int
    text: str
    stable_prefix: str
    unstable_suffix: str
    authoritative: bool = False
    boundary: EndpointEventKind | None = None

    def __post_init__(self) -> None:
        _identifier(self.call_id, "call_id")
        _identifier(self.channel_id, "channel_id")
        _generation(self.generation)
        if self.revision < 1:
            raise ValueError("revision must be positive")
        _timestamp(self.timestamp_ns)
        if not self.text.startswith(self.stable_prefix):
            raise ValueError("stable_prefix must be a prefix of text")
        if self.text[len(self.stable_prefix) :] != self.unstable_suffix:
            raise ValueError("unstable_suffix must match the text after stable_prefix")


@dataclass(frozen=True, slots=True)
class FinalUserTurn:
    """The sole authoritative text payload handed to the dialogue layer."""

    __data_plane__: ClassVar[bool] = True

    call_id: str
    channel_id: str
    generation: int
    turn_id: str
    text: str
    revision: int
    finalized_at_ns: int
    boundary: EndpointEventKind

    def __post_init__(self) -> None:
        _identifier(self.call_id, "call_id")
        _identifier(self.channel_id, "channel_id")
        _generation(self.generation)
        _identifier(self.turn_id, "turn_id")
        if not self.text.strip():
            raise ValueError("final user turn text must not be empty")
        if self.revision < 1:
            raise ValueError("revision must be positive")
        _timestamp(self.finalized_at_ns)
        if self.boundary is not EndpointEventKind.HARD_ENDPOINT:
            raise ValueError("authoritative user turn requires hard_endpoint")


def coerce_backend_hypothesis(
    value: Any,
    *,
    call_id: str,
    channel_id: str,
    generation: int,
    revision: int,
    timestamp_ns: int,
) -> AsrHypothesis:
    """Map a C2/backend item to the application ASR contract."""

    if isinstance(value, AsrHypothesis):
        if (value.call_id, value.channel_id, value.generation) != (call_id, channel_id, generation):
            raise ValueError("backend hypothesis lifecycle metadata does not match the operation")
        return value
    if isinstance(value, str):
        return AsrHypothesis(
            call_id=call_id,
            channel_id=channel_id,
            generation=generation,
            revision=revision,
            timestamp_ns=timestamp_ns,
            text=value,
        )
    if isinstance(value, dict):
        return AsrHypothesis(
            call_id=call_id,
            channel_id=channel_id,
            generation=generation,
            revision=int(value.get("revision", revision)),
            timestamp_ns=int(value.get("timestamp_ns", timestamp_ns)),
            text=str(value.get("text", "")),
            is_final=bool(value.get("is_final", False)),
            stable_prefix=value.get("stable_prefix"),
            confidence=value.get("confidence"),
            source=str(value.get("source", "streaming-asr")),
        )
    raise TypeError(f"unsupported ASR backend item: {type(value).__name__}")
