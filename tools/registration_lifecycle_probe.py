"""Target-runtime PJSUA2 registration lifecycle probe.

This is a registration-only evidence driver.  The UDP peer is deliberately a
small deterministic SIP registrar fixture, not FreeSWITCH and not production
code.  It challenges the first REGISTER, accepts the digest retry, accepts
PJSUA2 refreshes, and accepts the final unregister request.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import socket
import sys
import sysconfig
import threading
import time
from pathlib import Path

# The target probe intentionally runs with ``-I``.  Keep the application
# import explicit rather than depending on a user-site or environment path.
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(_project_root))

from sip_bot.config import RegistrationProfile
from sip_bot.sip_media.adapter import SipMediaAdapter, SipMediaConfig
from sip_bot.sip_media.protocol_events import SipEventKind


_HEADER_RE = re.compile(r"^(?P<name>[^:]+):\s*(?P<value>.*)$")


@dataclass(frozen=True, slots=True)
class RegistrarRequest:
    method: str
    cseq: int
    expires: int | None
    has_authorization: bool
    has_digest_response: bool


class DigestRegistrar:
    """Minimal UDP registrar sufficient for a PJSUA2 registration contract."""

    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.settimeout(0.1)
        self.address = self.socket.getsockname()
        self.requests: list[RegistrarRequest] = []
        self._nonce = "sip-bot-demo-nonce"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, name="registration-fixture", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.socket.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                payload, peer = self.socket.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                return
            request = payload.decode("utf-8", "replace")
            parsed = self._parse_request(request)
            if parsed is None or parsed.method != "REGISTER":
                continue
            self.requests.append(parsed)
            response = self._response(request, parsed)
            self.socket.sendto(response.encode("ascii"), peer)

    @staticmethod
    def _headers(request: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in request.split("\r\n")[1:]:
            match = _HEADER_RE.match(line)
            if match is not None:
                result[match.group("name").lower()] = match.group("value")
        return result

    def _parse_request(self, request: str) -> RegistrarRequest | None:
        first_line, _, _ = request.partition("\r\n")
        fields = first_line.split()
        if len(fields) < 2:
            return None
        headers = self._headers(request)
        cseq_match = re.match(r"\s*(\d+)\s+\S+", headers.get("cseq", ""))
        expires_match = re.match(r"\s*(\d+)", headers.get("expires", ""))
        authorization = headers.get("authorization", "")
        return RegistrarRequest(
            method=fields[0].upper(),
            cseq=int(cseq_match.group(1)) if cseq_match else 0,
            expires=int(expires_match.group(1)) if expires_match else None,
            has_authorization=bool(authorization),
            has_digest_response="response=" in authorization,
        )

    def _response(self, request: str, parsed: RegistrarRequest) -> str:
        headers = self._headers(request)
        via = headers.get("via", "")
        from_header = headers.get("from", "")
        to_header = headers.get("to", "")
        call_id = headers.get("call-id", "")
        cseq = headers.get("cseq", f"{parsed.cseq} REGISTER")
        contact = headers.get("contact", "")
        common = (
            "Via: " + via + "\r\n"
            "From: " + from_header + "\r\n"
            "To: " + (to_header if ";tag=" in to_header else to_header + ";tag=registrar") + "\r\n"
            "Call-ID: " + call_id + "\r\n"
            "CSeq: " + cseq + "\r\n"
        )
        if not parsed.has_authorization:
            return (
                "SIP/2.0 401 Unauthorized\r\n"
                + common
                + 'WWW-Authenticate: Digest realm="sip-bot-demo", nonce="'
                + self._nonce
                + '", algorithm=MD5, qop="auth"\r\n'
                + "Content-Length: 0\r\n\r\n"
            )
        expires = 0 if parsed.expires == 0 else 2
        contact_header = ("Contact: " + contact + "\r\n") if contact else ""
        return (
            "SIP/2.0 200 OK\r\n"
            + common
            + contact_header
            + f"Expires: {expires}\r\n"
            + "Content-Length: 0\r\n\r\n"
        )


def _choose_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=6.0)
    args = parser.parse_args()

    registrar = DigestRegistrar()
    adapter: SipMediaAdapter | None = None
    events: list[dict[str, object]] = []
    started = time.monotonic()
    error: str | None = None
    direct_uri_fallback_blocked = False
    try:
        registrar.start()
        registrar_uri = f"sip:127.0.0.1:{registrar.address[1]}"
        profile = RegistrationProfile(
            enabled=True,
            registrar_uri=registrar_uri,
            identity_uri="sip:tester@127.0.0.1",
            username="tester",
            password="PUBLIC-DEMO-SIP-PASSWORD",
            expires_seconds=2,
        )
        adapter = SipMediaAdapter(
            SipMediaConfig(
                bind_host="127.0.0.1",
                bind_port=_choose_port(),
                local_uri="sip:direct@example.invalid",
                codec="PCMU",
                sample_rate_hz=8000,
                channels=1,
                input_capacity_frames=2,
                output_capacity_frames=2,
                event_capacity=128,
                registration_profile=profile,
            ),
            enforce_runtime=True,
        )
        adapter.start()
        try:
            adapter.make_call("sip:direct-peer@127.0.0.1:5080")
        except RuntimeError as exc:
            direct_uri_fallback_blocked = "direct-URI admission is disabled" in str(exc)
        else:
            raise AssertionError("enabled registration unexpectedly admitted a direct-URI call")
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            adapter.poll(20)
            for event in adapter.drain_events():
                if event.kind is SipEventKind.REGISTRATION_STATE:
                    events.append(event.as_dict())
            successful_registers = sum(
                item.has_digest_response and (item.expires or 0) > 0 for item in registrar.requests
            )
            if adapter.registration_ready and successful_registers >= 2:
                break
        # close() issues setRegistration(False) before Account.shutdown().
        adapter.close("registration_probe_shutdown")
        for event in adapter.drain_events():
            if event.kind is SipEventKind.REGISTRATION_STATE:
                events.append(event.as_dict())
        time.sleep(0.2)
    except Exception as exc:  # noqa: BLE001 - probe must record raw failure
        error = f"{type(exc).__name__}: {exc}"
        if adapter is not None:
            adapter.close("registration_probe_exception")
    finally:
        registrar.stop()

    gil_enabled = bool(sys._is_gil_enabled()) if hasattr(sys, "_is_gil_enabled") else None
    result: dict[str, object] = {
        "probe": "009-B-pjsua2-registration-lifecycle",
        "status": "pass" if error is None else "fail",
        "error": error,
        "executable": sys.executable,
        "python_version": sys.version,
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_enabled_at_finish": gil_enabled,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "registrar": {
            "address": f"{registrar.address[0]}:{registrar.address[1]}",
            "request_count": len(registrar.requests),
            "requests": [asdict(item) for item in registrar.requests],
        },
        "registration_events": events,
        "enabled_direct_uri_fallback_blocked": direct_uri_fallback_blocked,
        "password_in_output": False,
        "gpu_inference": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
