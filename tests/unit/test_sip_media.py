"""Deterministic SIP/media boundary and callback contract tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sip_bot.config import RuntimeConfig
from sip_bot.sip_media.adapter import AdapterState, SipMediaAdapter, SipMediaConfig
from sip_bot.sip_media.media_port import PcmAudioBridge, PcmFrameQueue
from sip_bot.sip_media.models import MediaNegotiationError, NegotiatedMediaProfile, PcmFrame
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind, SipMethod, protocol_reply_for


class _FakeVector:
    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload

    def size(self) -> int:
        return len(self.payload)

    def copy_to_bytearray(self, target: bytearray) -> None:
        target[:] = self.payload

    def assign_from_bytes(self, payload: bytes) -> None:
        self.payload = bytes(payload)


class _FakeFrame:
    def __init__(self, payload: bytes = b"", capacity: int | None = None, frame_type: int = 1) -> None:
        self.buf = _FakeVector(payload)
        self.size = len(payload) if capacity is None else capacity
        self.type = frame_type


class _FakeAudioMediaPort:
    def __init__(self) -> None:
        self.format = None

    def createPort(self, _name: str, fmt: object) -> None:
        self.format = fmt

    def startTransmit(self, _sink: object) -> None:
        return None

    def stopTransmit(self, _sink: object) -> None:
        return None


class _FakeCall:
    def __init__(self, _account: object, _call_id: int) -> None:
        return None


class _FakeAccount:
    pass


class _FakePjsua:
    AudioMediaPort = _FakeAudioMediaPort
    MediaFormatAudio = type("MediaFormatAudio", (), {})
    Call = _FakeCall
    Account = _FakeAccount
    AudioMediaPort = _FakeAudioMediaPort
    MediaFormatAudio = type("MediaFormatAudio", (), {})
    PJMEDIA_TYPE_AUDIO = 1
    PJMEDIA_FRAME_TYPE_NONE = 0
    PJMEDIA_FRAME_TYPE_AUDIO = 1
    PJMEDIA_DIR_ENCODING = 1
    PJMEDIA_DIR_ENCODING_DECODING = 3


def _profile(ptime_ms: float = 30.0) -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        ptime_ms=ptime_ms,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=int(8000 * ptime_ms / 1000),
        source="test.pjmedia",
    )


def _frame(profile: NegotiatedMediaProfile, sequence: int = 1, byte: int = 1) -> PcmFrame:
    return PcmFrame(
        call_id="call-test",
        channel_id="call-test:media",
        generation=1,
        sequence=sequence,
        timestamp_ns=sequence,
        pcm_s16le=bytes([byte]) * profile.frame_bytes,
        profile=profile,
    )


def test_runtime_registration_profile_is_forwarded_without_changing_media_defaults() -> None:
    runtime_config = RuntimeConfig.from_constants()
    sip_config = SipMediaConfig.from_runtime_config(runtime_config)

    assert sip_config.registration_profile is runtime_config.registration_profile
    assert sip_config.registration_profile.enabled is True
    assert sip_config.registration_profile.username == "1002"
    assert sip_config.local_uri == "sip:tester@127.0.0.1"
    assert sip_config.media_no_vad is True
    assert sip_config.comfort_noise_level_dbov_magnitude == 50


def test_profile_comes_from_pjmedia_without_a_global_ptime() -> None:
    stream = SimpleNamespace(
        codecName="PCMU",
        codecClockRate=8000,
        rxPt=0,
        txPt=0,
        audCodecParam=SimpleNamespace(
            info=SimpleNamespace(frameLen=30, frameLenDenum=0, channelCnt=1, pcmBitsPerSample=16)
        ),
    )
    port_format = SimpleNamespace(clockRate=8000, channelCount=1, bitsPerSample=16, frameTimeUsec=30000)

    profile = NegotiatedMediaProfile.from_stream_info(stream, port_format=port_format)

    assert profile.ptime_ms == 30
    assert profile.frame_size_samples == 240
    assert profile.frame_bytes == 480
    assert profile.source == "pjmedia.stream_info"


def test_non_pcmu_negotiation_is_a_hard_slice_failure() -> None:
    stream = SimpleNamespace(
        codecName="PCMA",
        codecClockRate=8000,
        rxPt=8,
        txPt=8,
        audCodecParam=SimpleNamespace(info=SimpleNamespace(frameLen=20, frameLenDenum=0)),
    )

    with pytest.raises(MediaNegotiationError, match="not PCMU"):
        NegotiatedMediaProfile.from_stream_info(stream)


def test_from_call_requires_and_reuses_the_explicit_media_index() -> None:
    stream = SimpleNamespace(
        codecName="PCMU",
        codecClockRate=8000,
        rxPt=0,
        txPt=0,
        audCodecParam=SimpleNamespace(
            info=SimpleNamespace(frameLen=20, frameLenDenum=0, channelCnt=1, pcmBitsPerSample=16)
        ),
    )
    port_format = SimpleNamespace(clockRate=8000, channelCount=1, bitsPerSample=16, frameTimeUsec=20000)

    class RecordingCall:
        def __init__(self) -> None:
            self.stream_indices: list[int] = []
            self.audio_indices: list[int] = []

        def getStreamInfo(self, media_index: int) -> object:
            self.stream_indices.append(media_index)
            return stream

        def getAudioMedia(self, media_index: int) -> object:
            self.audio_indices.append(media_index)
            return SimpleNamespace(getPortInfo=lambda: SimpleNamespace(format=port_format))

    call = RecordingCall()
    profile = NegotiatedMediaProfile.from_call(call, 1)

    assert profile.codec == "PCMU"
    assert call.stream_indices == [1]
    assert call.audio_indices == [1]

    with pytest.raises(MediaNegotiationError, match="non-negative"):
        NegotiatedMediaProfile.from_call(call, -1)


def test_active_audio_media_selection_preserves_pjsua_media_index() -> None:
    adapter = SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:tester@127.0.0.1",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=2,
            output_capacity_frames=2,
            event_capacity=8,
            require_free_threaded=False,
        ),
        pjsua2_module=_FakePjsua,
        enforce_runtime=False,
    )

    inactive_video = SimpleNamespace(index=0, type=2, status=1)
    active_audio = SimpleNamespace(index=1, type=_FakePjsua.PJMEDIA_TYPE_AUDIO, status=1, dir=3)

    selected = adapter._select_active_audio_media([inactive_video, active_audio])

    assert selected == (1, active_audio)


def test_media_started_event_exposes_authoritative_media_index() -> None:
    event = NormalizedSipEvent(
        kind=SipEventKind.MEDIA_STARTED,
        call_id="call-test",
        sequence=1,
        timestamp_ns=99,
        media_profile=_profile(),
        details=(("direction", 3), ("media_index", 1)),
    )

    assert dict(event.details)["media_index"] == 1


def test_media_port_handoff_is_bounded_and_close_drops_stale_frames() -> None:
    profile = _profile()
    bridge = PcmAudioBridge(
        pjsua2_module=_FakePjsua,
        call_id="call-test",
        channel_id="call-test:media",
        generation=1,
        profile=profile,
        capacity_frames=1,
        clock_ns=lambda: 99,
    )

    inbound = _FakeFrame(bytes(profile.frame_bytes))
    bridge.port.onFrameReceived(inbound)
    assert bridge.stats.ingress_frames == 1
    assert bridge.next_ingress().pcm_s16le == bytes(profile.frame_bytes)  # type: ignore[union-attr]

    bridge.port.onFrameReceived(_FakeFrame(b"\x00", frame_type=_FakePjsua.PJMEDIA_FRAME_TYPE_NONE))
    assert bridge.stats.callback_errors == 0
    assert bridge.stats.ingress_frames == 1

    outbound = _frame(profile)
    assert bridge.enqueue(outbound) is True
    requested = _FakeFrame(capacity=profile.frame_bytes)
    bridge.port.onFrameRequested(requested)
    assert requested.buf.payload == outbound.pcm_s16le
    assert bridge.stats.egress_frames == 1

    assert bridge.close() is True
    assert bridge.close() is False
    assert bridge.enqueue(_frame(profile, sequence=2)) is False
    stale = _FakeFrame(bytes(profile.frame_bytes))
    bridge.port.onFrameReceived(stale)
    assert bridge.stats.ingress_dropped_closed == 1

    released_port = bridge.release_port()
    assert released_port is not None
    assert bridge.port is None
    assert bridge.release_port() is None


def test_local_protocol_reply_table_covers_all_required_edges() -> None:
    expected = {
        "BYE": "terminate_call",
        "CANCEL": "cancel_pending_invite",
        "OPTIONS": "automatic_endpoint_reply",
        "INVITE": "accept_media_offer",
        "UPDATE": "accept_media_update",
        "RTP": "close_media",
        "TRANSPORT": "close_call",
    }
    assert {method: protocol_reply_for(method).action for method in expected} == expected
    assert all(protocol_reply_for(method).automatic for method in expected)


def test_reinvite_callback_sets_local_reply_before_any_explicit_dispatch() -> None:
    adapter = SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:tester@127.0.0.1",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=2,
            output_capacity_frames=2,
            event_capacity=8,
            require_free_threaded=False,
        ),
        pjsua2_module=_FakePjsua,
        enforce_runtime=False,
    )
    adapter._state = AdapterState.RUNNING  # narrow callback contract fixture
    adapter._install_callback_classes(_FakePjsua)
    callback = adapter._call_class(object(), -1, adapter)  # type: ignore[misc]
    adapter._call = SimpleNamespace(call_id="call-test", call=callback, closed=False, last_protocol_method=None)
    prm = SimpleNamespace(statusCode=0, isAsync=True)

    callback.onCallRxReinvite(prm)

    event = adapter.drain_events()[0]
    assert prm.statusCode == 200
    assert prm.isAsync is False
    assert event.kind is SipEventKind.PROTOCOL_REPLY
    assert event.method is SipMethod.INVITE
    assert event.local_reply is not None
    assert event.local_reply.status_code == 200


def test_update_offer_and_media_failure_are_local_and_non_blocking() -> None:
    class Sink:
        def publish(self, _event: object) -> None:
            raise AssertionError("native callback must not call the event sink")

    adapter = SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:tester@127.0.0.1",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=2,
            output_capacity_frames=2,
            event_capacity=8,
            require_free_threaded=False,
        ),
        pjsua2_module=_FakePjsua,
        enforce_runtime=False,
        event_sink=Sink(),
    )
    adapter._state = AdapterState.RUNNING
    adapter._install_callback_classes(_FakePjsua)
    callback = adapter._call_class(object(), -1, adapter)  # type: ignore[misc]
    adapter._call = SimpleNamespace(
        call_id="call-test",
        call=callback,
        closed=False,
        last_protocol_method=SipMethod.UPDATE,
        bridge=None,
        media_started=False,
    )
    offer = SimpleNamespace(statusCode=0)

    callback.onCallRxOffer(offer)
    adapter._on_bridge_failure("call-test", "transport_failure")

    events = adapter.drain_events()
    assert offer.statusCode == 200
    assert events[0].kind is SipEventKind.PROTOCOL_REPLY
    assert events[0].method is SipMethod.UPDATE
    assert events[1].kind is SipEventKind.PROTOCOL_REPLY
    assert events[1].method is SipMethod.TRANSPORT
    assert events[2].kind is SipEventKind.MEDIA_FAILED
    assert events[2].method is SipMethod.TRANSPORT
