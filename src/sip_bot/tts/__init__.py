"""Typed TTS and direct playback-boundary components."""

from .adapter import EngineAudioChunk, TtsAdapterError, XttsEngine, XttsV2Adapter
from .contracts import ApprovedTextChunk, TtsCancelRequest, TtsPcmChunk, TtsStatus, TtsStatusKind
from .media_pacer import MediaPacer, PacerStats
from .output_buffer import TtsOutputBuffer, TtsOutputError, TtsOutputStats
from .telemetry import TtsLatencyEvent, TtsLatencySink, TtsLatencyStage

__all__ = [
    "ApprovedTextChunk", "EngineAudioChunk", "MediaPacer", "PacerStats",
    "TtsAdapterError", "TtsCancelRequest", "TtsOutputBuffer", "TtsOutputError", "TtsOutputStats",
    "TtsPcmChunk", "TtsStatus", "TtsStatusKind", "XttsEngine", "XttsV2Adapter",
    "TtsLatencyEvent", "TtsLatencySink", "TtsLatencyStage",
]
