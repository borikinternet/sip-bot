"""Typed, payload-free timing observations for the TTS playback path."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class TtsLatencyStage(StrEnum):
    """Ordered checkpoints from an authoritative LLM result to media egress."""

    LLM_FINAL_RESULT = "llm_final_result"
    TTS_COMMAND_ACCEPTED = "tts_command_accepted"
    TTS_WORKER_STARTED = "tts_worker_started"
    ADAPTER_STARTED = "tts_adapter_started"
    ENGINE_FIRST_CHUNK = "tts_engine_first_chunk"
    PCM_FIRST_CHUNK = "tts_pcm_first_chunk"
    PLAYBACK_FIRST_FRAME = "playback_first_frame"


@dataclass(frozen=True, slots=True)
class TtsLatencyEvent:
    """One monotonic timestamp; never a control event or audio payload."""

    operation_id: str
    call_id: str
    turn_id: str
    channel_id: str
    generation: int
    stage: TtsLatencyStage | str
    timestamp_ns: int
    payload_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.operation_id or not self.call_id or not self.channel_id:
            raise ValueError("TTS latency identity is required")
        if self.generation < 1 or self.timestamp_ns < 0 or self.payload_bytes < 0:
            raise ValueError("TTS latency values must be non-negative and generation must be positive")
        object.__setattr__(self, "stage", TtsLatencyStage(self.stage))

    def as_dict(self) -> dict[str, str | int]:
        return {
            "operation_id": self.operation_id,
            "call_id": self.call_id,
            "turn_id": self.turn_id,
            "channel_id": self.channel_id,
            "generation": self.generation,
            "stage": self.stage.value,
            "timestamp_ns": self.timestamp_ns,
            "payload_bytes": self.payload_bytes,
        }


TtsLatencySink = Callable[[TtsLatencyEvent], None]


__all__ = ["TtsLatencyEvent", "TtsLatencySink", "TtsLatencyStage"]
