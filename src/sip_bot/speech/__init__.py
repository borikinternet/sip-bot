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
    VadCandidateError,
    VadProcessor,
    WebRtcVadCandidate,
)

__all__ = [
    "AsrAdapterError",
    "AsrAudioChunk",
    "AsrHypothesis",
    "AsrOperation",
    "EndpointEvent",
    "EndpointEventKind",
    "EndpointingConfig",
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
    "VadDecision",
    "VadProcessor",
    "WebRtcVadCandidate",
]
