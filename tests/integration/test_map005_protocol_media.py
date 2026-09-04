"""Map-005-A deterministic SIP/media protocol and failure matrix.

The tests exercise the existing ``SipMediaAdapter`` owner with a small
PJSUA2-shaped stub.  They intentionally prove callback-local protocol
reactions and queued observations without requiring a live peer or AI work.
Live SIP/RTP evidence is produced by ``tools/map005_protocol_probe.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sip_bot.sip_media.adapter import AdapterState, SipMediaAdapter, SipMediaConfig
from sip_bot.sip_media.protocol_events import (
    SipEventKind,
    SipMethod,
    protocol_reply_for,
)


class _FakeCall:
    def __init__(self, _account: object, _call_id: int) -> None:
        pass


class _FakeAccount:
    pass


class _FakePjsua:
    Call = _FakeCall
    Account = _FakeAccount
    PJSUA_CALL_MEDIA_ACTIVE = 1
    PJSUA_CALL_MEDIA_LOCAL_HOLD = 2
    PJSUA_CALL_MEDIA_REMOTE_HOLD = 3
    PJMEDIA_TYPE_AUDIO = 1
    PJMEDIA_DIR_ENCODING = 1
    PJMEDIA_DIR_ENCODING_DECODING = 3


def _adapter() -> SipMediaAdapter:
    return SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:tester@127.0.0.1",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=4,
            output_capacity_frames=4,
            event_capacity=32,
            require_free_threaded=False,
        ),
        pjsua2_module=_FakePjsua,
        enforce_runtime=False,
    )


def _callback_with_context(adapter: SipMediaAdapter, *, answered: bool = True):
    adapter._state = AdapterState.RUNNING
    adapter._install_callback_classes(_FakePjsua)
    callback = adapter._call_class(object(), -1, adapter)  # type: ignore[misc]
    adapter._call = SimpleNamespace(
        call_id="call-map005-a",
        call=callback,
        peer_uri="sip:peer@127.0.0.1:5080",
        direction="outgoing",
        channel_id="call-map005-a:media",
        generation=1,
        closed=False,
        close_requested=False,
        answered=answered,
        media_started=False,
        bridge=None,
        profile=None,
        media_index=None,
        last_media_direction=None,
        last_protocol_method=None,
    )
    return callback


def test_supported_protocol_edges_have_immediate_local_replies() -> None:
    expected = {
        SipMethod.BYE: "terminate_call",
        SipMethod.CANCEL: "cancel_pending_invite",
        SipMethod.OPTIONS: "automatic_endpoint_reply",
        SipMethod.INVITE: "accept_media_offer",
        SipMethod.UPDATE: "accept_media_update",
        SipMethod.RTP: "close_media",
        SipMethod.TRANSPORT: "close_call",
    }

    assert {method: protocol_reply_for(method).action for method in expected} == expected
    assert all(protocol_reply_for(method).automatic for method in expected)
    with pytest.raises(ValueError, match="unsupported SIP protocol edge"):
        protocol_reply_for("NOT-A-SIP-METHOD")


def test_reinvite_and_offer_callbacks_reply_before_queued_observation() -> None:
    adapter = _adapter()
    callback = _callback_with_context(adapter)

    reinvite = SimpleNamespace(statusCode=0, isAsync=True)
    callback.onCallRxReinvite(reinvite)
    assert (reinvite.statusCode, reinvite.isAsync) == (200, False)

    offer = SimpleNamespace(statusCode=0)
    adapter._call.last_protocol_method = SipMethod.UPDATE
    callback.onCallRxOffer(offer)
    assert offer.statusCode == 200

    events = adapter.drain_events()
    assert [event.kind for event in events] == [
        SipEventKind.PROTOCOL_REPLY,
        SipEventKind.PROTOCOL_REPLY,
    ]
    assert [event.method for event in events] == [SipMethod.INVITE, SipMethod.UPDATE]
    assert all(event.local_reply is not None and event.local_reply.status_code == 200 for event in events)


def test_transport_failure_reacts_locally_and_only_then_exposes_control_event() -> None:
    published: list[object] = []
    adapter = _adapter()
    adapter.event_sink = published.append
    callback = _callback_with_context(adapter)

    callback.onCallMediaTransportState(
        SimpleNamespace(status=1, sipErrorCode=503, medIdx=0, state="FAILED")
    )

    assert published == []
    events = adapter.drain_events()
    assert [event.kind for event in events] == [
        SipEventKind.PROTOCOL_REPLY,
        SipEventKind.MEDIA_FAILED,
    ]
    assert events[0].method is SipMethod.TRANSPORT
    assert events[0].local_reply is not None
    assert events[1].method is SipMethod.TRANSPORT
    assert events[1].status_code == 503
    assert events[1].details_dict()["media_index"] == 0


def test_remote_disconnect_does_not_wait_for_dispatcher_and_repeated_callback_is_ignored() -> None:
    adapter = _adapter()
    callback = _callback_with_context(adapter)
    callback.getInfo = lambda: SimpleNamespace(
        stateText="DISCONNECTED",
        lastStatusCode=200,
        lastReason="OK",
        id=7,
    )

    adapter._on_call_state(callback, SimpleNamespace())
    first_events = adapter.drain_events()

    assert [event.kind for event in first_events] == [SipEventKind.REMOTE_HANGUP]
    assert first_events[0].method is SipMethod.BYE
    assert adapter.active_call_id is None
    assert adapter._call.closed is True

    adapter._on_call_state(callback, SimpleNamespace())
    assert adapter.drain_events() == ()
    assert adapter.close("remote-bye-after-cleanup") is True
    assert adapter.close("remote-bye-after-cleanup-again") is False


def test_unanswered_disconnect_is_normalized_as_remote_cancel() -> None:
    adapter = _adapter()
    callback = _callback_with_context(adapter, answered=False)
    callback.getInfo = lambda: SimpleNamespace(
        stateText="DISCONNECTED",
        lastStatusCode=487,
        lastReason="Request Terminated",
        id=8,
    )

    adapter._on_call_state(callback, SimpleNamespace())
    event = adapter.drain_events()[0]

    assert event.kind is SipEventKind.REMOTE_CANCEL
    assert event.method is SipMethod.CANCEL
    assert event.status_code == 487
    assert adapter.active_call_id is None
