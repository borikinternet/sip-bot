from __future__ import annotations

from tools.vad_energy_replay import apply_expectations


def _result(*, turns: int, maximum_ms: int | None) -> dict[str, object]:
    return {
        "status": "pass",
        "authoritative_turn_count": turns,
        "endpoint_timing": {"maximum_hard_endpoint_silence_ms": maximum_ms},
    }


def test_recorded_replay_accepts_four_turns_at_360ms() -> None:
    result = apply_expectations(
        _result(turns=4, maximum_ms=360),
        expected_turn_count=4,
        maximum_hard_endpoint_ms=400,
    )

    assert result["status"] == "pass"
    assert result["maximum_allowed_hard_endpoint_ms"] == 400


def test_recorded_replay_fails_when_endpoint_exceeds_owner_limit() -> None:
    result = apply_expectations(
        _result(turns=4, maximum_ms=420),
        expected_turn_count=4,
        maximum_hard_endpoint_ms=400,
    )

    assert result["status"] == "fail"


def test_recorded_replay_fails_when_no_authoritative_endpoint_exists() -> None:
    result = apply_expectations(
        _result(turns=0, maximum_ms=None),
        expected_turn_count=4,
        maximum_hard_endpoint_ms=400,
    )

    assert result["status"] == "fail"
    assert result["expected_turn_count"] == 4
