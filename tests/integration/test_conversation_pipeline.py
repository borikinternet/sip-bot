"""Deterministic full data-plane composition coverage for I0/J4 handoff."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace
from threading import Event
from typing import Callable

from sip_bot.context import ContextStore
from sip_bot.config import RuntimeConfig
from sip_bot.conversation_pipeline import ConversationPipeline
from sip_bot.dialogue import DialogueState
from sip_bot.dialogue.events import PlaybackEvent, PlaybackStatus, SpeechEvent, SpeechEventKind
from sip_bot.llm import LlmFacade, OllamaHttpClient
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
from sip_bot.sip_media.models import NegotiatedMediaProfile
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from sip_bot.speech import EndpointEventKind, FinalUserTurn
from sip_bot.tts import ApprovedTextChunk, TtsPcmChunk
from sip_bot.transfer import FakeOperator, TransferOrchestrator
from sip_bot.understanding import SemanticTurnParser


class _Response:
    def __init__(self, *, lines: list[bytes] = None, body: bytes = b"{}") -> None:
        self.lines = list(lines or [])
        self.body = body
        self.closed = False

    def readline(self) -> bytes:
        if self.closed or not self.lines:
            return b""
        return self.lines.pop(0)

    def read(self, amount: int = -1) -> bytes:
        return self.body

    def close(self) -> None:
        self.closed = True


class _BlockingResponse(_Response):
    def __init__(self) -> None:
        super().__init__(lines=[b'{"message":{"content":"prefix"},"done":false}\n'])
        self.read_started = Event()
        self.release = Event()

    def readline(self) -> bytes:
        if self.lines:
            return super().readline()
        self.read_started.set()
        self.release.wait(timeout=2.0)
        return b'{"message":{"content":"stale"},"done":true}\n'


class _Tts:
    def __init__(self) -> None:
        self.approved: list[ApprovedTextChunk] = []

    def stream_approved_text(self, chunks, *, channel_id, profile, cancel=None):
        values = tuple(chunks)
        self.approved.extend(values)
        for item in values:
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


def _submit(pipeline: ConversationPipeline, turn: FinalUserTurn) -> bool:
    semantic = SemanticTurnParser().parse(turn, pipeline.composition.fsm.current_expectation())
    return pipeline.submit_semantic_turn(semantic)


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
        source="test.sdp",
    )


def _finish_physical_playback(composition) -> None:
    playback_generation = next(
        generation
        for channel_id, generation in composition.fsm.active_channels
        if channel_id == "playback"
    )
    composition.submit_control(
        PlaybackEvent(
            composition.session.call_id,
            PlaybackStatus.COMPLETED,
            channel_id="playback",
            channel_generation=playback_generation,
            operation_id=composition.fsm.active_operation_id,
        )
    )
    composition.drain_control()


def _components(
    tmp_path: Path,
    *,
    response: dict[str, str] | None = None,
    response_factory: Callable[[], _Response] | None = None,
    transfer: TransferOrchestrator | None = None,
    observed_prompts: list[str] | None = None,
    greeting_text: str = "",
):
    call_id = "pipeline-call"
    corpus_root = Path(__file__).parents[2] / "data" / "knowledge" / "corpus"
    _, chunks = load_corpus(corpus_root)
    embedding = DeterministicEmbeddingBackend()

    def opener(url: str, body: bytes, timeout: float):
        payload = json.loads(body.decode("utf-8"))
        if url.endswith("/api/embed"):
            vector = embedding.embed(EmbeddingRequest("probe", payload["input"], payload["model"])).vector
            return _Response(body=json.dumps({"embeddings": [vector]}).encode("utf-8"))
        answer = response or {"action": "answer", "text": "Небо голубое из-за рэлеевского рассеяния."}
        if observed_prompts is not None:
            observed_prompts.append(payload["messages"][0]["content"])
        if response_factory is not None:
            return response_factory()
        line = json.dumps({"message": {"content": json.dumps(answer, ensure_ascii=False)}, "done": True}).encode()
        return _Response(lines=[line + b"\n"])

    llm = LlmFacade(
        OllamaHttpClient(
            chat_model="test-chat",
            embedding_model="fake-v1",
            opener=opener,
        )
    )
    index = LocalKnowledgeIndex.build(chunks, embedding, index_version="test-index", embedding_model="fake-v1")
    prompt = SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "Отвечай кратко и только по базе знаний."),
        prompt=PromptSpec(
            "mvp-answer-ru",
            "1",
            "{instruction}\nКонтекст:\n{context}\nЗнания:\n{knowledge}\nВопрос:\n{user_text}",
        ),
        profile=GenerationProfile("short", "1", 96, 0.1),
        output_schema_id="structured-dialogue-decision-v1",
    )
    runtime = ApplicationRuntime(replace(RuntimeConfig.from_constants(), call_greeting_text=greeting_text))
    runtime.start()
    owners = CallOwners(
        context=ContextStore(tmp_path / "context", call_id),
        report=ReportFinalizer(tmp_path / "reports"),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=_Tts(),
        transfer=transfer,
    )
    composition = runtime.compose_call(call_id, owners)
    return runtime, composition, llm, index, prompt, owners.tts


def test_call_greeting_uses_tts_without_llm_or_retrieval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    prompts: list[str] = []
    runtime, composition, llm, index, prompt, tts = _components(
        tmp_path,
        observed_prompts=prompts,
        greeting_text="Алло.",
    )
    audio: list[TtsPcmChunk] = []
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=_profile(),
        audio_sink=audio.append,
        greeting_text="Алло.",
    )

    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()
    assert composition.fsm.state is DialogueState.PLAYING
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert composition.fsm.state is DialogueState.PLAYING
    _finish_physical_playback(composition)

    assert composition.fsm.state is DialogueState.LISTENING
    assert [item.text for item in tts.approved] == ["Алло."]
    assert tts.approved[0].operation_id == "call-greeting"
    assert audio
    assert prompts == []
    assert composition.rag_contexts == ()
    assert composition.owners.context.snapshot().turns[0].text == "Алло."
    assert pipeline.errors == []
    runtime.shutdown()


def test_pipeline_runs_rag_llm_and_tts_off_dispatcher(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    runtime, composition, llm, index, prompt, tts = _components(tmp_path)
    profile = _profile()
    audio: list[TtsPcmChunk] = []
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=profile,
        audio_sink=audio.append,
    )
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()

    turn = FinalUserTurn(
        "pipeline-call",
        "speech_ingress",
        1,
        "pipeline-call:turn-1",
        "Почему небо днём кажется голубым?",
        1,
        500_000_000,
        EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, turn)
    assert composition.fsm.state is DialogueState.THINKING
    assert pipeline.wait(2.0)
    assert composition.fsm.state is DialogueState.THINKING

    pipeline.drain_control()
    assert any(item.current is DialogueState.PLAYING for item in composition.fsm.trace)
    assert pipeline.wait(2.0)
    pipeline.drain_control()

    assert composition.fsm.state is DialogueState.PLAYING
    _finish_physical_playback(composition)
    assert composition.fsm.state is DialogueState.LISTENING
    assert not pipeline.errors
    assert audio and audio[0].profile == profile
    assert tts.approved[0].text == "Небо голубое из-за рэлеевского рассеяния."
    assert composition.owners.context.snapshot().turns[-1].role == "assistant"
    assert composition.rag_contexts[0].sufficient is True
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.REMOTE_HANGUP, 3, 3, reason="BYE"))
    composition.drain_control()
    assert composition.report_finalized
    runtime.shutdown()


def test_pipeline_carries_previous_turn_context_into_the_next_prompt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    prompts: list[str] = []
    runtime, composition, llm, index, prompt, tts = _components(tmp_path, observed_prompts=prompts)
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=_profile(),
    )
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()

    first = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-context-1",
        "Почему небо днём кажется голубым?", 1, 500_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, first)
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    _finish_physical_playback(composition)
    assert composition.fsm.state is DialogueState.LISTENING

    second = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-context-2",
        "А что происходит на закате?", 2, 600_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, second)
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert pipeline.wait(2.0)
    pipeline.drain_control()

    assert len(prompts) == 2
    assert "Почему небо днём кажется голубым?" in prompts[1]
    assert "Небо голубое из-за рэлеевского рассеяния." in prompts[1]
    assert "А что происходит на закате?" in prompts[1]
    assert composition.owners.context.snapshot().turns[-1].role == "assistant"
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.REMOTE_HANGUP, 3, 3, reason="BYE"))
    composition.drain_control()
    assert composition.report_finalized
    runtime.shutdown()


def test_pipeline_cancels_inference_on_barge_in_without_stale_decision(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    blocking = _BlockingResponse()
    runtime, composition, llm, index, prompt, tts = _components(
        tmp_path,
        response_factory=lambda: blocking,
    )
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
    )
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()
    turn = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-1",
        "Почему небо днём кажется голубым?", 1, 500_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, turn)
    assert blocking.read_started.wait(timeout=2.0)

    composition.submit_control(SpeechEvent("pipeline-call", SpeechEventKind.BARGE_IN))
    composition.drain_control()
    blocking.release.set()
    assert pipeline.wait(2.0)
    assert composition.fsm.state is DialogueState.LISTENING
    assert not pipeline._decisions
    assert not pipeline.errors
    runtime.shutdown()


def test_pipeline_runs_unknown_answer_confirmation_transfer_and_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    operator = FakeOperator("sip:operator@127.0.0.1:5090")
    transfer = TransferOrchestrator(operator)
    runtime, composition, llm, index, prompt, tts = _components(
        tmp_path,
        response={"action": "offer_transfer", "text": "Подключить оператора?"},
        transfer=transfer,
    )
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=_profile(),
        transfer=transfer,
        threshold=0.99,
    )
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()
    unknown = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-unknown",
        "Как устроен телескоп?", 1, 500_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, unknown)
    assert pipeline.wait(2.0)
    composition.drain_control()
    assert pipeline.wait(2.0)
    composition.drain_control()
    _finish_physical_playback(composition)
    assert composition.fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION
    assert composition.rag_contexts[0].sufficient is False

    confirmation = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-confirm",
        "Да", 1, 600_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, confirmation)
    assert pipeline.wait(2.0)
    composition.drain_control()
    assert composition.fsm.state is DialogueState.TERMINAL
    assert operator.accepted
    assert composition.report_finalized
    assert "operator_connected" in composition.report_path.read_text(encoding="utf-8")
    runtime.shutdown()


def test_pipeline_compound_positive_answers_content_then_asks_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    answers = iter(
        (
            {"action": "offer_transfer", "text": "Подключить оператора?"},
            {"action": "answer", "text": "Небо голубое из-за рассеяния Рэлея."},
        )
    )

    def response_factory() -> _Response:
        line = json.dumps(
            {"message": {"content": json.dumps(next(answers), ensure_ascii=False)}, "done": True},
            ensure_ascii=False,
        ).encode("utf-8")
        return _Response(lines=[line + b"\n"])

    operator = FakeOperator("sip:operator@127.0.0.1:5090")
    transfer = TransferOrchestrator(operator)
    runtime, composition, llm, index, prompt, tts = _components(
        tmp_path,
        response_factory=response_factory,
        transfer=transfer,
    )
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=_profile(),
        transfer=transfer,
        transfer_confirmation_text="Подключить оператора?",
    )
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()

    unknown = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-unknown",
        "Как оформить отпуск?", 1, 500_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, unknown)
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    _finish_physical_playback(composition)
    assert composition.fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION

    compound = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-compound",
        "Да, соедините, но сначала ответьте, почему небо голубое?",
        2, 600_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, compound)
    assert composition.fsm.state is DialogueState.THINKING
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert composition.rag_contexts[-1].query_text == "ответьте, почему небо голубое?"

    _finish_physical_playback(composition)
    assert composition.fsm.state is DialogueState.OFFERING_TRANSFER
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    _finish_physical_playback(composition)
    assert composition.fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION
    assert [item.text for item in tts.approved][-2:] == [
        "Небо голубое из-за рассеяния Рэлея.",
        "Подключить оператора?",
    ]
    user_turns = [
        item for item in composition.owners.context.snapshot().turns if item.role == "user"
    ]
    assert [item.text for item in user_turns].count(compound.text) == 1

    confirmation = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-confirm",
        "Да", 3, 700_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, confirmation)
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert composition.fsm.state is DialogueState.TERMINAL
    assert operator.accepted
    report = composition.report_path.read_text(encoding="utf-8")
    assert "`confirm_pending`" in report
    assert "`knowledge_request`" in report
    runtime.shutdown()


def test_pipeline_compound_reject_keeps_residual_question(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    answers = iter(
        (
            {"action": "offer_transfer", "text": "Подключить оператора?"},
            {"action": "answer", "text": "Небо голубое из-за рассеяния Рэлея."},
        )
    )

    def response_factory() -> _Response:
        line = json.dumps(
            {"message": {"content": json.dumps(next(answers), ensure_ascii=False)}, "done": True},
            ensure_ascii=False,
        ).encode("utf-8")
        return _Response(lines=[line + b"\n"])

    runtime, composition, llm, index, prompt, tts = _components(
        tmp_path,
        response_factory=response_factory,
    )
    pipeline = ConversationPipeline(
        composition,
        query_builder=KnowledgeQueryBuilder(),
        retrieval=index,
        prompt=prompt,
        llm=llm,
        tts=tts,
        media_profile=_profile(),
    )
    composition.submit_control(NormalizedSipEvent("pipeline-call", SipEventKind.CALL_ANSWERED, 2, 2))
    composition.drain_control()

    unknown = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-unknown",
        "Как оформить отпуск?", 1, 500_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, unknown)
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    _finish_physical_playback(composition)

    compound = FinalUserTurn(
        "pipeline-call", "speech_ingress", 1, "pipeline-call:turn-compound-negative",
        "Нет, не надо. Почему небо голубое?", 2, 600_000_000, EndpointEventKind.HARD_ENDPOINT,
    )
    assert _submit(pipeline, compound)
    assert composition.fsm.state is DialogueState.THINKING
    assert pipeline.wait(2.0)
    pipeline.drain_control()
    assert pipeline.wait(2.0)
    pipeline.drain_control()

    assert composition.rag_contexts[-1].query_text == "Почему небо голубое?"
    assert [trace.kind.value for trace in composition.semantic_traces[-2:]] == [
        "reject_pending",
        "knowledge_request",
    ]
    user_turns = [turn for turn in composition.owners.context.snapshot().turns if turn.role == "user"]
    assert [turn.text for turn in user_turns].count(compound.text) == 1
    assert pipeline.errors == []
    runtime.shutdown()
