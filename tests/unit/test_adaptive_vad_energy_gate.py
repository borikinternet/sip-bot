"""Adaptive energy confirmation for the WebRTC VAD boundary."""

from __future__ import annotations

import math
import struct

import pytest

from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.speech import (
    AdaptiveEnergyGate,
    AdaptiveEnergyGateConfig,
    VadProcessor,
    WebRtcVadCandidate,
)


class _AlwaysSpeech:
    def is_speech(self, _pcm_s16le: bytes, _sample_rate_hz: int) -> bool:
        return True


def _pcm(dbfs: float, samples: int = 160) -> bytes:
    amplitude = max(1, min(32767, round(32768 * 10 ** (dbfs / 20.0))))
    return struct.pack("<h", amplitude) * samples


def _frame(dbfs: float, sequence: int = 1) -> PcmFrame:
    profile = NegotiatedMediaProfile(
        "PCMU",
        0,
        20.0,
        8000,
        1,
        160,
        rx_payload_type=0,
        tx_payload_type=0,
    )
    return PcmFrame(
        "adaptive-vad-call",
        "adaptive-vad-call:media",
        1,
        sequence,
        (sequence - 1) * 20_000_000,
        _pcm(dbfs),
        profile,
    )


def test_gate_rejects_low_energy_raw_positive_and_accepts_clear_speech() -> None:
    gate = AdaptiveEnergyGate()

    noise = gate.observe(_pcm(-52.0), raw_is_speech=True, frame_duration_ms=20)
    speech = gate.observe(_pcm(-18.0), raw_is_speech=True, frame_duration_ms=20)
    snapshot = gate.snapshot()

    assert noise.raw_is_speech is True
    assert noise.accepted_is_speech is False
    assert noise.rms_dbfs == pytest.approx(-52.0, abs=0.1)
    assert noise.speech_threshold_dbfs == -42.0
    assert speech.accepted_is_speech is True
    assert speech.speech_level_dbfs is None
    assert snapshot.total_frames == 2
    assert snapshot.raw_speech_frames == 2
    assert snapshot.accepted_speech_frames == 1
    assert snapshot.rejected_low_energy_frames == 1


def test_noise_floor_adapts_without_learning_immediate_speech_as_noise() -> None:
    gate = AdaptiveEnergyGate(
        AdaptiveEnergyGateConfig(
            minimum_dbfs=-80.0,
            noise_margin_db=10.0,
            initial_noise_floor_dbfs=-90.0,
            history_ms=1000,
            bootstrap_ms=100,
            noise_percentile=0.20,
            max_noise_rise_db_per_s=60.0,
        )
    )

    for _ in range(50):
        observation = gate.observe(_pcm(-50.0), raw_is_speech=False, frame_duration_ms=20)

    assert observation.noise_floor_dbfs == pytest.approx(-50.0, abs=0.1)
    assert observation.speech_threshold_dbfs == pytest.approx(-40.0, abs=0.1)
    assert gate.observe(
        _pcm(-45.0), raw_is_speech=True, frame_duration_ms=20
    ).accepted_is_speech is False
    assert gate.observe(
        _pcm(-25.0), raw_is_speech=True, frame_duration_ms=20
    ).accepted_is_speech is True


def test_processor_keeps_raw_decision_and_publishes_energy_diagnostics() -> None:
    processor = VadProcessor(
        WebRtcVadCandidate(mode=2, backend=_AlwaysSpeech()),
        energy_gate=AdaptiveEnergyGate(),
    )

    decision = processor.process(_frame(-55.0))
    snapshot = processor.analytics_snapshot()

    assert decision.raw_is_speech is True
    assert decision.is_speech is False
    assert decision.rms_dbfs == pytest.approx(-55.0, abs=0.1)
    assert decision.noise_floor_dbfs == -60.0
    assert decision.speech_threshold_dbfs == -42.0
    assert snapshot is not None
    assert snapshot.rejected_low_energy_frames == 1


def test_near_end_reference_rejects_echo_and_uses_stricter_barge_threshold() -> None:
    gate = AdaptiveEnergyGate(
        AdaptiveEnergyGateConfig(
            near_end_bootstrap_dbfs=-26.0,
            near_end_confirmation_ms=200,
            near_end_percentile=0.70,
            near_end_margin_db=12.0,
            barge_in_margin_db=8.0,
            barge_in_minimum_dbfs=-26.0,
            speech_level_alpha=0.20,
        )
    )

    pre_reference_echo = gate.observe(_pcm(-30.0), raw_is_speech=True, frame_duration_ms=20)
    near_end = [
        gate.observe(_pcm(-18.0), raw_is_speech=True, frame_duration_ms=20)
        for _ in range(10)
    ][-1]
    gate.observe(_pcm(-60.0), raw_is_speech=False, frame_duration_ms=20)
    post_reference_echo = gate.observe(_pcm(-32.0), raw_is_speech=True, frame_duration_ms=20)
    quieter_near_end = gate.observe(_pcm(-24.0), raw_is_speech=True, frame_duration_ms=20)

    assert pre_reference_echo.accepted_is_speech is True
    assert pre_reference_echo.barge_in_qualified is False
    assert near_end.speech_level_dbfs == pytest.approx(-18.0, abs=0.1)
    assert near_end.speech_threshold_dbfs == pytest.approx(-30.0, abs=0.1)
    assert near_end.barge_in_threshold_dbfs == pytest.approx(-26.0, abs=0.1)
    assert near_end.barge_in_qualified is True
    assert post_reference_echo.accepted_is_speech is False
    assert post_reference_echo.barge_in_qualified is False
    assert quieter_near_end.accepted_is_speech is True
    assert quieter_near_end.barge_in_qualified is True


def test_confirmed_energetic_onset_preserves_web_rtc_low_energy_hangover() -> None:
    gate = AdaptiveEnergyGate(AdaptiveEnergyGateConfig(confirmation_ms=80))

    onset = [
        gate.observe(_pcm(-18.0), raw_is_speech=True, frame_duration_ms=20)
        for _ in range(4)
    ]
    hangover = gate.observe(_pcm(-60.0), raw_is_speech=True, frame_duration_ms=20)
    reset = gate.observe(_pcm(-60.0), raw_is_speech=False, frame_duration_ms=20)
    unconfirmed = gate.observe(_pcm(-60.0), raw_is_speech=True, frame_duration_ms=20)

    assert all(item.accepted_is_speech for item in onset)
    assert hangover.accepted_is_speech is True
    assert reset.accepted_is_speech is False
    assert unconfirmed.accepted_is_speech is False


def test_processor_without_gate_preserves_existing_candidate_contract() -> None:
    decision = VadProcessor(WebRtcVadCandidate(backend=_AlwaysSpeech())).process(_frame(-96.0))

    assert decision.is_speech is True
    assert decision.raw_is_speech is True
    assert decision.rms_dbfs is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minimum_dbfs": 1.0},
        {"initial_noise_floor_dbfs": -30.0},
        {"noise_margin_db": 0.0},
        {"bootstrap_ms": 20_000},
        {"noise_percentile": 1.0},
        {"max_noise_rise_db_per_s": math.inf},
        {"near_end_bootstrap_dbfs": -97.0},
        {"near_end_confirmation_ms": 0},
        {"near_end_percentile": 1.0},
        {"near_end_margin_db": 0.0},
        {"barge_in_margin_db": 0.0},
        {"barge_in_minimum_dbfs": 1.0},
    ],
)
def test_energy_gate_configuration_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        AdaptiveEnergyGateConfig(**kwargs)  # type: ignore[arg-type]
