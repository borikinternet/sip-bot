"""Latency timestamps for one authoritative inference operation."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns


@dataclass(slots=True)
class LatencyTrace:
    final_user_turn_ns: int
    request_started_ns: int | None = None
    first_stream_event_ns: int | None = None
    first_usable_output_ns: int | None = None
    final_result_ns: int | None = None
    cancel_requested_ns: int | None = None
    completed_ns: int | None = None

    @classmethod
    def start(cls, final_user_turn_ns: int | None = None) -> "LatencyTrace":
        return cls(monotonic_ns() if final_user_turn_ns is None else final_user_turn_ns)

    def mark_request_started(self, timestamp_ns: int | None = None) -> int:
        self.request_started_ns = monotonic_ns() if timestamp_ns is None else timestamp_ns
        return self.request_started_ns

    def mark_first_stream_event(self, timestamp_ns: int | None = None) -> int:
        if self.first_stream_event_ns is None:
            self.first_stream_event_ns = monotonic_ns() if timestamp_ns is None else timestamp_ns
        return self.first_stream_event_ns

    def mark_first_usable_output(self, timestamp_ns: int | None = None) -> int:
        if self.first_usable_output_ns is None:
            self.first_usable_output_ns = monotonic_ns() if timestamp_ns is None else timestamp_ns
        return self.first_usable_output_ns

    def mark_final_result(self, timestamp_ns: int | None = None) -> int:
        self.final_result_ns = monotonic_ns() if timestamp_ns is None else timestamp_ns
        self.completed_ns = self.final_result_ns
        return self.final_result_ns

    def mark_cancel_requested(self, timestamp_ns: int | None = None) -> int:
        self.cancel_requested_ns = monotonic_ns() if timestamp_ns is None else timestamp_ns
        return self.cancel_requested_ns

    @staticmethod
    def _elapsed(start: int, end: int | None) -> float | None:
        return None if end is None else (end - start) / 1_000_000

    @property
    def final_to_first_usable_ms(self) -> float | None:
        return self._elapsed(self.final_user_turn_ns, self.first_usable_output_ns)

    @property
    def final_to_final_result_ms(self) -> float | None:
        return self._elapsed(self.final_user_turn_ns, self.final_result_ns)

    @property
    def request_to_first_usable_ms(self) -> float | None:
        return None if self.request_started_ns is None else self._elapsed(self.request_started_ns, self.first_usable_output_ns)

    @property
    def request_to_final_result_ms(self) -> float | None:
        return None if self.request_started_ns is None else self._elapsed(self.request_started_ns, self.final_result_ns)

    def as_dict(self) -> dict[str, int | float | None]:
        return {
            "final_user_turn_ns": self.final_user_turn_ns,
            "request_started_ns": self.request_started_ns,
            "first_stream_event_ns": self.first_stream_event_ns,
            "first_usable_output_ns": self.first_usable_output_ns,
            "final_result_ns": self.final_result_ns,
            "cancel_requested_ns": self.cancel_requested_ns,
            "completed_ns": self.completed_ns,
            "final_to_first_usable_ms": self.final_to_first_usable_ms,
            "final_to_final_result_ms": self.final_to_final_result_ms,
            "request_to_first_usable_ms": self.request_to_first_usable_ms,
            "request_to_final_result_ms": self.request_to_final_result_ms,
        }
