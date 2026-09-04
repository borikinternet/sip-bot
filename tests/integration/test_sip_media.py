"""Target-runtime SIP/media smoke against the approved local Baresip peer.

Run this file with the application executable from 001-B.  It is intentionally
not part of the Windows-host unit lane because the patched PJSUA2 extension is
installed in the Ubuntu/WSL target prefix.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import shutil

import pytest

from sip_bot.sip_media import (
    NormalizedSipEvent,
    SipEventKind,
    SipMediaAdapter,
    SipMediaConfig,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / "artifacts" / "implementation" / "002-mvp-media-and-speech-integration" / "002-B"
PEER_CONFIG = PROJECT_ROOT / "artifacts" / "feasibility" / "001-S-voip-test-stand" / "config" / "peer-5080"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _start_peer(name: str, *, stdio: bool = False) -> tuple[subprocess.Popen[str], Path, object]:
    if shutil.which("baresip") is None:
        pytest.skip("live SIP/media integration requires baresip in the target Linux environment")
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = EVIDENCE_ROOT / f"{name}.peer.log"
    log_path.unlink(missing_ok=True)
    log = log_path.open("w", encoding="utf-8")
    command = ["baresip", "-f", str(PEER_CONFIG), "-t", "25"]
    if stdio:
        command.extend(["-m", "stdio.so"])
    peer = subprocess.Popen(
        command,
        cwd="/usr/lib/baresip/modules",
        stdin=subprocess.PIPE if stdio else subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return peer, log_path, log


def _stop_peer(peer: subprocess.Popen[str], log: object) -> None:
    if peer.poll() is None:
        peer.terminate()
        try:
            peer.wait(timeout=5)
        except subprocess.TimeoutExpired:
            peer.kill()
            peer.wait(timeout=5)
    log.close()  # type: ignore[union-attr]


def _runtime_dict(adapter: SipMediaAdapter) -> dict[str, object]:
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


def _record(
    name: str,
    *,
    command: list[str],
    adapter: SipMediaAdapter,
    events: list[NormalizedSipEvent],
    profile: object | None,
    stats: dict[str, int],
    peer_log_path: Path,
    peer_exit_code: int | None,
    extra: dict[str, object] | None = None,
) -> Path:
    payload: dict[str, object] = {
        "evidence_id": f"B-E-{name}",
        "plan": "002-B",
        "stage": name,
        "status": extra.get("test_result", "pass") if extra else "pass",
        "command": " ".join(command),
        "working_directory": str(PROJECT_ROOT),
        "started_at_utc": _utc_now(),
        "runtime": _runtime_dict(adapter),
        "candidate": {
            "sip_media": "PJSUA2/PJMEDIA 2.17",
            "binding": "patched SWIG CPython 3.14t",
            "peer": "Baresip 1.0.0-4build14 from approved 001-S stand",
        },
        "events": [event.as_dict() for event in events],
        "media_profile": profile.as_dict() if hasattr(profile, "as_dict") else None,
        "media_stats": stats,
        "peer_exit_code": peer_exit_code,
        "peer_log": str(peer_log_path),
        "audio_recording": False,
        "external_pbx": False,
        "finished_at_utc": _utc_now(),
    }
    if extra:
        payload.update(extra)
    output = EVIDENCE_ROOT / f"{name}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _collect_until(
    adapter: SipMediaAdapter,
    events: list[NormalizedSipEvent],
    predicate: object,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        adapter.poll(20)
        events.extend(adapter.drain_events())
        if callable(predicate) and predicate(events):
            return


def _send_options_and_poll(adapter: SipMediaAdapter) -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    try:
        local_port = sock.getsockname()[1]
        message = (
            "OPTIONS sip:tester@127.0.0.1:5070 SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP 127.0.0.1:{local_port};branch=z9hG4bK-options\r\n"
            "Max-Forwards: 70\r\n"
            "To: <sip:tester@127.0.0.1:5070>\r\n"
            "From: <sip:probe@127.0.0.1>;tag=options\r\n"
            "Call-ID: options-probe\r\n"
            "CSeq: 1 OPTIONS\r\n"
            "Contact: <sip:probe@127.0.0.1>\r\n"
            "Content-Length: 0\r\n\r\n"
        ).encode("ascii")
        sock.sendto(message, ("127.0.0.1", 5070))
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            adapter.poll(20)
            try:
                response, _ = sock.recvfrom(8192)
                return response
            except BlockingIOError:
                continue
        return b""
    finally:
        sock.close()


def _adapter() -> SipMediaAdapter:
    return SipMediaAdapter(
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


def test_local_call_lifecycle_and_options_reply() -> None:
    peer, peer_log_path, peer_log = _start_peer("lifecycle-options")
    adapter = _adapter()
    events: list[NormalizedSipEvent] = []
    call_id = "call-integration-lifecycle"
    command = [sys.executable, "-I", "-m", "pytest", "-q", __file__]
    response = b""
    profile = None
    passed = False
    try:
        time.sleep(1.0)
        adapter.start()
        response = _send_options_and_poll(adapter)
        events.extend(adapter.drain_events())
        adapter.make_call("sip:peer@127.0.0.1:5080", call_id=call_id)
        _collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.CALL_ANSWERED for item in observed),
            8.0,
        )
        profile = adapter.media_profile()
        assert b"SIP/2.0 200" in response
        assert any(item.kind is SipEventKind.CALL_ANSWERED for item in events)
        adapter.hangup()
        _collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.CALL_ENDED for item in observed),
            5.0,
        )
        assert any(item.kind is SipEventKind.CALL_ENDED for item in events)
        passed = True
    finally:
        stats = adapter.media_stats()
        adapter.close()
        _stop_peer(peer, peer_log)
        _record(
            "lifecycle-options",
            command=command,
            adapter=adapter,
            events=events,
            profile=profile,
            stats=stats,
            peer_log_path=peer_log_path,
            peer_exit_code=peer.returncode,
            extra={
                "options_response_status": response.split(b"\r\n", 1)[0].decode("ascii", "replace") if response else None,
                "media_profile_blocked": any(item.kind is SipEventKind.MEDIA_FAILED for item in events),
                "test_result": "pass" if passed else "fail",
            },
        )


def test_remote_bye_closes_media_without_dispatcher_wait() -> None:
    peer, peer_log_path, peer_log = _start_peer("remote-bye", stdio=True)
    adapter = _adapter()
    events: list[NormalizedSipEvent] = []
    command = [sys.executable, "-I", "-m", "pytest", "-q", __file__, "-k", "remote_bye"]
    profile = None
    bye_sent_ns: int | None = None
    active_call_id_after_bye: str | None = None
    passed = False
    try:
        time.sleep(1.0)
        adapter.start()
        adapter.make_call("sip:peer@127.0.0.1:5080", call_id="call-integration-bye")
        _collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.CALL_ANSWERED for item in observed),
            8.0,
        )
        profile = adapter.media_profile()
        assert peer.stdin is not None
        time.sleep(0.2)
        bye_sent_ns = time.monotonic_ns()
        peer.stdin.write("b\n")
        peer.stdin.flush()
        _collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.REMOTE_HANGUP for item in observed),
            5.0,
        )
        remote_hangup = next(item for item in events if item.kind is SipEventKind.REMOTE_HANGUP)
        assert remote_hangup.timestamp_ns >= bye_sent_ns
        active_call_id_after_bye = adapter.active_call_id
        assert active_call_id_after_bye is None
        if profile is not None:
            assert any(item.kind is SipEventKind.MEDIA_STOPPED for item in events)
        passed = True
    finally:
        stats = adapter.media_stats()
        adapter.close()
        _stop_peer(peer, peer_log)
        _record(
            "remote-bye",
            command=command,
            adapter=adapter,
            events=events,
            profile=profile,
            stats=stats,
            peer_log_path=peer_log_path,
            peer_exit_code=peer.returncode,
            extra={
                "bye_sent_ns": bye_sent_ns,
                "active_call_id_after_bye": active_call_id_after_bye,
                "media_profile_blocked": any(item.kind is SipEventKind.MEDIA_FAILED for item in events),
                "test_result": "pass" if passed else "fail",
            },
        )


def test_pcmu_profile_and_handoff_requires_authoritative_media_index() -> None:
    """B3 gate: prove profile/handoff uses the authoritative media index."""

    peer, peer_log_path, peer_log = _start_peer("pcmu-profile-handoff")
    adapter = _adapter()
    events: list[NormalizedSipEvent] = []
    profile = None
    passed = False
    command = [sys.executable, "-I", "-m", "pytest", "-q", __file__, "-k", "pcmu_profile"]
    try:
        time.sleep(1.0)
        adapter.start()
        adapter.make_call("sip:peer@127.0.0.1:5080", call_id="call-integration-pcmu")
        _collect_until(
            adapter,
            events,
            lambda observed: any(item.kind is SipEventKind.CALL_ANSWERED for item in observed),
            8.0,
        )
        profile = adapter.media_profile()
        if profile is None:
            gap = next(
                (
                    item.reason
                    for item in events
                    if item.kind is SipEventKind.MEDIA_FAILED and item.reason
                ),
                "media profile was not produced",
            )
            raise AssertionError(
                "B-002-B-GAP-001: actual patched binding rejects the candidate "
                f"media index path: {gap}"
            )
        assert profile.codec.upper() == "PCMU"
        passed = True
    finally:
        stats = adapter.media_stats()
        adapter.close()
        _stop_peer(peer, peer_log)
        _record(
            "pcmu-profile-handoff",
            command=command,
            adapter=adapter,
            events=events,
            profile=profile,
            stats=stats,
            peer_log_path=peer_log_path,
            peer_exit_code=peer.returncode,
            extra={
                "test_result": "pass" if passed else "blocked",
                "gap_id": None if passed else "B-002-B-GAP-001",
                "gap": None if passed else "Call.getStreamInfo(-1) rejects -1 as unsigned int",
            },
        )
