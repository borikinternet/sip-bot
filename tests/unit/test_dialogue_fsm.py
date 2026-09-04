"""Deterministic 002-E Dialogue FSM scenarios."""

from sip_bot.dialogue import (
    CommandKind,
    DialogueFSM,
    DialogueState,
    FinalUserTurn,
    PlaybackEvent,
    PlaybackStatus,
    SpeechEvent,
    StructuredDecision,
    TransferResult,
    TransferStatus,
)
from sip_bot.speech import EndpointEventKind
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind


def _answered(fsm: DialogueFSM, call_id: str = "call-fsm") -> None:
    fsm.handle(NormalizedSipEvent(call_id, SipEventKind.CALL_STARTED, 1, 1))
    fsm.handle(NormalizedSipEvent(call_id, SipEventKind.CALL_ANSWERED, 2, 2))


def _turn(text: str, *, call_id: str = "call-fsm", turn_id: str = "call-fsm:turn-1") -> FinalUserTurn:
    return FinalUserTurn(
        call_id=call_id,
        channel_id=f"{call_id}:audio",
        generation=1,
        turn_id=turn_id,
        text=text,
        revision=1,
        finalized_at_ns=500_000_000,
        boundary=EndpointEventKind.HARD_ENDPOINT,
    )


def test_normal_turn_answer_and_playback_completion() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    fsm.handle(_turn("Как оформить заявку?", turn_id="t1"))
    assert fsm.state is DialogueState.THINKING
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("answer", "Нужно заполнить форму.", call_id="call-fsm", operation_id=operation))
    assert fsm.state is DialogueState.PLAYING
    generation = fsm.commands[-2].generation
    assert fsm.commands[-1].kind is CommandKind.APPROVE_ANSWER
    fsm.handle(PlaybackEvent("call-fsm", PlaybackStatus.COMPLETED, channel_generation=generation, operation_id=operation))
    assert fsm.state is DialogueState.LISTENING


def test_barge_in_cancels_playback_and_stale_playback_is_ignored() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    fsm.handle(_turn("Первый вопрос"))
    fsm.handle(StructuredDecision("answer", "Первый ответ", operation_id=fsm.active_operation_id))
    old_generation = fsm._playback_generation
    fsm.handle(SpeechEvent("call-fsm", "barge_in"))
    assert fsm.state is DialogueState.LISTENING
    assert any(command.kind is CommandKind.CANCEL for command in fsm.commands)
    before = len(fsm.trace)
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=old_generation))
    assert len(fsm.trace) == before
    assert fsm.state is DialogueState.LISTENING


def test_unknown_answer_offer_requires_confirmation_and_transfers() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    fsm.handle(_turn("Непонятный вопрос"))
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Могу подключить оператора.", operation_id=operation))
    assert fsm.state is DialogueState.OFFERING_TRANSFER
    generation = fsm._playback_generation
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=generation, operation_id=operation))
    assert fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION
    fsm.handle(_turn("Да", turn_id="call-fsm:turn-2"))
    assert fsm.state is DialogueState.TRANSFERRING
    transfer = fsm.commands[-1]
    assert transfer.kind is CommandKind.TRANSFER
    assert transfer.target == "sip:operator@example.test"
    fsm.handle(TransferResult("call-fsm", TransferStatus.COMPLETED))
    assert fsm.state is DialogueState.TERMINAL


def test_transfer_confirmation_accepts_terminal_punctuation() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    fsm.handle(_turn("Непонятный вопрос"))
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Могу подключить оператора.", operation_id=operation))
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=fsm._playback_generation, operation_id=operation))
    fsm.handle(_turn("Да.", turn_id="call-fsm:turn-2"))
    assert fsm.state is DialogueState.TRANSFERRING


def test_transfer_confirmation_keeps_state_while_speech_is_in_progress() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    fsm.handle(_turn("Непонятный вопрос"))
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Могу подключить оператора.", operation_id=operation))
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=fsm._playback_generation, operation_id=operation))

    fsm.handle(SpeechEvent("call-fsm", "speech_started"))

    assert fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION


def test_declined_transfer_returns_to_listening_and_explicit_transfer_is_allowlisted() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    fsm.handle(_turn("Вопрос"))
    fsm.handle(StructuredDecision("offer_transfer", "Соединить с оператором?", operation_id=fsm.active_operation_id))
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=fsm._playback_generation, operation_id=fsm.active_operation_id))
    fsm.handle(_turn("Нет", turn_id="call-fsm:turn-2"))
    assert fsm.state is DialogueState.LISTENING
    fsm.handle(_turn("Переведите меня", turn_id="call-fsm:turn-3"))
    fsm.handle(StructuredDecision("transfer", operation_id=fsm.active_operation_id))
    assert fsm.state is DialogueState.TRANSFERRING


def test_terminal_cancels_channels_discards_stale_decision_and_allows_new_call_reentry() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    fsm.handle(_turn("Вопрос"))
    old_operation = fsm.active_operation_id
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.REMOTE_HANGUP, 3, 3, reason="BYE"))
    assert fsm.state is DialogueState.TERMINAL
    command_count = len(fsm.commands)
    fsm.handle(StructuredDecision("answer", "Старый ответ", operation_id=old_operation))
    assert len(fsm.commands) == command_count
    _answered(fsm, "call-fsm-2")
    assert fsm.call_id == "call-fsm-2"
    assert fsm.state is DialogueState.LISTENING


def test_answer_opens_input_channel_and_hangup_emits_semantic_sip_command() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    assert ("speech_ingress", 1) in fsm.active_channels
    fsm.handle(_turn("Завершите разговор"))
    fsm.handle(StructuredDecision("hangup", operation_id=fsm.active_operation_id))
    assert fsm.state is DialogueState.TERMINAL
    assert any(command.kind is CommandKind.HANGUP for command in fsm.commands)


def test_unknown_structured_action_is_rejected_without_sip_side_effect() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    fsm.handle(_turn("Вопрос"))
    operation = fsm.active_operation_id

    fsm.handle(StructuredDecision("dial_arbitrary_number", "call now", operation_id=operation))

    assert fsm.state is DialogueState.LISTENING
    assert not any(command.kind is CommandKind.TRANSFER for command in fsm.commands)
    assert not any(command.kind is CommandKind.HANGUP for command in fsm.commands)
    assert any("unsupported dialogue action" in reason for _, reason in fsm.ignored_events)


def test_protocol_media_events_do_not_block_and_hold_resume_are_reentrant() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.REMOTE_HOLD_STARTED, 3, 3))
    assert fsm.state is DialogueState.CONNECTED
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.REMOTE_RESUMED, 4, 4))
    assert fsm.state is DialogueState.LISTENING
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.RTP_TIMEOUT, 5, 5, reason="timeout"))
    assert fsm.state is DialogueState.TERMINAL
