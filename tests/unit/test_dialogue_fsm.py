"""Deterministic 002-E Dialogue FSM scenarios."""

from sip_bot.dialogue import (
    CommandKind,
    DialogueFSM,
    DialogueState,
    FinalUserTurn,
    PlaybackEvent,
    PlaybackStatus,
    SpeechEvent,
    SpeechEventKind,
    StructuredDecision,
    TransferResult,
    TransferStatus,
)
from sip_bot.speech import EndpointEventKind
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from sip_bot.understanding import SemanticTurnParser


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


def _handle_turn(
    fsm: DialogueFSM,
    text: str,
    *,
    call_id: str = "call-fsm",
    turn_id: str = "call-fsm:turn-1",
) -> None:
    semantic = SemanticTurnParser().parse(
        _turn(text, call_id=call_id, turn_id=turn_id),
        fsm.current_expectation(),
    )
    for act in semantic.acts:
        fsm.handle(act)


def test_normal_turn_answer_and_playback_completion() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    _handle_turn(fsm, "Как оформить заявку?", turn_id="t1")
    assert fsm.state is DialogueState.THINKING
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("answer", "Нужно заполнить форму.", call_id="call-fsm", operation_id=operation))
    assert fsm.state is DialogueState.PLAYING
    generation = fsm.commands[-2].generation
    assert fsm.commands[-1].kind is CommandKind.APPROVE_ANSWER
    fsm.handle(PlaybackEvent("call-fsm", PlaybackStatus.COMPLETED, channel_generation=generation, operation_id=operation))
    assert fsm.state is DialogueState.LISTENING


def test_answered_call_plays_one_interruptible_greeting_before_listening() -> None:
    fsm = DialogueFSM(greeting_enabled=True)

    _answered(fsm)

    assert fsm.state is DialogueState.PLAYING
    assert ("speech_ingress", 1) in fsm.active_channels
    assert fsm.commands[-1].kind is CommandKind.PLAY_GREETING
    generation = fsm.commands[-1].generation
    greeting_count = sum(command.kind is CommandKind.PLAY_GREETING for command in fsm.commands)

    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.CALL_ANSWERED, 3, 3))
    assert sum(command.kind is CommandKind.PLAY_GREETING for command in fsm.commands) == greeting_count

    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=generation,
            operation_id=0,
        )
    )
    assert fsm.state is DialogueState.LISTENING


def test_user_speech_barges_into_call_greeting() -> None:
    fsm = DialogueFSM(greeting_enabled=True)
    _answered(fsm)

    fsm.handle(SpeechEvent("call-fsm", SpeechEventKind.SPEECH_STARTED))

    assert fsm.state is DialogueState.LISTENING
    assert any(
        command.kind is CommandKind.CANCEL and command.channel_id == "playback"
        for command in fsm.commands
    )


def test_vad_start_while_thinking_does_not_silently_cancel_answer() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Что такое таблица Менделеева?", turn_id="t1")
    operation = fsm.active_operation_id

    fsm.handle(SpeechEvent("call-fsm", SpeechEventKind.SPEECH_STARTED))
    fsm.handle(SpeechEvent("call-fsm", SpeechEventKind.SPEECH_RESUMED))

    assert fsm.state is DialogueState.THINKING
    assert not any(command.kind is CommandKind.CANCEL for command in fsm.commands)
    fsm.handle(StructuredDecision("answer", "Это система химических элементов.", operation_id=operation))
    assert fsm.state is DialogueState.PLAYING


def test_new_final_turn_while_thinking_replaces_inference() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Первый вопрос", turn_id="t1")
    first_operation = fsm.active_operation_id

    _handle_turn(fsm, "Другой вопрос", turn_id="t2")

    assert fsm.state is DialogueState.THINKING
    assert fsm.active_operation_id > first_operation
    assert any(
        command.kind is CommandKind.CANCEL and command.operation_id == first_operation
        for command in fsm.commands
    )


def test_tts_producer_completion_does_not_finish_physical_playback() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Как оформить заявку?")
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("answer", "Нужно заполнить форму.", operation_id=operation))
    generation = fsm._playback_generation

    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.PRODUCER_COMPLETED,
            channel_generation=generation,
            operation_id=operation,
        )
    )

    assert fsm.state is DialogueState.PLAYING


def test_barge_in_cancels_playback_and_stale_playback_is_ignored() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Первый вопрос")
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
    _handle_turn(fsm, "Непонятный вопрос")
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Могу подключить оператора.", operation_id=operation))
    assert fsm.state is DialogueState.OFFERING_TRANSFER
    generation = fsm._playback_generation
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=generation, operation_id=operation))
    assert fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION
    _handle_turn(fsm, "Да", turn_id="call-fsm:turn-2")
    assert fsm.state is DialogueState.TRANSFERRING
    transfer = fsm.commands[-1]
    assert transfer.kind is CommandKind.TRANSFER
    assert transfer.target == "sip:operator@example.test"
    fsm.handle(TransferResult("call-fsm", TransferStatus.COMPLETED))
    assert fsm.state is DialogueState.TERMINAL


def test_transfer_confirmation_accepts_terminal_punctuation() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    _handle_turn(fsm, "Непонятный вопрос")
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Могу подключить оператора.", operation_id=operation))
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=fsm._playback_generation, operation_id=operation))
    _handle_turn(fsm, "Да.", turn_id="call-fsm:turn-2")
    assert fsm.state is DialogueState.TRANSFERRING


def test_transfer_confirmation_keeps_state_while_speech_is_in_progress() -> None:
    fsm = DialogueFSM(operator_target="sip:operator@example.test")
    _answered(fsm)
    _handle_turn(fsm, "Непонятный вопрос")
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Могу подключить оператора.", operation_id=operation))
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=fsm._playback_generation, operation_id=operation))

    fsm.handle(SpeechEvent("call-fsm", "speech_started"))

    assert fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION


def test_declined_transfer_returns_to_listening_and_explicit_transfer_is_allowlisted() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Вопрос")
    fsm.handle(StructuredDecision("offer_transfer", "Соединить с оператором?", operation_id=fsm.active_operation_id))
    fsm.handle(PlaybackEvent("call-fsm", "completed", channel_generation=fsm._playback_generation, operation_id=fsm.active_operation_id))
    _handle_turn(fsm, "Нет", turn_id="call-fsm:turn-2")
    assert fsm.state is DialogueState.LISTENING
    _handle_turn(fsm, "Переведите меня", turn_id="call-fsm:turn-3")
    fsm.handle(StructuredDecision("transfer", operation_id=fsm.active_operation_id))
    assert fsm.state is DialogueState.TRANSFERRING


def test_terminal_cancels_channels_discards_stale_decision_and_allows_new_call_reentry() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Вопрос")
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
    _handle_turn(fsm, "Завершите разговор")
    fsm.handle(StructuredDecision("hangup", operation_id=fsm.active_operation_id))
    assert fsm.state is DialogueState.TERMINAL
    assert any(command.kind is CommandKind.HANGUP for command in fsm.commands)


def test_unknown_structured_action_is_rejected_without_sip_side_effect() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Вопрос")
    operation = fsm.active_operation_id

    fsm.handle(StructuredDecision("dial_arbitrary_number", "call now", operation_id=operation))

    assert fsm.state is DialogueState.LISTENING
    assert not any(command.kind is CommandKind.TRANSFER for command in fsm.commands)
    assert not any(command.kind is CommandKind.HANGUP for command in fsm.commands)
    assert any("unsupported dialogue action" in reason for _, reason in fsm.ignored_events)


def test_compound_reject_then_question_applies_both_acts_in_order() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Неизвестный вопрос")
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Подключить оператора?", operation_id=operation))
    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=fsm._playback_generation,
            operation_id=operation,
        )
    )

    _handle_turn(fsm, "Нет, не надо. Почему небо голубое?", turn_id="call-fsm:turn-2")

    assert fsm.state is DialogueState.THINKING
    assert fsm.active_operation_id == operation + 1
    assert [item.event for item in fsm.trace[-2:]] == ["transfer_declined", "knowledge_request"]
    assert fsm.commands[-1].kind is CommandKind.START_INFERENCE


def test_compound_confirm_answers_then_reconfirms_before_transfer() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Неизвестный вопрос")
    offered_operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Подключить оператора?", operation_id=offered_operation))
    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=fsm._playback_generation,
            operation_id=offered_operation,
        )
    )

    _handle_turn(
        fsm,
        "Да, соедините, но сначала скажите, почему небо голубое?",
        turn_id="call-fsm:turn-2",
    )
    content_operation = fsm.active_operation_id
    assert fsm.state is DialogueState.THINKING

    fsm.handle(StructuredDecision("answer", "Из-за рассеяния света.", operation_id=content_operation))
    answer_generation = fsm._playback_generation
    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=answer_generation,
            operation_id=content_operation,
        )
    )

    assert fsm.state is DialogueState.OFFERING_TRANSFER
    assert fsm.commands[-1].kind is CommandKind.PLAY_TRANSFER_CONFIRMATION
    confirmation_generation = fsm._playback_generation
    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=confirmation_generation,
            operation_id=content_operation,
        )
    )
    assert fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION

    _handle_turn(fsm, "Да", turn_id="call-fsm:turn-3")
    assert fsm.state is DialogueState.TRANSFERRING


def test_compound_confirm_does_not_duplicate_offer_from_content_path() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    _handle_turn(fsm, "Неизвестный вопрос")
    operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Подключить оператора?", operation_id=operation))
    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=fsm._playback_generation,
            operation_id=operation,
        )
    )
    baseline_static = sum(
        command.kind is CommandKind.PLAY_TRANSFER_CONFIRMATION for command in fsm.commands
    )

    _handle_turn(
        fsm,
        "Да, но сначала ответьте, где находится Марс?",
        turn_id="call-fsm:turn-2",
    )
    content_operation = fsm.active_operation_id
    fsm.handle(StructuredDecision("offer_transfer", "Подключить оператора?", operation_id=content_operation))
    fsm.handle(
        PlaybackEvent(
            "call-fsm",
            PlaybackStatus.COMPLETED,
            channel_generation=fsm._playback_generation,
            operation_id=content_operation,
        )
    )

    assert fsm.state is DialogueState.AWAITING_TRANSFER_CONFIRMATION
    assert sum(
        command.kind is CommandKind.PLAY_TRANSFER_CONFIRMATION for command in fsm.commands
    ) == baseline_static


def test_protocol_media_events_do_not_block_and_hold_resume_are_reentrant() -> None:
    fsm = DialogueFSM()
    _answered(fsm)
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.REMOTE_HOLD_STARTED, 3, 3))
    assert fsm.state is DialogueState.CONNECTED
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.REMOTE_RESUMED, 4, 4))
    assert fsm.state is DialogueState.LISTENING
    fsm.handle(NormalizedSipEvent("call-fsm", SipEventKind.RTP_TIMEOUT, 5, 5, reason="timeout"))
    assert fsm.state is DialogueState.TERMINAL
