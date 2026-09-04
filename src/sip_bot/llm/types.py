"""Typed, backend-neutral LLM operation values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sip_bot.dialogue.events import StructuredDecision


class StreamEventKind(StrEnum):
    STARTED = "started"
    DELTA = "delta"
    DECISION = "decision"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class InferenceStatusKind(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CancelRequest:
    operation_id: str
    call_id: str
    reason: str
    generation: int = 1

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id or not self.reason:
            raise ValueError("cancel request requires operation, call and reason")
        if self.generation < 1:
            raise ValueError("generation must be positive")


@dataclass(frozen=True, slots=True)
class LlmStreamEvent:
    operation_id: str
    call_id: str
    turn_id: str
    kind: StreamEventKind | str
    timestamp_ns: int
    text_delta: str = ""
    text: str | None = None
    decision: StructuredDecision | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id or not self.turn_id:
            raise ValueError("stream event identity is required")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp must be non-negative")
        object.__setattr__(self, "kind", StreamEventKind(self.kind))
        if self.kind is StreamEventKind.DELTA and not self.text_delta:
            raise ValueError("delta event requires text_delta")
        if self.kind is StreamEventKind.DECISION and self.decision is None:
            raise ValueError("decision event requires structured decision")
        if self.kind is StreamEventKind.ERROR and not self.error_code:
            raise ValueError("error event requires error_code")


@dataclass(frozen=True, slots=True)
class InferenceStatus:
    operation_id: str
    call_id: str
    status: InferenceStatusKind | str
    timestamp_ns: int
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id:
            raise ValueError("status identity is required")
        if self.timestamp_ns < 0:
            raise ValueError("status timestamp must be non-negative")
        object.__setattr__(self, "status", InferenceStatusKind(self.status))
