"""Deterministic call/channel lifecycle tests."""

from dataclasses import dataclass, field

import pytest

from sip_bot.config import RuntimeConfig
from sip_bot.control import (
    CallClose,
    ChannelClose,
    ChannelOpen,
    ControlEvent,
    ControlEventKind,
    LifecycleError,
)
from sip_bot.runtime import RuntimeCoordinator, RuntimeProbe


@dataclass
class RecordingSink:
    events: list[ControlEvent] = field(default_factory=list)

    def publish(self, event: ControlEvent) -> None:
        self.events.append(event)


def _runtime(sink: RecordingSink, timestamps: list[int]) -> RuntimeCoordinator:
    clock = iter(timestamps).__next__
    return RuntimeCoordinator(RuntimeConfig.from_constants(), sink, clock_ns=clock)


def test_call_and_channel_open_close_are_ordered_and_idempotent() -> None:
    sink = RecordingSink()
    runtime = _runtime(sink, [10, 11, 12, 13, 14, 15])

    scope = runtime.open_call("call-001")
    channel = runtime.open_channel("call-001", "asr-input", "speech")

    assert scope.is_open
    assert channel.is_open
    assert [event.kind for event in sink.events] == ["call_open", "channel_open"]
    assert [event.sequence for event in sink.events] == [1, 2]
    assert [event.timestamp_ns for event in sink.events] == [10, 11]

    assert runtime.close_channel("call-001", "asr-input", "endpoint") is True
    assert runtime.close_channel("call-001", "asr-input", "endpoint-again") is False
    assert channel.cancel_token.is_cancelled

    assert runtime.close_call("call-001", "normal") is True
    assert runtime.close_call("call-001", "normal-again") is False
    assert scope.state.value == "closed"

    close_events = [event for event in sink.events if event.kind == ControlEventKind.CHANNEL_CLOSE]
    assert len(close_events) == 2
    assert isinstance(close_events[0].payload, ChannelClose)
    assert [
        close_event.payload.already_closed
        for close_event in close_events
        if isinstance(close_event.payload, ChannelClose)
    ] == [False, True]
    call_close_events = [event for event in sink.events if event.kind == ControlEventKind.CALL_CLOSE]
    assert [event.payload.already_closed for event in call_close_events if isinstance(event.payload, CallClose)] == [
        False,
        True,
    ]


def test_terminal_event_closes_active_operation_and_stale_generation_is_dropped() -> None:
    sink = RecordingSink()
    runtime = _runtime(sink, list(range(10, 30)))
    runtime.open_call("call-002")
    old_channel = runtime.open_channel("call-002", "operation", "control")
    runtime.close_channel("call-002", "operation", "superseded")
    new_channel = runtime.open_channel("call-002", "operation", "control")

    stale_event = ControlEvent(
        kind=ControlEventKind.CHANNEL_OPEN,
        call_id="call-002",
        sequence=900,
        timestamp_ns=900,
        payload=ChannelOpen("call-002", "operation", "control", old_channel.generation),
        channel_id="operation",
        channel_generation=old_channel.generation,
    )

    accepted: list[ControlEvent] = []
    assert runtime.dispatch_to_channel(old_channel, stale_event, accepted.append) is False
    assert accepted == []

    current_event = ControlEvent(
        kind=ControlEventKind.CHANNEL_OPEN,
        call_id="call-002",
        sequence=901,
        timestamp_ns=901,
        payload=ChannelOpen("call-002", "operation", "control", new_channel.generation),
        channel_id="operation",
        channel_generation=new_channel.generation,
    )
    assert runtime.dispatch_to_channel(new_channel, current_event, accepted.append) is True
    assert accepted == [current_event]

    runtime.terminate_call("call-002", "remote_hangup")
    assert old_channel.cancel_token.is_cancelled
    assert new_channel.cancel_token.is_cancelled
    assert not old_channel.is_open
    assert not new_channel.is_open
    assert sink.events[4].kind is ControlEventKind.TERMINAL

    with pytest.raises(LifecycleError):
        runtime.open_channel("call-002", "operation", "control")


def test_registry_allows_only_one_active_call_and_never_reuses_identity() -> None:
    sink = RecordingSink()
    runtime = _runtime(sink, list(range(1, 10)))

    runtime.open_call("call-003")
    with pytest.raises(LifecycleError, match="one active call"):
        runtime.open_call("call-004")

    runtime.close_call("call-003", "done")
    with pytest.raises(LifecycleError, match="cannot be reused"):
        runtime.open_call("call-003")

    new_scope = runtime.open_call("call-004")
    new_channel = runtime.open_channel("call-004", "operation", "control")
    assert new_scope.is_open
    assert new_channel.generation == 1


def test_first_close_of_call_without_channels_is_not_mistaken_for_reclose() -> None:
    sink = RecordingSink()
    runtime = _runtime(sink, [30, 31, 32])

    runtime.open_call("call-005")

    assert runtime.close_call("call-005", "empty-call") is True
    assert runtime.close_call("call-005", "empty-call-again") is False
    call_close_events = [event for event in sink.events if event.kind == ControlEventKind.CALL_CLOSE]
    assert [event.payload.already_closed for event in call_close_events if isinstance(event.payload, CallClose)] == [
        False,
        True,
    ]


def test_runtime_probe_requires_actual_free_threading() -> None:
    config = RuntimeConfig.from_constants()
    regular = RuntimeProbe("python", "cpython", (3, 14, 3), 0, True)
    free_threaded = RuntimeProbe("python", "cpython", (3, 14, 3), 1, False)

    assert not regular.meets(config)
    assert free_threaded.meets(config)
