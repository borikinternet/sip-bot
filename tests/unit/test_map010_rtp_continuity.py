from __future__ import annotations

from tools.map010_rtp_continuity import audit_registered_result


def _result(*, egress_frames: int = 50, receive_packets: int = 50, underruns: int = 0) -> dict:
    return {
        "sip": {
            "adapter_profile": {"codec": "PCMU", "ptime_ms": 20.0, "sample_rate_hz": 8000},
            "adapter_events": [
                {"call_id": "call-in-0", "kind": "protocol_reply", "method": "INVITE", "status_code": 200, "timestamp_ns": 1_000_000_000},
                {"call_id": "call-in-0", "kind": "remote_hangup", "method": "BYE", "status_code": 200, "timestamp_ns": 2_000_000_000},
            ],
            "adapter_media_stats": {
                "egress_frames": egress_frames,
                "egress_underruns": underruns,
                "callback_errors": 0,
                "egress_dropped_closed": 0,
                "egress_dropped_overflow": 0,
            },
            "peer_rtp_packets": {"receive": receive_packets},
        }
    }


def _audit(result: dict) -> dict:
    return audit_registered_result(
        result,
        baresip_summary={"receive_packets": result["sip"]["peer_rtp_packets"]["receive"], "receive_lost_packets": 0},
    )


def test_rtp_continuity_uses_answered_call_window_and_ptime() -> None:
    result = _audit(_result())

    assert result["status"] == "pass"
    assert result["expected_frames"] == 50
    assert result["recording_duration_is_not_used_for_acceptance"] is True


def test_rtp_continuity_rejects_egress_count_shortfall() -> None:
    result = _audit(_result(egress_frames=45, receive_packets=45))

    assert result["status"] == "fail"
    assert result["checks"]["egress_count_matches_call_window"] is False


def test_rtp_continuity_rejects_media_underrun() -> None:
    result = _audit(_result(underruns=1))

    assert result["status"] == "fail"
    assert result["checks"]["egress_underruns_zero"] is False


def test_rtp_continuity_accepts_one_packet_counter_skew() -> None:
    result = _audit(_result(egress_frames=49, receive_packets=50))

    assert result["status"] == "pass"
    assert result["checks"]["peer_received_egress_count"] is True


def test_rtp_continuity_uses_peer_counter_as_diagnostic_behind_pbx() -> None:
    source = _result(egress_frames=50, receive_packets=275)
    result = audit_registered_result(source, external_pbx=True)

    assert result["status"] == "pass"
    assert result["checks"]["egress_count_matches_call_window"] is True
    assert result["checks"]["peer_received_rtp"] is True
    assert result["peer_diagnostics"]["counter_scope_comparable_to_bot_answered_window"] is False
    assert result["peer_diagnostics"]["peer_counter_matches_bot_window"] is False
    assert result["peer_diagnostics"]["peer_reported_no_receive_loss"] is None
