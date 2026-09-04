"""Contract tests for TTS/playback typed boundaries."""

from __future__ import annotations

import pytest

from sip_bot.playback import PlaybackCloseReason, PlaybackCommand, PlaybackEvent, PlaybackEventKind
from sip_bot.tts import TtsPcmChunk, TtsStatus, TtsStatusKind
from sip_bot.sip_media.models import NegotiatedMediaProfile


def profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile("PCMU", 0, 20.0, 8000, 1, 160, rx_payload_type=0, tx_payload_type=0)


def test_playback_contracts_are_typed_and_validate_lifecycle() -> None:
    command = PlaybackCommand("call-1", "call-1:playback", 1, "barge_in", "speech_detected")
    event = PlaybackEvent("call-1", "call-1:playback", 1, PlaybackEventKind.CANCELLED, 10, "barge_in")
    status = TtsStatus("tts-1", "call-1", 1, TtsStatusKind.COMPLETED, 20)
    assert command.action == "barge_in"
    assert event.kind is PlaybackEventKind.CANCELLED
    assert status.kind is TtsStatusKind.COMPLETED
    assert PlaybackCloseReason.BARGE_IN.value == "barge_in"

    with pytest.raises(ValueError):
        PlaybackCommand("call-1", "call-1:playback", 1, "hangup")
    with pytest.raises(ValueError):
        TtsPcmChunk("tts-1", "call-1", "call-1:tts", 1, 1, b"\x00", profile())
