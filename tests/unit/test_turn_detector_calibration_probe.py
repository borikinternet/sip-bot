from __future__ import annotations

from tools.turn_detector_calibration_probe import _expected_internal_gaps, _manifest_intervals


def test_manifest_groups_preserve_semantic_turns() -> None:
    manifest = {
        "segments": [
            {"segment_id": "a", "expected_turn_id": "one", "speech_started_s": 0.1, "speech_duration_s": 0.5},
            {"segment_id": "b", "expected_turn_id": "one", "speech_started_s": 0.84, "speech_duration_s": 0.3},
            {"segment_id": "c", "expected_turn_id": "two", "speech_started_s": 1.8, "speech_duration_s": 0.2},
        ]
    }
    assert _manifest_intervals(manifest)["one"]["segments"] == ["a", "b"]
    assert _manifest_intervals(manifest)["one"]["start_ms"] == 100.0
    assert _manifest_intervals(manifest)["one"]["end_ms"] == 1140.0


def test_internal_gap_is_explicitly_expected_not_to_split() -> None:
    manifest = {
        "segments": [
            {"segment_id": "a", "expected_turn_id": "one", "speech_started_s": 0.1, "speech_duration_s": 0.5},
            {"segment_id": "b", "expected_turn_id": "one", "speech_started_s": 0.84, "speech_duration_s": 0.3},
        ]
    }
    assert _expected_internal_gaps(manifest)[0]["gap_ms"] == 240.0
