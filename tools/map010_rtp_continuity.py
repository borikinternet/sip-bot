"""Audit continuous negotiated PCMU/RTP over the answered-call window.

The audit deliberately uses protocol/media lifecycle events and packet/frame
counters.  Baresip ``enc``/``dec`` WAV lengths are recording diagnostics and
are not used as evidence of bot egress continuity.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_PACKETS_RE = re.compile(r"packets:\s+(\d+)\s+(\d+)")
_LOST_RE = re.compile(r"lost:\s+(\d+)\s+(\d+)")


def parse_baresip_audio_summary(text: str) -> dict[str, int] | None:
    """Extract Baresip's final transmit/receive counters from its peer log."""

    packets = _PACKETS_RE.search(text)
    lost = _LOST_RE.search(text)
    if packets is None or lost is None:
        return None
    return {
        "transmit_packets": int(packets.group(1)),
        "receive_packets": int(packets.group(2)),
        "transmit_lost_packets": int(lost.group(1)),
        "receive_lost_packets": int(lost.group(2)),
    }


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_answer_event(events: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for event in events:
        status_code = event.get("status_code")
        if (
            event.get("kind") == "protocol_reply"
            and event.get("method") == "INVITE"
            and status_code is not None
            and int(status_code) == 200
            and event.get("call_id") != "__registration__"
        ):
            return event
    return None


def _find_stop_event(events: list[Mapping[str, Any]], start_ns: float) -> Mapping[str, Any] | None:
    candidates = [
        event
        for event in events
        if (_number(event.get("timestamp_ns")) or -1) > start_ns
        and (
            (event.get("kind") in {"remote_hangup", "local_hangup"} and event.get("method") == "BYE")
            or event.get("kind") == "media_stopped"
        )
    ]
    if not candidates:
        return None
    by_priority = {"remote_hangup": 0, "local_hangup": 0, "media_stopped": 1}
    return min(candidates, key=lambda event: (by_priority.get(str(event.get("kind")), 2), _number(event.get("timestamp_ns")) or 0))


def audit_registered_result(
    result: Mapping[str, Any],
    *,
    baresip_summary: Mapping[str, int] | None = None,
    frame_tolerance: int = 1,
    external_pbx: bool = False,
) -> dict[str, object]:
    """Audit egress coverage using the answered-call event window.

    The event timestamps and media callback counters share the target runtime
    monotonic clock.  One frame is tolerated for event/callback rounding.  A
    Baresip receive counter and zero loss counter provide the peer-side check;
    WAV durations are intentionally excluded.
    """

    sip = result.get("sip")
    sip = sip if isinstance(sip, Mapping) else {}
    events_value = sip.get("adapter_events")
    events = [event for event in events_value if isinstance(event, Mapping)] if isinstance(events_value, list) else []
    answer = _find_answer_event(events)
    answer_ns = _number(answer.get("timestamp_ns")) if answer is not None else None
    stop = _find_stop_event(events, answer_ns) if answer_ns is not None else None
    stop_ns = _number(stop.get("timestamp_ns")) if stop is not None else None

    profile = sip.get("adapter_profile")
    profile = profile if isinstance(profile, Mapping) else {}
    ptime_ms = _number(profile.get("ptime_ms"))
    elapsed_ms = (stop_ns - answer_ns) / 1_000_000 if answer_ns is not None and stop_ns is not None else None
    expected_frames = round(elapsed_ms / ptime_ms) if elapsed_ms is not None and ptime_ms else None

    stats = sip.get("adapter_media_stats")
    stats = stats if isinstance(stats, Mapping) else {}
    egress_frames = int(stats.get("egress_frames", -1))
    egress_underruns = int(stats.get("egress_underruns", -1))
    callback_errors = int(stats.get("callback_errors", -1))
    dropped_closed = int(stats.get("egress_dropped_closed", -1))
    dropped_overflow = int(stats.get("egress_dropped_overflow", -1))

    peer = baresip_summary
    if peer is None:
        peer_packets = sip.get("peer_rtp_packets")
        peer_packets = peer_packets if isinstance(peer_packets, Mapping) else {}
        peer = {
            "receive_packets": int(peer_packets.get("receive", -1)),
            "receive_lost_packets": -1,
        }
    peer_receive = int(peer.get("receive_packets", -1))
    peer_receive_lost = int(peer.get("receive_lost_packets", -1))

    checks = {
        "answered_call_window_present": answer_ns is not None and stop_ns is not None and (stop_ns > answer_ns),
        "ptime_is_negotiated": ptime_ms is not None and ptime_ms > 0,
        "egress_count_matches_call_window": expected_frames is not None and abs(egress_frames - expected_frames) <= frame_tolerance,
        "egress_underruns_zero": egress_underruns == 0,
        "callback_errors_zero": callback_errors == 0,
        "egress_drops_zero": dropped_closed == 0 and dropped_overflow == 0,
    }
    peer_diagnostics = {
        "counter_scope_comparable_to_bot_answered_window": not external_pbx,
        "peer_counter_matches_bot_window": peer_receive >= 0 and abs(peer_receive - egress_frames) <= frame_tolerance,
        "peer_reported_no_receive_loss": None if peer_receive_lost < 0 else peer_receive_lost == 0,
    }
    if external_pbx:
        # A PBX may emit early media and continue its peer leg around transfer,
        # so the peer's whole-call packet counter is not the bot's 200/BYE
        # window.  Keep it as diagnostic evidence and require only that RTP
        # reached the peer; bot continuity remains governed by its own event
        # clock, negotiated ptime, egress callbacks, underruns and drops.
        checks["peer_received_rtp"] = peer_receive > 0
    else:
        checks["peer_received_egress_count"] = bool(peer_diagnostics["peer_counter_matches_bot_window"])
        checks["peer_reported_no_receive_loss"] = peer_receive_lost == 0
    return {
        "schema": "sip-bot.map010-c-rtp-continuity.v2",
        "status": "pass" if all(checks.values()) else "fail",
        "acceptance_scope": "answered-call media continuity; recording timeline is diagnostic only",
        "window": {
            "start_event": dict(answer) if answer is not None else None,
            "start_semantics": "200 OK to INVITE / call answer",
            "stop_event": dict(stop) if stop is not None else None,
            "stop_semantics": "BYE received (or media_stopped fallback); 200 OK to BYE is transaction confirmation",
            "elapsed_ms": None if elapsed_ms is None else round(elapsed_ms, 3),
        },
        "negotiated": {"ptime_ms": ptime_ms, "codec": profile.get("codec"), "sample_rate_hz": profile.get("sample_rate_hz")},
        "expected_frames": expected_frames,
        "egress_frames": egress_frames,
        "peer_receive_packets": peer_receive,
        "peer_receive_lost_packets": peer_receive_lost,
        "external_pbx": external_pbx,
        "frame_tolerance": frame_tolerance,
        "checks": checks,
        "peer_diagnostics": peer_diagnostics,
        "recording_duration_is_not_used_for_acceptance": True,
    }
