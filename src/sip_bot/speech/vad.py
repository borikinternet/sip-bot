"""VAD candidate boundary and frame-level processor."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import struct
from typing import Any, Protocol

from sip_bot.sip_media.models import PcmFrame

from .contracts import VadDecision


class VadCandidate(Protocol):
    """Minimal candidate contract; native implementation is loaded lazily."""

    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        ...


class VadCandidateError(RuntimeError):
    """Raised when the selected VAD candidate cannot be used."""


@dataclass(frozen=True, slots=True)
class AdaptiveEnergyGateConfig:
    """Per-call energy policy applied after the spectral WebRTC decision."""

    minimum_dbfs: float = -42.0
    noise_margin_db: float = 10.0
    initial_noise_floor_dbfs: float = -60.0
    history_ms: int = 10_000
    bootstrap_ms: int = 500
    noise_percentile: float = 0.20
    max_noise_rise_db_per_s: float = 5.0
    noise_fall_alpha: float = 0.20
    speech_level_alpha: float = 0.05
    confirmation_ms: int = 80
    near_end_bootstrap_dbfs: float = -26.0
    near_end_confirmation_ms: int = 200
    near_end_percentile: float = 0.70
    near_end_margin_db: float = 12.0
    barge_in_margin_db: float = 8.0
    barge_in_minimum_dbfs: float = -26.0

    def __post_init__(self) -> None:
        for name in (
            "minimum_dbfs",
            "initial_noise_floor_dbfs",
            "near_end_bootstrap_dbfs",
            "barge_in_minimum_dbfs",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not -96.0 <= value <= 0.0:
                raise ValueError(f"{name} must be a finite dBFS value between -96 and 0")
        if self.initial_noise_floor_dbfs > self.minimum_dbfs:
            raise ValueError("initial noise floor must not exceed the minimum speech threshold")
        if not math.isfinite(self.noise_margin_db) or self.noise_margin_db <= 0:
            raise ValueError("noise margin must be positive")
        if self.history_ms < 1 or not 1 <= self.bootstrap_ms <= self.history_ms:
            raise ValueError("energy history and bootstrap durations are inconsistent")
        if not 0.0 < self.noise_percentile < 1.0:
            raise ValueError("noise percentile must be between 0 and 1")
        if not math.isfinite(self.max_noise_rise_db_per_s) or self.max_noise_rise_db_per_s <= 0:
            raise ValueError("maximum noise rise must be positive")
        for name in ("noise_fall_alpha", "speech_level_alpha"):
            value = getattr(self, name)
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.confirmation_ms < 1:
            raise ValueError("energy confirmation duration must be positive")
        if self.near_end_confirmation_ms < 1:
            raise ValueError("near-end confirmation duration must be positive")
        if not 0.0 < self.near_end_percentile < 1.0:
            raise ValueError("near_end_percentile must be between 0 and 1")
        for name in ("near_end_margin_db", "barge_in_margin_db"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class EnergyGateObservation:
    """One energy measurement and the resulting accepted speech decision."""

    raw_is_speech: bool
    accepted_is_speech: bool
    rms_dbfs: float
    noise_floor_dbfs: float
    speech_threshold_dbfs: float
    speech_level_dbfs: float | None
    barge_in_threshold_dbfs: float
    barge_in_qualified: bool


@dataclass(frozen=True, slots=True)
class VadAnalyticsSnapshot:
    """Compact observable summary of one call's adaptive VAD operation."""

    total_frames: int
    raw_speech_frames: int
    accepted_speech_frames: int
    rejected_low_energy_frames: int
    noise_floor_dbfs: float
    speech_threshold_dbfs: float
    speech_level_dbfs: float | None
    barge_in_threshold_dbfs: float
    barge_in_qualified_frames: int


class AdaptiveEnergyGate:
    """Reject low-energy WebRTC positives while adapting to the call noise floor.

    WebRTC VAD keeps useful internal spectral/noise state, but its public Python
    API exposes only a boolean.  This gate therefore keeps independent,
    inspectable energy state.  A low percentile is used instead of an average
    so ordinary speech cannot quickly redefine the noise floor.  Upward
    movement is rate-limited; a caller who starts speaking immediately cannot
    make the gate calibrate itself to speech.
    """

    def __init__(self, config: AdaptiveEnergyGateConfig | None = None) -> None:
        self.config = config or AdaptiveEnergyGateConfig()
        self._history: deque[tuple[int, float]] = deque()
        self._history_duration_ms = 0
        self._noise_floor_dbfs = self.config.initial_noise_floor_dbfs
        self._speech_threshold_dbfs = max(
            self.config.minimum_dbfs,
            self._noise_floor_dbfs + self.config.noise_margin_db,
        )
        self._speech_level_dbfs: float | None = None
        self._near_end_history: deque[tuple[int, float]] = deque()
        self._near_end_history_duration_ms = 0
        self._total_frames = 0
        self._raw_speech_frames = 0
        self._accepted_speech_frames = 0
        self._rejected_low_energy_frames = 0
        self._barge_in_qualified_frames = 0
        self._high_energy_streak_ms = 0
        self._confirmed_speech = False

    def observe(
        self,
        pcm_s16le: bytes,
        *,
        raw_is_speech: bool,
        frame_duration_ms: int,
    ) -> EnergyGateObservation:
        if frame_duration_ms not in (10, 20, 30):
            raise VadCandidateError("energy gate requires a 10, 20 or 30 ms frame")
        rms_dbfs = _rms_dbfs(pcm_s16le)
        self._history.append((frame_duration_ms, rms_dbfs))
        self._history_duration_ms += frame_duration_ms
        while self._history_duration_ms > self.config.history_ms and self._history:
            duration_ms, _value = self._history.popleft()
            self._history_duration_ms -= duration_ms

        if self._history_duration_ms >= self.config.bootstrap_ms:
            target = _percentile(
                tuple(value for _duration, value in self._history),
                self.config.noise_percentile,
            )
            if target > self._noise_floor_dbfs:
                max_rise = self.config.max_noise_rise_db_per_s * frame_duration_ms / 1000.0
                self._noise_floor_dbfs = min(target, self._noise_floor_dbfs + max_rise)
            else:
                alpha = self.config.noise_fall_alpha
                self._noise_floor_dbfs += alpha * (target - self._noise_floor_dbfs)

        base_threshold_dbfs = max(
            self.config.minimum_dbfs,
            self._noise_floor_dbfs + self.config.noise_margin_db,
        )
        if raw_is_speech and rms_dbfs >= max(
            base_threshold_dbfs,
            self.config.near_end_bootstrap_dbfs,
        ):
            self._near_end_history.append((frame_duration_ms, rms_dbfs))
            self._near_end_history_duration_ms += frame_duration_ms
            while (
                self._near_end_history_duration_ms > self.config.history_ms
                and self._near_end_history
            ):
                duration_ms, _value = self._near_end_history.popleft()
                self._near_end_history_duration_ms -= duration_ms
            if self._near_end_history_duration_ms >= self.config.near_end_confirmation_ms:
                target = _percentile(
                    tuple(value for _duration, value in self._near_end_history),
                    self.config.near_end_percentile,
                )
                if self._speech_level_dbfs is None:
                    self._speech_level_dbfs = target
                else:
                    alpha = self.config.speech_level_alpha
                    self._speech_level_dbfs += alpha * (target - self._speech_level_dbfs)
        self._speech_threshold_dbfs = base_threshold_dbfs
        if self._speech_level_dbfs is not None:
            self._speech_threshold_dbfs = max(
                self._speech_threshold_dbfs,
                self._speech_level_dbfs - self.config.near_end_margin_db,
            )
        barge_in_threshold_dbfs = max(
            base_threshold_dbfs,
            self.config.barge_in_minimum_dbfs,
        )
        if self._speech_level_dbfs is not None:
            barge_in_threshold_dbfs = max(
                barge_in_threshold_dbfs,
                self._speech_level_dbfs - self.config.barge_in_margin_db,
            )
        energy_positive = bool(raw_is_speech and rms_dbfs >= self._speech_threshold_dbfs)
        barge_in_qualified = bool(
            raw_is_speech and rms_dbfs >= barge_in_threshold_dbfs
        )
        if not raw_is_speech:
            self._high_energy_streak_ms = 0
            self._confirmed_speech = False
            accepted = False
        elif energy_positive:
            self._high_energy_streak_ms += frame_duration_ms
            if self._high_energy_streak_ms >= self.config.confirmation_ms:
                self._confirmed_speech = True
            accepted = True
        elif self._confirmed_speech:
            # Preserve the WebRTC spectral hangover after a real energetic
            # onset.  Removing this tail makes a 480 ms conversational pause
            # look longer than the 520 ms hard endpoint.
            accepted = True
        else:
            self._high_energy_streak_ms = 0
            accepted = False
        self._total_frames += 1
        if raw_is_speech:
            self._raw_speech_frames += 1
        if energy_positive:
            self._accepted_speech_frames += 1
        elif accepted:
            self._accepted_speech_frames += 1
        elif raw_is_speech:
            self._rejected_low_energy_frames += 1
        if barge_in_qualified:
            self._barge_in_qualified_frames += 1

        return EnergyGateObservation(
            raw_is_speech=raw_is_speech,
            accepted_is_speech=accepted,
            rms_dbfs=rms_dbfs,
            noise_floor_dbfs=self._noise_floor_dbfs,
            speech_threshold_dbfs=self._speech_threshold_dbfs,
            speech_level_dbfs=self._speech_level_dbfs,
            barge_in_threshold_dbfs=barge_in_threshold_dbfs,
            barge_in_qualified=barge_in_qualified,
        )

    def snapshot(self) -> VadAnalyticsSnapshot:
        return VadAnalyticsSnapshot(
            total_frames=self._total_frames,
            raw_speech_frames=self._raw_speech_frames,
            accepted_speech_frames=self._accepted_speech_frames,
            rejected_low_energy_frames=self._rejected_low_energy_frames,
            noise_floor_dbfs=self._noise_floor_dbfs,
            speech_threshold_dbfs=self._speech_threshold_dbfs,
            speech_level_dbfs=self._speech_level_dbfs,
            barge_in_threshold_dbfs=max(
                self.config.barge_in_minimum_dbfs,
                self._noise_floor_dbfs + self.config.noise_margin_db,
                (
                    -96.0
                    if self._speech_level_dbfs is None
                    else self._speech_level_dbfs - self.config.barge_in_margin_db
                ),
            ),
            barge_in_qualified_frames=self._barge_in_qualified_frames,
        )


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

    def __init__(
        self,
        candidate: VadCandidate,
        *,
        energy_gate: AdaptiveEnergyGate | None = None,
    ) -> None:
        self.candidate = candidate
        self.energy_gate = energy_gate

    def analytics_snapshot(self) -> VadAnalyticsSnapshot | None:
        return None if self.energy_gate is None else self.energy_gate.snapshot()

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
            raw_is_speech = bool(
                self.candidate.is_speech(frame.pcm_s16le, frame.profile.sample_rate_hz)
            )
        except VadCandidateError:
            raise
        except Exception as exc:
            raise VadCandidateError(f"VAD candidate operation failed: {exc}") from exc
        observation = (
            None
            if self.energy_gate is None
            else self.energy_gate.observe(
                frame.pcm_s16le,
                raw_is_speech=raw_is_speech,
                frame_duration_ms=rounded_duration,
            )
        )
        return VadDecision(
            call_id=frame.call_id,
            channel_id=frame.channel_id,
            generation=frame.generation,
            sequence=frame.sequence,
            timestamp_ns=frame.timestamp_ns,
            frame_duration_ms=rounded_duration,
            is_speech=(
                raw_is_speech
                if observation is None
                else observation.accepted_is_speech
            ),
            raw_is_speech=raw_is_speech,
            rms_dbfs=None if observation is None else observation.rms_dbfs,
            noise_floor_dbfs=None if observation is None else observation.noise_floor_dbfs,
            speech_threshold_dbfs=(
                None if observation is None else observation.speech_threshold_dbfs
            ),
            speech_level_dbfs=None if observation is None else observation.speech_level_dbfs,
            barge_in_threshold_dbfs=(
                None if observation is None else observation.barge_in_threshold_dbfs
            ),
            barge_in_qualified=(
                None if observation is None else observation.barge_in_qualified
            ),
            source=type(self.candidate).__name__,
        )


def build_configured_web_rtc_vad_processor(config: Any) -> VadProcessor:
    """Build the one authoritative application/live WebRTC VAD policy."""

    energy_gate = None
    if config.vad_energy_gate_enabled:
        energy_gate = AdaptiveEnergyGate(
            AdaptiveEnergyGateConfig(
                minimum_dbfs=config.vad_energy_min_dbfs,
                noise_margin_db=config.vad_energy_noise_margin_db,
                initial_noise_floor_dbfs=config.vad_energy_initial_noise_floor_dbfs,
                history_ms=config.vad_energy_history_ms,
                bootstrap_ms=config.vad_energy_bootstrap_ms,
                noise_percentile=config.vad_energy_noise_percentile,
                max_noise_rise_db_per_s=config.vad_energy_max_noise_rise_db_per_s,
                noise_fall_alpha=config.vad_energy_noise_fall_alpha,
                speech_level_alpha=config.vad_energy_speech_level_alpha,
                confirmation_ms=config.vad_energy_confirmation_ms,
                near_end_bootstrap_dbfs=config.vad_energy_near_end_bootstrap_dbfs,
                near_end_confirmation_ms=config.vad_energy_near_end_confirmation_ms,
                near_end_percentile=config.vad_energy_near_end_percentile,
                near_end_margin_db=config.vad_energy_near_end_margin_db,
                barge_in_margin_db=config.vad_energy_barge_in_margin_db,
                barge_in_minimum_dbfs=config.vad_energy_barge_in_minimum_dbfs,
            )
        )
    return VadProcessor(
        WebRtcVadCandidate(mode=config.vad_mode),
        energy_gate=energy_gate,
    )


def _rms_dbfs(pcm_s16le: bytes) -> float:
    if not pcm_s16le or len(pcm_s16le) % 2:
        raise VadCandidateError("energy gate requires non-empty PCM S16LE samples")
    sample_count = len(pcm_s16le) // 2
    sum_squares = sum(sample * sample for (sample,) in struct.iter_unpack("<h", pcm_s16le))
    rms = math.sqrt(sum_squares / sample_count)
    if rms <= 0.0:
        return -96.0
    return max(-96.0, 20.0 * math.log10(rms / 32768.0))


def _percentile(values: tuple[float, ...], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
