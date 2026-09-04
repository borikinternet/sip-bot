"""Typed audio boundary adapters built on the accepted per-call media model."""

from __future__ import annotations

from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame

from .codec import decode_pcmu, encode_pcmu


class AudioBoundaryError(ValueError):
    """Raised when payload bytes do not satisfy the negotiated call contract."""


def _validate_profile(profile: NegotiatedMediaProfile) -> None:
    if not isinstance(profile, NegotiatedMediaProfile):
        raise TypeError("profile must be NegotiatedMediaProfile")
    if profile.codec.upper() != "PCMU":
        raise AudioBoundaryError("audio boundary supports only negotiated PCMU")


def decode_pcmu_frame(
    payload: bytes | bytearray | memoryview,
    *,
    call_id: str,
    channel_id: str,
    generation: int,
    sequence: int,
    timestamp_ns: int,
    profile: NegotiatedMediaProfile,
) -> PcmFrame:
    """Convert one negotiated PCMU media frame into the internal ``PcmFrame``."""

    _validate_profile(profile)
    pcmu = bytes(payload)
    expected = profile.frame_size_samples * profile.channels
    if len(pcmu) != expected:
        raise AudioBoundaryError(
            f"PCMU frame has {len(pcmu)} octets; expected {expected} for the negotiated profile"
        )
    pcm = decode_pcmu(pcmu)
    if len(pcm) != profile.frame_bytes:
        raise AudioBoundaryError("decoded PCM frame size does not match the negotiated profile")
    return PcmFrame(
        call_id=call_id,
        channel_id=channel_id,
        generation=generation,
        sequence=sequence,
        timestamp_ns=timestamp_ns,
        pcm_s16le=pcm,
        profile=profile,
    )


def encode_pcm_frame(frame: PcmFrame) -> bytes:
    """Convert one internal ``PcmFrame`` back to a PCMU media frame."""

    if not isinstance(frame, PcmFrame):
        raise TypeError("frame must be PcmFrame")
    _validate_profile(frame.profile)
    if len(frame.pcm_s16le) != frame.profile.frame_bytes:
        raise AudioBoundaryError("PCM frame size does not match the negotiated profile")
    payload = encode_pcmu(frame.pcm_s16le)
    expected = frame.profile.frame_size_samples * frame.profile.channels
    if len(payload) != expected:
        raise AudioBoundaryError("encoded PCMU frame size does not match the negotiated profile")
    return payload


__all__ = [
    "AudioBoundaryError",
    "NegotiatedMediaProfile",
    "PcmFrame",
    "decode_pcmu_frame",
    "encode_pcm_frame",
]
