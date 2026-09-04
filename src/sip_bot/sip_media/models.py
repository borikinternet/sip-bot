"""Typed SIP/media boundary values owned by the application adapter.

The PJSUA2 wrapper exposes media details through PJMEDIA's stream and port
objects.  These values deliberately keep the negotiated profile attached to
every frame; no global ptime or frame-size assumption belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any


class MediaNegotiationError(RuntimeError):
    """Raised when the negotiated call media cannot satisfy the MVP profile."""


def _positive_int(value: Any, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise MediaNegotiationError(f"{name} must be an integer") from exc
    if result <= 0:
        raise MediaNegotiationError(f"{name} must be positive")
    return result


def _payload_type(value: Any, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise MediaNegotiationError(f"{name} must be an integer") from exc
    if not 0 <= result <= 127:
        raise MediaNegotiationError(f"{name} must be in the RTP payload range")
    return result


def _read_audio_codec_ptime(stream_info: Any) -> float:
    codec_param = getattr(stream_info, "audCodecParam", None)
    param_info = getattr(codec_param, "info", None)
    frame_len = getattr(param_info, "frameLen", None)
    if frame_len is None:
        raise MediaNegotiationError("PJMEDIA codec parameters do not expose decoder ptime")
    try:
        numerator = float(frame_len)
        denominator = float(getattr(param_info, "frameLenDenum", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise MediaNegotiationError("PJMEDIA codec ptime is not numeric") from exc
    if denominator <= 0:
        denominator = 1.0
    ptime_ms = numerator / denominator
    if ptime_ms <= 0:
        raise MediaNegotiationError("PJMEDIA codec ptime must be positive")
    return ptime_ms


@dataclass(frozen=True, slots=True)
class NegotiatedMediaProfile:
    """Per-call PCMU/PJMEDIA parameters used by both directions of the port."""

    codec: str
    payload_type: int
    ptime_ms: float
    sample_rate_hz: int
    channels: int
    frame_size_samples: int
    pcm_bits_per_sample: int = 16
    rx_payload_type: int | None = None
    tx_payload_type: int | None = None
    source: str = "pjmedia.stream_info"

    def __post_init__(self) -> None:
        if self.codec.upper() != "PCMU":
            raise MediaNegotiationError(f"unsupported negotiated codec: {self.codec!r}")
        if not self.codec:
            raise MediaNegotiationError("codec must not be empty")
        _payload_type(self.payload_type, "payload_type")
        if self.rx_payload_type is not None:
            _payload_type(self.rx_payload_type, "rx_payload_type")
        if self.tx_payload_type is not None:
            _payload_type(self.tx_payload_type, "tx_payload_type")
        if self.ptime_ms <= 0:
            raise MediaNegotiationError("ptime_ms must be positive")
        _positive_int(self.sample_rate_hz, "sample_rate_hz")
        _positive_int(self.channels, "channels")
        _positive_int(self.frame_size_samples, "frame_size_samples")
        if self.pcm_bits_per_sample != 16:
            raise MediaNegotiationError("only PCM S16LE is supported at the application boundary")
        expected = self.sample_rate_hz * self.ptime_ms / 1000.0
        if not isclose(self.frame_size_samples, expected, rel_tol=0.0, abs_tol=0.51):
            raise MediaNegotiationError(
                "frame_size_samples does not match the negotiated ptime/sample rate: "
                f"{self.frame_size_samples} != {expected:g}"
            )

    @property
    def frame_time_usec(self) -> int:
        return int(round(self.ptime_ms * 1000.0))

    @property
    def frame_bytes(self) -> int:
        return self.frame_size_samples * self.channels * (self.pcm_bits_per_sample // 8)

    @classmethod
    def from_stream_info(
        cls,
        stream_info: Any,
        *,
        port_format: Any | None = None,
        source: str = "pjmedia.stream_info",
    ) -> "NegotiatedMediaProfile":
        """Build the profile from PJSUA2 ``StreamInfo`` and PJMEDIA port data.

        The codec and RTP payload values come from ``StreamInfo``.  The
        callback frame clock, when available, comes from the active PJMEDIA
        port format.  Its absence uses the codec's negotiated ptime, never a
        fixed application default.
        """

        codec = str(getattr(stream_info, "codecName", "")).strip()
        if codec.upper() != "PCMU":
            raise MediaNegotiationError(f"negotiated codec is not PCMU: {codec!r}")

        stream_rate = _positive_int(getattr(stream_info, "codecClockRate", 0), "codecClockRate")
        rx_pt = _payload_type(getattr(stream_info, "rxPt", -1), "rxPt")
        tx_pt = _payload_type(getattr(stream_info, "txPt", -1), "txPt")
        payload_type = rx_pt
        ptime_ms = _read_audio_codec_ptime(stream_info)
        sample_rate = stream_rate
        codec_info = getattr(getattr(stream_info, "audCodecParam", None), "info", None)
        channels = _positive_int(getattr(codec_info, "channelCnt", 1) or 1, "PJMEDIA channelCnt")
        bits = _positive_int(getattr(codec_info, "pcmBitsPerSample", 16) or 16, "PJMEDIA pcmBitsPerSample")

        if port_format is not None:
            port_rate = getattr(port_format, "clockRate", None)
            if port_rate:
                sample_rate = _positive_int(port_rate, "PJMEDIA clockRate")
            port_channels = getattr(port_format, "channelCount", None)
            if port_channels:
                channels = _positive_int(port_channels, "PJMEDIA channelCount")
            port_bits = getattr(port_format, "bitsPerSample", None)
            if port_bits:
                bits = int(port_bits)
            frame_time_usec = getattr(port_format, "frameTimeUsec", None)
            if frame_time_usec:
                ptime_ms = float(frame_time_usec) / 1000.0

        frame_size_samples = int(round(sample_rate * ptime_ms / 1000.0))
        return cls(
            codec=codec,
            payload_type=payload_type,
            ptime_ms=ptime_ms,
            sample_rate_hz=sample_rate,
            channels=channels,
            frame_size_samples=frame_size_samples,
            pcm_bits_per_sample=bits,
            rx_payload_type=rx_pt,
            tx_payload_type=tx_pt,
            source=source,
        )

    @classmethod
    def from_call(cls, call: Any, media_index: int) -> "NegotiatedMediaProfile":
        """Read the active stream and port format for an explicit media index.

        ``getAudioMedia(-1)`` has a documented convenience meaning in PJSUA2,
        but ``getStreamInfo()`` accepts an actual unsigned media index.  Keep
        this boundary explicit so a wildcard sentinel cannot leak into the
        stream-info call.
        """

        try:
            media_index = int(media_index)
        except (TypeError, ValueError) as exc:
            raise MediaNegotiationError("media_index must be a non-negative integer") from exc
        if media_index < 0:
            raise MediaNegotiationError("media_index must be a non-negative integer")

        stream_info = call.getStreamInfo(media_index)
        port_format = None
        try:
            audio_media = call.getAudioMedia(media_index)
            port_info = audio_media.getPortInfo()
            port_format = getattr(port_info, "format", None)
        except Exception:
            # StreamInfo remains authoritative for a narrow callback where
            # the generated AudioMedia copy is not available yet.  This is
            # not a codec/ptime fallback: it is the same PJMEDIA call object.
            port_format = None
        return cls.from_stream_info(stream_info, port_format=port_format)

    def as_dict(self) -> dict[str, Any]:
        return {
            "codec": self.codec,
            "payload_type": self.payload_type,
            "rx_payload_type": self.rx_payload_type,
            "tx_payload_type": self.tx_payload_type,
            "ptime_ms": self.ptime_ms,
            "frame_time_usec": self.frame_time_usec,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "frame_size_samples": self.frame_size_samples,
            "frame_bytes": self.frame_bytes,
            "pcm_bits_per_sample": self.pcm_bits_per_sample,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class PcmFrame:
    """A decoded or to-be-encoded PCM frame on the direct media boundary."""

    call_id: str
    channel_id: str
    generation: int
    sequence: int
    timestamp_ns: int
    pcm_s16le: bytes
    profile: NegotiatedMediaProfile

    def __post_init__(self) -> None:
        if not self.call_id or not self.channel_id:
            raise ValueError("call_id and channel_id must be non-empty")
        if self.generation < 1 or self.sequence < 1 or self.timestamp_ns < 0:
            raise ValueError("invalid frame lifecycle metadata")
        if not isinstance(self.pcm_s16le, bytes):
            raise TypeError("pcm_s16le must be bytes")
        bytes_per_sample = self.profile.pcm_bits_per_sample // 8
        expected_alignment = self.profile.channels * bytes_per_sample
        if len(self.pcm_s16le) == 0 or len(self.pcm_s16le) % expected_alignment:
            raise ValueError("PCM frame payload is not aligned to the negotiated format")

    @property
    def sample_count(self) -> int:
        return len(self.pcm_s16le) // (self.profile.channels * (self.profile.pcm_bits_per_sample // 8))

    def as_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "call_id": self.call_id,
            "channel_id": self.channel_id,
            "generation": self.generation,
            "sequence": self.sequence,
            "timestamp_ns": self.timestamp_ns,
            "sample_count": self.sample_count,
            "bytes": len(self.pcm_s16le),
            "profile": self.profile.as_dict(),
        }
        if include_payload:
            result["pcm_s16le_hex"] = self.pcm_s16le.hex()
        return result
