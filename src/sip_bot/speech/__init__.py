"""Speech ingress components for VAD, endpointing, ASR and transcript assembly."""

from .asr_adapter import (
    AsrAdapterError,
    AsrOperation,
    FasterWhisperC2Backend,
    StreamingAsrAdapter,
)
from .contracts import (
    AsrAudioChunk,
    AsrHypothesis,
    AsrSpeechDecision,
    AsrSpeechEvidence,
    EndpointEvent,
    EndpointEventKind,
    FinalUserTurn,
    TranscriptUpdate,
    TranscriptUpdateKind,
    VadDecision,
)
from .endpointing import EndpointingConfig, TurnDetector
from .ingress import SpeechFrameResult, SpeechIngress
from .transcript_assembler import TranscriptAssembler, TranscriptContractError
from .vad import (
    AdaptiveEnergyGate,
    AdaptiveEnergyGateConfig,
    build_configured_web_rtc_vad_processor,
    EnergyGateObservation,
    VadCandidateError,
    VadAnalyticsSnapshot,
    VadProcessor,
    WebRtcVadCandidate,
)

__all__ = [
    "AsrAdapterError",
    "AdaptiveEnergyGate",
    "AdaptiveEnergyGateConfig",
    "build_configured_web_rtc_vad_processor",
    "AsrAudioChunk",
    "AsrHypothesis",
    "AsrSpeechDecision",
    "AsrSpeechEvidence",
    "AsrOperation",
    "EndpointEvent",
    "EndpointEventKind",
    "EndpointingConfig",
    "EnergyGateObservation",
    "FasterWhisperC2Backend",
    "FinalUserTurn",
    "StreamingAsrAdapter",
    "SpeechFrameResult",
    "SpeechIngress",
    "TranscriptAssembler",
    "TranscriptContractError",
    "TranscriptUpdate",
    "TranscriptUpdateKind",
    "TurnDetector",
    "VadCandidateError",
    "VadAnalyticsSnapshot",
    "VadDecision",
    "VadProcessor",
    "WebRtcVadCandidate",
]
