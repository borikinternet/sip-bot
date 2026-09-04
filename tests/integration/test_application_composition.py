"""Clean-start composition coverage for the I.0 execution boundary."""

from __future__ import annotations

from pathlib import Path

from sip_bot.context import ContextStore
from sip_bot.dialogue import DialogueAction, DialogueState
from sip_bot.dialogue.events import PlaybackEvent, PlaybackStatus, StructuredDecision
from sip_bot.report import ReportFinalizer
from sip_bot.retrieval import KnowledgeContext, KnowledgeHit
from sip_bot.runtime import ApplicationRuntime, RuntimeProbe, RuntimeWarmupError
from sip_bot.runtime_composition import CallOwners
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from sip_bot.speech import EndpointEventKind, FinalUserTurn


def test_application_runtime_composes_existing_dispatcher_fsm_and_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    runtime = ApplicationRuntime.from_constants()
    runtime.start()

    call_id = "composition-call"
    owners = CallOwners(
        context=ContextStore(tmp_path / "context", call_id),
        report=ReportFinalizer(tmp_path / "reports"),
        sip_media=object(),
        speech=object(),
        llm=object(),
        tts=object(),
        transfer=object(),
    )
    composition = runtime.compose_call(call_id, owners)

    assert composition.session.bindings.context is owners.context
    assert composition.session.bindings.llm is owners.llm
    assert composition.fsm.channels.scopes[call_id] is composition.session.scope
    assert composition.fsm.state is DialogueState.CALL_OPEN

    assert composition.submit_control(
        NormalizedSipEvent(call_id, SipEventKind.CALL_ANSWERED, timestamp_ns=2, sequence=2)
    )
    composition.drain_control()
    assert composition.fsm.state is DialogueState.LISTENING

    turn = FinalUserTurn(
        call_id=call_id,
        channel_id="speech_ingress",
        generation=1,
        turn_id="composition-call:turn-1",
        text="Почему небо днем голубое?",
        revision=1,
        finalized_at_ns=3,
        boundary=EndpointEventKind.HARD_ENDPOINT,
    )
    rag = KnowledgeContext(
        context_id="knowledge-context-1",
        query_text=turn.text,
        hits=(KnowledgeHit("physics-1", "demo-natural-science", "Рассеяние света", 0.91),),
        sufficient=True,
        threshold=0.35,
        top_k=3,
        index_version="test-v1",
        embedding_model="test-embedding",
    )
    composition.record_rag_context(rag)
    assert composition.accept_final_turn(turn)
    assert composition.fsm.state is DialogueState.THINKING
    assert composition.commands[-1].kind.value == "start_inference"

    decision = StructuredDecision(
        action=DialogueAction.ANSWER,
        text="Из-за рассеяния света в атмосфере.",
        call_id=call_id,
        operation_id=composition.fsm.active_operation_id,
    )
    assert composition.submit_control(decision)
    composition.drain_control()
    assert composition.fsm.state is DialogueState.PLAYING
    playback_generation = next(
        command.generation
        for command in reversed(composition.commands)
        if command.kind.value == "open_channel" and command.channel_id == "playback"
    )
    composition.submit_control(
        PlaybackEvent(
            call_id,
            PlaybackStatus.COMPLETED,
            channel_id="playback",
            channel_generation=playback_generation,
            operation_id=composition.fsm.active_operation_id,
        )
    )
    composition.drain_control()
    composition.append_assistant_text(
        "composition-call:turn-1-answer",
        "Из-за рассеяния света в атмосфере.",
        source_ids=("demo-natural-science",),
        knowledge_context_id=rag.context_id,
    )

    assert composition.submit_control(
        NormalizedSipEvent(
            call_id,
            SipEventKind.REMOTE_HANGUP,
            timestamp_ns=4,
            sequence=4,
            reason="BYE",
        )
    )
    composition.drain_control()

    assert composition.fsm.state is DialogueState.TERMINAL
    assert composition.report_finalized
    assert composition.report_path is not None and composition.report_path.exists()
    report = composition.report_path.read_text(encoding="utf-8")
    assert "demo-natural-science" in report
    assert "Почему небо днем голубое?" in report
    assert runtime.dispatcher.active_session is None

    runtime.shutdown()


def test_application_runtime_keeps_call_bootstrap_not_ready_until_all_warmup_stages_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    runtime = ApplicationRuntime.from_constants()
    runtime.start()
    order: list[str] = []

    report = runtime.warmup(
        (
            ("first", lambda: order.append("first") or {"ok": True}),
            ("second", lambda: order.append("second") or {"ok": True}),
        )
    )
    assert order == ["first", "second"]
    assert runtime.ready is True
    assert [item.name for item in report.stages] == ["first", "second"]

    runtime.shutdown()
    assert runtime.ready is False


def test_application_runtime_does_not_mark_failed_warmup_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        "sip_bot.runtime.probe_runtime",
        lambda: RuntimeProbe("python3.14t", "cpython", (3, 14, 7), 1, False),
    )
    runtime = ApplicationRuntime.from_constants()
    runtime.start()

    def fail() -> None:
        raise RuntimeError("model load failed")

    try:
        runtime.warmup((("broken", fail),))
    except RuntimeWarmupError as exc:
        assert "broken" in str(exc)
    else:
        raise AssertionError("failed warmup must raise RuntimeWarmupError")
    assert runtime.ready is False
    runtime.shutdown()
