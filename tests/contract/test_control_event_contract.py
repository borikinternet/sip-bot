"""Contract fixtures for Map-002-I lifecycle event envelopes."""

import pytest

from sip_bot.control import (
    CallClose,
    CallOpen,
    ChannelClose,
    ChannelOpen,
    ControlEvent,
    ControlEventKind,
    Terminal,
)


def test_lifecycle_envelope_shapes_match_candidate_contract() -> None:
    events = [
        ControlEvent(ControlEventKind.CALL_OPEN, "call-100", 1, 100, CallOpen("call-100")),
        ControlEvent(
            ControlEventKind.CALL_CLOSE,
            "call-100",
            2,
            101,
            CallClose("call-100", "normal", False),
        ),
        ControlEvent(
            ControlEventKind.CHANNEL_OPEN,
            "call-100",
            3,
            102,
            ChannelOpen("call-100", "playback", "media", 1),
            channel_id="playback",
            channel_generation=1,
        ),
        ControlEvent(
            ControlEventKind.CHANNEL_CLOSE,
            "call-100",
            4,
            103,
            ChannelClose("call-100", "playback", "media", 1, "barge_in", False),
            channel_id="playback",
            channel_generation=1,
        ),
        ControlEvent(ControlEventKind.TERMINAL, "call-100", 5, 104, Terminal("call-100", "remote_hangup")),
    ]

    assert [event.kind.value for event in events] == [
        "call_open",
        "call_close",
        "channel_open",
        "channel_close",
        "terminal",
    ]
    assert events[2].is_channel_scoped
    assert events[2].channel_generation == 1
    assert events[4].channel_id is None


def test_envelope_rejects_mismatched_scope_or_data_plane_payload() -> None:
    with pytest.raises(ValueError, match="call_id"):
        ControlEvent(
            ControlEventKind.CALL_OPEN,
            "call-200",
            1,
            1,
            CallOpen("call-201"),
        )

    with pytest.raises(ValueError, match="channel_generation"):
        ControlEvent(
            ControlEventKind.CHANNEL_OPEN,
            "call-200",
            1,
            1,
            ChannelOpen("call-200", "x", "control", 1),
            channel_id="x",
            channel_generation=2,
        )

    with pytest.raises(TypeError, match="payload type"):
        ControlEvent(
            ControlEventKind.TERMINAL,
            "call-200",
            1,
            1,
            b"pcm-or-large-payload",  # type: ignore[arg-type]
        )


def test_envelope_value_objects_are_immutable() -> None:
    event = ControlEvent(ControlEventKind.CALL_OPEN, "call-300", 1, 1, CallOpen("call-300"))

    with pytest.raises(AttributeError):
        event.sequence = 2  # type: ignore[misc]
