#!/usr/bin/env python3
"""Real ASR -> RAG/LLM -> XTTS composition probe.

The SIP/PJMEDIA ingress is represented by negotiated PCMU-compatible PCM
frames from the already accepted offline Common Voice fixture.  No call
recording is created; the fixture is an external test artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import wave
from pathlib import Path
from threading import Event

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from config import constants  # noqa: E402
from real_composition_probe import _RealXttsEngine, _profile  # noqa: E402
from sip_bot.context import ContextStore  # noqa: E402
from sip_bot.conversation_pipeline import ConversationPipeline  # noqa: E402
from sip_bot.dialogue import DialogueState  # noqa: E402
from sip_bot.dialogue.events import PlaybackStatus  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.media import AsrChunker  # noqa: E402
from sip_bot.prompt import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec  # noqa: E402
from sip_bot.report import ReportFinalizer  # noqa: E402
from sip_bot.retrieval import KnowledgeQueryBuilder, LocalKnowledgeIndex, load_corpus  # noqa: E402
from sip_bot.runtime import ApplicationRuntime  # noqa: E402
from sip_bot.runtime_composition import CallOwners  # noqa: E402
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame  # noqa: E402
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    AsrHypothesis,
    EndpointEventKind,
    EndpointingConfig,
    FasterWhisperC2Backend,
    FinalUserTurn,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TurnDetector,
    VadProcessor,
)
from sip_bot.tts import EngineAudioChunk, XttsV2Adapter  # noqa: E402
from sip_bot.transfer import FakeOperator, TransferOrchestrator  # noqa: E402


C2_SITE = "/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages"
C2_LIBS = "/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs"
C2_MODEL = "/home/sipbot/.local/models/faster-whisper-large-v3-edaa852e"


class _AmplitudeVad:
    def is_speech(self, pcm_s16le: bytes, sample_rate_hz: int) -> bool:
        del sample_rate_hz
        return bool(np.max(np.abs(np.frombuffer(pcm_s16le, dtype=np.int16))) > 350)


def _read_pcm(path: Path) -> bytes:
    import soundfile as sf

    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = samples.mean(axis=1)
    if rate != 8000:
        target_count = round(len(mono) * 8000 / rate)
        source_positions = np.arange(target_count, dtype=np.float64) * rate / 8000.0
        mono = np.interp(source_positions, np.arange(len(mono), dtype=np.float64), mono)
    return (np.clip(mono, -1.0, 1.0) * 32767.0).round().astype(np.int16).tobytes()


def _process_chunk(
    adapter: StreamingAsrAdapter,
    operation: object,
    chunk: object,
    ingress: SpeechIngress,
    hypotheses: list[AsrHypothesis],
) -> None:
    for hypothesis in adapter.stream(operation, (chunk,)):  # type: ignore[arg-type]
        if not isinstance(hypothesis, AsrHypothesis):
            raise TypeError("ASR adapter returned an untyped hypothesis")
        hypotheses.append(hypothesis)
        ingress.accept_hypothesis(hypothesis)


def _wait_pipeline(pipeline: ConversationPipeline, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pipeline.drain_control()
        if pipeline.active_workers == 0:
            pipeline.drain_control()
            return
        time.sleep(0.01)
    raise TimeoutError("composition pipeline did not become idle")


def _prompt() -> SkillPromptManager:
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
    parser.add_argument("--fixture", type=Path, default=PROJECT_ROOT / "artifacts/feasibility/001-C2/fixture.mp3")
    parser.add_argument("--model-root", type=Path, default=Path("/home/sipbot/.cache/sip-bot-c4-xtts-v2-model"))
    parser.add_argument("--voice", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    voice = args.voice or args.model_root / "samples" / "en_sample.wav"

    # The accepted C2 patched extension is reused in this free-threaded
    # interpreter.  It is appended so the XTTS environment keeps its own
    # transformer/tokenizer dependencies first.
    sys.path.append(C2_SITE)
    llm = LlmFacade(OllamaHttpClient(endpoint=constants.LLM_HTTP_ENDPOINT))
    profile = _profile()
    call_id = "real-media-composition-call"
    channel_id = f"{call_id}:media"
    started = time.monotonic_ns()

    asr = StreamingAsrAdapter(
        FasterWhisperC2Backend(C2_MODEL, language="ru", device="cuda", compute_type="int8_float16")
    )
    operation = asr.open_operation(call_id=call_id, channel_id=channel_id, generation=1)
    ingress = SpeechIngress(
        vad=VadProcessor(_AmplitudeVad()),
        turn_detector=TurnDetector(EndpointingConfig(
            soft_endpoint_ms=constants.ENDPOINT_SOFT_MS,
            hard_endpoint_ms=constants.ENDPOINT_HARD_MS,
            min_speech_ms=constants.MIN_SPEECH_MS,
        )),
        assembler=TranscriptAssembler(call_id, channel_id, 1, f"{call_id}:turn-1", constants.TRANSCRIPT_STABLE_PREFIX_MIN_CHARS),
    )
    chunker = AsrChunker(
        profile=profile,
        call_id=call_id,
        channel_id=channel_id,
        generation=1,
        chunk_ms=constants.ASR_CHUNK_MS,
        flush_ms=constants.ASR_CHUNK_FLUSH_MS,
    )
    hypotheses: list[AsrHypothesis] = []
    final_turn: FinalUserTurn | None = None
    pcm = _read_pcm(args.fixture)
    frame_bytes = profile.frame_bytes
    sequence = 0
    base_ns = time.monotonic_ns()
    for offset in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        sequence += 1
        timestamp_ns = base_ns + (sequence - 1) * profile.frame_time_usec * 1000
        frame = PcmFrame(call_id, channel_id, 1, sequence, timestamp_ns, pcm[offset : offset + frame_bytes], profile)
        result = ingress.process_frame(frame)
        if result.final_turn is not None:
            final_turn = result.final_turn
        chunker.push(frame)
        while (chunk := chunker.next_chunk()) is not None:
            _process_chunk(asr, operation, chunk, ingress, hypotheses)
    chunker.hard_endpoint()
    while (chunk := chunker.next_chunk()) is not None:
        _process_chunk(asr, operation, chunk, ingress, hypotheses)
    for silence_number in range(30):
        sequence += 1
        timestamp_ns = base_ns + (sequence - 1) * profile.frame_time_usec * 1000
        frame = PcmFrame(call_id, channel_id, 1, sequence, timestamp_ns, b"\x00" * frame_bytes, profile)
        result = ingress.process_frame(frame)
        if result.final_turn is not None:
            final_turn = result.final_turn
            break
        del silence_number
    if final_turn is None:
        raise RuntimeError("real ASR/VAD/endpointing path did not produce an authoritative final turn")
    asr.close()

    _, corpus_chunks = load_corpus(PROJECT_ROOT / constants.KNOWLEDGE_CORPUS_PATH)
    index = LocalKnowledgeIndex.build(
        corpus_chunks,
        llm,
        index_version=constants.RAG_INDEX_VERSION,
        embedding_model=constants.RAG_EMBEDDING_MODEL,
    )
    prompt = _prompt()
    tts = XttsV2Adapter(_RealXttsEngine(args.model_root, voice), operation_id_factory=lambda: "xtts-media-composition-op")
    operator = FakeOperator(constants.OPERATOR_TARGET)
    transfer = TransferOrchestrator(operator)
    runtime = ApplicationRuntime.from_constants()
    runtime.start()
    owners = CallOwners(
        context=ContextStore(args.output_root / "context", call_id),
        report=ReportFinalizer(args.output_root / "reports"),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        transfer=transfer,
    )
    composition = runtime.compose_call(call_id, owners)
    audio = bytearray()
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=profile,
        audio_sink=lambda chunk: audio.extend(chunk.pcm_s16le),
        transfer=transfer,
        top_k=constants.RAG_TOP_K,
        threshold=constants.RAG_RELEVANCE_THRESHOLD,
    )
    composition.submit_control(NormalizedSipEvent(call_id, SipEventKind.CALL_ANSWERED, 1, 1))
    composition.drain_control()
    if not pipeline.submit_final_turn(final_turn):
        raise RuntimeError("composition rejected the real ASR final turn")
    _wait_pipeline(pipeline, 240.0)
    composition.drain_control()

    confirmation_used = False
    if composition.fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION:
        confirmation_used = True
        confirmation = FinalUserTurn(
            call_id, channel_id, 1, f"{call_id}:transfer-confirm", "Да", final_turn.revision + 1,
            time.monotonic_ns(), EndpointEventKind.HARD_ENDPOINT,
        )
        if not pipeline.submit_final_turn(confirmation):
            raise RuntimeError("composition rejected transfer confirmation")
        _wait_pipeline(pipeline, 30.0)
        composition.drain_control()
    if composition.fsm.state is not DialogueState.TERMINAL:
        composition.submit_control(NormalizedSipEvent(call_id, SipEventKind.REMOTE_HANGUP, 2, 2, reason="BYE"))
        composition.drain_control()
    runtime.shutdown()

    wav = args.output_root / "tts-media-composition-sample.wav"
    with wave.open(str(wav), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(bytes(audio))
    result = {
        "status": "pass" if final_turn and composition.report_finalized and audio else "fail",
        "call_id": call_id,
        "state": composition.fsm.state.value,
        "final_turn": {
            "text": final_turn.text,
            "revision": final_turn.revision,
            "boundary": final_turn.boundary.value,
        },
        "asr": {
            "candidate": "faster-whisper-large-v3",
            "model_path": C2_MODEL,
            "hypotheses": [item.text for item in hypotheses],
            "hypothesis_count": len(hypotheses),
            "frames": sequence,
            "profile": profile.as_dict(),
        },
        "rag": {
            "contexts": len(composition.rag_contexts),
            "sufficient": bool(composition.rag_contexts and composition.rag_contexts[0].sufficient),
            "source_ids": composition.rag_contexts[0].source_ids if composition.rag_contexts else [],
        },
        "transfer_confirmation_used": confirmation_used,
        "operator_accepted": bool(operator.accepted),
        "operator_target": operator.target,
        "report": str(composition.report_path),
        "audio": {"path": str(wav), "bytes": len(audio), "sha256": hashlib.sha256(audio).hexdigest()},
        "elapsed_from_media_start_ms": round((time.monotonic_ns() - started) / 1_000_000, 3),
        "pipeline_errors": pipeline.errors,
        "runtime": {
            "python": sys.executable,
            "version": sys.version.replace("\n", " "),
            "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: None)(),
        },
    }
    result["status"] = "pass" if result["status"] == "pass" and not pipeline.errors and (not confirmation_used or operator.accepted) else "fail"
    (args.output_root / "real-media-composition.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
