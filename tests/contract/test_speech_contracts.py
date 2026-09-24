"""Contract-level checks for speech boundary lifecycle and ownership."""

from __future__ import annotations

import pytest

from sip_bot.media import AsrAudioChunk, FlushReason, NegotiatedMediaProfile
from sip_bot.speech import (
    AsrHypothesis,
    AsrSpeechDecision,
    AsrSpeechEvidence,
    EndpointEvent,
    EndpointEventKind,
    FinalUserTurn,
    TranscriptUpdate,
    TranscriptUpdateKind,
    VadDecision,
)


def test_contract_values_carry_call_channel_generation_scope() -> None:
    decision = VadDecision("call-1", "channel-1", 3, 1, 10, 20, True)
    profile = NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        ptime_ms=20.0,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=160,
    )
    chunk = AsrAudioChunk(
        "call-1",
        "channel-1",
        3,
        "call-1:turn-1",
        1,
        10,
        b"\x00" * 320,
        profile,
        FlushReason.TARGET,
    )
    hypothesis = AsrHypothesis("call-1", "channel-1", 3, 1, 10, "текст", turn_id="call-1:turn-1")

    assert (decision.call_id, decision.channel_id, decision.generation) == ("call-1", "channel-1", 3)
    assert (chunk.call_id, chunk.channel_id, chunk.generation) == ("call-1", "channel-1", 3)
    assert (hypothesis.call_id, hypothesis.channel_id, hypothesis.generation) == ("call-1", "channel-1", 3)
    assert chunk.turn_id == hypothesis.turn_id == "call-1:turn-1"


def test_hard_endpoint_is_the_only_authoritative_boundary() -> None:
    hard = EndpointEvent(
        EndpointEventKind.HARD_ENDPOINT,
        "call-1",
        "channel-1",
        1,
        "call-1:turn-1",
        500_000_000,
        500,
        "hard silence",
        authoritative=True,
    )
    candidate_final = TranscriptUpdate(
        TranscriptUpdateKind.FINAL,
        "call-1",
        "channel-1",
        1,
        2,
        400_000_000,
        "текст",
        "текст",
        "",
        authoritative=False,
    )

    assert hard.authoritative is True
    assert candidate_final.authoritative is False
    assert candidate_final.boundary is None


def test_authoritative_final_user_turn_requires_hard_endpoint() -> None:
    with pytest.raises(ValueError, match="hard_endpoint"):
        FinalUserTurn(
            call_id="call-1",
            channel_id="channel-1",
            generation=1,
            turn_id="call-1:turn-1",
            text="текст",
            revision=1,
            finalized_at_ns=10,
            boundary=EndpointEventKind.SOFT_ENDPOINT,
        )


def test_asr_speech_evidence_is_typed_and_validated() -> None:
    evidence = AsrSpeechEvidence(
        decision=AsrSpeechDecision.NO_SPEECH,
        no_speech_probability=0.91,
        average_log_probability=-0.2,
        compression_ratio=1.1,
        input_duration_ms=440.0,
        max_segment_end_ms=29_980.0,
        reason="no_speech_probability",
    )
    hypothesis = AsrHypothesis(
        "call-1",
        "channel-1",
        1,
        1,
        10,
        "Продолжение следует...",
        is_final=True,
        turn_id="call-1:turn-1",
        evidence=evidence,
    )

    assert hypothesis.speech_supported is False
    assert evidence.timeline_overrun_ms == pytest.approx(29_540.0)

    with pytest.raises(ValueError, match="no_speech_probability"):
        AsrSpeechEvidence(
            AsrSpeechDecision.SPEECH,
            1.1,
            None,
            None,
            100.0,
            100.0,
            "speech_supported",
        )
