"""Target-runtime C4 probe: live 002-B PCM output through C boundaries.

The approved Baresip peer supplies PCMU/8000/1 RTP.  PJMEDIA exposes the
negotiated media as PCM frames to the application port; this probe consumes
those real per-call frames through the public adapter handoff and validates
the C fan-out/chunker contract without starting any model or GPU runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path("/mnt/c/devel/sip-bot")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sip_bot.media import AsrChunker, FlushReason, PcmFanOut, encode_pcm_frame
from sip_bot.sip_media import SipEventKind, SipMediaAdapter, SipMediaConfig


ROOT = Path(__file__).resolve().parent
PEER_CONFIG = Path("/mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    peer_log_path = ROOT / "c4.peer.log"
    output_path = ROOT / "c4-target.json"
    command = "python3.14t -I artifacts/implementation/002-mvp-media-and-speech-integration/002-C/target_pcm_boundary_probe.py"
    peer_log = peer_log_path.open("w", encoding="utf-8")
    peer = subprocess.Popen(
        ["baresip", "-f", str(PEER_CONFIG), "-t", "12"],
        cwd="/usr/lib/baresip/modules",
        stdin=subprocess.DEVNULL,
        stdout=peer_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    adapter = SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:tester@127.0.0.1",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=100,
            output_capacity_frames=100,
            event_capacity=256,
        ),
        enforce_runtime=True,
    )
    events = []
    frames = []
    status = "fail"
    error = None
    profile = None
    try:
        time.sleep(1.0)
        adapter.start()
        adapter.make_call("sip:peer@127.0.0.1:5080", call_id="call-c4-boundary")
        deadline = time.monotonic() + 8.0
        answered_at = None
        while time.monotonic() < deadline:
            adapter.poll(20)
            events.extend(adapter.drain_events())
            profile = adapter.media_profile()
            while True:
                item = adapter.next_ingress_frame()
                if item is None:
                    break
                frames.append(item)
            if answered_at is None and any(item.kind is SipEventKind.CALL_ANSWERED for item in events):
                answered_at = time.monotonic()
            if answered_at is not None and time.monotonic() - answered_at >= 2.0 and frames:
                break
        if profile is None:
            raise AssertionError("live call did not publish NegotiatedMediaProfile")
        if not frames:
            raise AssertionError("live Baresip PCMU call did not deliver PCM frames to 002-C")

        fanout = PcmFanOut(capacity_frames=100, generation=frames[0].generation)
        vad = fanout.subscribe("vad")
        asr_input = fanout.subscribe("asr_input_accumulator")
        outcomes = [fanout.publish(item) for item in frames]
        fanout_frames = []
        while (item := asr_input.get_nowait()) is not None:
            fanout_frames.append(item)
        if len(fanout_frames) != len(frames):
            raise AssertionError("ASR fan-out did not preserve live frame count")
        if vad.qsize() != len(frames):
            raise AssertionError("VAD fan-out did not receive an independent live stream")

        chunker = AsrChunker(
            profile=profile,
            call_id=frames[0].call_id,
            channel_id=frames[0].channel_id,
            generation=frames[0].generation,
            chunk_ms=1000,
            flush_ms=1000,
        )
        for item in fanout_frames:
            chunker.push(item)
        chunker.flush(FlushReason.HARD_ENDPOINT, is_final=True)
        chunks = []
        while (chunk := chunker.next_chunk()) is not None:
            chunks.append(chunk)
        if not chunks:
            raise AssertionError("ASR chunker did not flush live PCM tail")

        encoded_first = encode_pcm_frame(frames[0])
        status = "pass"
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        chunks = []
        encoded_first = b""
    finally:
        stats = adapter.media_stats()
        try:
            if adapter.active_call_id is not None:
                adapter.hangup()
                for _ in range(100):
                    adapter.poll(10)
                    if adapter.active_call_id is None:
                        break
        except BaseException:
            pass
        adapter.close()
        if peer.poll() is None:
            peer.terminate()
            try:
                peer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                peer.kill()
                peer.wait(timeout=5)
        peer_log.close()

    result = {
        "evidence_id": "C-E-c4-target-pcm-boundary",
        "plan": "002-C",
        "stage": "C4",
        "status": status,
        "command": command,
        "started_at_utc": now(),
        "runtime": {
            "executable": "/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t",
            "free_threaded": True,
        },
        "candidate": "PJSUA2/PJMEDIA 2.17 with approved Baresip 001-S PCMU peer",
        "media_profile": profile.as_dict() if profile is not None else None,
        "live_pcm_frames": len(frames),
        "fanout_published": len(frames) if frames else 0,
        "fanout_delivery": {
            "vad_frames": len(frames) if frames else 0,
            "asr_frames": len(frames) if frames else 0,
        },
        "chunks": [item.as_dict() for item in chunks],
        "encoded_first_pcm_frame_bytes": len(encoded_first),
        "media_stats": stats,
        "events": [item.as_dict() for item in events],
        "peer_log": str(peer_log_path),
        "error": error,
        "audio_recording": False,
        "finished_at_utc": now(),
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "live_pcm_frames": len(frames), "chunks": len(chunks), "error": error}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
