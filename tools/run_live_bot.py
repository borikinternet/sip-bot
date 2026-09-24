#!/usr/bin/env python3
"""Run the warmed, registered, one-call-at-a-time SIP assistant.

The heavy providers are initialized before the SIP account is registered, so
FreeSWITCH cannot offer a queued call to an unready bot.  The adapter remains
registered between calls; every call receives a fresh Dispatcher/FSM/session
composition while sharing the already-warmed model owners.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
from queue import Empty, Queue
import signal
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
C2_SITE = "/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages"
XTTS_SITE = "/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/lib/python3.14t/site-packages"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "demo-web"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, XTTS_SITE)
sys.path.insert(0, TARGET_SITE)
sys.path.append(C2_SITE)

from config import constants  # noqa: E402
from backend.call_rag import CallScopedRagController  # noqa: E402
from real_composition_probe import _RealXttsEngine, _profile  # noqa: E402
from sip_bot.context import ContextSnapshot, ContextStore  # noqa: E402
from sip_bot.conversation_pipeline import ConversationPipeline  # noqa: E402
from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402
from sip_bot.prompt import build_default_prompt_manager  # noqa: E402
from sip_bot.report import ReportFinalizer  # noqa: E402
from sip_bot.retrieval import KnowledgeQueryBuilder, LocalKnowledgeIndex  # noqa: E402
from sip_bot.runtime import ApplicationRuntime  # noqa: E402
from sip_bot.runtime_composition import CallOwners  # noqa: E402
from sip_bot.sip_media import SipMediaAdapter, SipMediaConfig  # noqa: E402
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind  # noqa: E402
from sip_bot.speech import (  # noqa: E402
    EndpointingConfig,
    FasterWhisperC2Backend,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TurnDetector,
    build_configured_web_rtc_vad_processor,
)
from sip_bot.tts import XttsV2Adapter  # noqa: E402
from sip_bot.transfer import FakeOperator, TransferOrchestrator  # noqa: E402
from sip_bot.runtime_wiring import IncomingCallReadinessGate  # noqa: E402


LOGGER = logging.getLogger("sip_bot.live_service")
ASR_MODEL = "/home/sipbot/.local/models/faster-whisper-large-v3-edaa852e"
XTTS_MODEL = Path("/home/sipbot/.cache/sip-bot-c4-xtts-v2-model")
OUTPUT_ROOT = PROJECT_ROOT / constants.CONVERSATION_ROOT / "live-service"


def _log_tts_latency(event: Any) -> None:
    LOGGER.info(
        "tts_latency stage=%s call_id=%s turn_id=%s channel_id=%s generation=%d "
        "timestamp_ns=%d payload_bytes=%d",
        event.stage.value,
        event.call_id,
        event.turn_id or "-",
        event.channel_id,
        event.generation,
        event.timestamp_ns,
        event.payload_bytes,
    )


class _EventInbox:
    """Thread-safe temporary sink used while no call wiring owns the adapter."""

    def __init__(self) -> None:
        self._events: Queue[NormalizedSipEvent] = Queue()

    def publish(self, event: NormalizedSipEvent) -> None:
        self._events.put_nowait(event)

    def drain(self) -> list[NormalizedSipEvent]:
        result: list[NormalizedSipEvent] = []
        while True:
            try:
                result.append(self._events.get_nowait())
            except Empty:
                return result


@dataclass(slots=True)
class _SharedOwners:
    index: LocalKnowledgeIndex
    prompt: Any
    llm: LlmFacade
    tts: XttsV2Adapter
    asr_backend: FasterWhisperC2Backend
    query_builder: KnowledgeQueryBuilder
    transfer: TransferOrchestrator
    rag: CallScopedRagController


class _AlreadyWarmed:
    ready = True

    async def ensure_ready(self) -> None:
        return None


def _load_and_warm() -> _SharedOwners:
    """Initialize every lazy model owner before publishing SIP availability."""

    runtime = ApplicationRuntime.from_constants()
    runtime.start()
    profile = _profile()
    llm = LlmFacade(OllamaHttpClient(endpoint=constants.LLM_HTTP_ENDPOINT))
    prompt = build_default_prompt_manager()
    query_builder = KnowledgeQueryBuilder()
    holders: dict[str, Any] = {}
    asr_backend = FasterWhisperC2Backend(
        ASR_MODEL,
        language="ru",
        device="cuda",
        compute_type="int8_float16",
        no_speech_threshold=constants.ASR_NO_SPEECH_THRESHOLD,
        segment_end_tolerance_ms=constants.ASR_SEGMENT_END_TOLERANCE_MS,
    )

    def load_index() -> dict[str, object]:
        index = LocalKnowledgeIndex.load(
            PROJECT_ROOT / constants.KNOWLEDGE_INDEX_PATH,
            expected_index_version=constants.RAG_INDEX_VERSION,
            expected_corpus_version=constants.RAG_CORPUS_VERSION,
            expected_embedding_model=constants.RAG_EMBEDDING_MODEL,
            expected_dimension=constants.RAG_INDEX_DIMENSION,
            expected_chunking_policy=constants.RAG_CHUNKING_POLICY_VERSION,
            expected_corpus_sha256=constants.RAG_CORPUS_SHA256,
        )
        holders["index"] = index
        return {"chunks": index.item_count, "dimension": index.dimension}

    def warm_llm() -> dict[str, object]:
        question = "Почему небо днём кажется голубым?"
        index: LocalKnowledgeIndex = holders["index"]
        knowledge = index.query(
            query_builder.build(question),
            llm,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
            context_id="live-service-warmup-knowledge",
        )
        request = prompt.prepare(
            call_id="live-service-warmup",
            turn_id="live-service-warmup:turn-1",
            final_user_text=question,
            snapshot=ContextSnapshot("live-service-warmup", 0, ()),
            knowledge_context=knowledge,
        )
        trace = llm.warmup(request)
        return {"sources": list(knowledge.source_ids), "trace": trace.as_dict()}

    def initialize_tts() -> dict[str, object]:
        engine = _RealXttsEngine(XTTS_MODEL, XTTS_MODEL / "samples" / "en_sample.wav")
        holders["tts"] = XttsV2Adapter(
            engine,
            operation_id_factory=lambda: f"live-tts-{time.monotonic_ns()}",
            latency_sink=_log_tts_latency,
        )
        return {
            "model": str(XTTS_MODEL),
            "stream_chunk_size": constants.TTS_STREAM_CHUNK_SIZE,
            "overlap_wav_len": constants.TTS_STREAM_OVERLAP_WAV_LEN,
        }

    report = runtime.warmup(
        (
            ("rag-index", load_index),
            ("llm-chat", warm_llm),
            ("asr", lambda: asr_backend.warmup(input_sample_rate_hz=profile.sample_rate_hz)),
            ("tts-initialize", initialize_tts),
            ("tts-stream", lambda: holders["tts"].warmup(profile=profile)),
        )
    )
    LOGGER.info("all providers ready elapsed_ms=%.1f", report.elapsed_ms)
    runtime.shutdown("warmup_complete")

    # Keep a separate immutable baseline object.  The pipeline receives the
    # stable ``holders["index"]`` handle and the call-scoped controller
    # publishes custom artifacts into that same handle before SIP 200.
    baseline_index = LocalKnowledgeIndex.load(
        PROJECT_ROOT / constants.KNOWLEDGE_INDEX_PATH,
        expected_index_version=constants.RAG_INDEX_VERSION,
        expected_corpus_version=constants.RAG_CORPUS_VERSION,
        expected_embedding_model=constants.RAG_EMBEDDING_MODEL,
        expected_dimension=constants.RAG_INDEX_DIMENSION,
        expected_chunking_policy=constants.RAG_CHUNKING_POLICY_VERSION,
        expected_corpus_sha256=constants.RAG_CORPUS_SHA256,
    )

    def load_published_index(index_path: Path, payload: dict[str, Any]) -> LocalKnowledgeIndex:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("published RAG metadata is missing")
        index_version = metadata.get("index_version")
        corpus_version = metadata.get("corpus_version")
        embedding_model = metadata.get("embedding_model")
        dimension = metadata.get("dimension")
        if not all(isinstance(value, str) for value in (index_version, corpus_version, embedding_model)):
            raise ValueError("published RAG metadata is incomplete")
        if not isinstance(dimension, int):
            raise ValueError("published RAG dimension is invalid")
        if embedding_model != constants.RAG_EMBEDDING_MODEL or dimension != constants.RAG_INDEX_DIMENSION:
            raise ValueError("published RAG is incompatible with the live bot embedding contract")
        return LocalKnowledgeIndex.load(
            index_path,
            expected_index_version=index_version,
            expected_corpus_version=corpus_version,
            expected_embedding_model=constants.RAG_EMBEDDING_MODEL,
            expected_dimension=constants.RAG_INDEX_DIMENSION,
            expected_chunking_policy=constants.RAG_CHUNKING_POLICY_VERSION,
        )

    rag = CallScopedRagController(
        target_index=holders["index"],
        baseline_index=baseline_index,
        registry_root=PROJECT_ROOT / "demo-web" / "runtime" / "registry",
        index_loader=load_published_index,
        baseline_metadata={"topic": "демонстрационному корпусу"},
    )
    operator = FakeOperator(constants.OPERATOR_TARGET)
    return _SharedOwners(
        index=holders["index"],
        prompt=prompt,
        llm=llm,
        tts=holders["tts"],
        asr_backend=asr_backend,
        query_builder=query_builder,
        transfer=TransferOrchestrator(operator),
        rag=rag,
    )


def _create_call(adapter: SipMediaAdapter, call_id: str, shared: _SharedOwners):
    runtime = ApplicationRuntime.from_constants()
    runtime.start()
    owners = CallOwners(
        context=ContextStore(OUTPUT_ROOT / "context", call_id),
        report=ReportFinalizer(OUTPUT_ROOT / "reports"),
        retrieval=shared.index,
        prompt=shared.prompt,
        llm=shared.llm,
        tts=shared.tts,
        transfer=shared.transfer,
    )
    composition = runtime.compose_call(call_id, owners)
    pipeline = ConversationPipeline(
        composition,
        query_builder=shared.query_builder,
        retrieval=shared.index,
        prompt=shared.prompt,
        llm=shared.llm,
        tts=shared.tts,
        media_profile=adapter.media_profile,
        transfer=shared.transfer,
        greeting_text=runtime.config.call_greeting_text,
        transfer_confirmation_text=runtime.config.transfer_confirmation_text,
        top_k=constants.RAG_TOP_K,
        threshold=constants.RAG_RELEVANCE_THRESHOLD,
        latency_sink=_log_tts_latency,
    )
    speech = SpeechIngress(
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

    def prepare_call(_call_id: str, caller_id: str) -> dict[str, Any]:
        metadata = shared.rag.prepare(caller_id)
        topic = str(metadata.get("topic") or "текущему корпусу").strip()
        pipeline.greeting_text = (
            f"Здравствуйте! Я Василиса. Я готова ответить на вопросы по теме «{topic}»."
        )
        return metadata

    wiring = runtime.create_call_wiring(
        composition,
        sip_media=adapter,
        speech=speech,
        asr=StreamingAsrAdapter(shared.asr_backend),
        pipeline=pipeline,
        incoming_admission=IncomingCallReadinessGate(
            adapter,
            readiness=_AlreadyWarmed(),
            call_prepare=prepare_call,
            call_cleanup=lambda _call_id, caller_id: shared.rag.release(caller_id),
            preparation_timeout_s=15.0,
        ),
        latency_sink=_log_tts_latency,
    )
    return runtime, composition, pipeline, wiring


async def _wait_for_registration(adapter: SipMediaAdapter, stop: asyncio.Event, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not stop.is_set() and time.monotonic() < deadline:
        adapter.poll(10)
        adapter.dispatch_events()
        if adapter.registration_ready:
            LOGGER.info("SIP registration ready registrar=%s", constants.SIP_REGISTRAR_URI)
            return
        await asyncio.sleep(0.02)
    raise TimeoutError(f"SIP registration did not become ready: {adapter.registration_status}")


async def _run() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:
            pass

    LOGGER.info("warming natural-science assistant before SIP registration")
    shared = await asyncio.to_thread(_load_and_warm)
    inbox = _EventInbox()
    adapter = SipMediaAdapter(
        SipMediaConfig.from_runtime_config(
            ApplicationRuntime.from_constants().config,
            local_uri=constants.SIP_REGISTRATION_IDENTITY_URI,
            bind_port=constants.SIP_BIND_PORT,
        ),
        event_sink=inbox,
        enforce_runtime=True,
    )
    adapter.start()
    try:
        await _wait_for_registration(adapter, stop)
        LOGGER.info("assistant available: account=%s queue=7100", constants.SIP_REGISTRATION_USERNAME)
        while not stop.is_set():
            adapter.poll(10)
            adapter.dispatch_events()
            events = inbox.drain()
            incoming = next(
                (
                    event
                    for event in events
                    if event.kind is SipEventKind.CALL_STARTED
                    and event.details_dict().get("direction") == "incoming"
                ),
                None,
            )
            if incoming is None:
                await asyncio.sleep(0.01)
                continue

            call_id = incoming.call_id
            caller_id = incoming.caller_id or incoming.details_dict().get("caller_id")
            LOGGER.info("incoming call queued call_id=%s caller_id=%s", call_id, caller_id or "-")
            runtime, composition, pipeline, wiring = _create_call(adapter, call_id, shared)
            wiring.start()
            # compose_call opens the authoritative call state before wiring is
            # attached.  Replay protocol observations and explicitly complete
            # the already-provisioned 180 observation.  The admission gate
            # sends 200 only after the caller-scoped RAG has been loaded.
            for event in events:
                adapter.event_sink.publish(event)
            disconnected_at: float | None = None
            try:
                while not stop.is_set():
                    await wiring.step()
                    if wiring.errors or pipeline.errors:
                        raise RuntimeError("; ".join(wiring.errors + pipeline.errors))
                    if composition.report_finalized:
                        LOGGER.info("call complete call_id=%s report=%s", call_id, composition.report_path)
                        break
                    if adapter.active_call_id is None:
                        disconnected_at = disconnected_at or time.monotonic()
                        if time.monotonic() - disconnected_at > 10.0:
                            raise TimeoutError("call ended but report was not finalized")
                    await asyncio.sleep(0.01)
            except BaseException:
                LOGGER.exception("call failed call_id=%s", call_id)
            finally:
                vad_analytics = wiring.speech.vad.analytics_snapshot()
                if vad_analytics is not None:
                    LOGGER.info(
                        "VAD analytics call_id=%s total=%d raw_speech=%d accepted_speech=%d "
                        "rejected_low_energy=%d noise_floor_dbfs=%.1f threshold_dbfs=%.1f "
                        "speech_level_dbfs=%s",
                        call_id,
                        vad_analytics.total_frames,
                        vad_analytics.raw_speech_frames,
                        vad_analytics.accepted_speech_frames,
                        vad_analytics.rejected_low_energy_frames,
                        vad_analytics.noise_floor_dbfs,
                        vad_analytics.speech_threshold_dbfs,
                        (
                            "unknown"
                            if vad_analytics.speech_level_dbfs is None
                            else f"{vad_analytics.speech_level_dbfs:.1f}"
                        ),
                    )
                wiring.stop("call_complete")
                if isinstance(caller_id, str):
                    shared.rag.release(caller_id)
                runtime.shutdown("call_complete")
                inbox = _EventInbox()
                adapter.event_sink = inbox
    finally:
        adapter.close("service_stop")


def main() -> int:
    logging.basicConfig(
        level=getattr(logging, constants.LOG_LEVEL),
        format=constants.LOG_FORMAT,
        datefmt=constants.LOG_DATE_FORMAT,
    )
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 0
    except BaseException:
        LOGGER.exception("live assistant stopped")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
