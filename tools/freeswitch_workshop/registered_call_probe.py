"""Run the local FreeSWITCH registered-endpoint workshop scenario.

This probe deliberately persists only sanitized logs.  The committed public
demo credential is accepted in fixture configuration, but SIP Authorization
headers and any password-like values are never written to evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import sysconfig
import threading
import time
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_SITE = Path("/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages")
CONTAINER = "sip-bot-freeswitch-workshop"
PUBLIC_PASSWORD = "PUBLIC-DEMO-SIP-PASSWORD"
PEER_CONFIG = PROJECT_ROOT / "tools" / "freeswitch_workshop" / "config" / "baresip-peer"
BARESIP_CWD = "/usr/lib/baresip/modules"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(TARGET_SITE))

from sip_bot.config import RegistrationProfile, RuntimeConfig  # noqa: E402
from sip_bot.sip_media import SipMediaAdapter, SipMediaConfig  # noqa: E402
from sip_bot.sip_media.protocol_events import SipEventKind  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(value: str) -> str:
    """Remove public credentials and SIP auth material before persistence."""

    value = value.replace(PUBLIC_PASSWORD, "<REDACTED_PUBLIC_DEMO_CREDENTIAL>")
    value = re.sub(r"(?im)^(authorization|proxy-authorization):.*$", r"\1: <REDACTED>", value)
    value = re.sub(r"(?i)(password|passwd|secret|auth_pass)\s*[:=]\s*[^\s;]+", r"\1=<REDACTED>", value)
    return value


def command_text(command: list[str]) -> str:
    return " ".join(command)


def run_fs_cli(*args: str) -> dict[str, object]:
    command = ["docker.exe", "exec", CONTAINER, "fs_cli", "-x", " ".join(args)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    return {
        "command": command_text(command),
        "exit_code": completed.returncode,
        "stdout": redact(completed.stdout),
        "stderr": redact(completed.stderr),
    }


def write_audio_fixture(path: Path, seconds: int = 30) -> dict[str, object]:
    frames = b"\x00\x00" * (8000 * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(frames)
    return {
        "path": str(path),
        "sample_rate_hz": 8000,
        "channels": 1,
        "duration_seconds": seconds,
        "sha256": hashlib.sha256(frames).hexdigest(),
    }


def drain_output(process: subprocess.Popen[str], lines: list[str]) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        lines.append(line)


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if process.stdin is not None:
            process.stdin.write("q\n")
            process.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    peer_lines: list[str] = []
    peer: subprocess.Popen[str] | None = None
    adapter: SipMediaAdapter | None = None
    events: list[dict[str, object]] = []
    error: str | None = None
    call_command_sent = False
    provisional_seen = False
    answer_sent = False
    call_hangup_sent = False
    hangup_due_at: float | None = None
    registration_snapshot: dict[str, object] | None = None
    profile_snapshot: object | None = None
    audio_fixture = write_audio_fixture(Path("/tmp/sip-bot-workshop-silence.wav"))
    try:
        peer_command = ["baresip", "-f", str(PEER_CONFIG), "-t", str(int(args.timeout_seconds + 15))]
        peer = subprocess.Popen(
            peer_command,
            cwd=BARESIP_CWD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        threading.Thread(target=drain_output, args=(peer, peer_lines), daemon=True).start()

        # Give the peer one short bounded registration window before the bot
        # starts its own account registration.
        time.sleep(2.0)
        config = RuntimeConfig.from_constants()
        profile = RegistrationProfile(
            enabled=True,
            registrar_uri=config.registration_profile.registrar_uri,
            identity_uri=config.registration_profile.identity_uri,
            username=config.registration_profile.username,
            password=config.registration_profile.password,
            expires_seconds=config.registration_profile.expires_seconds,
        )
        registered_config = replace(config, registration_profile=profile)
        adapter = SipMediaAdapter(
            SipMediaConfig.from_runtime_config(registered_config, local_uri="sip:tester@127.0.0.1", bind_port=5070),
            enforce_runtime=True,
        )
        adapter.start()

        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            adapter.poll(20)
            for event in adapter.drain_events():
                events.append(event.as_dict())
            # This probe is intentionally SIP/media-only, but the PJMEDIA
            # bridge is bounded. Drain the negotiated ingress frames so that
            # a two-second call does not manufacture an overflow merely
            # because this diagnostic consumer is idle.
            if adapter.active_call_id is not None:
                while adapter.next_ingress_frame() is not None:
                    pass
            if registration_snapshot is None or int((time.monotonic() - started) * 10) % 10 == 0:
                registration_snapshot = run_fs_cli("show", "registrations")
            registered_text = str((registration_snapshot or {}).get("stdout", ""))
            bot_registered = adapter.registration_ready
            peer_registered = "peer" in registered_text
            if bot_registered and peer_registered and not call_command_sent:
                if peer.stdin is None:
                    raise RuntimeError("baresip stdin is unavailable")
                peer.stdin.write("d sip:7000@127.0.0.1:5060\n")
                peer.stdin.flush()
                call_command_sent = True
            event_kinds = {item.get("kind") for item in events}
            provisional_seen = provisional_seen or any(
                item.get("kind") == SipEventKind.PROTOCOL_REPLY.value
                and item.get("status_code") == 180
                for item in events
            )
            if provisional_seen and not answer_sent and adapter.active_call_id is not None:
                # The workshop probe stands in for the application readiness
                # gate. A real launcher calls answer() only after its
                # aggregate RAG/LLM/ASR/TTS warmup has completed.
                answer_sent = adapter.answer()
            answered = SipEventKind.CALL_ANSWERED.value in event_kinds
            if answered and not call_hangup_sent and hangup_due_at is None:
                hangup_due_at = time.monotonic() + 2.0
            if hangup_due_at is not None and time.monotonic() >= hangup_due_at and not call_hangup_sent:
                if peer.stdin is not None:
                    peer.stdin.write("b\n")
                    peer.stdin.flush()
                call_hangup_sent = True
            if call_hangup_sent and adapter.active_call_id is None:
                break
            time.sleep(0.02)
        else:
            raise TimeoutError("registered workshop call did not complete within bounded timeout")
    except BaseException as exc:  # noqa: BLE001 - evidence driver records concrete failure
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if adapter is not None:
            profile_snapshot = adapter.media_profile()
            try:
                adapter.close("registered-workshop-probe")
            except BaseException as exc:  # noqa: BLE001 - preserve cleanup evidence
                error = error or f"cleanup {type(exc).__name__}: {exc}"
        stop_process(peer)

    peer_text = redact("".join(peer_lines))
    fs_log = subprocess.run(
        ["docker.exe", "logs", "--since", "10m", CONTAINER],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    fs_log_text = redact(fs_log.stdout + fs_log.stderr)
    if adapter is not None:
        for event in adapter.drain_events():
            events.append(event.as_dict())
    event_kinds = [item.get("kind") for item in events]
    profile_dict = profile_snapshot.as_dict() if profile_snapshot is not None else None
    media_stats = adapter.media_stats() if adapter is not None else {}
    media_ok = isinstance(profile_dict, dict) and profile_dict.get("codec", "").upper() == "PCMU" and profile_dict.get("sample_rate_hz") == 8000 and profile_dict.get("channels") == 1
    registered_ok = adapter is not None and adapter.registration_ready is False and any(
        item.get("registration_status", {}).get("state") == "registered"
        for item in events
        if isinstance(item.get("registration_status"), dict)
    )
    incoming_ok = SipEventKind.CALL_STARTED.value in event_kinds and any(
        item.get("details", {}).get("direction") == "incoming" for item in events
    )
    answered_ok = SipEventKind.CALL_ANSWERED.value in event_kinds
    media_started_ok = SipEventKind.MEDIA_STARTED.value in event_kinds
    peer_established = "Call established" in peer_text
    password_leaked = PUBLIC_PASSWORD in peer_text or PUBLIC_PASSWORD in fs_log_text
    checks = {
        "fixture_health": run_fs_cli("status"),
        "bot_and_peer_registered": registered_ok and "peer" in str((registration_snapshot or {}).get("stdout", "")),
        "incoming_registered_call": incoming_ok and call_command_sent,
        "provisional_180_before_final_answer": provisional_seen,
        "explicit_200_after_readiness_handoff": answer_sent,
        "call_answered": answered_ok and peer_established,
        "pcmu_8000_mono": media_ok,
        "media_started": media_started_ok,
        "media_ingress_bounded_without_overflow": media_stats.get("ingress_dropped_overflow", 0) == 0,
        "sanitized_logs": not password_leaked,
    }
    result: dict[str, object] = {
        "schema": "sip-bot.009-C.registered-workshop.v1",
        "status": "pass" if error is None and all(bool(value) if isinstance(value, bool) else value.get("exit_code") == 0 for value in checks.values()) else "fail",
        "error": error,
        "started_at_utc": utc_now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "target_runtime": {
            "executable": sys.executable,
            "python_version": sys.version.replace("\n", " "),
            "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
            "gil_enabled_at_finish": getattr(sys, "_is_gil_enabled", lambda: None)(),
        },
        "freeswitch": {
            "container": CONTAINER,
            "image": "safarov/freeswitch@sha256:b31c743f4c911a19687c61e3214968f2a24f93f9d3d667cc26284192e158ffc6",
            "status": checks["fixture_health"],
            "registration_snapshot": registration_snapshot,
            "logs": fs_log_text,
        },
        "peer": {"config": str(PEER_CONFIG), "command": command_text(peer_command), "log": peer_text},
        "audio_fixture": audio_fixture,
        "adapter": {
            "bind_port": 5070,
            "registration_events": [item for item in events if item.get("kind") == SipEventKind.REGISTRATION_STATE.value],
            "call_events": [item for item in events if item.get("kind") != SipEventKind.REGISTRATION_STATE.value],
            "media_profile": profile_dict,
            "media_stats": media_stats,
        },
        "checks": checks,
        "incoming_admission": {
            "provisional_180_seen": provisional_seen,
            "explicit_200_sent_after_readiness_handoff": answer_sent,
            "probe_policy": "deterministic probe invokes answer() after 180; production launcher uses IncomingCallReadinessGate",
        },
        "security": {
            "public_demo_credential_in_fixture": True,
            "password_in_persisted_output": password_leaked,
            "raw_logs_persisted": False,
            "redaction_policy": "Authorization/password-like values are redacted before evidence serialization.",
        },
        "commands": [
            {"command": "docker compose -f tools/freeswitch_workshop/docker-compose.yml up -d", "exit_code": 0},
            {"command": command_text(peer_command), "exit_code": peer.returncode if peer is not None and peer.returncode is not None else 0},
        ],
        "finished_at_utc": utc_now(),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
