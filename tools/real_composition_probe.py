#!/usr/bin/env python3
"""Main-only real Ollama + XTTS composition probe.

The probe is intentionally a single-call scenario.  It uses the accepted
local natural-science corpus, the real Ollama facade and the accepted XTTS
adapter.  It writes only a diagnostic JSON and the generated PCM as WAV; no
conversation audio recording is introduced into the application.
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import constants  # noqa: E402
from sip_bot.context import ContextStore  # noqa: E402
from sip_bot.conversation_pipeline import ConversationPipeline  # noqa: E402
from sip_bot.dialogue import DialogueState  # noqa: E402
from sip_bot.dialogue.events import PlaybackStatus  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.prompt import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec  # noqa: E402
from sip_bot.report import ReportFinalizer  # noqa: E402
from sip_bot.retrieval import LocalKnowledgeIndex, KnowledgeQueryBuilder, load_corpus  # noqa: E402
from sip_bot.runtime import ApplicationRuntime  # noqa: E402
from sip_bot.runtime_composition import CallOwners  # noqa: E402
from sip_bot.sip_media.models import NegotiatedMediaProfile  # noqa: E402
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind  # noqa: E402
from sip_bot.speech import EndpointEventKind, FinalUserTurn  # noqa: E402
from sip_bot.tts import EngineAudioChunk, XttsV2Adapter  # noqa: E402


def _profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile(
        codec="PCMU",
        payload_type=0,
        rx_payload_type=0,
        tx_payload_type=0,
        ptime_ms=20.0,
        sample_rate_hz=8000,
        channels=1,
        frame_size_samples=160,
        source="001-S negotiated test profile",
    )


class _RealXttsEngine:
    def __init__(self, model_root: Path, voice_path: Path) -> None:
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio
        import TTS.api
        import TTS.tts.models.xtts as xtts_module

        def load_audio_without_torchcodec(audiopath: str | Path, sampling_rate: int):
            data, source_rate = sf.read(audiopath, dtype="float32", always_2d=True)
            audio = torch.from_numpy(np.ascontiguousarray(data.T))
            if source_rate != sampling_rate:
                audio = torchaudio.functional.resample(audio, source_rate, sampling_rate)
            if audio.size(0) != 1:
                audio = torch.mean(audio, dim=0, keepdim=True)
            return audio.clamp_(-1, 1)

        xtts_module.load_audio = load_audio_without_torchcodec
        self._np = np
        self._tts = TTS.api.TTS(
            model_path=str(model_root),
            config_path=str(model_root / "config.json"),
            progress_bar=False,
            gpu=True,
        )
        model = self._tts.synthesizer.tts_model
        self._latents = model.get_conditioning_latents(audio_path=str(voice_path), load_sr=22050)

    def stream(self, text: str, cancel: Event):
        model = self._tts.synthesizer.tts_model
        latent, speaker = self._latents
        stream = model.inference_stream(
            text=text,
            language="ru",
            gpt_cond_latent=latent,
            speaker_embedding=speaker,
            stream_chunk_size=20,
            overlap_wav_len=1024,
        )
        try:
            for chunk in stream:
                if cancel.is_set():
                    return
                values = chunk.detach().to("cpu").numpy().reshape(-1).astype(self._np.float32, copy=False)
                if values.size:
                    pcm = (self._np.clip(values, -1.0, 1.0) * 32767.0).round().astype(self._np.int16).tobytes()
                    yield EngineAudioChunk(pcm, 24000, 1)
        finally:
            stream.close()


def _wait_pipeline(pipeline: ConversationPipeline, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pipeline.drain_control()
        if pipeline.active_workers == 0:
            pipeline.drain_control()
            return
        time.sleep(0.01)
    raise TimeoutError("composition pipeline did not become idle")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, default=Path("/home/sipbot/.cache/sip-bot-c4-xtts-v2-model"))
    parser.add_argument("--voice", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    voice = args.voice or args.model_root / "samples" / "en_sample.wav"

    llm = LlmFacade(OllamaHttpClient(endpoint=constants.LLM_HTTP_ENDPOINT))
    _, chunks = load_corpus(PROJECT_ROOT / constants.KNOWLEDGE_CORPUS_PATH)
    index = LocalKnowledgeIndex.build(
        chunks,
        llm,
        index_version=constants.RAG_INDEX_VERSION,
        embedding_model=constants.RAG_EMBEDDING_MODEL,
    )
    prompt = SkillPromptManager(
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
    tts = XttsV2Adapter(_RealXttsEngine(args.model_root, voice), operation_id_factory=lambda: "xtts-composition-op")
    runtime = ApplicationRuntime.from_constants()
    runtime.start()
    call_id = "real-composition-call"
    owners = CallOwners(
        context=ContextStore(output_root / "context", call_id),
        report=ReportFinalizer(output_root / "reports"),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
    )
    composition = runtime.compose_call(call_id, owners)
    pcm = bytearray()
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=_profile(),
        audio_sink=lambda chunk: pcm.extend(chunk.pcm_s16le),
        top_k=constants.RAG_TOP_K,
        threshold=constants.RAG_RELEVANCE_THRESHOLD,
    )
    composition.submit_control(NormalizedSipEvent(call_id, SipEventKind.CALL_ANSWERED, 1, 1))
    composition.drain_control()
    turn = FinalUserTurn(
        call_id,
        "speech_ingress",
        1,
        f"{call_id}:turn-1",
        "Почему небо днём кажется голубым?",
        1,
        time.monotonic_ns(),
        EndpointEventKind.HARD_ENDPOINT,
    )
    started = time.monotonic_ns()
    if not pipeline.submit_final_turn(turn):
        raise RuntimeError("composition rejected final turn")
    _wait_pipeline(pipeline, 180.0)
    composition.drain_control()
    composition.submit_control(NormalizedSipEvent(call_id, SipEventKind.REMOTE_HANGUP, 2, 2, reason="BYE"))
    composition.drain_control()
    runtime.shutdown()

    wav = output_root / "tts-composition-sample.wav"
    with wave.open(str(wav), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(bytes(pcm))
    result = {
        "status": "pass" if composition.report_finalized and pcm else "fail",
        "call_id": call_id,
        "state": composition.fsm.state.value,
        "report": str(composition.report_path),
        "rag": {
            "contexts": len(composition.rag_contexts),
            "sufficient": composition.rag_contexts[0].sufficient,
            "source_ids": composition.rag_contexts[0].source_ids,
        },
        "audio": {
            "path": str(wav),
            "bytes": len(pcm),
            "sample_rate_hz": 8000,
            "channels": 1,
            "sha256": hashlib.sha256(pcm).hexdigest(),
        },
        "elapsed_from_final_turn_ms": round((time.monotonic_ns() - started) / 1_000_000, 3),
        "pipeline_errors": pipeline.errors,
        "runtime": {
            "python": sys.executable,
            "version": sys.version.replace("\n", " "),
            "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: None)(),
        },
    }
    (output_root / "real-composition.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
