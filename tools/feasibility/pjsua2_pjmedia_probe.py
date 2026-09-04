"""One-shot PJSUA2/PJMEDIA feasibility probe for the project target runtime."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import threading
from datetime import datetime, timezone
import time
import traceback
import warnings
from pathlib import Path


def gil_enabled() -> bool | None:
    checker = getattr(sys, "_is_gil_enabled", None)
    return None if checker is None else bool(checker())


def main() -> int:
    started_at = datetime.now(timezone.utc)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--call-uri")
    parser.add_argument("--call-seconds", type=float, default=3.0)
    parser.add_argument("--busy-seconds", type=float, default=0.0)
    parser.add_argument("--transfer-uri")
    parser.add_argument("--transfer-after", type=float, default=1.0)
    parser.add_argument("--callbacks", action="store_true")
    parser.add_argument("--stop-on-disconnect", action="store_true")
    parser.add_argument("--tone", action="store_true")
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()

    result: dict[str, object] = {
        "probe": "001-C1-pjsua2-pjmedia",
        "stage": "call" if "--call-uri" in sys.argv else "initialize",
        "command": " ".join(shlex.quote(argument) for argument in sys.argv),
        "working_directory": os.getcwd(),
        "started_at_utc": started_at.isoformat(),
        "pid": os.getpid(),
        "python": sys.version,
        "executable": sys.executable,
        "py_gil_disabled": sysconfig_value("Py_GIL_DISABLED"),
        "gil_before_import": gil_enabled(),
        "gil_after_import": None,
        "gil_after_initialization": None,
        "warnings": [],
        "import": {},
        "initialization": {},
        "call": {},
        "status": "fail",
    }

    import_ok = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            import pjsua2  # type: ignore[import-not-found]

            import_ok = True
            native_module = sys.modules.get("_pjsua2")
            result["import"] = {
                "status": "pass",
                "python_wrapper": getattr(pjsua2, "__file__", None),
                "native_module": getattr(native_module, "__file__", None),
            }
        except BaseException as exc:  # probe must preserve the concrete failure
            result["import"] = {
                "status": "fail",
                "exception": repr(exc),
                "traceback": traceback.format_exc(),
            }
        result["warnings"] = [
            {
                "category": warning.category.__name__,
                "message": str(warning.message),
            }
            for warning in caught
        ]

    result["gil_after_import"] = gil_enabled()

    if args.initialize and import_ok:
        endpoint = None
        started = time.perf_counter()
        try:
            endpoint = pjsua2.Endpoint()  # type: ignore[name-defined]
            endpoint.libCreate()
            ep_config = pjsua2.EpConfig()  # type: ignore[name-defined]
            ep_config.logConfig.level = 0
            endpoint.libInit(ep_config)
            result["initialization"] = {
                "status": "pass",
                "elapsed_seconds": time.perf_counter() - started,
            }
        except BaseException as exc:
            result["initialization"] = {
                "status": "fail",
                "exception": repr(exc),
                "traceback": traceback.format_exc(),
            }
        finally:
            # Keep the endpoint alive for the optional call probe.  Destroying
            # it here would make the subsequent transport/call operations use
            # an already-destroyed native PJSIP object.
            defer_destroy = args.call_uri and result["initialization"].get("status") == "pass"  # type: ignore[union-attr]
            if endpoint is not None and not defer_destroy:
                try:
                    endpoint.libDestroy()
                except BaseException as exc:
                    result["initialization_close_exception"] = repr(exc)
        result["gil_after_initialization"] = gil_enabled()

        if args.call_uri and result["initialization"].get("status") == "pass":  # type: ignore[union-attr]
            events: list[dict[str, object]] = []
            tone_generator = None
            tone_attempted = False
            capture_port = None
            capture_attempted = False
            call_media = None
            capture_stats = {"frames": 0, "bytes": 0, "checksum": 0}
            transfer_attempted = False
            busy_started = False
            busy_finished = False
            busy_thread = None

            if args.capture:
                class CapturingPort(pjsua2.AudioMediaPort):  # type: ignore[name-defined]
                    def onFrameReceived(self, frame: object) -> None:
                        size = int(frame.buf.size())  # type: ignore[union-attr]
                        capture_stats["frames"] += 1
                        capture_stats["bytes"] += size
                        if size:
                            sample = bytearray(size)
                            frame.buf.copy_to_bytearray(sample)  # type: ignore[union-attr]
                            capture_stats["checksum"] = (
                                capture_stats["checksum"] + sum(sample)
                            ) % 2**32

            if args.callbacks:
                class ObservedCall(pjsua2.Call):  # type: ignore[name-defined]
                    def onCallState(self, _prm: object) -> None:
                        try:
                            info = self.getInfo()
                            events.append(
                            {
                                "event": "call_state",
                                "timestamp": time.time(),
                                "state": getattr(info, "stateText", None),
                                "status_code": getattr(info, "lastStatusCode", None),
                                "call_id": getattr(info, "id", None),
                                }
                            )
                        except BaseException as exc:
                            events.append({"event": "call_state_error", "exception": repr(exc)})

                    def onCallMediaState(self, _prm: object) -> None:
                        try:
                            info = self.getInfo()
                            events.append(
                            {
                                "event": "call_media_state",
                                "timestamp": time.time(),
                                "media_count": getattr(info, "mediaCnt", None),
                                "media": [
                                    {
                                        "index": getattr(media, "index", None),
                                        "type": getattr(media, "type", None),
                                        "status": getattr(media, "status", None),
                                        "direction": getattr(media, "dir", None),
                                    }
                                    for media in info.media
                                ],
                                }
                            )
                        except BaseException as exc:
                            events.append({"event": "call_media_state_error", "exception": repr(exc)})
            else:
                ObservedCall = pjsua2.Call  # type: ignore[name-defined,assignment]

            account = None
            call = None
            try:
                print("call: transportCreate", flush=True)
                transport_config = pjsua2.TransportConfig()  # type: ignore[name-defined]
                transport_config.port = 5070
                endpoint.transportCreate(pjsua2.PJSIP_TRANSPORT_UDP, transport_config)  # type: ignore[name-defined]
                print("call: libStart", flush=True)
                endpoint.libStart()
                print("call: setNullDev", flush=True)
                endpoint.audDevManager().setNullDev()
                print("call: account.create", flush=True)
                account_config = pjsua2.AccountConfig()  # type: ignore[name-defined]
                account_config.idUri = "sip:tester@127.0.0.1"
                account = pjsua2.Account()  # type: ignore[name-defined]
                account.create(account_config)
                print("call: Call.makeCall", flush=True)
                call = ObservedCall(account)
                call.makeCall(args.call_uri, pjsua2.CallOpParam(True))  # type: ignore[name-defined]
                print("call: event loop", flush=True)
                deadline = time.monotonic() + max(args.call_seconds, 0.1)
                while time.monotonic() < deadline:
                    endpoint.libHandleEvents(10)
                    if args.busy_seconds > 0 and not busy_started:
                        try:
                            info = call.getInfo()
                            if getattr(info, "stateText", None) == "CONFIRMED":
                                busy_started = True
                                busy_deadline = time.monotonic() + args.busy_seconds

                                def busy_operation() -> None:
                                    nonlocal busy_finished
                                    while time.monotonic() < busy_deadline:
                                        time.sleep(0.05)
                                    busy_finished = True

                                busy_thread = threading.Thread(target=busy_operation, name="bounded-fixture", daemon=True)
                                busy_thread.start()
                                events.append(
                                    {
                                        "event": "busy_operation_started",
                                        "timestamp": time.time(),
                                        "duration_seconds": args.busy_seconds,
                                    }
                                )
                        except BaseException as exc:
                            busy_started = True
                            events.append({"event": "busy_operation_error", "exception": repr(exc)})
                    if args.transfer_uri and not transfer_attempted:
                        elapsed = max(args.call_seconds - (deadline - time.monotonic()), 0.0)
                        try:
                            info = call.getInfo()
                            if getattr(info, "stateText", None) == "CONFIRMED" and elapsed >= args.transfer_after:
                                transfer_attempted = True
                                call.xfer(args.transfer_uri, pjsua2.CallOpParam(True))  # type: ignore[name-defined]
                                events.append(
                                    {
                                        "event": "transfer_requested",
                                        "timestamp": time.time(),
                                        "destination": args.transfer_uri,
                                    }
                                )
                        except BaseException as exc:
                            transfer_attempted = True
                            events.append({"event": "transfer_error", "exception": repr(exc)})
                    if any(
                        event.get("event") == "call_state" and event.get("state") == "DISCONNECTED"
                        for event in events
                    ):
                        tone_attempted = True
                        capture_attempted = True
                    if args.tone and not tone_attempted:
                        try:
                            info = call.getInfo()
                            state_text = getattr(info, "stateText", None)
                            if state_text in {"CONFIRMED", "DISCONNECTED"}:
                                tone_attempted = True
                            if state_text == "CONFIRMED":
                                tone_generator = pjsua2.ToneGenerator()  # type: ignore[name-defined]
                                tone_generator.createToneGenerator(8000, 1)
                                tone = pjsua2.ToneDesc()  # type: ignore[name-defined]
                                tone.freq1 = 440
                                tone.freq2 = 0
                                tone.on_msec = 1000
                                tone.off_msec = 0
                                tone_list = pjsua2.ToneDescVector()  # type: ignore[name-defined]
                                tone_list.push_back(tone)
                                tone_generator.play(tone_list, True)
                                tone_generator.startTransmit(call.getAudioMedia(-1))
                                events.append({"event": "tone_started", "timestamp": time.time()})
                        except BaseException as exc:
                            events.append({"event": "tone_error", "exception": repr(exc)})
                    if args.capture and not capture_attempted and tone_generator is not None:
                        try:
                            capture_attempted = True
                            capture_port = CapturingPort()
                            capture_format = pjsua2.MediaFormatAudio()  # type: ignore[name-defined]
                            capture_format.type = pjsua2.PJMEDIA_TYPE_AUDIO  # type: ignore[name-defined]
                            capture_format.clockRate = 8000
                            capture_format.channelCount = 1
                            capture_format.bitsPerSample = 16
                            capture_format.frameTimeUsec = 20000
                            capture_port.createPort("probe-capture", capture_format)
                            call_media = call.getAudioMedia(-1)
                            call_media.startTransmit(capture_port)
                            events.append({"event": "capture_attached", "timestamp": time.time()})
                        except BaseException as exc:
                            events.append({"event": "capture_error", "exception": repr(exc)})
                    if args.stop_on_disconnect and any(
                        event.get("event") == "call_state" and event.get("state") == "DISCONNECTED"
                        for event in events
                    ):
                        break
                events.append({"event": "probe_window_complete", "timestamp": time.time()})
                peer_disconnected = any(
                    event.get("event") == "call_state" and event.get("state") == "DISCONNECTED"
                    for event in events
                )
                try:
                    print("call: hangup", flush=True)
                    if not peer_disconnected:
                        call.hangup(pjsua2.CallOpParam(True))  # type: ignore[name-defined]
                except BaseException as exc:
                    events.append({"event": "hangup_error", "exception": repr(exc)})
                result["call"] = {
                    "status": "pass",
                    "uri": args.call_uri,
                    "callbacks": args.callbacks,
                    "stop_on_disconnect": args.stop_on_disconnect,
                    "tone": args.tone,
                    "capture": args.capture,
                    "transfer_uri": args.transfer_uri,
                    "transfer_attempted": transfer_attempted,
                    "busy_seconds": args.busy_seconds,
                    "busy_operation_started": busy_started,
                    "busy_operation_finished": busy_finished,
                    "busy_operation_active_at_disconnect": busy_started and not busy_finished,
                    "capture_stats": capture_stats,
                    "peer_disconnected_before_local_hangup": peer_disconnected,
                    "events": events,
                    "gil_after_call": gil_enabled(),
                }
            except BaseException as exc:
                result["call"] = {
                    "status": "fail",
                    "uri": args.call_uri,
                    "events": events,
                    "exception": repr(exc),
                    "traceback": traceback.format_exc(),
                    "gil_after_call": gil_enabled(),
                }
            finally:
                # PJSUA2 object destructors call back into pjsua.  Release
                # them while the endpoint/library is still alive, otherwise
                # libDestroy() leaves their call/account ids invalid.
                call = None
                account = None
                call_media = None
                capture_port = None
                tone_generator = None
                result["gil_after_call"] = gil_enabled()
                if endpoint is not None:
                    try:
                        print("call: libDestroy", flush=True)
                        endpoint.libDestroy()
                    except BaseException as exc:
                        result["call_close_exception"] = repr(exc)
                    endpoint = None

    import_pass = result["import"].get("status") == "pass"  # type: ignore[union-attr]
    no_gil_pass = result["gil_before_import"] is False and result["gil_after_import"] is False
    initialization_pass = not args.initialize or (
        result["initialization"].get("status") == "pass"  # type: ignore[union-attr]
        and result["gil_after_initialization"] is False
    )
    call_pass = not args.call_uri or (
        result["call"].get("status") == "pass"  # type: ignore[union-attr]
        and result["call"].get("gil_after_call") is False  # type: ignore[union-attr]
    )
    result["status"] = "pass" if import_pass and no_gil_pass and initialization_pass and call_pass else "fail"
    result["exit_code"] = 0 if result["status"] == "pass" else 1
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["exit_code"])


def sysconfig_value(name: str) -> object:
    import sysconfig

    return sysconfig.get_config_var(name)


if __name__ == "__main__":
    raise SystemExit(main())
