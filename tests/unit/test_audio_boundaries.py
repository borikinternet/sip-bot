"""Deterministic tests for the direct PCMU/PCM audio data plane."""

from __future__ import annotations

import pytest

from sip_bot.media import (
    AsrChunker,
    AudioBoundaryError,
    FlushReason,
    NegotiatedMediaProfile,
    PcmFanOut,
    PcmFrame,
    decode_pcmu,
    decode_pcmu_frame,
    encode_pcm_frame,
    encode_pcmu,
)


def profile(ptime_ms: float = 20.0) -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        rx_payload_type=0,
        tx_payload_type=0,
        ptime_ms=ptime_ms,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=int(8000 * ptime_ms / 1000),
        source="002-B.test",
    )


def frame(
    *,
    sequence: int = 1,
    timestamp_ns: int | None = None,
    generation: int = 1,
    media_profile: NegotiatedMediaProfile | None = None,
    value: int = 0,
) -> PcmFrame:
    selected = profile() if media_profile is None else media_profile
    return PcmFrame(
        call_id="call-test",
        channel_id="call-test:asr",
        generation=generation,
        sequence=sequence,
        timestamp_ns=sequence * 20_000_000 if timestamp_ns is None else timestamp_ns,
        pcm_s16le=(value.to_bytes(2, "little", signed=True) * selected.frame_size_samples),
        profile=selected,
    )


def test_pcmu_known_vectors_and_round_trip_shape() -> None:
    assert decode_pcmu(bytes((0xFF, 0x7F))) == b"\x00\x00\x00\x00"
    decoded = decode_pcmu(bytes((0x00, 0x80)))
    assert int.from_bytes(decoded[:2], "little", signed=True) == -32124
    assert int.from_bytes(decoded[2:], "little", signed=True) == 32124
    assert encode_pcmu(b"\x00\x00") == b"\xFF"
    assert encode_pcmu(decoded) == bytes((0x00, 0x80))


def test_pcmu_frame_conversion_preserves_call_contract() -> None:
    selected = profile()
    pcm_frame = decode_pcmu_frame(
        bytes((0xFF,)) * selected.frame_size_samples,
        call_id="call-42",
        channel_id="call-42:media",
        generation=3,
        sequence=7,
        timestamp_ns=123,
        profile=selected,
    )

    assert pcm_frame.call_id == "call-42"
    assert pcm_frame.channel_id == "call-42:media"
    assert pcm_frame.generation == 3
    assert pcm_frame.sequence == 7
    assert pcm_frame.profile is selected
    assert len(pcm_frame.pcm_s16le) == selected.frame_bytes
    assert encode_pcm_frame(pcm_frame) == bytes((0xFF,)) * selected.frame_size_samples


def test_pcmu_frame_rejects_payload_not_matching_negotiated_ptime() -> None:
    selected = profile(ptime_ms=30.0)

    with pytest.raises(AudioBoundaryError, match="expected 240"):
        decode_pcmu_frame(
            b"\xff" * 160,
            call_id="call-test",
            channel_id="call-test:media",
            generation=1,
            sequence=1,
            timestamp_ns=1,
            profile=selected,
        )


def test_pcm_fanout_keeps_slow_consumer_isolated_and_drops_stale() -> None:
    selected = profile()
    fanout = PcmFanOut(capacity_frames=1, generation=1)
    vad = fanout.subscribe("vad")
    asr = fanout.subscribe("asr")
    first = frame(sequence=1, media_profile=selected)
    second = frame(sequence=2, media_profile=selected)

    result = fanout.publish(first)
    assert result.accepted is True
    assert result.delivered_to == ("vad", "asr")
    assert vad.get_nowait() == first
    assert asr.get_nowait() == first

    assert fanout.publish(first).overflowed == ()
    duplicate = fanout.publish(first)
    assert duplicate.overflowed == ("vad", "asr")
    assert fanout.publish(second).overflowed == ("vad", "asr")

    # A different generation is stale for both live subscriptions and does
    # not enter either data-plane queue.
    stale = frame(sequence=3, generation=2, media_profile=selected)
    stale_result = fanout.publish(stale)
    assert stale_result.accepted is False
    assert stale_result.stale_for == ("vad", "asr")
    assert vad.qsize() == 1
    assert asr.qsize() == 1

    assert vad.close() is True
    asr.get_nowait()
    closed_result = fanout.publish(second)
    assert closed_result.closed_for == ("vad",)
    assert closed_result.delivered_to == ("asr",)


def test_fanout_close_is_idempotent_and_closes_subscriptions() -> None:
    fanout = PcmFanOut(capacity_frames=1)
    subscription = fanout.subscribe("asr")
    assert fanout.close() is True
    assert fanout.close() is False
    assert subscription.closed is True
    with pytest.raises(RuntimeError, match="closed"):
        fanout.subscribe("vad")


def test_asr_chunker_emits_exact_target_from_media_frames() -> None:
    selected = profile()
    chunker = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
        chunk_ms=1000,
        flush_ms=1000,
    )

    emitted = 0
    for sequence in range(1, 51):
        emitted += chunker.push(frame(sequence=sequence, media_profile=selected))

    chunk = chunker.next_chunk()
    assert emitted == 1
    assert chunk is not None
    assert chunk.flush_reason is FlushReason.TARGET
    assert chunk.is_final is False
    assert chunk.sample_count == 8000
    assert chunk.duration_ms == 1000.0
    assert len(chunk.pcm_s16le) == selected.frame_bytes * 50
    assert chunker.buffered_bytes == 0


def test_asr_chunker_timer_flushes_partial_tail_without_background_thread() -> None:
    selected = profile()
    chunker = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
        flush_ms=1000,
    )

    assert chunker.push(frame(sequence=1, timestamp_ns=0, media_profile=selected)) == 0
    assert chunker.on_timer(999_999_999) == 0
    assert chunker.on_timer(1_000_000_000) == 1
    chunk = chunker.next_chunk()
    assert chunk is not None
    assert chunk.flush_reason is FlushReason.TIMER
    assert chunk.is_final is False
    assert chunk.duration_ms == 20.0


def test_asr_chunker_hard_endpoint_and_close_mark_final_tail() -> None:
    selected = profile()
    hard = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
    )
    hard.push(frame(sequence=1, media_profile=selected))
    assert hard.hard_endpoint() == 1
    hard_chunk = hard.next_chunk()
    assert hard_chunk is not None
    assert hard_chunk.flush_reason is FlushReason.HARD_ENDPOINT
    assert hard_chunk.is_final is True

    closing = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
    )
    closing.push(frame(sequence=1, media_profile=selected))
    assert closing.close() is True
    assert closing.close() is False
    close_chunk = closing.next_chunk()
    assert close_chunk is not None
    assert close_chunk.flush_reason is FlushReason.CLOSE
    assert close_chunk.is_final is True
    assert closing.push(frame(sequence=2, media_profile=selected)) == 0


def test_asr_chunker_hard_endpoint_marks_exact_target_asr_chunk_without_duplicate_audio() -> None:
    selected = profile()
    chunker = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
        chunk_ms=40,
    )
    for sequence in range(1, 3):
        chunker.push(frame(sequence=sequence, media_profile=selected))

    assert chunker.hard_endpoint() == 1
    target = chunker.next_chunk()
    marker = chunker.next_chunk()
    assert target is not None and target.flush_reason is FlushReason.TARGET
    assert marker is not None
    assert marker.flush_reason is FlushReason.HARD_ENDPOINT
    assert marker.is_final is True
    assert marker.pcm_s16le == b""


def test_asr_chunker_cancel_discards_pending_and_future_stale_audio() -> None:
    selected = profile()
    chunker = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
        max_pending_chunks=1,
    )
    chunker.push(frame(sequence=1, media_profile=selected))
    assert chunker.cancel() is True
    assert chunker.cancel() is False
    assert chunker.next_chunk() is None
    assert chunker.buffered_bytes == 0
    assert chunker.push(frame(sequence=2, media_profile=selected)) == 0
    assert chunker.stats.dropped_cancelled >= 2


def test_asr_chunker_overflow_is_non_blocking_and_observable() -> None:
    selected = profile()
    chunker = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=1,
        max_pending_chunks=1,
    )
    for sequence in range(1, 101):
        chunker.push(frame(sequence=sequence, media_profile=selected))

    assert chunker.pending_chunks == 1
    assert chunker.stats.emitted_chunks == 1
    assert chunker.stats.dropped_overflow == 1
    assert chunker.buffered_bytes == 0


def test_asr_chunker_rejects_duplicate_and_wrong_generation_frames() -> None:
    selected = profile()
    chunker = AsrChunker(
        profile=selected,
        call_id="call-test",
        channel_id="call-test:asr",
        generation=2,
    )
    assert chunker.push(frame(sequence=1, generation=1, media_profile=selected)) == 0
    assert chunker.push(frame(sequence=1, generation=2, media_profile=selected)) == 0
    assert chunker.push(frame(sequence=2, generation=2, media_profile=selected)) == 0
    assert chunker.push(frame(sequence=2, generation=2, media_profile=selected)) == 0
    assert chunker.stats.dropped_stale == 2
