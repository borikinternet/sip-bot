#!/usr/bin/env python3
"""Main-only clean-start full J4 live scenario gate.

The caller is one real Baresip SIP/RTP call.  Its generated input fixture
contains several user turns with controlled pauses; the bot must process the
turns through the live SIP/media wiring, including a playback interruption,
source-aware context continuation and a confirmed transfer to the local
fake-operator peer.  Generated input audio and TTS output are test artifacts,
not conversation recordings.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import wave
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, TARGET_SITE)

from config import constants  # noqa: E402
from live_i1_gate import (  # noqa: E402
    C2_MODEL,
    C2_SITE,
    XTTS_MODEL,
    _AmplitudeVad,
    _RealXttsEngine,
    _RecordingAsrBackend,
    _RecordingSink,
    _profile,
    _prompt,
)
from demo_fixture_timing import J4_SCENARIO_SPECS  # noqa: E402
from sip_bot.context import ContextSnapshot, ContextStore  # noqa: E402
from sip_bot.conversation_pipeline import ConversationPipeline  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.media import AsrChunker  # noqa: E402
from sip_bot.prompt import SkillPromptManager  # noqa: E402
from sip_bot.report import ReportFinalizer  # noqa: E402
from sip_bot.retrieval import KnowledgeQueryBuilder, LocalKnowledgeIndex, load_corpus  # noqa: E402
from sip_bot.runtime import ApplicationRuntime  # noqa: E402
from sip_bot.runtime_composition import CallOwners  # noqa: E402
from sip_bot.runtime_wiring import CallRuntimeWiring  # noqa: E402
from sip_bot.sip_media import SipMediaAdapter, SipMediaConfig  # noqa: E402
from sip_bot.sip_media.protocol_events import NormalizedSipEvent  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    EndpointingConfig,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TurnDetector,
    VadProcessor,
)
from sip_bot.tts import ApprovedTextChunk, XttsV2Adapter  # noqa: E402
from sip_bot.transfer import FakeOperator, TransferOrchestrator  # noqa: E402


OPERATOR_CONFIG = PROJECT_ROOT / "artifacts" / "feasibility" / "001-S-voip-test-stand" / "config" / "operator-5090"
PEER_CONFIG_TEMPLATE = PROJECT_ROOT / "artifacts" / "feasibility" / "001-S-voip-test-stand" / "config" / "peer-5080"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_wav(path: Path, pcm: bytes, sample_rate_hz: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate_hz)
        stream.writeframes(pcm)


def _silence(seconds: float, profile: Any) -> bytes:
    if seconds < 0:
        raise ValueError("silence duration must not be negative")
    frame_count = round(seconds * profile.sample_rate_hz / profile.frame_size_samples)
    return b"\x00" * (frame_count * profile.frame_bytes)


def _render_user_turn(tts: XttsV2Adapter, text: str, number: int, profile: Any) -> bytes:
    approved = ApprovedTextChunk(
        operation_id=f"j4-fixture-operation-{number}",
        call_id="j4-fixture-call",
        turn_id=f"j4-fixture-turn-{number}",
        generation=1,
        sequence=1,
        text=text,
        is_final=True,
    )
    return b"".join(
        chunk.pcm_s16le
        for chunk in tts.stream_approved_text(
            (approved,),
            channel_id="j4-fixture-call:media",
            profile=profile,
        )
    )


def _make_scenario_fixture(tts: XttsV2Adapter, profile: Any, path: Path) -> dict[str, object]:
    """Render one caller fixture with timing windows for all mandatory turns."""

    # Turn 3 starts shortly after turn 2, while the answer is expected to be
    # audible.  This is deliberate: the live VAD-to-FSM edge must classify it
    # as barge-in and cancel the old playback generation.
    specs = J4_SCENARIO_SPECS
    pcm = bytearray()
    segments: list[dict[str, object]] = []
    timeline_s = 0.0
    for number, (turn_id, text, leading_s, trailing_s) in enumerate(specs, start=1):
        leading = _silence(leading_s, profile)
        pcm.extend(leading)
        timeline_s += len(leading) / (profile.sample_rate_hz * profile.channels * 2)
        speech_started_s = timeline_s
        speech = _render_user_turn(tts, text, number, profile)
        pcm.extend(speech)
        speech_duration_s = len(speech) / (profile.sample_rate_hz * profile.channels * 2)
        timeline_s += speech_duration_s
        pcm.extend(_silence(trailing_s, profile))
        timeline_s += trailing_s
        segments.append(
            {
                "turn_id": turn_id,
                "text": text,
                "speech_started_s": round(speech_started_s, 3),
                "speech_duration_s": round(speech_duration_s, 3),
                "leading_s": leading_s,
                "trailing_s": trailing_s,
            }
        )
    _write_wav(path, bytes(pcm), profile.sample_rate_hz)
    return {
        "path": str(path),
        "bytes": len(pcm),
        "sha256": hashlib.sha256(pcm).hexdigest(),
        "sample_rate_hz": profile.sample_rate_hz,
        "channels": profile.channels,
        "duration_s": round(timeline_s, 3),
        "segments": segments,
        "source": "local XTTS-generated multi-turn fixture; not a call recording",
        "timing_profile": "compact-demo-v1",
    }


def _prepare_peer_config(root: Path, fixture_path: Path) -> Path:
    peer_config = root / "peer-5080"
    shutil.copytree(PEER_CONFIG_TEMPLATE, peer_config)
    (peer_config / "uuid").unlink(missing_ok=True)
    config_path = peer_config / "config"
    config = config_path.read_text(encoding="utf-8")
    config = re.sub(r"^module\s+ausine\.so\s*$", "module            aufile.so", config, flags=re.MULTILINE)
    config = re.sub(r"^audio_source\s+.*$", f"audio_source      aufile,{fixture_path}", config, flags=re.MULTILINE)
    config = re.sub(r"^ausrc_srate\s+.*$", "ausrc_srate       8000", config, flags=re.MULTILINE)
    config = re.sub(r"^ausrc_channels\s+.*$", "ausrc_channels    1", config, flags=re.MULTILINE)
    config_path.write_text(config, encoding="utf-8")
    return peer_config


def _load_context(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


async def _run(args: argparse.Namespace) -> dict[str, object]:
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"full live gate output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    live_root = output_root / "live-stand"
    fixture_path = live_root / "input-scenario.wav"
    # Baresip has a bounded configuration-line buffer. Keep the durable
    # fixture in the evidence directory, but expose a short path to the
    # peer so a deep Windows-mounted artifact path is not truncated.
    peer_fixture_path = Path("/tmp/sip-bot-j4-input-scenario.wav")
    peer_fixture_path.unlink(missing_ok=True)
    peer_config = _prepare_peer_config(live_root, peer_fixture_path)
    peer_log_path = output_root / "baresip-peer.log"
    operator_log_path = output_root / "baresip-operator.log"
    operator_call_log_path = output_root / "operator-transfer.log"
    call_id = "j4-full-live-call"
    profile = _profile()
    sys.path.append(C2_SITE)

    # The live gate is an acceptance probe, so generation must be reproducible
    # across clean-start runs.  Keep the project default unchanged for normal
    # operation, but remove sampling noise from this deterministic scenario.
    llm = LlmFacade(OllamaHttpClient(endpoint=constants.LLM_HTTP_ENDPOINT, temperature=0.0))
    prompt = _prompt()
    started_ns = time.monotonic_ns()
    call_started_ns: int | None = None
    report_seen_ns: int | None = None
    error: str | None = None
    fixture: dict[str, object] = {}
    warmup_report: Any | None = None
    events: list[NormalizedSipEvent] = []
    peer: subprocess.Popen[str] | None = None
    operator: subprocess.Popen[str] | None = None
    peer_log = peer_log_path.open("w", encoding="utf-8")
    operator_log = operator_log_path.open("w", encoding="utf-8")
    adapter: SipMediaAdapter | None = None
    wiring: CallRuntimeWiring | None = None
    runtime: ApplicationRuntime | None = None
    composition: Any | None = None
    pipeline: ConversationPipeline | None = None
    transfer_owner: FakeOperator | None = None
    asr_backend: _RecordingAsrBackend | None = None
    profile_snapshot: Any | None = None
    try:
        runtime = ApplicationRuntime.from_constants()
        runtime.start()
        index_holder: dict[str, LocalKnowledgeIndex] = {}
        tts_holder: dict[str, XttsV2Adapter] = {}
        fixture_holder: dict[str, dict[str, object]] = {}
        asr_backend = _RecordingAsrBackend(C2_MODEL)
        query_builder = KnowledgeQueryBuilder()

        def warm_rag_index() -> dict[str, object]:
            _, corpus_chunks = load_corpus(PROJECT_ROOT / constants.KNOWLEDGE_CORPUS_PATH)
            index_holder["index"] = LocalKnowledgeIndex.build(
                corpus_chunks,
                llm,
                index_version=constants.RAG_INDEX_VERSION,
                embedding_model=constants.RAG_EMBEDDING_MODEL,
            )
            return {"chunks": len(corpus_chunks), "embedding_model": constants.RAG_EMBEDDING_MODEL}

        def warm_llm_chat() -> dict[str, object]:
            knowledge = index_holder["index"].query(
                query_builder.build("Почему небо днём кажется голубым?"),
                llm,
                top_k=constants.RAG_TOP_K,
                threshold=constants.RAG_RELEVANCE_THRESHOLD,
                context_id="j4-full-live-warmup-knowledge",
            )
            request = prompt.prepare(
                call_id="j4-full-live-warmup",
                turn_id="j4-full-live-warmup:turn-1",
                final_user_text="Проверка готовности модели.",
                snapshot=ContextSnapshot("j4-full-live-warmup", 0, ()),
                knowledge_context=knowledge,
            )
            return {"sources": list(knowledge.source_ids), "trace": llm.warmup(request).as_dict()}

        def initialize_tts() -> dict[str, object]:
            tts_holder["tts"] = XttsV2Adapter(
                _RealXttsEngine(XTTS_MODEL, XTTS_MODEL / "samples" / "en_sample.wav"),
                operation_id_factory=lambda: "j4-full-live-tts",
            )
            return {"initialized": True}

        def warm_tts() -> dict[str, object]:
            return tts_holder["tts"].warmup(profile=profile)

        def build_fixture() -> dict[str, object]:
            fixture_holder["fixture"] = _make_scenario_fixture(tts_holder["tts"], profile, fixture_path)
            return {"path": str(fixture_path), "bytes": fixture_holder["fixture"]["bytes"]}

        warmup_report = runtime.warmup(
            (
                ("rag-embedding-index", warm_rag_index),
                ("llm-chat", warm_llm_chat),
                ("asr", lambda: asr_backend.warmup(input_sample_rate_hz=profile.sample_rate_hz)),
                ("tts-initialize", initialize_tts),
                ("tts-stream", warm_tts),
                ("fixture", build_fixture),
            )
        )
        index = index_holder["index"]
        tts = tts_holder["tts"]
        fixture = fixture_holder["fixture"]
        shutil.copy2(fixture_path, peer_fixture_path)

        operator = subprocess.Popen(
            ["baresip", "-f", str(OPERATOR_CONFIG), "-t", str(args.timeout_s + 30)],
            cwd="/usr/lib/baresip/modules",
            stdout=operator_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        peer = subprocess.Popen(
            ["baresip", "-f", str(peer_config), "-t", str(args.timeout_s + 30)],
            cwd="/usr/lib/baresip/modules",
            stdout=peer_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        await asyncio.sleep(1.5)

        adapter = SipMediaAdapter(
            SipMediaConfig.from_runtime_config(
                runtime.config,
                local_uri="sip:tester@127.0.0.1",
                bind_port=5070,
            ),
            enforce_runtime=True,
        )
        adapter.start()
        transfer_owner = FakeOperator(constants.OPERATOR_TARGET)
        transfer = TransferOrchestrator(transfer_owner)
        owners = CallOwners(
            context=ContextStore(output_root / "context", call_id),
            report=ReportFinalizer(output_root / "reports"),
            retrieval=index,
            prompt=prompt,
            llm=llm,
            tts=tts,
            transfer=transfer,
        )
        composition = runtime.compose_call(call_id, owners)
        pipeline = ConversationPipeline(
            composition,
            query_builder=query_builder,
            retrieval=index,
            prompt=prompt,
            llm=llm,
            tts=tts,
            media_profile=adapter.media_profile,
            transfer=transfer,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
        )
        wiring = runtime.create_call_wiring(
            composition,
            sip_media=adapter,
            speech=SpeechIngress(
                vad=VadProcessor(_AmplitudeVad()),
                turn_detector=TurnDetector(
                    EndpointingConfig(
                        soft_endpoint_ms=constants.ENDPOINT_SOFT_MS,
                        hard_endpoint_ms=constants.ENDPOINT_HARD_MS,
                        min_speech_ms=constants.MIN_SPEECH_MS,
                    )
                ),
                assembler=TranscriptAssembler(
                    call_id,
                    f"{call_id}:media",
                    1,
                    f"{call_id}:turn-1",
                    constants.TRANSCRIPT_STABLE_PREFIX_MIN_CHARS,
                ),
                assembler_factory=lambda turn_id: TranscriptAssembler(
                    call_id,
                    f"{call_id}:media",
                    1,
                    turn_id,
                    constants.TRANSCRIPT_STABLE_PREFIX_MIN_CHARS,
                ),
                defer_endpoint_finalization=True,
            ),
            asr=StreamingAsrAdapter(asr_backend),
            pipeline=pipeline,
        )
        adapter.event_sink = _RecordingSink(composition.dispatcher, events)
        wiring.start()
        call_started_ns = time.monotonic_ns()
        adapter.make_call("sip:peer@127.0.0.1:5080", call_id=call_id)

        deadline = time.monotonic() + args.timeout_s
        while time.monotonic() < deadline:
            await wiring.step()
            if wiring.errors or pipeline.errors:
                raise RuntimeError("; ".join(wiring.errors + pipeline.errors))
            if composition.report_finalized:
                if report_seen_ns is None:
                    report_seen_ns = time.monotonic_ns()
                if time.monotonic_ns() - report_seen_ns >= int(args.post_report_grace_s * 1_000_000_000):
                    break
            await asyncio.sleep(0.01)
        if not composition.report_finalized:
            raise TimeoutError("full J4 live scenario did not finalize report within timeout")
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if wiring is not None:
            wiring.stop()
        if adapter is not None:
            profile_snapshot = adapter.media_profile()
            adapter.close("j4-full-live-cleanup")
        if runtime is not None:
            runtime.shutdown("j4-full-live-cleanup")
        _stop_process(peer)
        _stop_process(operator)
        peer_fixture_path.unlink(missing_ok=True)
        peer_log.close()
        operator_log.close()

    peer_text = peer_log_path.read_text(encoding="utf-8", errors="replace")
    operator_text = operator_log_path.read_text(encoding="utf-8", errors="replace")
    adapter_stats = adapter.media_stats() if adapter is not None else {}
    context_path = output_root / "context" / call_id / "conversation.jsonl"
    report_path = output_root / "reports" / call_id / "report.md"
    context = _load_context(context_path)
    user_turns = [item for item in context if item.get("turn", {}).get("role") == "user"]
    assistant_turns = [item for item in context if item.get("turn", {}).get("role") == "assistant"]
    trace = composition.fsm.trace if composition is not None else ()
    trace_events = [item.event for item in trace]
    trace_states = [item.current.value for item in trace]
    packet_match = re.search(r"packets:\s+(\d+)\s+(\d+)", peer_text)
    peer_packets = (
        {"transmit": int(packet_match.group(1)), "receive": int(packet_match.group(2))}
        if packet_match
        else None
    )
    scenario_checks = {
        "follow_up_turn_present": len(user_turns) >= 2,
        "barge_in_transition_present": "barge_in" in trace_events,
        "unknown_answer_offer_present": "awaiting_transfer_confirmation" in trace_states,
        "transfer_transition_present": "transferring" in trace_states,
        "operator_transfer_result": bool(transfer_owner and transfer_owner.accepted),
        "report_present": report_path.exists(),
    }
    result: dict[str, object] = {
        "evidence_id": f"E-002-J4-FULL-LIVE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "plan": "002-J",
        "stage": "J4",
        "status": "fail",
        "acceptance": "one clean-start SIP/RTP call covers follow-up, barge-in, unknown-answer/transfer and report",
        "started_at_utc": _utc_now(),
        "elapsed_ms": round((time.monotonic_ns() - started_ns) / 1_000_000, 3),
        "elapsed_from_call_start_ms": (
            round((time.monotonic_ns() - call_started_ns) / 1_000_000, 3)
            if call_started_ns is not None
            else None
        ),
        "warmup": warmup_report.as_dict() if warmup_report is not None else None,
        "fixture": fixture,
        "runtime": {
            "python": sys.executable,
            "version": sys.version.replace("\n", " "),
            "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: None)(),
        },
        "sip": {
            "peer_established": "Call established" in peer_text,
            "rtp_ingress_established": "incoming rtp for 'audio' established" in peer_text,
            "pcmu_8000_mono": "PCMU 8000Hz 1ch" in peer_text,
            "peer_rtp_packets": peer_packets,
            "adapter_profile": profile_snapshot.as_dict() if hasattr(profile_snapshot, "as_dict") else None,
            "adapter_media_stats": adapter_stats,
            "adapter_events": [event.as_dict() for event in events],
        },
        "operator": {
            "target": constants.OPERATOR_TARGET,
            "peer_established": "Call established" in operator_text,
            "log": str(operator_log_path),
            "transfer_result": asdict(transfer_owner) if transfer_owner is not None else None,
        },
        "conversation": {
            "context": context,
            "user_turn_count": len(user_turns),
            "assistant_turn_count": len(assistant_turns),
            "rag_context_count": len(composition.rag_contexts) if composition is not None else 0,
            "rag_source_ids": [list(item.source_ids) for item in composition.rag_contexts] if composition is not None else [],
        },
        "asr_hypotheses": list(asr_backend.hypotheses) if asr_backend is not None else [],
        "fsm": {
            "state": composition.fsm.state.value if composition is not None else None,
            "trace_events": trace_events,
            "trace_states": trace_states,
        },
        "wiring": wiring.stats.as_dict() if wiring is not None else {},
        "tts_output": wiring.tts_output_stats() if wiring is not None else {},
        "scenario_checks": scenario_checks,
        "report": str(report_path) if report_path.exists() else None,
        "peer_log": str(peer_log_path),
        "errors": ([error] if error else []) + (wiring.errors if wiring is not None else []) + (pipeline.errors if pipeline is not None else []),
        "audio_recording": False,
        "external_pbx": False,
        "notes": [
            "The fixture is generated before call admission and is not a conversation recording.",
            "PCM/RTP payload stays on direct data-plane edges; only compact control events enter Dispatcher.",
            "A separate operator Baresip peer is used for the approved local transfer scenario.",
        ],
    }
    result["status"] = "pass" if error is None and all(scenario_checks.values()) and not result["errors"] else "fail"
    (output_root / "j4-full-live.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=240.0)
    parser.add_argument("--post-report-grace-s", type=float, default=5.0)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
