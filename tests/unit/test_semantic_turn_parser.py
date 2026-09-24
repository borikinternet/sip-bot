from __future__ import annotations

import pytest

from sip_bot.speech import EndpointEventKind, FinalUserTurn
from sip_bot.understanding import (
    ConfirmPendingAct,
    DialogueExpectation,
    ExpectationKind,
    KnowledgeRequestAct,
    RejectPendingAct,
    SemanticTurnParser,
    TransferRequestAct,
)


def _turn(text: str) -> FinalUserTurn:
    return FinalUserTurn(
        call_id="semantic-call",
        channel_id="speech_ingress",
        generation=2,
        turn_id="semantic-call:turn-1",
        text=text,
        revision=3,
        finalized_at_ns=500_000_000,
        boundary=EndpointEventKind.HARD_ENDPOINT,
    )


TRANSFER = DialogueExpectation(ExpectationKind.TRANSFER_CONFIRMATION, "sip:operator@example.test")
NONE = DialogueExpectation()


@pytest.mark.parametrize("text", ["Нет.", "Нет, спасибо, не надо.", "Не нужно!"])
def test_pure_negative_confirmation(text: str) -> None:
    result = SemanticTurnParser().parse(_turn(text), TRANSFER)

    assert len(result.acts) == 1
    assert isinstance(result.acts[0], RejectPendingAct)
    assert result.source.text[result.acts[0].span.start : result.acts[0].span.end] == text.strip()


def test_negative_confirmation_preserves_residual_question() -> None:
    text = "Нет, не надо. Почему небо голубое?"
    result = SemanticTurnParser().parse(_turn(text), TRANSFER)

    assert [type(act) for act in result.acts] == [RejectPendingAct, KnowledgeRequestAct]
    assert result.acts[1].content == "Почему небо голубое?"
    assert result.acts[0].span.end <= result.acts[1].span.start


@pytest.mark.parametrize("text", ["Да.", "Да, соедините.", "Конечно!"])
def test_pure_positive_confirmation(text: str) -> None:
    result = SemanticTurnParser().parse(_turn(text), TRANSFER)

    assert len(result.acts) == 1
    assert isinstance(result.acts[0], ConfirmPendingAct)


def test_positive_confirmation_preserves_residual_question() -> None:
    text = "Да, соедините, но сначала скажите, почему небо голубое?"
    result = SemanticTurnParser().parse(_turn(text), TRANSFER)

    assert [type(act) for act in result.acts] == [ConfirmPendingAct, KnowledgeRequestAct]
    assert result.acts[1].content == "скажите, почему небо голубое?"


@pytest.mark.parametrize(
    "text",
    [
        "Переведите меня на оператора.",
        "Пожалуйста, соедините меня с человеком!",
        "Я хочу поговорить с оператором.",
    ],
)
def test_explicit_operator_request(text: str) -> None:
    result = SemanticTurnParser().parse(_turn(text), NONE)

    assert len(result.acts) == 1
    assert isinstance(result.acts[0], TransferRequestAct)


def test_explicit_operator_request_overrides_pending_confirmation() -> None:
    result = SemanticTurnParser().parse(_turn("Переведите меня на оператора."), TRANSFER)

    assert len(result.acts) == 1
    assert isinstance(result.acts[0], TransferRequestAct)
    assert result.diagnostics == (
        "confirmation:ambiguous_as_content",
        "explicit_transfer_request",
    )


def test_ordinary_question_is_knowledge_request() -> None:
    result = SemanticTurnParser().parse(_turn("Почему небо голубое?"), NONE)

    assert len(result.acts) == 1
    assert isinstance(result.acts[0], KnowledgeRequestAct)
    assert result.acts[0].content == "Почему небо голубое?"


@pytest.mark.parametrize("text", ["Нет ли другого варианта?", "Даже не знаю.", "Возможно."])
def test_ambiguous_confirmation_never_produces_critical_act(text: str) -> None:
    result = SemanticTurnParser().parse(_turn(text), TRANSFER)

    assert len(result.acts) == 1
    assert isinstance(result.acts[0], KnowledgeRequestAct)
    assert "ambiguous_as_content" in result.diagnostics[0]


def test_semantic_turn_preserves_authoritative_identity() -> None:
    source = _turn("Нет. Почему небо голубое?")
    result = SemanticTurnParser().parse(source, TRANSFER)

    assert result.source is source
    assert result.call_id == source.call_id
    assert result.generation == source.generation
    assert result.turn_id == source.turn_id
    assert source.text[result.acts[0].span.start : result.acts[0].span.end] == "Нет"
    assert source.text[result.acts[1].span.start : result.acts[1].span.end] == "Почему небо голубое?"
    assert result.acts[0].span.end <= result.acts[1].span.start
