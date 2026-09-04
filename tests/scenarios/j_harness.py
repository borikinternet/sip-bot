"""Clean-start deterministic harness owned by plan 002-J.

It drives the approved FSM boundary with typed fixtures.  It intentionally
does not invoke ASR, LLM, Ollama, TTS, GPU or live SIP/RTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sip_bot.context import ContextSnapshot, ContextStore
from sip_bot.dialogue import (
    DialogueFSM,
    FinalUserTurn,
    PlaybackEvent,
    PlaybackStatus,
    StructuredDecision,
    TransferResult,
)
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind
from sip_bot.speech import EndpointEventKind
from sip_bot.transfer import FakeOperator, TransferOrchestrator


@dataclass(slots=True)
class JScenario:
    root: Path
    call_id: str = "j-clean-call"
    operator_target: str = field(init=False)
    fsm: DialogueFSM = field(init=False)
    store: ContextStore = field(init=False)
    operator: FakeOperator = field(init=False)
    transfer: TransferOrchestrator = field(init=False)

    def __post_init__(self) -> None:
        self.operator_target = "sip:operator@example.test"
        self.fsm = DialogueFSM(operator_target=self.operator_target)
        self.store = ContextStore(self.root / "context", self.call_id)
        self.operator = FakeOperator(self.operator_target)
        self.transfer = TransferOrchestrator(self.operator)

    def answered(self) -> None:
        self.fsm.handle(NormalizedSipEvent(self.call_id, SipEventKind.CALL_STARTED, 1, 1))
        self.fsm.handle(NormalizedSipEvent(self.call_id, SipEventKind.CALL_ANSWERED, 2, 2))

    def turn(self, text: str, turn_id: str) -> FinalUserTurn:
        turn = FinalUserTurn(
            self.call_id,
            f"{self.call_id}:audio",
            1,
            turn_id,
            text,
            1,
            500_000_000,
            EndpointEventKind.HARD_ENDPOINT,
        )
        self.store.append_user(turn_id, text)
        return turn

    def confirmed_transfer(self) -> TransferResult:
        self.answered()
        self.fsm.handle(self.turn("Нужен оператор", "turn-1"))
        operation = self.fsm.active_operation_id
        self.fsm.handle(StructuredDecision("offer_transfer", "Подключить оператора?", operation_id=operation))
        generation = self.fsm.commands[-2].generation
        self.fsm.handle(PlaybackEvent(self.call_id, PlaybackStatus.COMPLETED, channel_generation=generation, operation_id=operation))
        self.fsm.handle(self.turn("Да", "turn-2"))
        command = self.fsm.commands[-1]
        result = self.transfer.execute(command)
        self.fsm.handle(result)
        return result

    def context_snapshot(self) -> ContextSnapshot:
        return self.store.snapshot()
