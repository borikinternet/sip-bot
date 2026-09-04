"""002-E control bus contract fixtures."""

from dataclasses import dataclass
from queue import Empty

import pytest

from sip_bot.control import (
    CallOpen,
    ControlEvent,
    ControlEventBus,
    ControlEventKind,
    ControlPayloadError,
    Dispatcher,
    SubscriptionClosedError,
)
from sip_bot.dialogue import DialogueFSM, DialogueState


def _event(sequence: int = 1) -> ControlEvent:
    return ControlEvent(ControlEventKind.CALL_OPEN, "call-002-e", sequence, sequence, CallOpen("call-002-e"))


def test_bus_fans_out_in_order_and_does_not_block_on_full_subscription() -> None:
    bus = ControlEventBus(capacity=1)
    first = bus.subscribe(call_id="call-002-e")
    second = bus.subscribe(call_id="call-002-e", capacity=2)

    assert bus.publish(_event(1)).delivered == 2
    report = bus.publish(_event(2))
    assert report.delivered == 1
    assert report.dropped == 1
    assert first.get_nowait().sequence == 1
    assert second.drain() == [_event(1), _event(2)]
    assert bus.dropped_count == 1
    with pytest.raises(Empty):
        first.get_nowait()


def test_close_unsubscribe_is_bounded_and_clears_pending_terminal_events() -> None:
    bus = ControlEventBus()
    subscription = bus.subscribe(call_id="call-002-e")
    bus.publish(_event())
    assert bus.unsubscribe(subscription)
    assert bus.subscription_count == 0
    with pytest.raises(SubscriptionClosedError):
        subscription.get_nowait()
    assert not bus.unsubscribe(subscription)


def test_bus_rejects_binary_or_oversized_control_payload() -> None:
    bus = ControlEventBus(text_limit=8)
    bus.subscribe()
    with pytest.raises(ControlPayloadError, match="binary"):
        bus.publish(b"pcm")
    with pytest.raises(ControlPayloadError, match="text"):
        bus.publish("this is not a typed control event")


def test_bus_rejects_binary_nested_in_typed_event() -> None:
    @dataclass(frozen=True)
    class BinaryEvent:
        payload: bytes

    bus = ControlEventBus()
    bus.subscribe()
    with pytest.raises(ControlPayloadError, match="binary"):
        bus.publish(BinaryEvent(b"pcm"))


def test_dispatcher_enqueue_and_process_are_non_blocking_and_serialized() -> None:
    received: list[object] = []

    class Handler:
        def handle(self, event: object) -> None:
            received.append(event)

    dispatcher = Dispatcher(Handler(), capacity=1)
    assert dispatcher.submit(_event())
    assert dispatcher.process_one()
    assert received == [_event()]
    assert dispatcher.drain() == 0


def test_dispatcher_pumps_typed_bus_events_into_the_fsm() -> None:
    bus = ControlEventBus()
    fsm = DialogueFSM()
    dispatcher = Dispatcher(fsm, bus=bus)
    dispatcher.attach(call_id="call-002-e")
    bus.publish(_event())
    assert dispatcher.pump() == 1
    assert dispatcher.drain() == 1
    assert fsm.state is DialogueState.CALL_OPEN
