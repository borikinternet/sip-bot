"""Typed data-plane contracts for answer text and TTS PCM output."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sip_bot.sip_media.models import NegotiatedMediaProfile
from sip_bot.llm.types import CancelRequest as TtsCancelRequest


class TtsStatusKind(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ApprovedTextChunk:
    """Approved answer text travelling directly from the LLM path to TTS."""

    operation_id: str
    call_id: str
    turn_id: str
    generation: int
    sequence: int
    text: str
    is_final: bool = False

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id or not self.turn_id:
            raise ValueError("approved text identity is required")
        if self.generation < 1 or self.sequence < 1:
            raise ValueError("approved text lifecycle metadata must be positive")
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("approved text must be non-empty")


@dataclass(frozen=True, slots=True)
class TtsPcmChunk:
    """Normalized S16LE PCM emitted by a TTS adapter.

    The adapter normalizes the XTTS result to the active call's sample rate
    and channel count.  Chunk size and arrival timing are intentionally not
    part of the media ``ptime`` contract; the output boundary owns that
    conversion.
    """

    operation_id: str
    call_id: str
    channel_id: str
    generation: int
    sequence: int
    pcm_s16le: bytes
    profile: NegotiatedMediaProfile
    is_final: bool = False

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id or not self.channel_id:
            raise ValueError("TTS PCM identity is required")
        if self.generation < 1 or self.sequence < 1:
            raise ValueError("TTS PCM lifecycle metadata must be positive")
        if not isinstance(self.pcm_s16le, bytes) or not self.pcm_s16le:
            raise ValueError("TTS PCM payload must be non-empty bytes")
        if len(self.pcm_s16le) % (self.profile.channels * 2) != 0:
            raise ValueError("TTS PCM payload is not sample aligned")
        if self.profile.sample_rate_hz <= 0 or self.profile.channels <= 0:
            raise ValueError("TTS PCM profile is invalid")

    @property
    def sample_count(self) -> int:
        return len(self.pcm_s16le) // (self.profile.channels * 2)


@dataclass(frozen=True, slots=True)
class TtsStatus:
    operation_id: str
    call_id: str
    generation: int
    kind: TtsStatusKind | str
    timestamp_ns: int
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id or self.generation < 1:
            raise ValueError("TTS status identity is required")
        if self.timestamp_ns < 0:
            raise ValueError("TTS status timestamp must be non-negative")
        object.__setattr__(self, "kind", TtsStatusKind(self.kind))
        if self.kind is TtsStatusKind.FAILED and not self.error_code:
            raise ValueError("failed TTS status requires error_code")


__all__ = ["ApprovedTextChunk", "TtsCancelRequest", "TtsPcmChunk", "TtsStatus", "TtsStatusKind"]
