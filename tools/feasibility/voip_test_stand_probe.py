"""Run a bounded local Baresip/PJSUA2 SIP/RTP stand scenario."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PEER_CONFIG = (
    PROJECT_ROOT
    / "artifacts"
    / "feasibility"
    / "001-S-voip-test-stand"
    / "config"
    / "peer-5080"
)
DEFAULT_OPERATOR_CONFIG = (
    PROJECT_ROOT
    / "artifacts"
    / "feasibility"
    / "001-S-voip-test-stand"
    / "config"
    / "operator-5090"
)
PYTHON_EXE = Path("/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t")
PJSUA_PROBE = PROJECT_ROOT / "tools" / "feasibility" / "pjsua2_pjmedia_probe.py"
BARESIP_MODULE_DIR = Path("/usr/lib/baresip/modules")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def pjsua_command(
    output: Path,
    peer_uri: str,
    scenario: str,
    call_seconds: float,
    transfer_uri: str | None = None,
) -> list[str]:
    command = [
        str(PYTHON_EXE),
        "-I",
        str(PJSUA_PROBE),
        "--output",
        str(output),
        "--initialize",
        "--call-uri",
        peer_uri,
        "--call-seconds",
        str(call_seconds),
        "--callbacks",
    ]
    if scenario == "pcmu":
        command.extend(["--tone", "--capture"])
    elif scenario == "bye":
        command.extend(["--tone", "--busy-seconds", "10.0", "--stop-on-disconnect"])
    elif scenario == "transfer":
        command.extend(["--transfer-uri", transfer_uri or "", "--transfer-after", "1.0", "--stop-on-disconnect"])
    return command


def packet_counters(peer_log: str) -> dict[str, int] | None:
    match = re.search(r"packets:\s+(\d+)\s+(\d+)", peer_log)
    if not match:
        return None
    return {"transmit": int(match.group(1)), "receive": int(match.group(2))}


def call_events(pjsua_result: dict[str, object]) -> list[dict[str, object]]:
    call = pjsua_result.get("call")
    if not isinstance(call, dict):
        return []
    events = call.get("events")
    return events if isinstance(events, list) else []


def first_event_timestamp(events: list[dict[str, object]], event_name: str) -> float | None:
    for event in events:
        if event.get("event") == event_name and isinstance(event.get("timestamp"), (float, int)):
            return float(event["timestamp"])
    return None


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("lifecycle", "pcmu", "bye", "transfer"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--peer-config", default=str(DEFAULT_PEER_CONFIG))
    parser.add_argument("--peer-uri", default="sip:peer@127.0.0.1:5080")
    parser.add_argument("--operator-config", default=str(DEFAULT_OPERATOR_CONFIG))
    parser.add_argument("--operator-uri", default="sip:operator@127.0.0.1:5090")
    parser.add_argument("--call-seconds", type=float, default=None)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    peer_config = Path(args.peer_config)
    call_seconds = args.call_seconds or (30.0 if args.scenario == "bye" else 6.0 if args.scenario == "transfer" else 4.0)
    pjsua_output = output.with_name(output.stem + ".pjsua.json")
    peer_log_path = output.with_name(output.stem + ".peer.log")
    peer_log_path.unlink(missing_ok=True)

    peer_command = ["baresip", "-f", str(peer_config), "-t", str(max(call_seconds + 15, 20))]
    peer_stdin = None
    if args.scenario == "bye":
        peer_command.extend(["-m", "stdio.so"])
        peer_stdin = subprocess.PIPE

    result: dict[str, object] = {
        "evidence_id": f"S-E-{args.scenario}",
        "plan": "001-S",
        "candidate": "Baresip + PJSUA2/PJMEDIA local peer",
        "stage": args.scenario,
        "command": " ".join(
            pjsua_command(pjsua_output, args.peer_uri, args.scenario, call_seconds, args.operator_uri)
        ),
        "peer_command": " ".join(peer_command),
        "working_directory": str(PROJECT_ROOT),
        "started_at_utc": utc_now(),
        "peer_config": str(peer_config),
        "status": "fail",
        "exit_code": 1,
        "blocker": None,
    }

    peer = None
    operator = None
    operator_log = None
    probe = None
    probe_stdout = ""
    probe_stderr = ""
    bye_sent_epoch = None
    try:
        peer_log = peer_log_path.open("w", encoding="utf-8")
        peer = subprocess.Popen(
            peer_command,
            cwd=str(BARESIP_MODULE_DIR) if args.scenario == "bye" else None,
            stdin=peer_stdin,
            stdout=peer_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        operator_log_path = output.with_name(output.stem + ".operator.log")
        operator_log_path.unlink(missing_ok=True)
        if args.scenario == "transfer":
            operator_log = operator_log_path.open("w", encoding="utf-8")
            operator = subprocess.Popen(
                ["baresip", "-f", args.operator_config, "-t", str(max(call_seconds + 15, 20))],
                stdout=operator_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        time.sleep(1.5)

        command = pjsua_command(pjsua_output, args.peer_uri, args.scenario, call_seconds, args.operator_uri)
        probe = subprocess.Popen(command, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if args.scenario == "bye":
            deadline = time.monotonic() + min(call_seconds, 12.0)
            while time.monotonic() < deadline:
                if "Call established" in read_text(peer_log_path):
                    break
                if probe.poll() is not None:
                    break
                time.sleep(0.1)
            bye_sent_epoch = time.time()
            if peer.stdin is not None:
                peer.stdin.write("b\n")
                peer.stdin.flush()

        try:
            probe_stdout, probe_stderr = probe.communicate(timeout=call_seconds + 15)
        except subprocess.TimeoutExpired:
            probe.kill()
            probe_stdout, probe_stderr = probe.communicate()
            result["blocker"] = "S-B-004: PJSUA2 probe did not finish within the bounded scenario window"

        if args.scenario == "transfer":
            # The REFER is asynchronous; allow the fake operator to finish its
            # auto-answer before taking the operator log snapshot.
            time.sleep(1.0)

        result["exit_code"] = probe.returncode
        peer_log.flush()
        peer_text = read_text(peer_log_path)
        pjsua_result = json.loads(read_text(pjsua_output)) if pjsua_output.exists() else {}
        events = call_events(pjsua_result)
        established = "Call established" in peer_text
        disconnected_before_local = bool(
            isinstance(pjsua_result.get("call"), dict)
            and pjsua_result["call"].get("peer_disconnected_before_local_hangup") is True
        )
        pjsua_pass = pjsua_result.get("status") == "pass" and result["exit_code"] == 0

        result["runtime"] = {
            "python": pjsua_result.get("python"),
            "executable": pjsua_result.get("executable"),
            "py_gil_disabled": pjsua_result.get("py_gil_disabled"),
            "gil_before_import": pjsua_result.get("gil_before_import"),
            "gil_after_call": pjsua_result.get("gil_after_call"),
        }
        result["pjsua"] = pjsua_result
        result["stdout"] = probe_stdout[-20000:]
        result["stderr"] = probe_stderr[-20000:]
        result["peer_log"] = peer_text[-30000:]
        result["peer_log_path"] = str(peer_log_path)
        operator_text = read_text(operator_log_path) if args.scenario == "transfer" else ""
        if args.scenario == "transfer":
            result["operator_log"] = operator_text[-30000:]
            result["operator_log_path"] = str(operator_log_path)
        result["event_sequence"] = [
            {"event": event.get("event"), "state": event.get("state"), "status_code": event.get("status_code")}
            for event in events
        ]
        result["pcmu"] = {
            "negotiated_in_peer_log": "PCMU/8000/1" in peer_text,
            "decoder_encoder_in_peer_log": "PCMU 8000Hz 1ch" in peer_text,
            "rtp_counters": packet_counters(peer_text),
            "pjsua_capture": (
                pjsua_result.get("call", {}).get("capture_stats")
                if isinstance(pjsua_result.get("call"), dict)
                else None
            ),
        }

        if args.scenario == "lifecycle":
            result["status"] = "pass" if pjsua_pass and established else "fail"
            if not established:
                result["blocker"] = "S-B-003: Baresip did not report an established call"
        elif args.scenario == "pcmu":
            media_ok = (
                result["pcmu"]["negotiated_in_peer_log"]
                and result["pcmu"]["decoder_encoder_in_peer_log"]
                and isinstance(result["pcmu"]["rtp_counters"], dict)
                and result["pcmu"]["rtp_counters"]["transmit"] > 0
                and result["pcmu"]["rtp_counters"]["receive"] > 0
                and isinstance(result["pcmu"]["pjsua_capture"], dict)
                and result["pcmu"]["pjsua_capture"]["frames"] > 0
            )
            result["status"] = "pass" if pjsua_pass and established and media_ok else "fail"
            if not media_ok:
                result["blocker"] = "S-B-002: PCMU/RTP bidirectional evidence is incomplete"
        elif args.scenario == "bye":
            bye_received_epoch = first_event_timestamp(events, "call_state")
            for event in events:
                if event.get("state") == "DISCONNECTED" and isinstance(event.get("timestamp"), (float, int)):
                    bye_received_epoch = float(event["timestamp"])
                    break
            result["bye"] = {
                "sent_at_utc": datetime.fromtimestamp(bye_sent_epoch, timezone.utc).isoformat()
                if bye_sent_epoch is not None
                else None,
                "received_at_utc": datetime.fromtimestamp(bye_received_epoch, timezone.utc).isoformat()
                if bye_received_epoch is not None
                else None,
                "latency_ms": round((bye_received_epoch - bye_sent_epoch) * 1000, 3)
                if bye_sent_epoch is not None and bye_received_epoch is not None
                else None,
                "peer_disconnected_before_local_hangup": disconnected_before_local,
            }
            result["status"] = "pass" if pjsua_pass and established and disconnected_before_local else "fail"
            if not disconnected_before_local:
                result["blocker"] = "S-B-004: remote BYE was not observed before local close"
        if args.scenario == "transfer":
            transfer_requested = any(event.get("event") == "transfer_requested" for event in events)
            operator_answered = "Call established" in operator_text
            result["transfer"] = {
                "requested": transfer_requested,
                "destination": args.operator_uri,
                "operator_answered": operator_answered,
                "operator_log_path": str(operator_log_path),
            }
            result["status"] = "pass" if pjsua_pass and established and transfer_requested and operator_answered else "fail"
            if not transfer_requested:
                result["blocker"] = "S-B-005: PJSUA2 did not issue a transfer request"
            elif not operator_answered:
                result["blocker"] = "S-B-005: fake operator did not report an established transferred call"
    except (OSError, json.JSONDecodeError) as exc:
        result["blocker"] = repr(exc)
        result["stdout"] = probe_stdout[-20000:]
        result["stderr"] = probe_stderr[-20000:]
    finally:
        if probe is not None and probe.poll() is None:
            probe.send_signal(signal.SIGTERM)
            probe.wait(timeout=5)
        if peer is not None and peer.poll() is None:
            peer.terminate()
            try:
                peer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                peer.kill()
                peer.wait()
        if operator is not None and operator.poll() is None:
            operator.terminate()
            try:
                operator.wait(timeout=5)
            except subprocess.TimeoutExpired:
                operator.kill()
                operator.wait()
        if "peer_log" not in result:
            result["peer_log"] = read_text(peer_log_path)[-30000:]
        if "stdout" not in result:
            result["stdout"] = probe_stdout[-20000:]
        if "stderr" not in result:
            result["stderr"] = probe_stderr[-20000:]
        result["finished_at_utc"] = utc_now()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if peer is not None:
            peer_log.close()
        if operator_log is not None:
            operator_log.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(run())
