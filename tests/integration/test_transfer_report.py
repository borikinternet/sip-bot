"""Deterministic J1-J3 transfer/report integration tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from sip_bot.dialogue import CommandKind, DialogueFSM, DialogueState, FinalUserTurn, StructuredDecision, TransferStatus
from sip_bot.report import ReportFinalizationError, ReportFinalizer, ReportInput
from sip_bot.retrieval import KnowledgeContext, KnowledgeHit
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from sip_bot.speech import EndpointEventKind
from sip_bot.transfer import FakeOperator, TransferCommand, TransferContractError, TransferOrchestrator

from tests.scenarios.j_harness import JScenario


def test_confirmed_transfer_is_authorized_by_fsm_and_returns_typed_result(tmp_path: Path) -> None:
    scenario = JScenario(tmp_path)
    result = scenario.confirmed_transfer()

    assert result.status is TransferStatus.COMPLETED
    assert scenario.fsm.state is DialogueState.TERMINAL
    assert len(scenario.operator.accepted) == 1
    assert any(command.kind is CommandKind.TRANSFER for command in scenario.fsm.commands)
    assert any(command.kind is CommandKind.REPORT for command in scenario.fsm.commands)


def test_transfer_failure_is_typed_and_fsm_keeps_failed_call_nonterminal(tmp_path: Path) -> None:
    scenario = JScenario(tmp_path)
    scenario.operator.available = False
    scenario.answered()
    scenario.fsm.handle(scenario.turn("Переведите на оператора", "turn-1"))
    scenario.fsm.handle(StructuredDecision("transfer", operation_id=scenario.fsm.active_operation_id))

    result = scenario.transfer.execute(scenario.fsm.commands[-1])
    scenario.fsm.handle(result)

    assert result.status is TransferStatus.FAILED
    assert result.reason == "operator_unavailable"
    assert scenario.fsm.state is DialogueState.LISTENING


def test_transfer_adapter_rejects_non_transfer_command_and_cannot_bypass_fsm() -> None:
    operator = FakeOperator("sip:operator@example.test")
    adapter = TransferOrchestrator(operator)
    fsm = DialogueFSM(operator_target=operator.target)
    fsm.handle(NormalizedSipEvent("call-1", SipEventKind.CALL_STARTED, 1, 1))
    answer = fsm.commands[-1]

    with pytest.raises(TransferContractError):
        adapter.execute(answer)
    assert operator.accepted == []


def test_transfer_command_requires_existing_fsm_boundary() -> None:
    with pytest.raises(TransferContractError):
        TransferCommand.from_dialogue_command(object())  # type: ignore[arg-type]


def test_report_is_source_aware_text_only_and_idempotent(tmp_path: Path) -> None:
    scenario = JScenario(tmp_path)
    result = scenario.confirmed_transfer()
    rag = KnowledgeContext(
        context_id="ctx-1",
        query_text="Почему небо голубое?",
        hits=(KnowledgeHit("chunk-1", "wiki-physics-rayleigh", "Рассеяние света", 0.81),),
        sufficient=True,
        threshold=0.35,
        top_k=3,
        index_version="demo-v1",
        embedding_model="embeddinggemma",
    )
    report_input = ReportInput(
        call_id=scenario.call_id,
        terminal_state=scenario.fsm.state.value,
        terminal_reason="transfer_completed",
        context=scenario.context_snapshot(),
        rag_contexts=(rag,),
        transitions=tuple(scenario.fsm.trace),
        transfer_result=result,
    )
    finalizer = ReportFinalizer(tmp_path / "reports")

    first = finalizer.finalize(report_input)
    second = finalizer.finalize(report_input)
    text = first.read_text(encoding="utf-8")

    assert first == second
    assert "wiki-physics-rayleigh" in text
    assert "operator_connected" in text
    assert "Аудиозапись проектом не создаётся" in text
    assert not list(tmp_path.rglob("*.wav"))

    changed = replace(report_input, terminal_reason="other")
    with pytest.raises(ReportFinalizationError):
        finalizer.finalize(changed)


def test_normal_terminal_report_is_created_once_without_audio(tmp_path: Path) -> None:
    scenario = JScenario(tmp_path)
    scenario.answered()
    scenario.fsm.handle(NormalizedSipEvent(scenario.call_id, SipEventKind.REMOTE_HANGUP, 3, 3, reason="BYE"))
    report_input = ReportInput(
        call_id=scenario.call_id,
        terminal_state=scenario.fsm.state.value,
        terminal_reason="BYE",
        context=scenario.context_snapshot(),
        transitions=tuple(scenario.fsm.trace),
    )
    finalizer = ReportFinalizer(tmp_path / "reports")

    path = finalizer.finalize(report_input)
    finalizer.finalize(report_input)
    assert path.name == "report.md"
    assert len(list((tmp_path / "reports" / scenario.call_id).iterdir())) == 1
    assert sum(command.kind is CommandKind.REPORT for command in scenario.fsm.commands) == 1
