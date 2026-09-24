"""Composition boundary for the VAD, endpointing and transcript owners."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from sip_bot.sip_media.models import PcmFrame

from .contracts import (
    AsrHypothesis,
    EndpointEvent,
    EndpointEventKind,
    FinalUserTurn,
    TranscriptUpdate,
    VadDecision,
)
from .endpointing import TurnDetector
from .transcript_assembler import TranscriptAssembler, TranscriptContractError
from .vad import VadProcessor


@dataclass(frozen=True, slots=True)
class SpeechFrameResult:
    """Direct data-plane result from one PCM frame."""

    vad_decision: VadDecision
    endpoint_events: tuple[EndpointEvent, ...]
    transcript_update: TranscriptUpdate | None = None
    final_turn: FinalUserTurn | None = None


class SpeechIngress:
    """Connect speech owners without routing audio or text through Dispatcher."""

    def __init__(
        self,
        *,
        vad: VadProcessor,
        turn_detector: TurnDetector,
        assembler: TranscriptAssembler,
        assembler_factory: Callable[[str], TranscriptAssembler] | None = None,
        defer_endpoint_finalization: bool = False,
    ) -> None:
        self.vad = vad
        self.turn_detector = turn_detector
        self.assembler = assembler
        self.assembler_factory = assembler_factory
        self.defer_endpoint_finalization = defer_endpoint_finalization
        self._closed = False
        self._assemblers: dict[str, TranscriptAssembler] = {assembler.turn_id: assembler}
        self._pending_endpoints: dict[str, EndpointEvent] = {}
        self._ready_final_turns: deque[FinalUserTurn] = deque()
        self.rejected_turns = 0

    @property
    def closed(self) -> bool:
        return self._closed

    def process_frame(self, frame: PcmFrame) -> SpeechFrameResult:
        if self._closed:
            raise RuntimeError("speech ingress is closed")
        decision = self.vad.process(frame)
        events = self.turn_detector.consume(decision)
        update: TranscriptUpdate | None = None
        final_turn: FinalUserTurn | None = None
        for event in events:
            if event.kind is EndpointEventKind.SPEECH_STARTED:
                self._assembler_for(event.turn_id)
            if event.authoritative:
                self._pending_endpoints[event.turn_id] = event
                finalized = (
                    None
                    if self.defer_endpoint_finalization
                    else self._try_finalize_pending(event.turn_id)
                )
                if finalized is not None:
                    update, final_turn = finalized
        return SpeechFrameResult(
            vad_decision=decision,
            endpoint_events=events,
            transcript_update=update,
            final_turn=final_turn,
        )

    def accept_hypothesis(self, hypothesis: AsrHypothesis) -> TranscriptUpdate | None:
        if self._closed:
            return None
        if not hypothesis.speech_supported:
            if hypothesis.is_final:
                self._discard_turn(hypothesis.turn_id)
                self.rejected_turns += 1
            return None
        assembler = self._assembler_for(hypothesis.turn_id)
        update = assembler.accept(hypothesis)
        finalized = (
            self._try_finalize_pending(hypothesis.turn_id)
            if not self.defer_endpoint_finalization or hypothesis.is_final
            else None
        )
        if finalized is not None:
            _final_update, final_turn = finalized
            self._ready_final_turns.append(final_turn)
        return update

    def _discard_turn(self, turn_id: str) -> None:
        assembler = self._assemblers.pop(turn_id, None)
        if assembler is not None:
            assembler.cancel()
        self._pending_endpoints.pop(turn_id, None)
        self._ready_final_turns = deque(
            turn for turn in self._ready_final_turns if turn.turn_id != turn_id
        )

    def take_final_turn(self) -> FinalUserTurn | None:
        """Return a turn finalized after a delayed ASR hypothesis arrived."""

        if not self._ready_final_turns:
            return None
        return self._ready_final_turns.popleft()

    def _assembler_for(self, turn_id: str) -> TranscriptAssembler:
        assembler = self._assemblers.get(turn_id)
        if assembler is not None:
            self.assembler = assembler
            return assembler
        if self.assembler_factory is None:
            raise TranscriptContractError(
                f"no TranscriptAssembler factory for turn {turn_id!r}"
            )
        assembler = self.assembler_factory(turn_id)
        if assembler.turn_id != turn_id:
            raise TranscriptContractError("assembler factory returned another transcript scope")
        self._assemblers[turn_id] = assembler
        self.assembler = assembler
        return assembler

    def _try_finalize_pending(self, turn_id: str) -> tuple[TranscriptUpdate, FinalUserTurn] | None:
        boundary = self._pending_endpoints.get(turn_id)
        if boundary is None:
            return None
        assembler = self._assemblers.get(turn_id)
        if assembler is None:
            return None
        try:
            finalized = assembler.finalize(boundary)
        except TranscriptContractError as exc:
            if str(exc) == "cannot finalize an empty transcript":
                return None
            raise
        self._pending_endpoints.pop(turn_id, None)
        self._assemblers.pop(turn_id, None)
        return finalized

    def cancel(self) -> None:
        self.turn_detector.cancel()
        for assembler in tuple(self._assemblers.values()):
            assembler.cancel()
        self._assemblers.clear()
        self._pending_endpoints.clear()
        self._ready_final_turns.clear()
        self._closed = True

    def close(self) -> None:
        self.cancel()
