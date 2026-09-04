"""002-I.0 CallSession composition and control-boundary contracts."""

from dataclasses import dataclass, field

import pytest

from sip_bot.control import (
    CallOpen,
    ControlEvent,
    ControlEventKind,
    Dispatcher,
    LifecycleError,
)
from sip_bot.dialogue import DialogueFSM, FinalUserTurn
from sip_bot.speech import EndpointEventKind
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind


def _call_open(call_id: str, sequence: int = 1) -> ControlEvent:
    return ControlEvent(
        ControlEventKind.CALL_OPEN,
        call_id,
        sequence,
        sequence,
        CallOpen(call_id),
    )


@dataclass
class ClosingComponent:
    reasons: list[str] = field(default_factory=list)

    def close(self, reason: str) -> None:
        self.reasons.append(reason)


def test_dispatcher_composes_existing_fsm_without_creating_another_dispatcher_or_fsm() -> None:
    fsm = DialogueFSM()
    dispatcher = Dispatcher(fsm)

    session = dispatcher.open_session("call-i0", components=())

    assert session is not dispatcher
    assert session.fsm is fsm
    assert dispatcher.active_session is session
    assert session.call_id == "call-i0"
    assert session.generation == 1
    assert fsm.channels.scopes[session.call_id] is session.scope


def test_dispatcher_accepts_one_active_session_and_rejects_concurrent_reentry() -> None:
    dispatcher = Dispatcher(DialogueFSM())
    first = dispatcher.open_session("call-first")

    with pytest.raises(LifecycleError, match="one active call"):
        dispatcher.open_session("call-second")
    with pytest.raises(LifecycleError, match="one active call"):
        dispatcher.open_session("call-first")

    assert first.close("remote_hangup") is True
    assert first.close("remote_hangup_again") is False
    assert dispatcher.active_session is None

    second = dispatcher.open_session("call-second")
    assert second.generation == 2
    assert second.close("normal") is True
    with pytest.raises(LifecycleError, match="cannot be reused"):
        dispatcher.open_session("call-first")


def test_call_open_control_event_creates_session_and_duplicate_is_idempotently_ignored() -> None:
    fsm = DialogueFSM()
    dispatcher = Dispatcher(fsm)

    assert dispatcher.submit(_call_open("call-control")) is True
    assert dispatcher.process_one() is True
    session = dispatcher.active_session
    assert session is not None
    assert session.fsm is fsm

    assert dispatcher.submit(_call_open("call-control", sequence=2)) is True
    assert dispatcher.process_one() is True
    assert dispatcher.active_session is session


def test_dispatcher_routes_typed_sip_control_events_through_existing_session() -> None:
    fsm = DialogueFSM()
    dispatcher = Dispatcher(fsm)

    assert dispatcher.submit(
        NormalizedSipEvent("call-sip-control", SipEventKind.CALL_STARTED, timestamp_ns=1, sequence=1)
    ) is True
    assert dispatcher.process_one() is True
    assert dispatcher.active_session is not None

    assert dispatcher.submit(
        NormalizedSipEvent("call-sip-control", SipEventKind.CALL_ANSWERED, timestamp_ns=2, sequence=2)
    ) is True
    assert dispatcher.process_one() is True
    assert fsm.state.value == "listening"


def test_dispatcher_closes_session_after_typed_terminal_sip_event() -> None:
    fsm = DialogueFSM()
    dispatcher = Dispatcher(fsm)
    dispatcher.submit(_call_open("call-sip-terminal"))
    dispatcher.process_one()

    dispatcher.submit(
        NormalizedSipEvent(
            "call-sip-terminal",
            SipEventKind.REMOTE_HANGUP,
            timestamp_ns=2,
            sequence=2,
            reason="remote_bye",
        )
    )
    assert dispatcher.process_one() is True
    assert dispatcher.active_session is None


def test_session_close_is_idempotent_cancels_scope_and_closes_component_hooks_once() -> None:
    component = ClosingComponent()
    dispatcher = Dispatcher(DialogueFSM())
    session = dispatcher.open_session("call-close", components=(component,))

    assert session.cancel_token.is_cancelled is False
    assert session.close("normal") is True
    assert session.cancel_token.is_cancelled is True
    assert session.close("normal_again") is False
    assert component.reasons == ["normal"]


def test_session_lease_generation_rejects_stale_direct_data_after_close_and_reentry() -> None:
    dispatcher = Dispatcher(DialogueFSM())
    old = dispatcher.open_session("call-old")
    old_lease = old.lease()

    assert old.accepts(old_lease) is True
    old.close("media_failed")
    assert old.accepts(old_lease) is False

    current = dispatcher.open_session("call-current")
    assert current.generation > old.generation
    assert current.accepts(old_lease) is False
    assert current.accepts(current.lease()) is True


def test_call_session_control_route_rejects_data_plane_payload() -> None:
    dispatcher = Dispatcher(DialogueFSM())
    session = dispatcher.open_session("call-boundary")
    turn = FinalUserTurn(
        call_id="call-boundary",
        channel_id="audio",
        generation=1,
        turn_id="turn-1",
        text="вопрос",
        revision=1,
        finalized_at_ns=1,
        boundary=EndpointEventKind.HARD_ENDPOINT,
    )

    with pytest.raises(TypeError, match="typed control messages only"):
        session.dispatch_control(turn)  # type: ignore[arg-type]

    assert dispatcher.submit(turn) is False


def test_terminal_control_closes_session_and_old_events_are_dropped() -> None:
    fsm = DialogueFSM()
    dispatcher = Dispatcher(fsm)
    dispatcher.submit(_call_open("call-terminal"))
    dispatcher.process_one()
    session = dispatcher.active_session
    assert session is not None

    from sip_bot.control import CallClose, ControlEvent

    terminal = ControlEvent(
        ControlEventKind.CALL_CLOSE,
        "call-terminal",
        2,
        2,
        CallClose("call-terminal", "remote_hangup", already_closed=False),
    )
    dispatcher.submit(terminal)
    assert dispatcher.process_one() is True
    assert dispatcher.active_session is None

    # A queued result from the closed scope cannot reach the old FSM.
    dispatcher.submit(_call_open("call-terminal", sequence=3))
    assert dispatcher.process_one() is True
    assert dispatcher.active_session is None
