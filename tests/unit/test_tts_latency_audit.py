from __future__ import annotations

from tools.tts_latency_audit import audit


def _document(*, playback_ns: int = 220_000_000) -> dict[str, object]:
    stages = (
        ("llm_final_result", 0),
        ("tts_command_accepted", 5_000_000),
        ("tts_worker_started", 6_000_000),
        ("tts_adapter_started", 8_000_000),
        ("tts_engine_first_chunk", 210_000_000),
        ("tts_pcm_first_chunk", 215_000_000),
        ("playback_first_frame", playback_ns),
    )
    return {
        "status": "pass",
        "runtime": {"gil_enabled": False},
        "wiring": {"errors": 0},
        "tts_output": {"dropped_overflow_bytes": 0},
        "rtp_continuity": {"checks": {"egress_underruns_zero": True}},
        "errors": [],
        "tts_latency_events": [
            {
                "call_id": "call-1",
                "turn_id": "turn-1" if stage == "llm_final_result" else "",
                "channel_id": "playback",
                "generation": 2,
                "stage": stage,
                "timestamp_ns": timestamp_ns,
            }
            for stage, timestamp_ns in stages
        ],
    }


def test_tts_latency_audit_accepts_complete_improved_trace() -> None:
    result = audit(_document(), baseline_median_ms=398.059)

    assert result["status"] == "pass"
    assert result["maximum_llm_final_to_playback_ms"] == 220.0
    assert result["traces"][0]["stage_ms"]["adapter_to_engine_first_chunk"] == 202.0


def test_tts_latency_audit_rejects_trace_slower_than_baseline() -> None:
    result = audit(_document(playback_ns=410_000_000), baseline_median_ms=398.059)

    assert result["status"] == "fail"
    assert result["checks"]["improves_over_chunk_20_baseline"] is False
