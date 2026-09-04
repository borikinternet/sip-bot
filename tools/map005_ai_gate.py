#!/usr/bin/env python3
"""Main-executor AI gate for Map-005-C.

The gate performs one sequential, source-aware RAG -> Ollama -> XTTS run after
pre-call warmup.  It deliberately uses the existing typed owners and writes
diagnostic evidence plus a listenable mono WAV; it does not create call
recordings or introduce a second model/provider.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave
from threading import Event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from config import constants  # noqa: E402
from real_composition_probe import _RealXttsEngine, _profile  # noqa: E402
from sip_bot.context import ContextStore  # noqa: E402
from sip_bot.dialogue.events import StructuredDecision  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.llm.types import StreamEventKind  # noqa: E402
from sip_bot.prompt import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec  # noqa: E402
from sip_bot.retrieval import KnowledgeQueryBuilder, LocalKnowledgeIndex, load_corpus  # noqa: E402
from sip_bot.speech import EndpointEventKind, FinalUserTurn  # noqa: E402
from sip_bot.tts import ApprovedTextChunk, XttsV2Adapter  # noqa: E402


PRIMARY_MODEL = "Qwen/Qwen3.5-9B"
PRIMARY_ARTIFACT = "/home/sipbot/models/c3-qwen35-9b-gguf/Qwen3.5-9B-Q4_K_M.gguf"
PRIMARY_ARTIFACT_SHA256 = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"
XTTS_MODEL = "/home/sipbot/.cache/sip-bot-c4-xtts-v2-model"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def gil_enabled() -> bool | None:
    checker = getattr(sys, "_is_gil_enabled", None)
    return bool(checker()) if checker is not None else None


def gpu_snapshot(label: str) -> dict[str, object]:
    record: dict[str, object] = {"label": label, "captured_at": now_utc()}
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        fields = [item.strip() for item in completed.stdout.strip().split(",")]
        if len(fields) >= 5:
            record.update(
                {
                    "name": fields[0],
                    "memory_total_mib": int(fields[1]),
                    "memory_used_mib": int(fields[2]),
                    "memory_free_mib": int(fields[3]),
                    "utilization_gpu_percent": int(fields[4]),
                }
            )
            return record
        record["error"] = "unexpected nvidia-smi output"
    except Exception as exc:  # evidence must preserve unavailable telemetry
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def build_prompt() -> SkillPromptManager:
    return SkillPromptManager(
        skill=SkillSpec(constants.DEFAULT_SKILL_ID, "1", "Отвечай кратко и только на основании найденных источников."),
        prompt=PromptSpec(
            constants.PROMPT_TEMPLATE_ID,
            constants.PROMPT_TEMPLATE_VERSION,
            "Отвечай только валидным JSON без Markdown и рассуждений. "
            "Допустимые action: answer, clarify, offer_transfer.\n"
            "{instruction}\nКонтекст:\n{context}\nЗнания:\n{knowledge}\n"
            "Вопрос пользователя:\n{user_text}",
        ),
        profile=GenerationProfile(
            constants.GENERATION_PROFILE_ID,
            constants.GENERATION_PROFILE_VERSION,
            constants.LLM_MAX_GENERATION_TOKENS,
            constants.LLM_TEMPERATURE,
        ),
        output_schema_id=constants.OUTPUT_SCHEMA_ID,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--allow-gpu", action="store_true")
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()
    if not args.allow_gpu:
        parser.error("the target AI gate requires explicit --allow-gpu")
    if gil_enabled() is True:
        raise RuntimeError("Map-005-C requires the target free-threaded runtime")

    args.output_root.mkdir(parents=True, exist_ok=True)
    profile = _profile()
    call_id = "map005-c-ai-gate"
    channel_id = f"{call_id}:tts"
    llm = LlmFacade(OllamaHttpClient(endpoint=constants.LLM_HTTP_ENDPOINT))
    query_builder = KnowledgeQueryBuilder()
    prompt = build_prompt()
    context_store = ContextStore(args.output_root / "context", call_id)
    _, corpus_chunks = load_corpus(PROJECT_ROOT / constants.KNOWLEDGE_CORPUS_PATH)

    evidence: dict[str, object] = {
        "schema": "sip-bot.map005-c-ai-gate.v1",
        "status": "running",
        "started_at": now_utc(),
        "target_runtime": {
            "executable": sys.executable,
            "python": sys.version.replace("\n", " "),
            "gil_enabled": gil_enabled(),
            "platform": sys.platform,
        },
        "candidate": {
            "model_id": PRIMARY_MODEL,
            "quantization": "Q4_K_M / 4-bit",
            "ollama_model": constants.LLM_CHAT_MODEL,
            "ollama_version": "0.33.1",
            "artifact": PRIMARY_ARTIFACT,
            "artifact_sha256": PRIMARY_ARTIFACT_SHA256,
            "fallback_run": False,
        },
        "gpu": {"before": gpu_snapshot("before")},
        "profile": profile.as_dict(),
        "warmup": {},
        "rag": {},
        "llm": {},
        "tts": {},
        "source_mode": {
            "implementation": "PcmAudioBridge EgressSourceMode; IDLE/PREROLL/PLAYING/CANCELLED/CLOSED",
            "underrun_policy": "only empty TTS buffer while PLAYING increments egress_underruns",
        },
        "errors": [],
    }

    try:
        index_started = time.monotonic_ns()
        index = LocalKnowledgeIndex.build(
            corpus_chunks,
            llm,
            index_version=constants.RAG_INDEX_VERSION,
            embedding_model=constants.RAG_EMBEDDING_MODEL,
        )
        index_ready = time.monotonic_ns()
        positive_text = "Почему небо днём кажется голубым?"
        negative_text = "Как устроен телескоп?"
        positive_query = query_builder.build(positive_text)
        negative_query = query_builder.build(negative_text)
        positive = index.query(
            positive_query,
            llm,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
            context_id=f"{constants.RAG_CONTEXT_ID_PREFIX}-{call_id}-positive",
        )
        negative = index.query(
            negative_query,
            llm,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
            context_id=f"{constants.RAG_CONTEXT_ID_PREFIX}-{call_id}-negative",
        )
        warmup_context = positive
        warmup_turn = FinalUserTurn(
            call_id, channel_id, 1, f"{call_id}:warmup", "Проверка готовности.", 1,
            time.monotonic_ns(), EndpointEventKind.HARD_ENDPOINT,
        )
        warmup_request = prompt.prepare_for_turn(
            final_turn=warmup_turn,
            snapshot=context_store.snapshot(),
            knowledge_context=warmup_context,
        )
        llm_warmup_started = time.monotonic_ns()
        llm_warmup_trace = llm.warmup(warmup_request)
        llm_warmup_finished = time.monotonic_ns()

        # The accepted C4 engine is initialized only after the LLM warmup and
        # is consumed once before the measured turn, so lazy model loading is
        # not misrepresented as live latency.
        tts_engine = _RealXttsEngine(Path(XTTS_MODEL), Path(XTTS_MODEL) / "samples" / "en_sample.wav")
        tts = XttsV2Adapter(tts_engine, operation_id_factory=lambda: "map005-c-tts")
        tts_warmup_started = time.monotonic_ns()
        tts_warmup = tts.warmup(profile=profile, call_id=call_id, channel_id=channel_id, turn_id=f"{call_id}:warmup")
        tts_warmup_finished = time.monotonic_ns()
        evidence["warmup"] = {
            "embedding_index_ms": round((index_ready - index_started) / 1_000_000, 3),
            "llm_trace": llm_warmup_trace.as_dict(),
            "llm_wall_ms": round((llm_warmup_finished - llm_warmup_started) / 1_000_000, 3),
            "tts_first_chunk": tts_warmup,
            "tts_wall_ms": round((tts_warmup_finished - tts_warmup_started) / 1_000_000, 3),
            "excluded_from_live_turn_latency": True,
        }

        evidence["rag"] = {
            "corpus_version": constants.RAG_CORPUS_VERSION,
            "index_version": index.index_version,
            "embedding_model": index.embedding_model,
            "corpus_chunks": len(corpus_chunks),
            "query_builder": {
                "policy_version": positive_query.policy_version,
                "capabilities": query_builder.capabilities,
                "positive_normalized": positive_query.normalized_text,
                "positive_lexical_terms": positive_query.lexical_terms,
                "positive_phrases": positive_query.phrases,
            },
            "positive": {
                "query": positive_text,
                "sufficient": positive.sufficient,
                "threshold": positive.threshold,
                "source_ids": positive.source_ids,
                "hits": [
                    {"source_id": hit.source_id, "chunk_id": hit.chunk_id, "score": hit.score}
                    for hit in positive.hits
                ],
            },
            "negative": {
                "query": negative_text,
                "sufficient": negative.sufficient,
                "allowed_action": prompt.prepare(
                    call_id=call_id,
                    turn_id=f"{call_id}:negative",
                    final_user_text=negative_text,
                    snapshot=context_store.snapshot(),
                    knowledge_context=negative,
                ).allowed_actions,
                "source_ids": negative.source_ids,
                "top_scores": [hit.score for hit in negative.hits],
            },
        }

        final_turn_ns = time.monotonic_ns()
        turn = FinalUserTurn(
            call_id, channel_id, 1, f"{call_id}:turn-1", positive_text, 1,
            final_turn_ns, EndpointEventKind.HARD_ENDPOINT,
        )
        query = query_builder.build(turn.text)
        knowledge = index.query(
            query,
            llm,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
            context_id=f"{constants.RAG_CONTEXT_ID_PREFIX}-{turn.turn_id}",
        )
        request = prompt.prepare_for_turn(
            final_turn=turn,
            snapshot=context_store.snapshot(),
            knowledge_context=knowledge,
        )
        request_started = time.monotonic_ns()
        operation = llm.start_chat(request, final_user_turn_ns=final_turn_ns)
        stream_events = []
        decision: StructuredDecision | None = None
        for event in operation:
            stream_events.append(event.kind.value)
            if event.kind is StreamEventKind.DECISION:
                decision = event.decision
        if decision is None or decision.action != "answer" or not decision.text:
            raise RuntimeError("real source-aware LLM operation did not return answer decision")
        evidence["llm"] = {
            "final_phrase": turn.text,
            "request_started_ns": request_started,
            "trace": operation.trace.as_dict(),
            "stream_event_kinds": stream_events,
            "status": operation.status.status.value,
            "decision": {"action": decision.action, "text": decision.text},
            "request": {
                "answer_mode": request.answer_mode,
                "allowed_actions": request.allowed_actions,
                "skill_id": request.skill_id,
                "skill_version": request.skill_version,
                "prompt_template_id": request.prompt_template_id,
                "prompt_template_version": request.prompt_template_version,
                "generation_profile_id": request.generation_profile_id,
                "generation_profile_version": request.generation_profile_version,
                "output_schema_id": request.output_schema_id,
                "source_ids": request.diagnostics.source_ids,
                "knowledge_context_id": request.diagnostics.knowledge_context_id,
            },
        }

        approved = ApprovedTextChunk(
            operation_id="map005-c-llm",
            call_id=call_id,
            turn_id=turn.turn_id,
            generation=1,
            sequence=1,
            text=decision.text,
            is_final=True,
        )
        audio = bytearray()
        tts_started = time.monotonic_ns()
        first_pcm_ns: int | None = None
        chunk_count = 0
        for chunk in tts.stream_approved_text((approved,), channel_id=channel_id, profile=profile):
            if first_pcm_ns is None:
                first_pcm_ns = time.monotonic_ns()
            chunk_count += 1
            audio.extend(chunk.pcm_s16le)
        tts_finished = time.monotonic_ns()
        if not audio or first_pcm_ns is None:
            raise RuntimeError("real XTTS operation produced no PCM")
        wav_path = args.output_root / "tts-answer-sample.wav"
        with wave.open(str(wav_path), "wb") as stream:
            stream.setnchannels(profile.channels)
            stream.setsampwidth(profile.pcm_bits_per_sample // 8)
            stream.setframerate(profile.sample_rate_hz)
            stream.writeframes(bytes(audio))
        evidence["tts"] = {
            "status": "completed",
            "text": decision.text,
            "chunks": chunk_count,
            "pcm_bytes": len(audio),
            "wav": str(wav_path),
            "wav_sha256": hashlib.sha256(audio).hexdigest(),
            "first_pcm_ms_from_llm_final": round((first_pcm_ns - final_turn_ns) / 1_000_000, 3),
            "first_pcm_ms_from_tts_start": round((first_pcm_ns - tts_started) / 1_000_000, 3),
            "completion_ms_from_tts_start": round((tts_finished - tts_started) / 1_000_000, 3),
            "profile": profile.as_dict(),
            "cancellation_evidence": "reused accepted 002-H cancellation.json; generator close, no independent native token",
        }
        evidence["gpu"]["after"] = gpu_snapshot("after")  # type: ignore[index]
        evidence["status"] = "pass"
    except Exception as exc:
        evidence["status"] = "fail"
        evidence["errors"].append(f"{type(exc).__name__}: {exc}")  # type: ignore[union-attr]
        evidence["gpu"]["after_error"] = gpu_snapshot("after-error")  # type: ignore[index]
    evidence["finished_at"] = now_utc()
    output = args.output_root / "map005-c-ai-gate.json"
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=list) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2, default=list))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
