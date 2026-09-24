"""Application-boundary evidence for the selected WebRTC VAD candidate."""

from __future__ import annotations

from dataclasses import replace

from sip_bot.config import RuntimeConfig
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.speech import (
    VadProcessor,
    WebRtcVadCandidate,
    build_configured_web_rtc_vad_processor,
)


class _AlwaysSpeech:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        self.calls.append((len(pcm_s16le), sample_rate_hz))
        return True


def _frame() -> PcmFrame:
    profile = NegotiatedMediaProfile("PCMU", 0, 20.0, 8000, 1, 160, rx_payload_type=0, tx_payload_type=0)
    return PcmFrame(
        "application-boundary-call",
        "application-boundary-call:media",
        1,
        1,
        0,
        b"\x00\x00" * profile.frame_size_samples,
        profile,
    )


def test_application_config_exposes_web_rtc_mode_without_changing_speech_contract() -> None:
    config = RuntimeConfig.from_constants()
    backend = _AlwaysSpeech()
    processor = VadProcessor(WebRtcVadCandidate(mode=config.vad_mode, backend=backend))

    decision = processor.process(_frame())

    assert config.vad_mode == 2
    assert processor.candidate.mode == config.vad_mode
    assert decision.is_speech is True
    assert decision.source == "WebRtcVadCandidate"
    assert backend.calls == [(320, 8000)]


def test_candidate_preserves_negotiated_frame_rate_at_existing_boundary() -> None:
    profile = NegotiatedMediaProfile("PCMU", 0, 20.0, 16000, 1, 320, rx_payload_type=0, tx_payload_type=0)
    frame = replace(_frame(), pcm_s16le=b"\x00\x00" * profile.frame_size_samples, profile=profile)
    backend = _AlwaysSpeech()

    decision = VadProcessor(WebRtcVadCandidate(mode=2, backend=backend)).process(frame)

    assert decision.frame_duration_ms == 20
    assert backend.calls == [(640, 16000)]


def test_live_factory_enables_adaptive_energy_gate() -> None:
    processor = build_configured_web_rtc_vad_processor(RuntimeConfig.from_constants())

    assert processor.energy_gate is not None
    assert processor.candidate.mode == 2
