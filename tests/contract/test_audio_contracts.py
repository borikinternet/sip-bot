"""Contract fixtures for the 002-B -> 002-C direct media boundary."""

from __future__ import annotations

from sip_bot.media import (
    AsrAudioChunk,
    AsrChunker,
    FlushReason,
    NegotiatedMediaProfile,
    PcmFanOut,
    PcmFrame,
    decode_pcmu_frame,
)


def negotiated_profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        rx_payload_type=0,
        tx_payload_type=0,
        ptime_ms=20.0,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=160,
        source="pjmedia.stream_info",
    )


def make_frame(sequence: int = 1) -> PcmFrame:
    profile = negotiated_profile()
    return decode_pcmu_frame(
        b"\xff" * profile.frame_size_samples,
        call_id="call-contract",
        channel_id="call-contract:media",
        generation=4,
        sequence=sequence,
        timestamp_ns=(sequence - 1) * 20_000_000,
        profile=profile,
    )


def test_media_profile_and_pcm_frame_are_authoritative_per_call_contract() -> None:
    profile = negotiated_profile()
    frame = make_frame()

    assert profile.as_dict() == {
        "codec": "PCMU",
        "payload_type": 0,
        "rx_payload_type": 0,
        "tx_payload_type": 0,
        "ptime_ms": 20.0,
        "frame_time_usec": 20000,
        "sample_rate_hz": 8000,
        "channels": 1,
        "frame_size_samples": 160,
        "frame_bytes": 320,
        "pcm_bits_per_sample": 16,
        "source": "pjmedia.stream_info",
    }
    assert frame.as_dict()["profile"] == profile.as_dict()
    assert frame.sample_count == 160
    assert len(frame.pcm_s16le) == 320


def test_pcm_fanout_contract_has_independent_named_channels() -> None:
    fanout = PcmFanOut(capacity_frames=2, generation=4)
    vad = fanout.subscribe("vad")
    asr = fanout.subscribe("asr_input_accumulator")

    frame = make_frame()
    outcome = fanout.publish(frame)

    assert outcome.accepted is True
    assert outcome.delivered_to == ("vad", "asr_input_accumulator")
    assert vad.get_nowait() is frame
    assert asr.get_nowait() is frame


def test_asr_chunk_contract_carries_generation_profile_and_flush_semantics() -> None:
    profile = negotiated_profile()
    chunker = AsrChunker(
        profile=profile,
        call_id="call-contract",
        channel_id="call-contract:media",
        generation=4,
        chunk_ms=1000,
        flush_ms=1000,
    )
    for sequence in range(1, 6):
        chunker.push(make_frame(sequence))
    assert chunker.flush(FlushReason.MANUAL, is_final=True) == 1
    chunk = chunker.next_chunk()

    assert isinstance(chunk, AsrAudioChunk)
    assert chunk is not None
    assert chunk.call_id == "call-contract"
    assert chunk.channel_id == "call-contract:media"
    assert chunk.generation == 4
    assert chunk.profile is profile
    assert chunk.flush_reason is FlushReason.MANUAL
    assert chunk.is_final is True
    assert chunk.sample_count == 800
    assert chunk.duration_ms == 100.0


def test_asr_contract_does_not_route_payload_through_control_objects() -> None:
    chunk = AsrAudioChunk(
        call_id="call-contract",
        channel_id="call-contract:media",
        generation=4,
        sequence=1,
        timestamp_ns=0,
        pcm_s16le=b"\x00\x00" * 160,
        profile=negotiated_profile(),
        flush_reason=FlushReason.TARGET,
    )

    assert isinstance(chunk.pcm_s16le, bytes)
    assert "pcm_s16le" not in chunk.as_dict()  # evidence metadata does not duplicate payload
