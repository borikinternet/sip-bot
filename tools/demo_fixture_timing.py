"""Timing profile for the deterministic Baresip demo input fixture."""

from __future__ import annotations

from typing import Final


# The profile keeps a 6.5 s turn-2 -> turn-3 window.  The extra margin lets
# the current live path start audible TTS before turn 3, while turn 3 still
# overlaps the answer and is classified as barge-in.  This is a deterministic
# test-fixture delay, not a production endpointing policy.
J4_SCENARIO_SPECS: Final[tuple[tuple[str, str, float, float], ...]] = (
    ("turn-1", "Почему небо днём кажется голубым?", 1.5, 14.5),
    ("turn-2", "А почему на закате оно становится красным?", 0.0, 1.0),
    ("turn-3", "Стоп, небо голубое?", 5.5, 11.0),
    ("turn-4", "Каков точный состав атмосферы на экзопланете Кеплер семьсот восемьдесят шесть?", 11.0, 10.5),
    ("turn-5", "Да", 10.5, 10.0),
)


def total_silence_seconds() -> float:
    """Return the configured silence budget, excluding generated speech."""

    return sum(leading + trailing for _, _, leading, trailing in J4_SCENARIO_SPECS)


def inter_turn_silence_seconds(index: int) -> float:
    """Return the silence between the end of turn *index* and next speech."""

    if index < 0 or index >= len(J4_SCENARIO_SPECS) - 1:
        raise IndexError("inter-turn index must reference a non-final turn")
    _, _, _, trailing = J4_SCENARIO_SPECS[index]
    next_leading = J4_SCENARIO_SPECS[index + 1][2]
    return trailing + next_leading
