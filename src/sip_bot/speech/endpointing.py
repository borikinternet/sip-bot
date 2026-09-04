"""Fixed-policy VAD-to-turn endpointing state machine."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import EndpointEvent, EndpointEventKind, VadDecision


@dataclass(frozen=True, slots=True)
class EndpointingConfig:
    """MVP timing policy; values are explicit and independently testable."""

    soft_endpoint_ms: int = 300
    hard_endpoint_ms: int = 500
    min_speech_ms: int = 80

    def __post_init__(self) -> None:
        if not 1 <= self.soft_endpoint_ms < self.hard_endpoint_ms:
            raise ValueError("soft endpoint must be positive and below hard endpoint")
        if not 1 <= self.min_speech_ms <= self.soft_endpoint_ms:
            raise ValueError("min_speech_ms must be within the endpoint policy")


class TurnDetector:
    """Owns speech/pause state and emits one authoritative hard boundary."""

    def __init__(self, config: EndpointingConfig | None = None) -> None:
        self.config = config or EndpointingConfig()
        self._call_id: str | None = None
        self._channel_id: str | None = None
        self._generation: int | None = None
        self._turn_number = 0
        self._turn_id: str | None = None
        self._speech_ms = 0
        self._speech_started = False
        self._pause_started_ns: int | None = None
        self._soft_emitted = False
        self._last_sequence = 0

    @property
    def active_turn_id(self) -> str | None:
        return self._turn_id if self._speech_started else None

    def _ensure_scope(self, decision: VadDecision) -> None:
        scope = (decision.call_id, decision.channel_id, decision.generation)
        current = (self._call_id, self._channel_id, self._generation)
        if self._call_id is None:
            self._call_id, self._channel_id, self._generation = scope
            return
        if current != scope:
            raise ValueError(f"VAD decision scope changed from {current} to {scope}")

    def _event(
        self,
        kind: EndpointEventKind,
        decision: VadDecision,
        *,
        silence_ms: int,
        reason: str,
        authoritative: bool = False,
    ) -> EndpointEvent:
        assert self._call_id is not None
        assert self._channel_id is not None
        assert self._generation is not None
        assert self._turn_id is not None
        return EndpointEvent(
            kind=kind,
            call_id=self._call_id,
            channel_id=self._channel_id,
            generation=self._generation,
            turn_id=self._turn_id,
            timestamp_ns=decision.end_timestamp_ns,
            silence_ms=silence_ms,
            reason=reason,
            authoritative=authoritative,
        )

    def _reset_turn(self) -> None:
        self._turn_id = None
        self._speech_ms = 0
        self._speech_started = False
        self._pause_started_ns = None
        self._soft_emitted = False

    def consume(self, decision: VadDecision) -> tuple[EndpointEvent, ...]:
        """Consume one ordered VAD decision and emit lifecycle events."""

        self._ensure_scope(decision)
        if decision.sequence <= self._last_sequence:
            return ()
        self._last_sequence = decision.sequence
        events: list[EndpointEvent] = []

        if decision.is_speech:
            if self._turn_id is None:
                self._turn_number += 1
                self._turn_id = f"{decision.call_id}:turn-{self._turn_number}"
            self._speech_ms += decision.frame_duration_ms
            if not self._speech_started and self._speech_ms >= self.config.min_speech_ms:
                self._speech_started = True
                events.append(
                    self._event(
                        EndpointEventKind.SPEECH_STARTED,
                        decision,
                        silence_ms=0,
                        reason="minimum_speech_duration_reached",
                    )
                )
            if self._pause_started_ns is not None and self._speech_started:
                events.append(
                    self._event(
                        EndpointEventKind.SPEECH_RESUMED,
                        decision,
                        silence_ms=max(
                            0,
                            int((decision.timestamp_ns - self._pause_started_ns) / 1_000_000),
                        ),
                        reason="speech_before_hard_endpoint",
                    )
                )
                self._pause_started_ns = None
                self._soft_emitted = False
            return tuple(events)

        if not self._speech_started:
            # A short noise burst below min_speech_ms is not a user turn.
            self._reset_turn()
            return ()

        if self._pause_started_ns is None:
            self._pause_started_ns = decision.timestamp_ns
            events.append(
                self._event(
                    EndpointEventKind.PAUSE_CANDIDATE,
                    decision,
                    silence_ms=0,
                    reason="silence_started",
                )
            )

        silence_ms = max(
            0,
            int((decision.end_timestamp_ns - self._pause_started_ns) / 1_000_000),
        )
        if not self._soft_emitted and silence_ms >= self.config.soft_endpoint_ms:
            self._soft_emitted = True
            events.append(
                self._event(
                    EndpointEventKind.SOFT_ENDPOINT,
                    decision,
                    silence_ms=silence_ms,
                    reason="soft_silence_threshold_reached",
                )
            )
        if silence_ms >= self.config.hard_endpoint_ms:
            events.append(
                self._event(
                    EndpointEventKind.HARD_ENDPOINT,
                    decision,
                    silence_ms=silence_ms,
                    reason="hard_silence_threshold_reached",
                    authoritative=True,
                )
            )
            self._reset_turn()
        return tuple(events)

    def cancel(self) -> None:
        """Discard a speculative/current turn without producing a final turn."""

        self._reset_turn()
