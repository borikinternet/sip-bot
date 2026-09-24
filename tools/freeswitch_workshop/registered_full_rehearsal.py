#!/usr/bin/env python3
"""Run the full AI rehearsal through a registered FreeSWITCH endpoint.

The existing J4 gate owns the accepted full conversation scenario.  This
thin workshop adapter changes only its transport fixture and call admission:
the peer registers at the local FreeSWITCH registrar, calls extension 7000,
and the bot admits the incoming call through ``IncomingCallReadinessGate``.
The model/RAG/ASR/TTS owners and the conversation scenario remain the
existing J4 implementation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from typing import Any, Final


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSHOP_PEER_TEMPLATE = PROJECT_ROOT / "tools" / "freeswitch_workshop" / "config" / "baresip-peer"
REGISTERED_FIXTURE_SOURCE = (
    PROJECT_ROOT
    / "artifacts"
    / "implementation"
    / "008-vad-turn-calibration"
    / "008-C"
    / "j4-full-live-20260913-r1"
    / "live-stand"
    / "input-scenario.wav"
)
REGISTERED_FIXTURE_TRAILING_SILENCE_S: Final[float] = 30.0
# The registered runner starts from the durable compact-demo fixture because
# its call admission is background/readiness driven.  Its old turn-2 ->
# turn-3 gap is 2.5 s; insert 4 s at the known turn-3 boundary to keep the
# registered fixture aligned with the current 6.5 s deterministic profile and
# leave audible time for the bot answer before the scripted interruption.
REGISTERED_BARGE_IN_INSERT_AT_S: Final[float] = 23.0
REGISTERED_BARGE_IN_SHIFT_S: Final[float] = 4.0
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, TARGET_SITE)

from map005_stereo_recording import build_stereo  # noqa: E402
from map010_rtp_continuity import audit_registered_result, parse_baresip_audio_summary  # noqa: E402


def _prepare_continuous_fixture(source: Path, target: Path, trailing_silence_s: float) -> None:
    """Keep the Baresip aufile source clock alive after the last user turn."""

    if trailing_silence_s < 0:
        raise ValueError("trailing fixture silence must not be negative")
    with wave.open(str(source), "rb") as stream:
        params = stream.getparams()
        frames = stream.readframes(stream.getnframes())
    trailing_frames = round(trailing_silence_s * params.framerate)
    suffix = b"\x00" * (trailing_frames * params.nchannels * params.sampwidth)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setparams(params)
        stream.writeframes(frames + suffix)


def _insert_silence(source: Path, target: Path, *, at_s: float, duration_s: float) -> None:
    """Insert a deterministic pause into the registered demo fixture."""

    if at_s < 0 or duration_s < 0:
        raise ValueError("fixture silence position and duration must not be negative")
    with wave.open(str(source), "rb") as stream:
        params = stream.getparams()
        frames = stream.readframes(stream.getnframes())
    frame_width = params.nchannels * params.sampwidth
    insert_at = min(round(at_s * params.framerate), len(frames) // frame_width) * frame_width
    inserted_frames = round(duration_s * params.framerate)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setparams(params)
        stream.writeframes(frames[:insert_at] + b"\x00" * (inserted_frames * frame_width) + frames[insert_at:])


def _registered_peer_config(
    root: Path,
    fixture_path: Path,
    recording_dir: Path,
    *,
    registrar_address: str,
    peer_user: str,
    peer_password: str,
) -> Path:
    peer_config = root / "peer-5080"
    shutil.copytree(WORKSHOP_PEER_TEMPLATE, peer_config)
    (peer_config / "uuid").unlink(missing_ok=True)
    config_path = peer_config / "config"
    config = config_path.read_text(encoding="utf-8")
    lines = []
    for line in config.splitlines():
        if line.startswith("audio_source"):
            lines.append(f"audio_source      aufile,{fixture_path}")
        else:
            lines.append(line)
    if "module            sndfile.so" not in config:
        lines.append("module            sndfile.so")
    lines.append(f"snd_path          {recording_dir}")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (peer_config / "accounts").write_text(
        f"<sip:{peer_user}@{registrar_address}>;auth_user={peer_user};"
        f"auth_pass={peer_password};regint=300;answermode=auto;"
        "audio_codecs=PCMU/8000/1\n",
        encoding="utf-8",
    )
    return peer_config


def _collect_recording(
    recording_dir: Path,
    output_root: Path,
    *,
    expected_ptime_ms: float | None = None,
    call_window_ms: float | None = None,
    call_window_start_ns: int | None = None,
) -> dict[str, object]:
    """Copy Baresip raw tracks and build the event-window stereo derivative."""

    raw_root = output_root / "recordings" / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in sorted(recording_dir.glob("*.wav")):
        target = raw_root / source.name
        shutil.copy2(source, target)
        copied.append(target)
    enc = next((path for path in copied if path.name.endswith("-enc.wav")), None)
    dec = next((path for path in copied if path.name.endswith("-dec.wav")), None)
    if enc is None or dec is None:
        return {
            "status": "fail",
            "error": "Baresip sndfile did not produce both *-enc.wav and *-dec.wav",
            "files": [str(path) for path in copied],
        }
    try:
        return build_stereo(
            enc,
            dec,
            output_root / "recordings" / "conversation-stereo.wav",
            output_root / "recordings" / "recording-manifest.json",
            expected_ptime_ms=expected_ptime_ms,
            call_window_ms=call_window_ms,
            call_window_start_ns=call_window_start_ns,
        )
    except Exception as exc:  # noqa: BLE001 - evidence records the concrete audit failure
        return {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}


async def _run(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    import j4_full_live_gate
    from config import constants
    from sip_bot.runtime import ApplicationRuntime
    from sip_bot.runtime_wiring import IncomingCallReadinessGate

    state: dict[str, Any] = {"popen_commands": [], "popen_processes": []}
    original_prepare = j4_full_live_gate._prepare_peer_config
    original_sink = j4_full_live_gate._RecordingSink
    original_popen = subprocess.Popen
    original_make_call = j4_full_live_gate.SipMediaAdapter.make_call
    original_create_wiring = ApplicationRuntime.create_call_wiring
    original_configure_warmup = ApplicationRuntime.configure_warmup
    original_registration_enabled = constants.SIP_REGISTRATION_ENABLED
    recording_dir = Path(tempfile.mkdtemp(prefix="sip-bot-010-c-recording-", dir="/tmp"))
    recording_dir.mkdir(parents=True, exist_ok=True)
    continuous_fixture_path = recording_dir / "input-scenario-with-continuity-tail.wav"
    shifted_fixture_path = recording_dir / "input-scenario-with-barge-in-shift.wav"
    _insert_silence(
        Path(args.fixture_source).resolve(),
        shifted_fixture_path,
        at_s=args.barge_in_insert_at_s,
        duration_s=args.barge_in_shift_s,
    )
    _prepare_continuous_fixture(
        shifted_fixture_path,
        continuous_fixture_path,
        args.continuity_tail_s,
    )

    def prepare(root: Path, fixture_path: Path) -> Path:
        # Keep J4's normal fixture-copy path.  In particular, its leading
        # silence must be applied before the registered peer starts consuming
        # the file; pointing the peer directly at the source would make the
        # source clock run during registration/readiness and invalidate the
        # audio-vs-FSM timing check.
        return _registered_peer_config(
            root,
            fixture_path,
            recording_dir,
            registrar_address=args.registrar_address,
            peer_user=args.peer_user,
            peer_password=args.peer_password,
        )

    class RecordingSinkWithAdmission:
        def __init__(self, dispatcher: Any, events: list[Any]) -> None:
            self._delegate = original_sink(dispatcher, events)

        def publish(self, event: Any) -> None:
            if (
                getattr(event, "kind", None) == "protocol_reply"
                and getattr(event, "method", None) == "INVITE"
                and getattr(event, "status_code", None) == 200
                and getattr(event, "call_id", None) != "__registration__"
            ):
                # The raw Baresip recording names carry local wall-clock
                # creation time.  Keep the corresponding answer wall-clock
                # before the temporary peer directory is removed so the
                # stereo builder can align both directions to 200 OK.
                state["answer_wall_time_ns"] = time.time_ns()
            if getattr(event, "call_id", None) == "__registration__":
                # Registration status is adapter/runtime control, not a
                # call-scoped Dispatcher event. Keep it in the evidence list
                # without violating the active CallSession contract.
                self._delegate.events.append(event)
            else:
                self._delegate.events.append(event)
                wiring = state.get("wiring")
                if wiring is None:
                    raise RuntimeError("registered event arrived before live wiring was bound")
                expected_call_id = wiring.composition.session.call_id
                if event.call_id != expected_call_id:
                    raise RuntimeError(
                        "incoming adapter call id "
                        f"{event.call_id!r} is not bound to active composition {expected_call_id!r}"
                    )
                wiring._on_sip_event(event)
            admission = state.get("admission")
            if admission is not None:
                admission.observe(event)

    def capture_peer(process_args: Any, *popen_args: Any, **kwargs: Any) -> Any:
        command = process_args if isinstance(process_args, (list, tuple)) else []
        command_text = " ".join(str(item) for item in command)
        popen_kwargs = dict(kwargs)
        if "peer-5080" in command_text:
            popen_kwargs["stdin"] = subprocess.PIPE
        process = original_popen(process_args, *popen_args, **popen_kwargs)
        state["popen_commands"].append(command_text)
        state["popen_processes"].append((command_text, process))
        if command_text.startswith("baresip ") and sum(
            1 for item in state["popen_commands"] if item.startswith("baresip ")
        ) == 2:
            state["peer"] = process
        return process

    def make_incoming_call(adapter: Any, _target: str, *, call_id: str | None = None) -> bool:
        peer = state.get("peer")
        if peer is None or peer.stdin is None:
            raise RuntimeError("registered Baresip peer is not available")
        registration_deadline = time.monotonic() + 15.0
        while not adapter.registration_ready and time.monotonic() < registration_deadline:
            adapter.poll(20)
            time.sleep(0.02)
        if not adapter.registration_ready:
            raise RuntimeError("bot registration did not become ready before incoming call")
        if args.prewarm:
            readiness = state.get("readiness")
            if readiness is None:
                raise RuntimeError("prewarm was requested but no readiness coordinator was configured")
            if not readiness.ready:
                snapshot = readiness.snapshot()
                raise RuntimeError(
                    "registered call was requested before prewarm reached READY: "
                    f"{snapshot.state.value}"
                )
        peer.stdin.write(f"d sip:{args.target_extension}@{args.registrar_address}\n")
        peer.stdin.flush()
        state["incoming_call_requested"] = True
        return True

    def configure_warmup(runtime: ApplicationRuntime, *warmup_args: Any, **warmup_kwargs: Any) -> Any:
        readiness = original_configure_warmup(runtime, *warmup_args, **warmup_kwargs)
        state["readiness"] = readiness
        return readiness

    def create_wiring(
        runtime: ApplicationRuntime,
        composition: Any,
        *,
        sip_media: Any,
        speech: Any,
        asr: Any,
        pipeline: Any,
        incoming_admission: Any | None = None,
        latency_sink: Any | None = None,
    ) -> Any:
        readiness = runtime.readiness
        if readiness is None:
            raise RuntimeError("registered replay requires configured runtime readiness coordinator")
        admission = IncomingCallReadinessGate(
            sip_media,
            readiness=readiness,
        )
        state["admission"] = admission
        wiring = original_create_wiring(
            runtime,
            composition,
            sip_media=sip_media,
            speech=speech,
            asr=asr,
            pipeline=pipeline,
            incoming_admission=admission,
            latency_sink=latency_sink,
        )
        state["wiring"] = wiring
        return wiring

    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    constants.SIP_REGISTRATION_ENABLED = True
    j4_full_live_gate._prepare_peer_config = prepare
    j4_full_live_gate._RecordingSink = RecordingSinkWithAdmission
    j4_full_live_gate.SipMediaAdapter.make_call = make_incoming_call
    ApplicationRuntime.create_call_wiring = create_wiring
    ApplicationRuntime.configure_warmup = configure_warmup
    subprocess.Popen = capture_peer
    try:
        j4_exit_code = await j4_full_live_gate._run(
            argparse.Namespace(
                output_root=output_root,
                timeout_s=args.timeout_s,
                post_report_grace_s=args.post_report_grace_s,
                warmup_mode="background",
                defer_composition=True,
                trigger_background_warmup=args.prewarm,
                fixture_source=continuous_fixture_path,
                fixture_leading_silence_s=args.fixture_leading_silence_s,
                warmup_question=args.warmup_question,
                require_barge_in=not args.skip_barge_in_check,
            )
        )
        result_path = output_root / "j4-full-live.json"
        if not result_path.exists():
            raise RuntimeError("J4 runner did not write j4-full-live.json")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        fixture = result.get("fixture")
        if isinstance(fixture, dict):
            fixture["source_path"] = str(continuous_fixture_path)
            fixture["trailing_silence_s"] = args.continuity_tail_s
            fixture["fixture_generation"] = "prepared scenario with configurable barge-in shift and continuity tail"
            fixture["barge_in_shift_s"] = args.barge_in_shift_s
            fixture["continuity_tail_purpose"] = "keep Baresip aufile transmitting until the bot finishes its final response"
        peer_log_text = Path(result["peer_log"]).read_text(encoding="utf-8", errors="replace")
        rtp_continuity = audit_registered_result(
            result,
            baresip_summary=parse_baresip_audio_summary(peer_log_text),
            external_pbx=args.external_pbx,
        )
        adapter_profile = result.get("sip", {}).get("adapter_profile") or {}
        recording = _collect_recording(
            recording_dir,
            output_root,
            expected_ptime_ms=adapter_profile.get("ptime_ms"),
            call_window_ms=(rtp_continuity.get("window", {}).get("elapsed_ms")),
            call_window_start_ns=state.get("answer_wall_time_ns"),
        )
        checks = dict(result.get("scenario_checks", {}))
        checks["rtp_continuity_present"] = rtp_continuity.get("status") == "pass"
        checks["stereo_recording_present"] = recording.get("status") == "pass"
        result["scenario_checks"] = checks
        result["acceptance_checks"] = {
            key: value
            for key, value in checks.items()
            if key != "stereo_recording_present"
        }
        result["diagnostic_checks"] = {
            "stereo_recording_present": checks["stereo_recording_present"],
            "stereo_recording_required_for_rtp_continuity": False,
        }
        result["rtp_continuity"] = rtp_continuity
        result["recording"] = recording
        result["audio_recording"] = recording.get("status") == "pass"
        result["notes"] = [
            note
            for note in result.get("notes", [])
            if "not a conversation recording" not in note
        ] + [
            "Baresip test peer sndfile raw enc/dec tracks are retained under recordings/raw.",
            "conversation-stereo.wav maps left=user_to_bot and right=bot_to_user; its target duration is the answered-call event window and alignment is explicit in recording-manifest.json.",
            "The registered input fixture includes an explicit 30 s trailing continuity tail for the Baresip aufile source.",
            "RTP continuity acceptance uses the answered-call event window and negotiated ptime; enc/dec WAV duration is diagnostic only.",
        ]
        result["status"] = (
            "pass"
            if result.get("status") == "pass" and all(result["acceptance_checks"].values()) and not result.get("errors")
            else "fail"
        )
        result["registration_mode"] = "enabled"
        result["external_pbx"] = args.external_pbx
        result["registered_peer"] = {
            "registrar_address": args.registrar_address,
            "user": args.peer_user,
            "target_extension": args.target_extension,
        }
        result["incoming_admission"] = {
            "gate": "IncomingCallReadinessGate",
            "incoming_call_requested": bool(state.get("incoming_call_requested")),
            "runtime_ready_at_replay_end": bool(state.get("admission") and state["admission"].readiness.ready),
            "readiness_state_at_replay_end": (
                state["admission"].readiness.state.value if state.get("admission") is not None else None
            ),
            "prewarm_triggered": bool(args.prewarm),
            "policy": (
                f"registered peer calls {args.target_extension}; "
                "prewarm mode waits for aggregate readiness before dial"
            ),
        }
        result["wrapper_debug"] = {
            "popen_commands": list(state["popen_commands"]),
            "peer_captured": state.get("peer") is not None,
        }
        output_path = output_root / "registered-j4-full-live.json"
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result, 0 if result["status"] == "pass" else 1
    finally:
        j4_full_live_gate._prepare_peer_config = original_prepare
        j4_full_live_gate._RecordingSink = original_sink
        j4_full_live_gate.SipMediaAdapter.make_call = original_make_call
        ApplicationRuntime.create_call_wiring = original_create_wiring
        ApplicationRuntime.configure_warmup = original_configure_warmup
        subprocess.Popen = original_popen
        constants.SIP_REGISTRATION_ENABLED = original_registration_enabled
        shutil.rmtree(recording_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=300.0)
    parser.add_argument("--post-report-grace-s", type=float, default=5.0)
    parser.add_argument("--prewarm", action="store_true", help="start the shared warmup before the incoming call")
    parser.add_argument("--registrar-address", default="127.0.0.1:5060")
    parser.add_argument("--peer-user", default="peer")
    parser.add_argument("--peer-password", default="PUBLIC-DEMO-SIP-PASSWORD")
    parser.add_argument("--target-extension", default="7000")
    parser.add_argument("--external-pbx", action="store_true")
    parser.add_argument("--skip-barge-in-check", action="store_true")
    parser.add_argument("--fixture-source", type=Path, default=REGISTERED_FIXTURE_SOURCE)
    parser.add_argument(
        "--warmup-question",
        default="Сколько стоит диагностический выезд мастера?",
    )
    parser.add_argument("--barge-in-insert-at-s", type=float, default=REGISTERED_BARGE_IN_INSERT_AT_S)
    parser.add_argument("--barge-in-shift-s", type=float, default=REGISTERED_BARGE_IN_SHIFT_S)
    parser.add_argument("--continuity-tail-s", type=float, default=REGISTERED_FIXTURE_TRAILING_SILENCE_S)
    parser.add_argument(
        "--fixture-leading-silence-s",
        type=float,
        default=45.0,
        help="delay prerecorded speech so it is not sent before incoming 200 OK",
    )
    args = parser.parse_args()
    result, exit_code = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
