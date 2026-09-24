"""Revision reconciliation and authoritative final-turn assembly."""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import (
    AsrHypothesis,
    EndpointEvent,
    EndpointEventKind,
    FinalUserTurn,
    TranscriptUpdate,
    TranscriptUpdateKind,
)


class TranscriptContractError(RuntimeError):
    """Raised when an ASR revision violates the transcript boundary."""


def _comparison_text(value: str) -> str:
    """Return the conservative comparison form used for ASR revisions.

    Russian ASR backends legitimately alternate between ``ё`` and ``е``
    without changing the spoken content. This equivalence is used only to
    validate revision continuity; the text exposed to the caller remains the
    backend's latest spelling.
    """

    return value.replace("ё", "е").replace("Ё", "Е")


@dataclass(slots=True)
class TranscriptAssembler:
    """Keep one current revision and emit exactly one final user turn."""

    call_id: str
    channel_id: str
    generation: int
    turn_id: str
    stable_prefix_min_chars: int = 12
    _latest_revision: int = field(init=False, default=0, repr=False)
    _latest_text: str = field(init=False, default="", repr=False)
    _stable_prefix: str = field(init=False, default="", repr=False)
    _finalized: bool = field(init=False, default=False, repr=False)
    stale_revisions: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if not self.call_id or not self.channel_id or not self.turn_id:
            raise ValueError("transcript scope identifiers must be non-empty")
        if self.generation < 1:
            raise ValueError("generation must be positive")
        if self.stable_prefix_min_chars < 0:
            raise ValueError("stable_prefix_min_chars must not be negative")
        self._latest_revision = 0
        self._latest_text = ""
        self._stable_prefix = ""
        self._finalized = False
        self.stale_revisions = 0

    def _check_scope(self, hypothesis: AsrHypothesis) -> None:
        if (hypothesis.call_id, hypothesis.channel_id, hypothesis.generation, hypothesis.turn_id) != (
            self.call_id,
            self.channel_id,
            self.generation,
            self.turn_id,
        ):
            raise TranscriptContractError("hypothesis belongs to another call/channel generation")

    def _snapshot(
        self,
        hypothesis: AsrHypothesis,
        *,
        kind: TranscriptUpdateKind,
        authoritative: bool = False,
        boundary: EndpointEventKind | None = None,
    ) -> TranscriptUpdate:
        text = hypothesis.normalized_text
        explicit_stable_prefix = hypothesis.stable_prefix is not None
        if explicit_stable_prefix:
            candidate = " ".join(hypothesis.stable_prefix.split())
        else:
            # A common prefix of two consecutive hypotheses is not evidence of
            # semantic stability: an early ASR error may be repeated and then
            # corrected by the next revision.  Only a backend-provided prefix
            # is authoritative enough to advance this boundary.
            candidate = self._stable_prefix
        if not _comparison_text(text).startswith(_comparison_text(self._stable_prefix)):
            raise TranscriptContractError("ASR revision contradicts the already stable prefix")
        if not candidate.startswith(self._stable_prefix):
            candidate = self._stable_prefix
        self._stable_prefix = candidate
        self._latest_text = text
        return TranscriptUpdate(
            kind=kind,
            call_id=self.call_id,
            channel_id=self.channel_id,
            generation=self.generation,
            revision=hypothesis.revision,
            timestamp_ns=hypothesis.timestamp_ns,
            text=text,
            stable_prefix=self._stable_prefix,
            unstable_suffix=text[len(self._stable_prefix) :],
            authoritative=authoritative,
            boundary=boundary,
        )

    def accept(self, hypothesis: AsrHypothesis) -> TranscriptUpdate | None:
        """Accept a newer revision; discard stale/late output as ``None``."""

        self._check_scope(hypothesis)
        if self._finalized or hypothesis.revision <= self._latest_revision:
            self.stale_revisions += 1
            return None
        kind = TranscriptUpdateKind.FINAL if hypothesis.is_final else TranscriptUpdateKind.PARTIAL
        # A backend ``is_final`` flag is only a candidate final hypothesis.
        # The dialogue layer receives authority after the hard endpoint below.
        update = self._snapshot(hypothesis, kind=kind, authoritative=False)
        self._latest_revision = hypothesis.revision
        return update

    def finalize(self, boundary: EndpointEvent) -> tuple[TranscriptUpdate, FinalUserTurn]:
        """Seal the latest text only at an authoritative hard endpoint."""

        if boundary.kind is not EndpointEventKind.HARD_ENDPOINT or not boundary.authoritative:
            raise TranscriptContractError("finalization requires an authoritative hard_endpoint")
        if (boundary.call_id, boundary.channel_id, boundary.generation, boundary.turn_id) != (
            self.call_id,
            self.channel_id,
            self.generation,
            self.turn_id,
        ):
            raise TranscriptContractError("endpoint belongs to another transcript scope")
        if self._finalized:
            raise TranscriptContractError("transcript is already finalized")
        if not self._latest_text.strip() or not self._latest_revision:
            raise TranscriptContractError("cannot finalize an empty transcript")
        hypothesis = AsrHypothesis(
            call_id=self.call_id,
            channel_id=self.channel_id,
            generation=self.generation,
            revision=self._latest_revision + 1,
            timestamp_ns=boundary.timestamp_ns,
            text=self._latest_text,
            is_final=True,
            stable_prefix=self._latest_text,
            source="endpoint-finalization",
            turn_id=self.turn_id,
        )
        self._latest_revision = hypothesis.revision
        update = self._snapshot(
            hypothesis,
            kind=TranscriptUpdateKind.FINAL,
            authoritative=True,
            boundary=EndpointEventKind.HARD_ENDPOINT,
        )
        self._finalized = True
        final_turn = FinalUserTurn(
            call_id=self.call_id,
            channel_id=self.channel_id,
            generation=self.generation,
            turn_id=self.turn_id,
            text=update.text,
            revision=update.revision,
            finalized_at_ns=boundary.timestamp_ns,
            boundary=EndpointEventKind.HARD_ENDPOINT,
        )
        return update, final_turn

    def cancel(self) -> None:
        """Close speculative state; all later hypotheses become stale."""

        self._finalized = True
