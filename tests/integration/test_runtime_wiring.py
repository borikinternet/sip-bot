"""Deterministic coverage for the I.1 asyncio/thread wiring boundary."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from queue import Queue
from threading import Event

from sip_bot.config import RuntimeConfig
from sip_bot.context import ContextStore
from sip_bot.conversation_pipeline import ConversationPipeline
from sip_bot.dialogue.events import PlaybackStatus, SpeechEvent, SpeechEventKind
from sip_bot.llm import LlmFacade, OllamaHttpClient
from sip_bot.media import AsrChunker
from sip_bot.prompt import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec
from sip_bot.report import ReportFinalizer
from sip_bot.retrieval import (
    DeterministicEmbeddingBackend,
    EmbeddingRequest,
    LocalKnowledgeIndex,
    KnowledgeQueryBuilder,
    load_corpus,
)
from sip_bot.runtime import ApplicationRuntime, RuntimeProbe
from sip_bot.runtime_composition import CallOwners
from sip_bot.runtime_wiring import CallRuntimeWiring
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from sip_bot.speech import (
    AsrHypothesis,
    EndpointingConfig,
    EndpointEventKind,
    SpeechIngress,
    StreamingAsrAdapter,
    TranscriptAssembler,
    TurnDetector,
    VadProcessor,
    WebRtcVadCandidate,
)
from sip_bot.tts import TtsPcmChunk


class _ByteVad:
    def is_speech(self, pcm_s16le: bytes, _sample_rate_hz: int) -> bool:
        return pcm_s16le[:1] == b"\x01"


class _Response:
    def __init__(self, *, lines: list[bytes] | None = None, body: bytes = b"{}") -> None:
        self.lines = list(lines or [])
        self.body = body
        self.closed = False

    def readline(self) -> bytes:
        if self.closed or not self.lines:
            return b""
        return self.lines.pop(0)

    def read(self, _amount: int = -1) -> bytes:
        return self.body

    def close(self) -> None:
        self.closed = True


class _AsrBackend:
    def transcribe_chunk(self, _chunk):
        return [{"text": "почему небо голубое", "is_final": False}]


class _BlockingAsrBackend:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def transcribe_chunk(self, _chunk):
        self.started.set()
        self.release.wait(timeout=2.0)
        return [{"text": "запоздалый результат", "is_final": False}]


class _Tts:
    def stream_approved_text(self, chunks, *, channel_id, profile, cancel=None):
        for item in chunks:
            if cancel is not None and cancel.is_set():
                return
            yield TtsPcmChunk(
                operation_id=item.operation_id,
                call_id=item.call_id,
                channel_id=channel_id,
                generation=item.generation,
                sequence=1,
                pcm_s16le=b"\x01\x00" * profile.frame_size_samples,
                profile=profile,
                is_final=True,
            )


class _Sip:
    def __init__(self, profile: NegotiatedMediaProfile) -> None:
        self.profile = profile
        self.event_sink = None
        self.events: Queue[NormalizedSipEvent] = Queue()
        self.frames: Queue[PcmFrame] = Queue()
        self.answered = 0
        self.hung_up = 0
        self.transfers: list[str] = []
        self.egress: list[PcmFrame] = []
        self.polls = 0
        self.active_call_id = "call-wiring"

    def poll(self, _timeout_ms: int = 0) -> int:
        self.polls += 1
        return 0

    def dispatch_events(self) -> int:
        delivered = 0
        while not self.events.empty():
            event = self.events.get_nowait()
            self.event_sink.publish(event)
            delivered += 1
        return delivered

    def next_ingress_frame(self) -> PcmFrame | None:
        try:
            return self.frames.get_nowait()
        except Exception:
            return None

    def enqueue_egress_frame(self, frame: PcmFrame) -> bool:
        self.egress.append(frame)
        return True

    def media_profile(self):
        return self.profile

    def answer(self) -> bool:
        self.answered += 1
        return True

    def hangup(self, _reason: str = "local_hangup") -> bool:
        self.hung_up += 1
        return True

    def transfer(self, target: str) -> bool:
        self.transfers.append(target)
        return True


class _Pipeline:
    def __init__(self) -> None:
        self.audio_sink = lambda _chunk: None
        self.turns = []
        self.closed = False

    @property
    def active_workers(self) -> int:
        return 0

    def submit_final_turn(self, turn) -> bool:
        self.turns.append(turn)
        return True

    def drain_control(self) -> int:
        return 0

    def close(self, _reason: str) -> None:
        self.closed = True


def _profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile("PCMU", 0, 20.0, 8000, 1, 160, rx_payload_type=0, tx_payload_type=0)


def _frame(sequence: int, speech: bool) -> PcmFrame:
    profile = _profile()
    return PcmFrame(
        "call-wiring",
        "call-wiring:media",
        1,
        sequence,
        sequence * 20_000_000,
        (b"\x01" if speech else b"\x00") * profile.frame_bytes,
        profile,
    )


def _speech() -> SpeechIngress:
    def assembler(turn_id: str) -> TranscriptAssembler:
        return TranscriptAssembler("call-wiring", "call-wiring:media", 1, turn_id, stable_prefix_min_chars=0)

    return SpeechIngress(
        vad=VadProcessor(WebRtcVadCandidate(backend=_ByteVad())),
        turn_detector=TurnDetector(EndpointingConfig(soft_endpoint_ms=20, hard_endpoint_ms=40, min_speech_ms=20)),
        assembler=assembler("call-wiring:turn-1"),
        assembler_factory=assembler,
        defer_endpoint_finalization=True,
    )


def _runtime(tmp_path):
    runtime = ApplicationRuntime.from_constants()
    runtime.start = lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False)
    runtime.started = True
    owners = CallOwners(
        context=ContextStore(tmp_path / "context", "call-wiring"),
        report=ReportFinalizer(tmp_path / "reports"),
    )
    composition = runtime.compose_call("call-wiring", owners)
    config = replace(
        RuntimeConfig.from_constants(),
        asr_chunk_ms=40,
        asr_chunk_flush_ms=40,
        audio_input_buffer_capacity_frames=8,
        audio_output_buffer_capacity_frames=8,
    )
    sip = _Sip(_profile())
    pipeline = _Pipeline()
    wiring = CallRuntimeWiring(
        composition,
        sip_media=sip,
        speech=_speech(),
        asr=StreamingAsrAdapter(_AsrBackend()),
        pipeline=pipeline,
        config=config,
    )
    return runtime, composition, sip, pipeline, wiring


def test_asyncio_wiring_delivers_pcm_to_asr_and_keeps_control_on_main_loop(tmp_path) -> None:
    async def scenario() -> None:
        runtime, composition, sip, pipeline, wiring = _runtime(tmp_path)
        sip.events.put(NormalizedSipEvent("call-wiring", SipEventKind.CALL_ANSWERED, 1, 1))
        for sequence in range(1, 3):
            sip.frames.put(_frame(sequence, True))
        for sequence in range(3, 6):
            sip.frames.put(_frame(sequence, False))
        for _ in range(40):
            await wiring.step()
            await asyncio.sleep(0.001)
            if pipeline.turns:
                break
        assert sip.polls > 0
        assert composition.fsm.state.value == "listening"
        assert len(pipeline.turns) == 1
        assert pipeline.turns[0].text == "почему небо голубое"
        assert wiring.stats.asr_chunks_queued >= 1
        assert wiring.stats.asr_hypotheses >= 1
        wiring.stop()
        runtime.shutdown()

    asyncio.run(scenario())


def test_endpointing_events_are_materialized_on_the_fsm_control_boundary(tmp_path) -> None:
    async def scenario() -> None:
        runtime, composition, sip, _pipeline, wiring = _runtime(tmp_path)
        observed: list[SpeechEvent] = []

        def observe(event: object, accepted: bool) -> None:
            if accepted and isinstance(event, SpeechEvent):
                observed.append(event)

        composition.add_control_observer(observe)
        sip.events.put(NormalizedSipEvent("call-wiring", SipEventKind.CALL_ANSWERED, 1, 1))
        for sequence in range(1, 3):
            sip.frames.put(_frame(sequence, True))
        for sequence in range(3, 6):
            sip.frames.put(_frame(sequence, False))

        for _ in range(80):
            await wiring.step()
            await asyncio.sleep(0.001)
            if wiring.stats.asr_hypotheses:
                break

        assert [event.kind for event in observed[:4]] == [
            SpeechEventKind.SPEECH_STARTED,
            SpeechEventKind.PAUSE_CANDIDATE,
            SpeechEventKind.SOFT_ENDPOINT,
            SpeechEventKind.HARD_ENDPOINT,
        ]
        assert all(event.channel_id == "call-wiring:media" for event in observed)
        assert all(event.channel_generation == 1 for event in observed)
        wiring.stop()
        runtime.shutdown()

    asyncio.run(scenario())


def test_tts_sink_materializes_buffer_pacer_and_direct_sip_egress(tmp_path) -> None:
    async def scenario() -> None:
        runtime, _composition, sip, pipeline, wiring = _runtime(tmp_path)
        wiring.start()
        chunk = TtsPcmChunk(
            "tts-op",
            "call-wiring",
            "call-wiring:playback",
            1,
            1,
            b"\x01\x00" * 160,
            _profile(),
            is_final=True,
        )
        pipeline.audio_sink(chunk)
        await wiring.step(now_ns=10**18)
        assert len(sip.egress) == 1
        assert sip.egress[0].profile == _profile()
        assert wiring.stats.tts_chunks == 1
        assert wiring.stats.tts_frames_sent == 1
        wiring.stop()
        runtime.shutdown()

    asyncio.run(scenario())


def test_playback_is_cancelled_when_sip_media_closes_before_next_pump(tmp_path) -> None:
    async def scenario() -> None:
        runtime, _composition, sip, pipeline, wiring = _runtime(tmp_path)
        wiring.start()
        chunk = TtsPcmChunk(
            "tts-op",
            "call-wiring",
            "call-wiring:playback",
            1,
            1,
            b"\x01\x00" * 160,
            _profile(),
            is_final=True,
        )
        pipeline.audio_sink(chunk)
        sip.active_call_id = None
        await wiring.step(now_ns=10**18)

        assert wiring.stats.tts_frames_sent == 0
        assert wiring.errors == []
        wiring.stop()
        runtime.shutdown()

    asyncio.run(scenario())


def test_runtime_wiring_drives_existing_rag_llm_tts_pipeline(tmp_path) -> None:
    async def scenario() -> None:
        runtime, composition, _sip_unused, _pipeline_unused, _wiring_unused = _runtime(tmp_path)
        profile = _profile()
        corpus_root = Path(__file__).parents[2] / "data" / "knowledge" / "corpus"
        _, chunks = load_corpus(corpus_root)
        embedding = DeterministicEmbeddingBackend()

        def opener(url: str, body: bytes, _timeout: float):
            payload = json.loads(body.decode("utf-8"))
            if url.endswith("/api/embed"):
                vector = embedding.embed(
                    EmbeddingRequest("runtime-test", payload["input"], payload["model"])
                ).vector
                return _Response(body=json.dumps({"embeddings": [vector]}).encode("utf-8"))
            decision = {"action": "answer", "text": "Из-за рассеяния света в атмосфере."}
            line = json.dumps(
                {"message": {"content": json.dumps(decision, ensure_ascii=False)}, "done": True},
                ensure_ascii=False,
            ).encode("utf-8")
            return _Response(lines=[line + b"\n"])

        llm = LlmFacade(
            OllamaHttpClient(
                chat_model="runtime-test-chat",
                embedding_model="runtime-test-embedding",
                opener=opener,
            )
        )
        index = LocalKnowledgeIndex.build(
            chunks,
            embedding,
            index_version="runtime-test-index",
            embedding_model="runtime-test-embedding",
        )
        prompt = SkillPromptManager(
            skill=SkillSpec("answer-ru", "1", "Отвечай кратко и только по базе знаний."),
            prompt=PromptSpec(
                "runtime-test-prompt",
                "1",
                "{instruction}\nКонтекст:\n{context}\nЗнания:\n{knowledge}\nВопрос:\n{user_text}",
            ),
            profile=GenerationProfile("short", "1", 96, 0.1),
            output_schema_id="structured-dialogue-decision-v1",
        )
        sip = _Sip(profile)
        pipeline = ConversationPipeline(
            composition,
            query_builder=KnowledgeQueryBuilder(),
            retrieval=index,
            prompt=prompt,
            llm=llm,
            tts=_Tts(),
            media_profile=profile,
        )
        wiring = CallRuntimeWiring(
            composition,
            sip_media=sip,
            speech=_speech(),
            asr=StreamingAsrAdapter(_AsrBackend()),
            pipeline=pipeline,
            config=replace(
                RuntimeConfig.from_constants(),
                asr_chunk_ms=40,
                asr_chunk_flush_ms=40,
                audio_input_buffer_capacity_frames=8,
                audio_output_buffer_capacity_frames=8,
            ),
        )
        sip.events.put(NormalizedSipEvent("call-wiring", SipEventKind.CALL_ANSWERED, 1, 1))
        for sequence in range(1, 3):
            sip.frames.put(_frame(sequence, True))
        for sequence in range(3, 6):
            sip.frames.put(_frame(sequence, False))

        for _ in range(100):
            await wiring.step()
            await asyncio.sleep(0.001)
            if pipeline.active_workers == 0 and wiring.stats.tts_frames_sent:
                break
        assert pipeline.wait(2.0)
        for _ in range(20):
            await wiring.step()
            await asyncio.sleep(0.001)
            if composition.fsm.state.value == "listening" and sip.egress:
                break

        assert composition.fsm.state.value == "listening"
        assert composition.rag_contexts and composition.rag_contexts[0].sufficient
        assert sip.egress and sip.egress[0].profile == profile
        assert wiring.stats.final_turns == 1
        assert wiring.stats.tts_frames_sent == 1
        assert not pipeline.errors
        composition.submit_control(
            NormalizedSipEvent("call-wiring", SipEventKind.REMOTE_HANGUP, 2, 2, reason="BYE")
        )
        await wiring.step()
        assert composition.report_finalized
        wiring.stop()
        runtime.shutdown()

    asyncio.run(scenario())


def test_protocol_terminal_event_does_not_wait_for_asr_worker(tmp_path) -> None:
    async def scenario() -> None:
        runtime, composition, sip, _pipeline, _wiring = _runtime(tmp_path)
        backend = _BlockingAsrBackend()
        wiring = CallRuntimeWiring(
            composition,
            sip_media=sip,
            speech=_speech(),
            asr=StreamingAsrAdapter(backend),
            pipeline=_Pipeline(),
            config=replace(
                RuntimeConfig.from_constants(),
                asr_chunk_ms=40,
                asr_chunk_flush_ms=40,
                audio_input_buffer_capacity_frames=8,
                audio_output_buffer_capacity_frames=8,
            ),
        )
        sip.events.put(NormalizedSipEvent("call-wiring", SipEventKind.CALL_ANSWERED, 1, 1))
        sip.frames.put(_frame(1, True))
        sip.frames.put(_frame(2, True))
        await wiring.step()
        assert backend.started.wait(timeout=1.0)

        sip.events.put(
            NormalizedSipEvent("call-wiring", SipEventKind.REMOTE_HANGUP, 2, 2, reason="BYE")
        )
        await asyncio.wait_for(wiring.step(), timeout=0.2)
        assert composition.fsm.is_terminal
        assert composition.report_finalized

        backend.release.set()
        wiring.stop()
        runtime.shutdown()

    asyncio.run(scenario())
