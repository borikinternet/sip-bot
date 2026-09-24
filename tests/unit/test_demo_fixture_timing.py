from __future__ import annotations

import pytest

from tools.demo_fixture_timing import J4_SCENARIO_SPECS, inter_turn_silence_seconds, total_silence_seconds


def test_compact_profile_keeps_all_required_turns() -> None:
    assert [item[0] for item in J4_SCENARIO_SPECS] == [
        "turn-1",
        "turn-2",
        "turn-3",
        "turn-4",
        "turn-5",
    ]
    assert total_silence_seconds() == pytest.approx(75.5)


def test_barge_in_window_is_preserved() -> None:
    assert inter_turn_silence_seconds(1) == pytest.approx(6.5)


def test_non_barge_windows_are_compact() -> None:
    assert inter_turn_silence_seconds(0) == pytest.approx(14.5)
    assert inter_turn_silence_seconds(2) == pytest.approx(22.0)
    assert inter_turn_silence_seconds(3) == pytest.approx(21.0)


def test_final_tail_is_bounded() -> None:
    assert J4_SCENARIO_SPECS[-1][3] == pytest.approx(10.0)
