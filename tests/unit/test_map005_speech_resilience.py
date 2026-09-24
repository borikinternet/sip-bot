"""Focused unit checks for the Map-005-B speech boundaries."""

from __future__ import annotations

from sip_bot.media import AsrChunker, PcmFanOut
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.speech import VadProcessor, WebRtcVadCandidate


def _profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        rx_payload_type=0,
        tx_payload_type=0,
        ptime_ms=20.0,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=160,
        source="map005-b-unit",
    )


def _frame(sequence: int, *, generation: int = 1) -> PcmFrame:
    profile = _profile()
    return PcmFrame(
        call_id="unit-call",
        channel_id="unit-call:audio",
        generation=generation,
        sequence=sequence,
        timestamp_ns=(sequence - 1) * 20_000_000,
        pcm_s16le=b"\x01\x00" * profile.frame_size_samples,
        profile=profile,
    )


class _AlwaysSpeech:
    def is_speech(self, _pcm_s16le: bytes, _sample_rate_hz: int) -> bool:
        return True


def test_fanout_rejects_stale_generation_without_delivering_payload() -> None:
    fanout = PcmFanOut(capacity_frames=2, generation=2)
    subscription = fanout.subscribe("asr")

    result = fanout.publish(_frame(1, generation=1))

    assert result.accepted is False
    assert result.stale_for == ("asr",)
    assert subscription.get_nowait() is None
    assert fanout.stats.dropped_stale == 1


def test_chunker_preserves_negotiated_pcm_profile_and_frame_units() -> None:
    profile = _profile()
    chunker = AsrChunker(
        profile=profile,
        call_id="unit-call",
        channel_id="unit-call:audio",
        generation=1,
        chunk_ms=100,
    )
    chunker.begin_turn("unit-call:turn-1")

    for sequence in range(1, 6):
        chunker.push(_frame(sequence))

    chunk = chunker.next_chunk()
    assert chunk is not None
    assert chunk.profile == profile
    assert chunk.sample_count == 800
    assert chunk.duration_ms == 100.0


def test_vad_processor_passes_pcm_s16le_and_negotiated_rate_to_candidate() -> None:
    decision = VadProcessor(WebRtcVadCandidate(backend=_AlwaysSpeech())).process(_frame(1))

    assert decision.is_speech is True
    assert decision.frame_duration_ms == 20
    assert decision.source == "WebRtcVadCandidate"
