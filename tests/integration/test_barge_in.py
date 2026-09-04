"""Deterministic barge-in integration at the TTS/playback boundary.

Real RTP/PCMU smoke remains a main-executor gate in the 001-S stand.
"""

from __future__ import annotations

from sip_bot.playback import PlaybackChannel, PlaybackEventKind
from sip_bot.sip_media.models import NegotiatedMediaProfile
from sip_bot.tts import MediaPacer, TtsOutputBuffer, TtsPcmChunk


def test_barge_in_closes_playback_and_suppresses_old_generation_audio() -> None:
    profile = NegotiatedMediaProfile("PCMU", 0, 20.0, 8000, 1, 160, rx_payload_type=0, tx_payload_type=0)
    output = TtsOutputBuffer(profile=profile, call_id="call-1", channel_id="call-1:playback", generation=1)
    output.push(TtsPcmChunk("tts-1", "call-1", "call-1:playback", 1, 1, b"\x01\x00" * 160, profile))
    output.push(TtsPcmChunk("tts-1", "call-1", "call-1:playback", 1, 2, b"\x02\x00" * 160, profile))
    sent = []
    cancelled = []
    channel = PlaybackChannel(
        call_id="call-1", channel_id="call-1:playback", generation=1,
        pacer=MediaPacer(output), send_frame=sent.append, cancel_producer=cancelled.append,
    )
    channel.open()
    assert channel.pump(0) is not None
    assert len(sent) == 1
    assert channel.barge_in() is True
    assert channel.close() is False
    assert cancelled == ["barge_in"]
    assert channel.pump(20_000_000) is None
    assert len(sent) == 1
    assert any(event.kind is PlaybackEventKind.CANCELLED for event in channel.events)

    # A late producer result from the old generation is rejected at the
    # output boundary before it can reach the direct egress.
    assert output.push(TtsPcmChunk("tts-1", "call-1", "call-1:playback", 1, 3, b"\x03\x00" * 160, profile)) is False
