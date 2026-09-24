"""Deterministic speech-ingress tests without native VAD or GPU inference."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from sip_bot.media import AsrAudioChunk, FlushReason
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.speech import (
    AsrAudioChunk,
    AsrHypothesis,
    AsrSpeechDecision,
    AsrSpeechEvidence,
    EndpointEvent,
    EndpointEventKind,
    EndpointingConfig,
    FasterWhisperC2Backend,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TranscriptContractError,
    TranscriptUpdateKind,
    TurnDetector,
    VadCandidateError,
    VadProcessor,
    WebRtcVadCandidate,
)


def _profile(ptime_ms: float = 20.0) -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        ptime_ms=ptime_ms,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=int(8000 * ptime_ms / 1000),
    )


def _frame(sequence: int, *, speech: bool, timestamp_ms: int, generation: int = 1) -> PcmFrame:
    profile = _profile()
    return PcmFrame(
        call_id="call-speech",
        channel_id="call-speech:audio",
        generation=generation,
        sequence=sequence,
        timestamp_ns=timestamp_ms * 1_000_000,
        pcm_s16le=(b"\x01" if speech else b"\x00") * profile.frame_bytes,
        profile=profile,
    )


class _ByteVad:
    def is_speech(self, pcm_s16le: bytes, _sample_rate_hz: int) -> bool:
        return pcm_s16le[:1] == b"\x01"


def _speech_processor() -> VadProcessor:
    return VadProcessor(WebRtcVadCandidate(backend=_ByteVad()))


def _decision_sequence(detector: TurnDetector, *, include_resume: bool = False):
    sequence = 0
    for timestamp_ms in range(0, 80, 20):
        sequence += 1
        yield from detector.consume(
            _speech_processor().process(_frame(sequence, speech=True, timestamp_ms=timestamp_ms))
        )
    if include_resume:
        for timestamp_ms in range(80, 280, 20):
            sequence += 1
            yield from detector.consume(
                _speech_processor().process(_frame(sequence, speech=False, timestamp_ms=timestamp_ms))
            )
        sequence += 1
        yield from detector.consume(
            _speech_processor().process(_frame(sequence, speech=True, timestamp_ms=280))
        )
        return
    for timestamp_ms in range(80, 580, 20):
        sequence += 1
        yield from detector.consume(
            _speech_processor().process(_frame(sequence, speech=False, timestamp_ms=timestamp_ms))
        )


def test_webrtc_candidate_contract_is_lazy_and_accepts_deterministic_backend() -> None:
    candidate = WebRtcVadCandidate(backend=_ByteVad())

    assert candidate.is_speech(bytes(320), 8000) is False
    assert candidate.is_speech(b"\x01" * 320, 8000) is True

    with pytest.raises(VadCandidateError, match="10, 20 or 30"):
        candidate.is_speech(bytes(640), 8000)


def test_vad_processor_preserves_frame_scope_and_rejects_invalid_duration() -> None:
    decision = _speech_processor().process(_frame(1, speech=True, timestamp_ms=0))

    assert decision.is_speech is True
    assert decision.call_id == "call-speech"
    assert decision.channel_id == "call-speech:audio"
    assert decision.generation == 1
    assert decision.frame_duration_ms == 20

    profile = _profile(40.0)
    bad_frame = PcmFrame(
        call_id="call-speech",
        channel_id="call-speech:audio",
        generation=1,
        sequence=2,
        timestamp_ns=20_000_000,
        pcm_s16le=b"\x00" * profile.frame_bytes,
        profile=profile,
    )
    with pytest.raises(VadCandidateError):
        _speech_processor().process(bad_frame)


def test_turn_detector_emits_soft_at_300ms_and_authoritative_hard_at_500ms() -> None:
    detector = TurnDetector(EndpointingConfig(soft_endpoint_ms=300, hard_endpoint_ms=500, min_speech_ms=80))

    events = list(_decision_sequence(detector))
    kinds = [event.kind for event in events]

    assert kinds == [
        EndpointEventKind.SPEECH_STARTED,
        EndpointEventKind.PAUSE_CANDIDATE,
        EndpointEventKind.SOFT_ENDPOINT,
        EndpointEventKind.HARD_ENDPOINT,
    ]
    soft = next(event for event in events if event.kind is EndpointEventKind.SOFT_ENDPOINT)
    hard = next(event for event in events if event.kind is EndpointEventKind.HARD_ENDPOINT)
    assert soft.silence_ms == 300
    assert hard.silence_ms == 500
    assert hard.authoritative is True
    assert detector.active_turn_id is None


def test_default_turn_detector_hard_endpoint_stays_below_400ms_owner_limit() -> None:
    detector = TurnDetector()

    events = list(_decision_sequence(detector))
    hard = [event for event in events if event.kind is EndpointEventKind.HARD_ENDPOINT]

    assert len(hard) == 1
    assert hard[0].silence_ms == 360
    assert hard[0].silence_ms <= 400
    assert hard[0].authoritative is True


def test_turn_detector_resume_before_hard_cancels_speculative_endpoint() -> None:
    detector = TurnDetector(EndpointingConfig(soft_endpoint_ms=100, hard_endpoint_ms=500, min_speech_ms=40))

    events = list(_decision_sequence(detector, include_resume=True))
    kinds = [event.kind for event in events]

    assert EndpointEventKind.SOFT_ENDPOINT in kinds
    assert EndpointEventKind.SPEECH_RESUMED in kinds
    assert EndpointEventKind.HARD_ENDPOINT not in kinds
    assert detector.active_turn_id is not None


def test_transcript_assembler_replaces_revisions_and_finalizes_only_at_hard_boundary() -> None:
    assembler = TranscriptAssembler(
        call_id="call-speech",
        channel_id="call-speech:audio",
        generation=1,
        turn_id="call-speech:turn-1",
        stable_prefix_min_chars=12,
    )
    first = assembler.accept(
        AsrHypothesis(
            call_id="call-speech",
            channel_id="call-speech:audio",
            generation=1,
            revision=1,
            timestamp_ns=1,
            text="почему небо",
            turn_id="call-speech:turn-1",
        )
    )
    second = assembler.accept(
        AsrHypothesis(
            call_id="call-speech",
            channel_id="call-speech:audio",
            generation=1,
            revision=2,
            timestamp_ns=2,
            text="почему небо днем голубое",
            stable_prefix="почему небо",
            turn_id="call-speech:turn-1",
        )
    )

    assert first is not None and first.kind is TranscriptUpdateKind.PARTIAL
    assert second is not None
    assert second.stable_prefix == "почему небо"
    assert second.unstable_suffix == " днем голубое"
    assert assembler.accept(
        AsrHypothesis(
            call_id="call-speech",
            channel_id="call-speech:audio",
            generation=1,
            revision=1,
            timestamp_ns=3,
            text="почему",
            turn_id="call-speech:turn-1",
        )
    ) is None

    boundary = EndpointEvent(
        kind=EndpointEventKind.HARD_ENDPOINT,
        call_id="call-speech",
        channel_id="call-speech:audio",
        generation=1,
        turn_id="call-speech:turn-1",
        timestamp_ns=500_000_000,
        silence_ms=500,
        reason="hard_silence_threshold_reached",
        authoritative=True,
    )
    update, final_turn = assembler.finalize(boundary)

    assert update.kind is TranscriptUpdateKind.FINAL
    assert update.authoritative is True
    assert update.boundary is EndpointEventKind.HARD_ENDPOINT
    assert final_turn.text == "почему небо днем голубое"
    assert assembler.accept(
        AsrHypothesis(
            call_id="call-speech",
            channel_id="call-speech:audio",
            generation=1,
            revision=3,
            timestamp_ns=4,
            text="поздняя stale revision",
            turn_id="call-speech:turn-1",
        )
    ) is None


def test_transcript_assembler_requires_hard_boundary_and_nonempty_text() -> None:
    assembler = TranscriptAssembler("call", "channel", 1, "call:turn", stable_prefix_min_chars=0)
    assembler.accept(
        AsrHypothesis("call", "channel", 1, 1, 1, "ответ", is_final=True, turn_id="call:turn")
    )
    not_hard = EndpointEvent(
        kind=EndpointEventKind.SOFT_ENDPOINT,
        call_id="call",
        channel_id="channel",
        generation=1,
        turn_id="call:turn",
        timestamp_ns=300_000_000,
        silence_ms=300,
        reason="soft",
    )
    with pytest.raises(TranscriptContractError, match="hard_endpoint"):
        assembler.finalize(not_hard)


def test_transcript_assembler_accepts_russian_yo_e_spelling_revision() -> None:
    assembler = TranscriptAssembler("call", "channel", 1, "call:turn", stable_prefix_min_chars=0)
    assembler.accept(AsrHypothesis("call", "channel", 1, 1, 1, "Почему небо днём", turn_id="call:turn"))

    update = assembler.accept(
        AsrHypothesis(
            "call",
            "channel",
            1,
            2,
            2,
            "Почему небо днем кажется голубым",
            stable_prefix="Почему небо дн",
            turn_id="call:turn",
        )
    )

    assert update is not None
    assert update.text == "Почему небо днем кажется голубым"
    assert update.stable_prefix == "Почему небо дн"


def test_transcript_assembler_does_not_freeze_an_early_common_asr_prefix() -> None:
    assembler = TranscriptAssembler("call", "channel", 1, "call:turn", stable_prefix_min_chars=12)

    first = assembler.accept(AsrHypothesis("call", "channel", 1, 1, 1, "Почему не ободнёшься?", turn_id="call:turn"))
    second = assembler.accept(AsrHypothesis("call", "channel", 1, 2, 2, "Почему не ободнем, кажется, глупость?", turn_id="call:turn"))
    corrected = assembler.accept(AsrHypothesis("call", "channel", 1, 3, 3, "Почему небо днем кажется голубым", turn_id="call:turn"))

    assert first is not None and second is not None and corrected is not None
    assert first.stable_prefix == ""
    assert second.stable_prefix == ""
    assert corrected.stable_prefix == ""


class _FakeBackend:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def transcribe_chunk(self, chunk: AsrAudioChunk):
        self.calls.append(chunk.sequence)
        return [{"text": f"chunk-{chunk.sequence}", "is_final": False}]


def _chunk(sequence: int, generation: int = 1) -> AsrAudioChunk:
    profile = _profile()
    return AsrAudioChunk(
        call_id="call-speech",
        channel_id="call-speech:asr",
        generation=generation,
        turn_id="call-speech:turn-1",
        sequence=sequence,
        timestamp_ns=sequence * 1_000_000,
        pcm_s16le=b"\x00" * 320,
        profile=profile,
        flush_reason=FlushReason.TARGET,
    )


def test_asr_adapter_maps_backend_and_drops_old_generation_after_cancel() -> None:
    backend = _FakeBackend()
    adapter = StreamingAsrAdapter(backend)
    first = adapter.open_operation(call_id="call-speech", channel_id="call-speech:asr", generation=1)

    result = list(adapter.stream(first, [_chunk(1)]))
    assert [item.text for item in result] == ["chunk-1"]

    second = adapter.open_operation(call_id="call-speech", channel_id="call-speech:asr", generation=2)
    assert first.cancel_token.is_cancelled is True
    assert list(adapter.stream(first, [_chunk(2)])) == []
    assert [item.text for item in adapter.stream(second, [_chunk(3, generation=2)])] == ["chunk-3"]

    adapter.close()
    assert list(adapter.stream(second, [_chunk(4, generation=2)])) == []


def test_faster_whisper_boundary_resamples_negotiated_pcmu_rate_and_warmups() -> None:
    pytest.importorskip("numpy")
    observed: list[object] = []

    class FakeModel:
        def transcribe(self, samples, **_kwargs):
            observed.append(samples)
            return iter(()), None

    backend = FasterWhisperC2Backend(
        "fake-model",
        model_factory=lambda *_args, **_kwargs: FakeModel(),
    )
    list(backend.transcribe_chunk(_chunk(1)))
    report = backend.warmup(input_sample_rate_hz=8000, duration_ms=1000)

    assert observed[0].shape == (320,)  # 20 ms at the model's required 16 kHz
    assert observed[1].shape == (16000,)
    assert report["model_sample_rate_hz"] == 16000


def test_faster_whisper_partial_is_transcribed_from_growing_turn_prefix() -> None:
    pytest.importorskip("numpy")
    observed: list[object] = []

    class FakeModel:
        def transcribe(self, samples, **_kwargs):
            observed.append(samples)
            return iter(()), None

    backend = FasterWhisperC2Backend(
        "fake-model",
        model_factory=lambda *_args, **_kwargs: FakeModel(),
    )
    list(backend.transcribe_chunk(_chunk(1)))
    list(backend.transcribe_chunk(_chunk(2)))
    list(backend.transcribe_chunk(replace(_chunk(3), is_final=True)))
    list(backend.transcribe_chunk(_chunk(4)))

    assert [item.shape[0] for item in observed] == [320, 640, 960, 320]


def test_faster_whisper_preserves_segment_speech_evidence() -> None:
    pytest.importorskip("numpy")

    class FakeModel:
        def transcribe(self, _samples, **_kwargs):
            segment = SimpleNamespace(
                text=" Продолжение следует... ",
                no_speech_prob=0.91,
                avg_logprob=-0.2,
                compression_ratio=1.1,
                start=0.0,
                end=29.98,
            )
            return iter((segment,)), None

    backend = FasterWhisperC2Backend(
        "fake-model",
        no_speech_threshold=0.60,
        segment_end_tolerance_ms=500.0,
        model_factory=lambda *_args, **_kwargs: FakeModel(),
    )
    adapter = StreamingAsrAdapter(backend)
    operation = adapter.open_operation(
        call_id="call-speech",
        channel_id="call-speech:asr",
        generation=1,
    )

    result = list(adapter.stream(operation, [replace(_chunk(1), is_final=True)]))

    assert len(result) == 1
    assert result[0].speech_supported is False
    assert result[0].evidence is not None
    assert result[0].evidence.no_speech_probability == pytest.approx(0.91)
    assert result[0].evidence.max_segment_end_ms == pytest.approx(29_980.0)
    assert result[0].evidence.reason == "no_speech_probability"
    assert result[0].evidence.segment_timeline_valid is False


def test_rejected_final_discards_matching_turn_and_next_turn_remains_usable() -> None:
    def assembler(turn_id: str) -> TranscriptAssembler:
        return TranscriptAssembler(
            "call-speech",
            "call-speech:audio",
            1,
            turn_id,
            stable_prefix_min_chars=0,
        )

    ingress = SpeechIngress(
        vad=_speech_processor(),
        turn_detector=TurnDetector(
            EndpointingConfig(soft_endpoint_ms=40, hard_endpoint_ms=60, min_speech_ms=40)
        ),
        assembler=assembler("call-speech:turn-1"),
        assembler_factory=assembler,
        defer_endpoint_finalization=True,
    )
    sequence = 1
    for speech in (True, True, False, False, False, False):
        ingress.process_frame(_frame(sequence, speech=speech, timestamp_ms=(sequence - 1) * 20))
        sequence += 1
    ingress.accept_hypothesis(
        AsrHypothesis(
            "call-speech",
            "call-speech:audio",
            1,
            1,
            100_000_000,
            "ложный partial",
            turn_id="call-speech:turn-1",
        )
    )
    rejected = AsrHypothesis(
        "call-speech",
        "call-speech:audio",
        1,
        2,
        120_000_000,
        "Продолжение следует...",
        is_final=True,
        turn_id="call-speech:turn-1",
        evidence=AsrSpeechEvidence(
            AsrSpeechDecision.NO_SPEECH,
            0.91,
            -0.2,
            1.1,
            440.0,
            29_980.0,
            "no_speech_probability",
        ),
    )

    assert ingress.accept_hypothesis(rejected) is None
    assert ingress.take_final_turn() is None
    assert ingress.rejected_turns == 1

    for speech in (True, True, False, False, False, False):
        ingress.process_frame(_frame(sequence, speech=speech, timestamp_ms=(sequence - 1) * 20))
        sequence += 1
    accepted = AsrHypothesis(
        "call-speech",
        "call-speech:audio",
        1,
        3,
        sequence * 20_000_000,
        "настоящий вопрос",
        is_final=True,
        turn_id="call-speech:turn-2",
        evidence=AsrSpeechEvidence(
            AsrSpeechDecision.SPEECH,
            0.01,
            -0.1,
            1.0,
            800.0,
            780.0,
            "speech_supported",
        ),
    )

    assert ingress.accept_hypothesis(accepted) is not None
    final_turn = ingress.take_final_turn()
    assert final_turn is not None
    assert final_turn.turn_id == "call-speech:turn-2"
    assert final_turn.text == "настоящий вопрос"


def test_composed_ingress_emits_final_user_turn_at_hard_endpoint() -> None:
    detector = TurnDetector(EndpointingConfig(soft_endpoint_ms=100, hard_endpoint_ms=200, min_speech_ms=40))
    assembler = TranscriptAssembler("call-speech", "call-speech:audio", 1, "call-speech:turn-1", 0)
    ingress = SpeechIngress(vad=_speech_processor(), turn_detector=detector, assembler=assembler)

    for sequence, timestamp_ms in enumerate((0, 20), start=1):
        ingress.process_frame(_frame(sequence, speech=True, timestamp_ms=timestamp_ms))
    partial = ingress.accept_hypothesis(
        AsrHypothesis(
            "call-speech", "call-speech:audio", 1, 1, 50_000_000,
            "ответ пользователю", turn_id="call-speech:turn-1"
        )
    )
    assert partial is not None

    final_result = None
    for sequence, timestamp_ms in enumerate(range(40, 240, 20), start=3):
        final_result = ingress.process_frame(_frame(sequence, speech=False, timestamp_ms=timestamp_ms))
        if final_result.final_turn is not None:
            break

    assert final_result is not None
    assert final_result.final_turn is not None
    assert final_result.final_turn.text == "ответ пользователю"
    assert final_result.transcript_update is not None
    assert final_result.transcript_update.authoritative is True
