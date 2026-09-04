"""Typed, control-plane-only event envelopes.

The envelope carries lifecycle/control metadata only.  Audio frames, ASR/TTS
streams, RAG fragments, and other data-plane payloads have no representation in
this module and must use their future direct channels.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ControlEventKind(StrEnum):
    CALL_OPEN = "call_open"
    CALL_CLOSE = "call_close"
    CHANNEL_OPEN = "channel_open"
    CHANNEL_CLOSE = "channel_close"
    TERMINAL = "terminal"


def _validate_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"{field_name} must be a non-empty string of at most 128 characters")


def _validate_reason(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 160:
        raise ValueError("reason must be a non-empty string of at most 160 characters")


@dataclass(frozen=True, slots=True)
class CallOpen:
    call_id: str

    def __post_init__(self) -> None:
        _validate_identifier(self.call_id, "call_id")


@dataclass(frozen=True, slots=True)
class CallClose:
    call_id: str
    reason: str
    already_closed: bool

    def __post_init__(self) -> None:
        _validate_identifier(self.call_id, "call_id")
        _validate_reason(self.reason)


@dataclass(frozen=True, slots=True)
class ChannelOpen:
    call_id: str
    channel_id: str
    channel_kind: str
    generation: int

    def __post_init__(self) -> None:
        _validate_identifier(self.call_id, "call_id")
        _validate_identifier(self.channel_id, "channel_id")
        _validate_identifier(self.channel_kind, "channel_kind")
        if self.generation < 1:
            raise ValueError("generation must be positive")


@dataclass(frozen=True, slots=True)
class ChannelClose:
    call_id: str
    channel_id: str
    channel_kind: str
    generation: int
    reason: str
    already_closed: bool

    def __post_init__(self) -> None:
        _validate_identifier(self.call_id, "call_id")
        _validate_identifier(self.channel_id, "channel_id")
        _validate_identifier(self.channel_kind, "channel_kind")
        if self.generation < 1:
            raise ValueError("generation must be positive")
        _validate_reason(self.reason)


@dataclass(frozen=True, slots=True)
class Terminal:
    call_id: str
    reason: str

    def __post_init__(self) -> None:
        _validate_identifier(self.call_id, "call_id")
        _validate_reason(self.reason)


ControlEventPayload = CallOpen | CallClose | ChannelOpen | ChannelClose | Terminal


@dataclass(frozen=True, slots=True)
class ControlEvent:
    """Immutable envelope used at the runtime-to-Dispatcher boundary."""

    kind: ControlEventKind
    call_id: str
    sequence: int
    timestamp_ns: int
    payload: ControlEventPayload
    channel_id: str | None = None
    channel_generation: int | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.call_id, "call_id")
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must not be negative")

        expected: dict[ControlEventKind, type[ControlEventPayload]] = {
            ControlEventKind.CALL_OPEN: CallOpen,
            ControlEventKind.CALL_CLOSE: CallClose,
            ControlEventKind.CHANNEL_OPEN: ChannelOpen,
            ControlEventKind.CHANNEL_CLOSE: ChannelClose,
            ControlEventKind.TERMINAL: Terminal,
        }
        payload_type = expected.get(self.kind)
        if payload_type is None or type(self.payload) is not payload_type:
            raise TypeError(f"payload type does not match event kind {self.kind.value}")
        if self.payload.call_id != self.call_id:
            raise ValueError("envelope call_id must match payload call_id")

        channel_payload = isinstance(self.payload, (ChannelOpen, ChannelClose))
        if channel_payload:
            if self.channel_id != self.payload.channel_id:
                raise ValueError("channel_id must match channel payload")
            if self.channel_generation != self.payload.generation:
                raise ValueError("channel_generation must match channel payload")
        elif self.channel_id is not None or self.channel_generation is not None:
            raise ValueError("call-level events cannot carry channel scope")

    @property
    def is_channel_scoped(self) -> bool:
        return self.channel_id is not None


class ControlEventSink(Protocol):
    """Future Dispatcher/FSM boundary; no subscription semantics are owned here."""

    def publish(self, event: ControlEvent) -> None:
        """Accept one typed control-plane event."""
