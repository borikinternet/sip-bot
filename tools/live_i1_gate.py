#!/usr/bin/env python3
"""Execute the I1-8 live SIP/RTP -> AI -> SIP/RTP gate.

The tool is intentionally a procedural harness.  It creates no new semantic
owner: the application runtime, SipMediaAdapter, SpeechIngress,
ConversationPipeline and existing AI owners are connected through
CallRuntimeWiring.  Baresip supplies a local, generated speech fixture over
the negotiated PCMU call; no call recording is created.
"""

from __future__ import annotations

import argparse
import asyncio
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
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from config import constants  # noqa: E402
from real_composition_probe import _RealXttsEngine, _profile  # noqa: E402
from sip_bot.context import ContextSnapshot, ContextStore  # noqa: E402
from sip_bot.conversation_pipeline import ConversationPipeline  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.media import AsrChunker  # noqa: E402
from sip_bot.prompt import SkillPromptManager, build_default_prompt_manager  # noqa: E402
from sip_bot.report import ReportFinalizer  # noqa: E402
from sip_bot.retrieval import KnowledgeQueryBuilder, LocalKnowledgeIndex  # noqa: E402
from sip_bot.runtime import ApplicationRuntime  # noqa: E402
from sip_bot.runtime_composition import CallOwners  # noqa: E402
from sip_bot.runtime_wiring import CallRuntimeWiring  # noqa: E402
from sip_bot.sip_media import SipMediaAdapter, SipMediaConfig  # noqa: E402
from sip_bot.sip_media.protocol_events import NormalizedSipEvent  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    AsrHypothesis,
    EndpointingConfig,
    FasterWhisperC2Backend,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TurnDetector,
    build_configured_web_rtc_vad_processor,
)
from sip_bot.tts import ApprovedTextChunk, XttsV2Adapter  # noqa: E402


C2_MODEL = "/home/sipbot/.local/models/faster-whisper-large-v3-edaa852e"
XTTS_MODEL = Path("/home/sipbot/.cache/sip-bot-c4-xtts-v2-model")
C2_SITE = "/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages"
PEER_CONFIG_TEMPLATE = PROJECT_ROOT / "artifacts" / "feasibility" / "001-S-voip-test-stand" / "config" / "peer-5080"


class _AmplitudeVad:
    """Deterministic test double retained for isolated non-live probes."""

    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        del sample_rate_hz
        values = np.frombuffer(pcm_s16le, dtype=np.int16)
        return bool(values.size and np.max(np.abs(values)) > 350)


class _RecordingSpeechIngress(SpeechIngress):
    """Test-harness observer over the existing speech ingress boundary."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._vad_decisions: list[dict[str, object]] = []
        self._endpoint_events: list[dict[str, object]] = []
        self._max_frame_abs = 0
        self._nonzero_frame_count = 0

    def process_frame(self, frame: Any):
        values = np.frombuffer(frame.pcm_s16le, dtype=np.int16)
        frame_abs = int(np.max(np.abs(values))) if values.size else 0
        self._max_frame_abs = max(self._max_frame_abs, frame_abs)
        if frame_abs:
            self._nonzero_frame_count += 1
        result = super().process_frame(frame)
        decision = result.vad_decision
        self._vad_decisions.append(
            {
                "sequence": decision.sequence,
                "timestamp_ns": decision.timestamp_ns,
                "frame_duration_ms": decision.frame_duration_ms,
                "sample_rate_hz": frame.profile.sample_rate_hz,
                "is_speech": decision.is_speech,
                "source": decision.source,
            }
        )
        self._endpoint_events.extend(
            {
                "kind": event.kind.value,
                "turn_id": event.turn_id,
                "timestamp_ns": event.timestamp_ns,
                "silence_ms": event.silence_ms,
                "reason": event.reason,
                "authoritative": event.authoritative,
            }
            for event in result.endpoint_events
        )
        return result

    def evidence(self) -> dict[str, object]:
        speech = [item for item in self._vad_decisions if item["is_speech"]]
        rates = sorted({int(item["sample_rate_hz"]) for item in self._vad_decisions})
        durations = sorted({int(item["frame_duration_ms"]) for item in self._vad_decisions})
        return {
            "candidate": "WebRtcVadCandidate",
            "mode": constants.VAD_MODE,
            "decision_count": len(self._vad_decisions),
            "speech_decision_count": len(speech),
            "silence_decision_count": len(self._vad_decisions) - len(speech),
            "sample_rates_hz": rates,
            "frame_durations_ms": durations,
            "first_speech_sequence": speech[0]["sequence"] if speech else None,
            "last_speech_sequence": speech[-1]["sequence"] if speech else None,
            "max_frame_abs": self._max_frame_abs,
            "nonzero_frame_count": self._nonzero_frame_count,
            "endpoint_events": list(self._endpoint_events),
        }


class _RecordingAsrBackend(FasterWhisperC2Backend):
    def __init__(self, model_path: str) -> None:
        super().__init__(model_path, language="ru", device="cuda", compute_type="int8_float16")
        self.hypotheses: list[str] = []

    def transcribe_chunk(self, chunk: Any):
        for item in super().transcribe_chunk(chunk):
            if isinstance(item, dict):
                self.hypotheses.append(str(item.get("text", "")))
            yield item


class _RecordingSink:
    def __init__(self, dispatcher: Any, events: list[NormalizedSipEvent]) -> None:
        self.dispatcher = dispatcher
        self.events = events

    def publish(self, event: NormalizedSipEvent) -> None:
        self.events.append(event)
        self.dispatcher.publish(event)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_wav(path: Path, pcm: bytes, sample_rate_hz: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate_hz)
        stream.writeframes(pcm)


def _make_input_fixture(tts: XttsV2Adapter, profile: Any, path: Path) -> dict[str, object]:
    """Generate a speech fixture, kept separate from the call runtime."""

    text = "Почему небо днём кажется голубым?"
    approved = ApprovedTextChunk(
        operation_id="i1-8-fixture-operation",
        call_id="i1-8-fixture",
        turn_id="i1-8-fixture-turn",
        generation=1,
        sequence=1,
        text=text,
        is_final=True,
    )
    pcm = b"".join(
        chunk.pcm_s16le
        for chunk in tts.stream_approved_text(
            (approved,),
            channel_id="i1-8-fixture:media",
            profile=profile,
        )
    )
    # Baresip's aufile source ends the call at EOF.  Keep the call alive long
    # enough for a cold ASR load and the downstream AI path, without changing
    # the speech payload or creating a call recording.
    pcm += b"\x00" * (8000 * 2 * 30)
    _write_wav(path, pcm)
    return {
        "text": text,
        "path": str(path),
        "bytes": len(pcm),
        "sha256": hashlib.sha256(pcm).hexdigest(),
        "sample_rate_hz": 8000,
        "channels": 1,
        "speech_bytes": len(pcm) - 8000 * 2 * 30,
        "silence_tail_s": 30,
        "source": "local XTTS-generated test fixture; not a call recording",
    }


def _prepare_peer_config(root: Path, fixture_path: Path) -> Path:
    """Create a clean Baresip peer from the accepted local stand template."""

    peer_config = root / "peer-5080"
    root.mkdir(parents=True, exist_ok=True)
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


def _prompt() -> SkillPromptManager:
    return build_default_prompt_manager()


def _load_context(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event_dict(event: NormalizedSipEvent) -> dict[str, object]:
    return event.as_dict()


async def _run(args: argparse.Namespace) -> dict[str, object]:
    output_root = args.output_root
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"live gate output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    # Keep every clean-start run self-contained; a previous gate must not
    # leave a peer config or fixture that changes the next run.
    live_root = output_root / "live-stand"
    peer_fixture_path = Path("/tmp/sip-bot-i1-input-question.wav")
    peer_fixture_path.unlink(missing_ok=True)
    peer_config = _prepare_peer_config(live_root, peer_fixture_path)
    input_fixture = live_root / "input-question.wav"
    peer_log_path = output_root / "baresip-peer.log"
    call_id = "i1-8-live-call"
    profile = _profile()
    sys.path.append(C2_SITE)

    llm = LlmFacade(OllamaHttpClient(endpoint=constants.LLM_HTTP_ENDPOINT))     
    prompt = _prompt()
    peer_log = peer_log_path.open("w", encoding="utf-8")
    peer: subprocess.Popen[str] | None = None
    events: list[NormalizedSipEvent] = []
    adapter: SipMediaAdapter | None = None
    wiring: CallRuntimeWiring | None = None
    speech: _RecordingSpeechIngress | None = None
    runtime: ApplicationRuntime | None = None
    composition: Any | None = None
    pipeline: ConversationPipeline | None = None
    index: LocalKnowledgeIndex | None = None
    tts: XttsV2Adapter | None = None
    fixture: dict[str, object] = {}
    warmup_report: Any | None = None
    started_ns = time.monotonic_ns()
    call_started_ns: int | None = None
    hangup_requested = False
    error: str | None = None
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
            index_holder["index"] = LocalKnowledgeIndex.load(
                PROJECT_ROOT / constants.KNOWLEDGE_INDEX_PATH,
                expected_index_version=constants.RAG_INDEX_VERSION,
                expected_corpus_version=constants.RAG_CORPUS_VERSION,
                expected_embedding_model=constants.RAG_EMBEDDING_MODEL,
                expected_dimension=constants.RAG_INDEX_DIMENSION,
                expected_chunking_policy=constants.RAG_CHUNKING_POLICY_VERSION,
                expected_corpus_sha256=constants.RAG_CORPUS_SHA256,
            )
            return {
                "operation": "load-prebuilt-index",
                "chunks": index_holder["index"].item_count,
                "dimension": index_holder["index"].dimension,
                "embedding_model": index_holder["index"].embedding_model,
                "corpus_embedding_requests": 0,
            }

        def warm_llm_chat() -> dict[str, object]:
            knowledge = index_holder["index"].query(
                query_builder.build("Почему небо днём кажется голубым?"),
                llm,
                top_k=constants.RAG_TOP_K,
                threshold=constants.RAG_RELEVANCE_THRESHOLD,
                context_id="warmup-knowledge-context",
            )
            request = prompt.prepare(
                call_id="warmup-call",
                turn_id="warmup-call:turn-1",
                final_user_text="Проверка готовности модели.",
                snapshot=ContextSnapshot("warmup-call", 0, ()),
                knowledge_context=knowledge,
            )
            return {"sources": list(knowledge.source_ids), "trace": llm.warmup(request).as_dict()}

        def initialize_tts() -> dict[str, object]:
            tts_holder["tts"] = XttsV2Adapter(
                _RealXttsEngine(XTTS_MODEL, XTTS_MODEL / "samples" / "en_sample.wav"),
                operation_id_factory=lambda: "i1-8-tts",
            )
            return {"initialized": True}

        def warm_tts() -> dict[str, object]:
            return tts_holder["tts"].warmup(profile=profile)

        def build_fixture() -> dict[str, object]:
            fixture_holder["fixture"] = _make_input_fixture(tts_holder["tts"], profile, input_fixture)
            return {"path": str(input_fixture), "bytes": fixture_holder["fixture"]["bytes"]}

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
        shutil.copy2(input_fixture, peer_fixture_path)

        # The peer is started only after every lazy model and the RAG index
        # have passed readiness.  A caller therefore cannot enter a cold AI
        # path while the SIP/media loop is already serving a conversation.
        peer = subprocess.Popen(
            ["baresip", "-f", str(peer_config), "-t", str(args.timeout_s + 20)],
            cwd="/usr/lib/baresip/modules",
            stdout=peer_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        await asyncio.sleep(1.2)
        adapter = SipMediaAdapter(
            SipMediaConfig.from_runtime_config(
                runtime.config,
                local_uri="sip:tester@127.0.0.1",
                bind_port=5070,
            ),
            enforce_runtime=True,
        )
        adapter.start()
        owners = CallOwners(
            context=ContextStore(output_root / "context", call_id),
            report=ReportFinalizer(output_root / "reports"),
            retrieval=index,
            prompt=prompt,
            llm=llm,
            tts=tts,
        )
        composition = runtime.compose_call(call_id, owners)
        pipeline = ConversationPipeline(
            composition,
            query_builder=KnowledgeQueryBuilder(),
            retrieval=index,
            prompt=prompt,
            llm=llm,
            tts=tts,
            media_profile=adapter.media_profile,
            greeting_text=runtime.config.call_greeting_text,
            transfer_confirmation_text=runtime.config.transfer_confirmation_text,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
        )
        speech = _RecordingSpeechIngress(
            vad=build_configured_web_rtc_vad_processor(runtime.config),
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
        )
        wiring = runtime.create_call_wiring(
            composition,
            sip_media=adapter,
            speech=speech,
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
            state = composition.fsm.state.value
            if (
                not hangup_requested
                and wiring.stats.tts_frames_sent > 0
                and pipeline.active_workers == 0
                and state in {"listening", "awaiting_transfer_confirmation"}
            ):
                adapter.hangup("i1-8-live-gate-complete")
                hangup_requested = True
            if composition.report_finalized:
                break
            if wiring.errors or pipeline.errors:
                raise RuntimeError("; ".join(wiring.errors + pipeline.errors))
            await asyncio.sleep(0.01)
        if not composition.report_finalized:
            raise TimeoutError("live I1-8 call did not finalize report within timeout")
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if wiring is not None:
            wiring.stop()
        if adapter is not None:
            profile_snapshot = adapter.media_profile()
            adapter.close("i1-8-live-gate-cleanup")
        if runtime is not None:
            runtime.shutdown("i1-8-live-gate-cleanup")
        if peer is not None and peer.poll() is None:
            peer.terminate()
            try:
                peer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                peer.kill()
                peer.wait(timeout=5)
        peer_log.close()

    peer_text = peer_log_path.read_text(encoding="utf-8", errors="replace")
    adapter_stats = adapter.media_stats() if adapter is not None else {}
    context_path = output_root / "context" / call_id / "conversation.jsonl"
    report_path = output_root / "reports" / call_id / "report.md"
    profile_actual = profile_snapshot
    peer_rtp = "incoming rtp for 'audio' established" in peer_text
    peer_established = "Call established" in peer_text
    peer_pcmu = "PCMU 8000Hz 1ch" in peer_text
    packet_match = re.search(r"packets:\s+(\d+)\s+(\d+)", peer_text)
    peer_packets = (
        {"transmit": int(packet_match.group(1)), "receive": int(packet_match.group(2))}
        if packet_match
        else None
    )
    peer_received_packets = bool(peer_packets and peer_packets["receive"] > 0)
    result: dict[str, object] = {
        "status": "fail",
        "gate": "I1-8",
        "call_id": call_id,
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
            "peer_established": peer_established,
            "rtp_ingress_established": peer_rtp,
            "pcmu_8000_mono": peer_pcmu,
            "peer_reported_packets": peer_received_packets,
            "peer_rtp_packets": peer_packets,
            "adapter_profile": profile_actual.as_dict() if hasattr(profile_actual, "as_dict") else None,
            "adapter_media_stats": adapter_stats,
            "adapter_events": [_event_dict(event) for event in events],
        },
        "wiring": wiring.stats.as_dict() if wiring is not None else {},
        "speech": speech.evidence() if speech is not None else {},
        "context": _load_context(context_path),
        "report": str(report_path) if report_path.exists() else None,
        "rag": {
            "contexts": len(composition.rag_contexts) if composition is not None else 0,
            "sufficient": bool(composition and composition.rag_contexts and composition.rag_contexts[0].sufficient),
            "source_ids": list(composition.rag_contexts[0].source_ids) if composition and composition.rag_contexts else [],
        },
        "fsm": {
            "state": composition.fsm.state.value if composition is not None else None,
            "trace": [
                {
                    "sequence": item.sequence,
                    "event": item.event,
                    "previous": item.previous.value,
                    "current": item.current.value,
                    "reason": item.reason,
                }
                for item in composition.fsm.trace
            ] if composition is not None else [],
        },
        "peer_log": str(peer_log_path),
        "errors": ([error] if error else []) + (wiring.errors if wiring is not None else []) + (pipeline.errors if pipeline is not None else []),
    }
    result["status"] = "pass" if (
        error is None
        and composition is not None
        and composition.report_finalized
        and report_path.exists()
        and peer_established
        and peer_rtp
        and peer_pcmu
        and peer_received_packets
        and (wiring.stats.ingress_frames > 0 if wiring is not None else False)
        and (wiring.stats.final_turns > 0 if wiring is not None else False)
        and (wiring.stats.tts_frames_sent > 0 if wiring is not None else False)
        and bool(adapter_stats.get("egress_frames", 0))
        and not result["errors"]
    ) else "fail"
    (output_root / "live-i1-gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, default=240.0)
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
