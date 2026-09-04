#!/usr/bin/env python3
"""Main-executor live protocol/media probe for Map-005-A.

This probe uses the approved local Baresip peer and the existing
SipMediaAdapter.  It keeps protocol reactions local to the adapter, records
the normalized observations, and copies Baresip ``sndfile`` raw tracks into a
new evidence root.  It does not invoke ASR, LLM or TTS.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, TARGET_SITE)

from sip_bot.sip_media import (  # noqa: E402
    NormalizedSipEvent,
    SipEventKind,
    SipMediaAdapter,
    SipMediaConfig,
)


PEER_CONFIG_TEMPLATE = (
    PROJECT_ROOT
    / "artifacts"
    / "feasibility"
    / "001-S-voip-test-stand"
    / "config"
    / "peer-5080"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_peer_config(root: Path, recording_path: Path) -> Path:
    peer_config = root / "peer-5080"
    shutil.copytree(PEER_CONFIG_TEMPLATE, peer_config)
    (peer_config / "uuid").unlink(missing_ok=True)
    config_path = peer_config / "config"
    config = config_path.read_text(encoding="utf-8")
    if not re.search(r"^module\s+sndfile\.so\s*$", config, flags=re.MULTILINE):
        config += "\nmodule            sndfile.so\n"
    if re.search(r"^snd_path\s+", config, flags=re.MULTILINE):
        config = re.sub(
            r"^snd_path\s+.*$",
            f"snd_path          {recording_path}",
            config,
            flags=re.MULTILINE,
        )
    else:
        config += f"snd_path          {recording_path}\n"
    config_path.write_text(config, encoding="utf-8")
    return peer_config


def start_peer(peer_config: Path, log_path: Path) -> tuple[subprocess.Popen[str], Any]:
    if shutil.which("baresip") is None:
        raise RuntimeError("Baresip is not installed in the target environment")
    log = log_path.open("w", encoding="utf-8")
    peer = subprocess.Popen(
        ["baresip", "-f", str(peer_config), "-t", "20", "-m", "stdio.so"],
        cwd="/usr/lib/baresip/modules",
        stdin=subprocess.PIPE,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return peer, log


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def send_options(adapter: SipMediaAdapter) -> tuple[bytes, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    started_ns = time.monotonic_ns()
    try:
        local_port = sock.getsockname()[1]
        message = (
            "OPTIONS sip:tester@127.0.0.1:5070 SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP 127.0.0.1:{local_port};branch=z9hG4bK-map005-options\r\n"
            "Max-Forwards: 70\r\n"
            "To: <sip:tester@127.0.0.1:5070>\r\n"
            "From: <sip:probe@127.0.0.1>;tag=map005-options\r\n"
            "Call-ID: map005-options\r\n"
            "CSeq: 1 OPTIONS\r\n"
            "Contact: <sip:probe@127.0.0.1>\r\n"
            "Content-Length: 0\r\n\r\n"
        ).encode("ascii")
        sock.sendto(message, ("127.0.0.1", 5070))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            adapter.poll(20)
            try:
                response, _ = sock.recvfrom(8192)
                return response, time.monotonic_ns() - started_ns
            except BlockingIOError:
                continue
        return b"", time.monotonic_ns() - started_ns
    finally:
        sock.close()


def collect_until(
    adapter: SipMediaAdapter,
    events: list[NormalizedSipEvent],
    predicate: Any,
    timeout_s: float,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        adapter.poll(20)
        events.extend(adapter.drain_events())
        if predicate(events):
            return


def runtime_record(adapter: SipMediaAdapter) -> dict[str, object]:
    probe = adapter.runtime_probe
    if probe is None:
        return {"status": "not-captured"}
    return {
        "executable": probe.executable,
        "implementation": probe.implementation,
        "version": ".".join(str(part) for part in probe.version),
        "py_gil_disabled": probe.py_gil_disabled,
        "gil_enabled": probe.gil_enabled,
        "free_threaded": probe.is_free_threaded,
    }


def recording_manifest(recording_dir: Path, evidence_dir: Path) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    destination = evidence_dir / "recordings"
    destination.mkdir(parents=True, exist_ok=True)
    for source in sorted(recording_dir.glob("*.wav")):
        target = destination / source.name
        shutil.copy2(source, target)
        output.append(
            {
                "name": target.name,
                "path": str(target),
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    return output


def run(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    peer_log_path = output_root / "baresip-peer.log"
    command = [sys.executable, "-I", str(Path(__file__)), "--scenario", args.scenario, "--output-root", str(output_root)]
    events: list[NormalizedSipEvent] = []
    peer: subprocess.Popen[str] | None = None
    peer_log: Any | None = None
    adapter: SipMediaAdapter | None = None
    recording_dir = Path(tempfile.mkdtemp(prefix="sipbot-map005-a-", dir="/tmp"))
    started_at = utc_now()
    result: dict[str, object] = {
        "evidence_id": "E-005-A-live-protocol-media",
        "plan": "005-A",
        "scenario": args.scenario,
        "status": "fail",
        "command": " ".join(command),
        "working_directory": str(PROJECT_ROOT),
        "started_at_utc": started_at,
        "runtime": None,
        "options": {},
        "events": [],
        "media_profile": None,
        "media_stats": {},
        "recordings": [],
        "deferred_live_stimuli": [
            "CANCEL during an unanswered INVITE",
            "re-INVITE/UPDATE hold-resume initiated by the peer",
            "RTP timeout/transport failure stimulus",
        ],
        "errors": [],
    }
    try:
        peer_config = prepare_peer_config(output_root, recording_dir)
        peer, peer_log = start_peer(peer_config, peer_log_path)
        time.sleep(1.0)
        adapter = SipMediaAdapter(
            SipMediaConfig(
                bind_host="127.0.0.1",
                bind_port=5070,
                local_uri="sip:tester@127.0.0.1",
                codec="PCMU",
                sample_rate_hz=8000,
                channels=1,
                input_capacity_frames=50,
                output_capacity_frames=50,
                event_capacity=256,
            ),
            enforce_runtime=True,
        )
        adapter.start()
        options_response, options_rtt_ns = send_options(adapter)
        events.extend(adapter.drain_events())
        result["options"] = {
            "response_status": options_response.split(b"\r\n", 1)[0].decode("ascii", "replace")
            if options_response
            else None,
            "response_ok": b"SIP/2.0 200" in options_response,
            "elapsed_ms": round(options_rtt_ns / 1_000_000, 3),
        }
        adapter.make_call("sip:peer@127.0.0.1:5080", call_id="map005-a-live-call")
        collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.CALL_ANSWERED for item in observed),
            8.0,
        )
        time.sleep(0.5)
        if peer.stdin is None:
            raise RuntimeError("Baresip stdio is unavailable for remote BYE stimulus")
        bye_sent_ns = time.monotonic_ns()
        peer.stdin.write("b\n")
        peer.stdin.flush()
        collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.REMOTE_HANGUP for item in observed),
            5.0,
        )
        remote_hangup = next(
            (item for item in events if item.kind is SipEventKind.REMOTE_HANGUP),
            None,
        )
        profile = adapter.media_profile()
        stats = adapter.media_stats()
        result["runtime"] = runtime_record(adapter)
        result["media_profile"] = profile.as_dict() if profile is not None else None
        result["media_stats"] = stats
        result["remote_bye"] = {
            "stimulus_sent_ns": bye_sent_ns,
            "observed": remote_hangup is not None,
            "observed_ns": remote_hangup.timestamp_ns if remote_hangup else None,
            "active_call_id_after_bye": adapter.active_call_id,
        }
        if not result["options"]["response_ok"]:  # type: ignore[index]
            raise AssertionError("OPTIONS did not receive SIP/2.0 200")
        if not any(item.kind is SipEventKind.CALL_ANSWERED for item in events):
            raise AssertionError("call was not answered by the approved Baresip peer")
        if profile is None or profile.codec.upper() != "PCMU":
            raise AssertionError("negotiated live media profile is not PCMU")
        if remote_hangup is None or adapter.active_call_id is not None:
            raise AssertionError("remote BYE did not close the active call")
        result["status"] = "pass"
    except BaseException as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")  # type: ignore[union-attr]
    finally:
        if adapter is not None:
            result["events"] = [event.as_dict() for event in events]
            if result["runtime"] is None:
                result["runtime"] = runtime_record(adapter)
            result["media_stats"] = adapter.media_stats()
            try:
                adapter.close("map005-a-cleanup")
            except BaseException as exc:
                result["errors"].append(f"cleanup {type(exc).__name__}: {exc}")  # type: ignore[union-attr]
        stop_process(peer)
        if peer_log is not None:
            peer_log.close()
        result["recordings"] = recording_manifest(recording_dir, output_root)
        shutil.rmtree(recording_dir, ignore_errors=True)
        result["peer_exit_code"] = peer.returncode if peer is not None else None
        result["finished_at_utc"] = utc_now()
        (output_root / "map005-a-live.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result, 0 if result["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("matrix",), default="matrix")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result, exit_code = run(args)
    except BaseException as exc:
        result = {"status": "blocked", "error": f"{type(exc).__name__}: {exc}"}
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
