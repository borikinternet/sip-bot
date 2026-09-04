"""Contract checks for the authoritative 002-C -> 002-D boundary."""

from __future__ import annotations

import pytest

from sip_bot.control import ControlEventBus, ControlPayloadError
from sip_bot.media import AsrAudioChunk, FlushReason, NegotiatedMediaProfile
from sip_bot.speech import AsrAudioChunk as SpeechAsrAudioChunk
from sip_bot.speech import EndpointEventKind, FinalUserTurn
from sip_bot.speech import StreamingAsrAdapter


def _profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        ptime_ms=20.0,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=160,
        source="002-C.propagation",
    )


def test_speech_reexports_the_media_chunk_contract_without_duplication() -> None:
    chunk = AsrAudioChunk(
        call_id="call-propagation",
        channel_id="call-propagation:asr",
        generation=1,
        sequence=1,
        timestamp_ns=0,
        pcm_s16le=b"\x00\x00" * 160,
        profile=_profile(),
        flush_reason=FlushReason.TARGET,
    )

    assert SpeechAsrAudioChunk is AsrAudioChunk
    assert chunk.duration_ms == 20.0
    assert chunk.profile.sample_rate_hz == 8000
    assert chunk.flush_reason is FlushReason.TARGET


def test_asr_adapter_accepts_the_chunk_emitted_by_media_chunker() -> None:
    class Backend:
        def transcribe_chunk(self, chunk: AsrAudioChunk):
            assert chunk.profile.sample_rate_hz == 8000
            assert chunk.flush_reason is FlushReason.HARD_ENDPOINT
            return [{"text": "вопрос"}]

    adapter = StreamingAsrAdapter(Backend())
    operation = adapter.open_operation(
        call_id="call-propagation",
        channel_id="call-propagation:asr",
        generation=1,
    )
    chunk = AsrAudioChunk(
        call_id="call-propagation",
        channel_id="call-propagation:asr",
        generation=1,
        sequence=1,
        timestamp_ns=0,
        pcm_s16le=b"\x00\x00" * 160,
        profile=_profile(),
        flush_reason=FlushReason.HARD_ENDPOINT,
        is_final=True,
    )

    result = list(adapter.stream(operation, [chunk]))
    assert [item.text for item in result] == ["вопрос"]


def test_final_user_turn_is_direct_payload_and_cannot_enter_control_bus() -> None:
    final_turn = FinalUserTurn(
        call_id="call-propagation",
        channel_id="call-propagation:audio",
        generation=1,
        turn_id="call-propagation:turn-1",
        text="почему небо голубое",
        revision=2,
        finalized_at_ns=500_000_000,
        boundary=EndpointEventKind.HARD_ENDPOINT,
    )

    bus = ControlEventBus()
    bus.subscribe()
    with pytest.raises(ControlPayloadError, match="data-plane"):
        bus.publish(final_turn)
