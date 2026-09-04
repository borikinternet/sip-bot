"""Deterministic TTS aggregation, framing, pacing and adapter tests."""

from __future__ import annotations

from threading import Event

import pytest

from sip_bot.sip_media.models import NegotiatedMediaProfile
from sip_bot.tts import (
    ApprovedTextChunk,
    EngineAudioChunk,
    MediaPacer,
    TtsOutputBuffer,
    TtsOutputError,
    TtsPcmChunk,
    XttsV2Adapter,
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
        frame_size_samples=round(8000 * ptime_ms / 1000),
        source="002-H.test.sdp",
    )


def chunk(*, sequence: int, size: int, generation: int = 1, selected: NegotiatedMediaProfile | None = None) -> TtsPcmChunk:
    return TtsPcmChunk(
        operation_id="op-1",
        call_id="call-1",
        channel_id="call-1:tts",
        generation=generation,
        sequence=sequence,
        pcm_s16le=(sequence.to_bytes(2, "little", signed=True) * (size // 2)),
        profile=selected or profile(),
    )


def test_output_buffer_aggregates_arbitrary_chunks_and_flushes_exact_tail() -> None:
    output = TtsOutputBuffer(
        profile=profile(), call_id="call-1", channel_id="call-1:tts", generation=1,
        start_timestamp_ns=10,
    )

    assert output.push(chunk(sequence=1, size=100)) is True
    assert output.push(chunk(sequence=2, size=500)) is True
    assert output.push(chunk(sequence=3, size=20)) is True
    assert output.pending_frames == 1
    assert output.buffered_bytes == 620
    assert output.complete() == 1

    first = output.next_frame()
    second = output.next_frame()
    assert first is not None and second is not None
    assert len(first.pcm_s16le) == profile().frame_bytes
    assert len(second.pcm_s16le) == profile().frame_bytes
    assert second.pcm_s16le[300:] == b"\x00" * 20
    assert second.timestamp_ns - first.timestamp_ns == 20_000_000
    assert output.next_frame() is None
    assert output.complete() == 0


def test_output_buffer_drops_tail_on_cancel_and_rejects_stale_generation() -> None:
    output = TtsOutputBuffer(profile=profile(), call_id="call-1", channel_id="call-1:tts", generation=2)
    assert output.push(chunk(sequence=1, size=100, generation=1)) is False
    assert output.push(chunk(sequence=1, size=100, generation=2)) is True
    assert output.cancel() is True
    assert output.cancel() is False
    assert output.buffered_bytes == 0
    assert output.pending_frames == 0
    assert output.push(chunk(sequence=2, size=320, generation=2)) is False
    assert output.stats.dropped_stale_chunks == 1
    assert output.stats.dropped_cancelled_chunks == 1
    assert output.stats.dropped_tail_bytes == 100


def test_output_buffer_reports_high_water_without_silent_drop() -> None:
    output = TtsOutputBuffer(
        profile=profile(), call_id="call-1", channel_id="call-1:tts", generation=1,
        max_buffer_bytes=320,
    )
    assert output.push(chunk(sequence=1, size=320)) is True
    with pytest.raises(TtsOutputError, match="high-water"):
        output.push(chunk(sequence=2, size=322))
    assert output.stats.dropped_overflow_bytes == 322


def test_output_buffer_ready_frames_grow_dynamically_without_pending_frame_cap() -> None:
    output = TtsOutputBuffer(
        profile=profile(), call_id="call-1", channel_id="call-1:tts", generation=1,
        max_buffer_bytes=320 * 12, max_pending_frames=1,
    )

    for sequence in range(1, 11):
        assert output.push(chunk(sequence=sequence, size=320)) is True

    assert output.pending_frames == 10
    frames = [output.next_frame() for _ in range(10)]
    assert all(frame is not None for frame in frames)
    assert [frame.sequence for frame in frames if frame is not None] == list(range(1, 11))
    assert output.pending_frames == 0
    assert output.stats.accepted_bytes == 3200
    assert output.stats.emitted_bytes == 3200


def test_output_buffer_keeps_pcm_segments_until_media_frame_is_consumed() -> None:
    output = TtsOutputBuffer(
        profile=profile(), call_id="call-1", channel_id="call-1:tts", generation=1,
        max_buffer_bytes=320 * 4,
    )

    assert output.push(chunk(sequence=1, size=100)) is True
    assert output.push(chunk(sequence=2, size=540)) is True
    assert output.buffered_bytes == 640
    assert output.pending_frames == 2
    first = output.next_frame()
    assert first is not None
    assert first.pcm_s16le == (b"\x01\x00" * 50) + (b"\x02\x00" * 110)
    assert output.buffered_bytes == 320
    assert output.next_frame() is not None
    assert output.buffered_bytes == 0


def test_media_pacer_uses_per_call_ptime_not_a_20ms_constant() -> None:
    selected = profile(ptime_ms=30.0)
    output = TtsOutputBuffer(
        profile=selected, call_id="call-1", channel_id="call-1:tts", generation=1,
        start_timestamp_ns=100,
    )
    assert output.push(chunk(sequence=1, size=480, selected=selected)) is True
    assert output.push(chunk(sequence=2, size=480, selected=selected)) is True
    pacer = MediaPacer(output)
    assert pacer.next_ready(99) is None
    first = pacer.next_ready(100)
    assert first is not None and first.sequence == 1
    assert pacer.next_ready(20_000_099) is None
    second = pacer.next_ready(30_000_100)
    assert second is not None and second.sequence == 2
    assert second.timestamp_ns - first.timestamp_ns == 30_000_000


def test_media_pacer_allows_one_bounded_lookahead_for_direct_media_buffer() -> None:
    selected = profile(ptime_ms=20.0)
    output = TtsOutputBuffer(
        profile=selected, call_id="call-1", channel_id="call-1:tts", generation=1,
        start_timestamp_ns=100,
    )
    assert output.push(chunk(sequence=1, size=640, selected=selected)) is True
    pacer = MediaPacer(output)
    assert pacer.next_ready(100) is not None
    # The second frame is queued up to 10 ms before its media timestamp so
    # a normal 10 ms application-loop jitter cannot starve PJMEDIA.
    assert pacer.next_ready(10_000_100) is not None
    assert output.pending_frames == 0


def test_xtts_adapter_normalizes_injected_engine_chunks_to_call_profile() -> None:
    class FakeEngine:
        def stream(self, text: str, cancel: Event):
            assert text == "Привет"
            yield EngineAudioChunk(b"\x01\x00" * 24, sample_rate_hz=24000)

    adapter = XttsV2Adapter(FakeEngine(), operation_id_factory=lambda: "tts-op-1")
    chunks = list(adapter.stream("Привет", call_id="call-1", channel_id="call-1:tts", turn_id="turn-1",
                                 generation=1, profile=profile()))
    assert len(chunks) == 1
    assert chunks[0].operation_id == "tts-op-1"
    assert chunks[0].sample_count == 8
    assert chunks[0].profile.sample_rate_hz == 8000


def test_xtts_adapter_accepts_only_approved_text_chunks_and_honors_cancel() -> None:
    class FakeEngine:
        def stream(self, text: str, cancel: Event):
            assert text == "одиндва"
            yield EngineAudioChunk(b"\x01\x00" * 24, sample_rate_hz=24000)

    adapter = XttsV2Adapter(FakeEngine(), operation_id_factory=lambda: "tts-op-2")
    approved = [
        ApprovedTextChunk("llm-op", "call-1", "turn-1", 1, 1, "один"),
        ApprovedTextChunk("llm-op", "call-1", "turn-1", 1, 2, "два", is_final=True),
    ]
    assert list(adapter.stream_approved_text(approved, channel_id="call-1:tts", profile=profile()))
    with pytest.raises(TypeError):
        list(adapter.stream_approved_text(["raw text"], channel_id="call-1:tts", profile=profile()))

    cancelled = Event()
    cancelled.set()
    assert list(adapter.stream("Привет", call_id="call-1", channel_id="call-1:tts", turn_id="turn-1",
                               generation=1, profile=profile(), cancel=cancelled)) == []


def test_xtts_adapter_warmup_executes_one_real_output_chunk() -> None:
    class FakeEngine:
        def stream(self, _text: str, _cancel: Event):
            yield EngineAudioChunk(b"\x01\x00" * 24, sample_rate_hz=24000)

    adapter = XttsV2Adapter(FakeEngine(), operation_id_factory=lambda: "tts-warmup")
    result = adapter.warmup(profile=profile())

    assert result["sample_rate_hz"] == 8000
    assert result["channels"] == 1
    assert result["first_chunk_bytes"] == 16
