"""Composition boundary for the VAD, endpointing and transcript owners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sip_bot.sip_media.models import PcmFrame

from .contracts import (
    AsrHypothesis,
    EndpointEvent,
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
        self._pending_endpoint: EndpointEvent | None = None
        self._ready_final_turn: FinalUserTurn | None = None

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
            if event.authoritative:
                self._pending_endpoint = event
                finalized = (
                    None
                    if self.defer_endpoint_finalization
                    else self._try_finalize_pending()
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
        update = self.assembler.accept(hypothesis)
        finalized = (
            self._try_finalize_pending()
            if not self.defer_endpoint_finalization or hypothesis.is_final
            else None
        )
        if finalized is not None:
            _final_update, self._ready_final_turn = finalized
        return update

    def take_final_turn(self) -> FinalUserTurn | None:
        """Return a turn finalized after a delayed ASR hypothesis arrived."""

        final_turn = self._ready_final_turn
        self._ready_final_turn = None
        return final_turn

    def _try_finalize_pending(self) -> tuple[TranscriptUpdate, FinalUserTurn] | None:
        boundary = self._pending_endpoint
        if boundary is None:
            return None
        try:
            finalized = self.assembler.finalize(boundary)
        except TranscriptContractError as exc:
            if str(exc) == "cannot finalize an empty transcript":
                return None
            raise
        self._pending_endpoint = None
        if self.assembler_factory is not None:
            next_turn_number = _next_turn_number(boundary.turn_id)
            self.assembler = self.assembler_factory(
                f"{boundary.call_id}:turn-{next_turn_number}"
            )
        return finalized

    def cancel(self) -> None:
        self.turn_detector.cancel()
        self.assembler.cancel()
        self._pending_endpoint = None
        self._ready_final_turn = None
        self._closed = True

    def close(self) -> None:
        self.cancel()


def _next_turn_number(turn_id: str) -> int:
    """Return the next numeric turn id without adding a second turn owner."""

    try:
        return int(turn_id.rsplit("-", 1)[1]) + 1
    except (IndexError, ValueError) as exc:
        raise ValueError(f"turn_id must end in a numeric suffix: {turn_id!r}") from exc
