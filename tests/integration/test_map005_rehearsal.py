from __future__ import annotations

from tools.map005_rehearsal_gate import write_package


def test_rehearsal_package_keeps_recording_and_latency_claims_explicit(tmp_path) -> None:
    result = {
        "status": "pass",
        "scenario_checks": {"stereo_recording_present": True, "report_present": True},
        "upstream_j4": {"sip": {"pcmu_8000_mono": True}},
    }

    write_package(tmp_path, result)

    matrix = (tmp_path / "requirement-matrix.md").read_text(encoding="utf-8")
    checklist = (tmp_path / "freeze-checklist.md").read_text(encoding="utf-8")
    assert "Baresip stereo recording" in matrix
    assert "Overall latency observation retained: yes" in checklist
