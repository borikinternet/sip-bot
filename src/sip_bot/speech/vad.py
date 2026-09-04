"""VAD candidate boundary and frame-level processor."""

from __future__ import annotations

from typing import Any, Protocol

from sip_bot.sip_media.models import PcmFrame

from .contracts import VadDecision


class VadCandidate(Protocol):
    """Minimal candidate contract; native implementation is loaded lazily."""

    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        ...


class VadCandidateError(RuntimeError):
    """Raised when the selected VAD candidate cannot be used."""


class WebRtcVadCandidate:
    """Lazy adapter for the open-source WebRTC VAD Python binding.

    The binding is deliberately not imported at module import time.  This
    keeps application startup and deterministic contract tests independent of
    native packages; target execution can inject a tested backend or load
    ``webrtcvad`` explicitly when the dependency is installed.
    """

    def __init__(self, mode: int = 2, *, backend: Any | None = None) -> None:
        if mode not in (0, 1, 2, 3):
            raise ValueError("WebRTC VAD mode must be between 0 and 3")
        self.mode = mode
        self._backend = backend

    def _load_backend(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            import webrtcvad  # type: ignore[import-not-found]
        except ImportError as exc:
            raise VadCandidateError(
                "WebRTC VAD binding is not installed; inject a tested backend or install webrtcvad"
            ) from exc
        self._backend = webrtcvad.Vad(self.mode)
        return self._backend

    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        if sample_rate_hz not in (8000, 16000, 32000, 48000):
            raise VadCandidateError("WebRTC VAD supports 8/16/32/48 kHz")
        if not isinstance(pcm_s16le, bytes) or not pcm_s16le:
            raise VadCandidateError("VAD input must be non-empty PCM bytes")
        duration_ms = len(pcm_s16le) / 2 / sample_rate_hz * 1000.0
        if duration_ms not in (10.0, 20.0, 30.0):
            raise VadCandidateError("WebRTC VAD input must be a 10, 20 or 30 ms frame")
        try:
            return bool(self._load_backend().is_speech(pcm_s16le, sample_rate_hz))
        except Exception as exc:
            if isinstance(exc, VadCandidateError):
                raise
            raise VadCandidateError(f"WebRTC VAD operation failed: {exc}") from exc


class VadProcessor:
    """Apply a candidate to each direct PCM frame without owning endpoint state."""

    def __init__(self, candidate: VadCandidate) -> None:
        self.candidate = candidate

    def process(self, frame: PcmFrame) -> VadDecision:
        if frame.profile.channels != 1 or frame.profile.pcm_bits_per_sample != 16:
            raise VadCandidateError("speech ingress requires mono PCM S16LE")
        duration_ms = frame.sample_count / frame.profile.sample_rate_hz * 1000.0
        rounded_duration = int(round(duration_ms))
        if rounded_duration not in (10, 20, 30):
            raise VadCandidateError(
                f"VAD frame duration must be 10/20/30 ms, got {duration_ms:g} ms"
            )
        try:
            is_speech = bool(
                self.candidate.is_speech(frame.pcm_s16le, frame.profile.sample_rate_hz)
            )
        except VadCandidateError:
            raise
        except Exception as exc:
            raise VadCandidateError(f"VAD candidate operation failed: {exc}") from exc
        return VadDecision(
            call_id=frame.call_id,
            channel_id=frame.channel_id,
            generation=frame.generation,
            sequence=frame.sequence,
            timestamp_ns=frame.timestamp_ns,
            frame_duration_ms=rounded_duration,
            is_speech=is_speech,
            source=type(self.candidate).__name__,
        )
