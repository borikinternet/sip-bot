from __future__ import annotations

from tools.endpoint_live_audit import audit


def _document(silences: list[int]) -> dict[str, object]:
    return {
        "status": "pass",
        "runtime": {"gil_enabled": False},
        "wiring": {"final_turns": 4, "errors": 0},
        "errors": [],
        "speech": {
            "endpoint_events": [
                {"kind": "hard_endpoint", "silence_ms": silence_ms, "turn_id": f"turn-{index}"}
                for index, silence_ms in enumerate(silences, start=1)
            ]
        },
    }


def test_live_endpoint_audit_accepts_scheduler_jitter_within_400ms() -> None:
    result = audit(_document([380, 362, 361, 383]))

    assert result["status"] == "pass"
    assert result["maximum_observed_ms"] == 383


def test_live_endpoint_audit_rejects_one_boundary_above_400ms() -> None:
    result = audit(_document([380, 401, 361, 383]))

    assert result["status"] == "fail"
    assert result["checks"]["all_hard_endpoints_within_limit"] is False
