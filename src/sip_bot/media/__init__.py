"""Direct audio data-plane boundaries for the MVP speech pipeline.

The package deliberately contains no SIP callbacks, event-bus code, model
runtime, or GPU dependency.  It consumes the per-call media contract emitted
by ``sip_bot.sip_media`` and owns only format conversion, fan-out, and ASR
chunking.
"""

from .asr_chunker import AsrAudioChunk, AsrChunker, ChunkerStats, FlushReason
from .codec import PcmuCodec, decode_pcmu, encode_pcmu
from .fanout import FanOutStats, PcmFanOut, PcmFanOutSubscription, PublishResult
from .types import (
    AudioBoundaryError,
    NegotiatedMediaProfile,
    PcmFrame,
    decode_pcmu_frame,
    encode_pcm_frame,
)

__all__ = [
    "AsrAudioChunk",
    "AsrChunker",
    "AudioBoundaryError",
    "ChunkerStats",
    "FanOutStats",
    "FlushReason",
    "NegotiatedMediaProfile",
    "PcmFrame",
    "PcmFanOut",
    "PcmFanOutSubscription",
    "PcmuCodec",
    "PublishResult",
    "decode_pcmu",
    "decode_pcmu_frame",
    "encode_pcm_frame",
    "encode_pcmu",
]
