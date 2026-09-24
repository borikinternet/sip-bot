"""Typed semantic boundary between final ASR text and dialogue consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, TypeAlias

from sip_bot.speech.contracts import FinalUserTurn


class ExpectationKind(StrEnum):
    NONE = "none"
    TRANSFER_CONFIRMATION = "transfer_confirmation"


@dataclass(frozen=True, slots=True)
class DialogueExpectation:
    """Read-only semantic expectation exposed by the dialogue FSM."""

    kind: ExpectationKind | str = ExpectationKind.NONE
    target: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ExpectationKind(self.kind))
        if self.kind is ExpectationKind.NONE and self.target is not None:
            raise ValueError("an empty expectation cannot carry a target")
        if self.target is not None and not self.target.strip():
            raise ValueError("expectation target must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Half-open character range in the authoritative source text."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if isinstance(self.start, bool) or isinstance(self.end, bool):
            raise TypeError("source span offsets must be integers")
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise TypeError("source span offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("source span must be a non-empty half-open range")


class DialogueActKind(StrEnum):
    CONFIRM_PENDING = "confirm_pending"
    REJECT_PENDING = "reject_pending"
    KNOWLEDGE_REQUEST = "knowledge_request"
    TRANSFER_REQUEST = "transfer_request"


@dataclass(frozen=True, slots=True)
class ConfirmPendingAct:
    kind: ClassVar[DialogueActKind] = DialogueActKind.CONFIRM_PENDING
    span: SourceSpan
    has_following_content: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.has_following_content, bool):
            raise TypeError("has_following_content must be bool")


@dataclass(frozen=True, slots=True)
class RejectPendingAct:
    kind: ClassVar[DialogueActKind] = DialogueActKind.REJECT_PENDING
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class KnowledgeRequestAct:
    kind: ClassVar[DialogueActKind] = DialogueActKind.KNOWLEDGE_REQUEST
    span: SourceSpan
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("knowledge request content must be non-empty")


@dataclass(frozen=True, slots=True)
class TransferRequestAct:
    kind: ClassVar[DialogueActKind] = DialogueActKind.TRANSFER_REQUEST
    span: SourceSpan
    target: str | None = None

    def __post_init__(self) -> None:
        if self.target is not None and not self.target.strip():
            raise ValueError("transfer target must be non-empty when supplied")


DialogueAct: TypeAlias = ConfirmPendingAct | RejectPendingAct | KnowledgeRequestAct | TransferRequestAct


@dataclass(frozen=True, slots=True)
class SemanticTurn:
    """One authoritative final turn split into ordered dialogue acts."""

    __data_plane__: ClassVar[bool] = True

    source: FinalUserTurn
    expectation: DialogueExpectation
    acts: tuple[DialogueAct, ...]
    parser_version: str
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, FinalUserTurn):
            raise TypeError("semantic turn source must be FinalUserTurn")
        if not isinstance(self.expectation, DialogueExpectation):
            raise TypeError("semantic turn expectation must be DialogueExpectation")
        if not self.acts:
            raise ValueError("semantic turn must contain at least one dialogue act")
        if not isinstance(self.parser_version, str) or not self.parser_version.strip():
            raise ValueError("parser_version must be non-empty")
        previous_end = -1
        for act in self.acts:
            if not isinstance(
                act,
                (ConfirmPendingAct, RejectPendingAct, KnowledgeRequestAct, TransferRequestAct),
            ):
                raise TypeError("semantic turn contains an unsupported dialogue act")
            if act.span.end > len(self.source.text):
                raise ValueError("dialogue act span is outside source text")
            if act.span.start < previous_end:
                raise ValueError("dialogue act spans must be ordered and non-overlapping")
            previous_end = act.span.end
            if isinstance(act, KnowledgeRequestAct):
                if self.source.text[act.span.start : act.span.end] != act.content:
                    raise ValueError("knowledge request content must equal its source span")

    @property
    def call_id(self) -> str:
        return self.source.call_id

    @property
    def generation(self) -> int:
        return self.source.generation

    @property
    def turn_id(self) -> str:
        return self.source.turn_id


@dataclass(frozen=True, slots=True)
class SemanticActTrace:
    """Observable result of applying one parsed act to the dialogue owner."""

    turn_id: str
    act_index: int
    kind: DialogueActKind | str
    span: SourceSpan
    outcome: str
    state_before: str
    state_after: str
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", DialogueActKind(self.kind))
        if self.act_index < 1:
            raise ValueError("act_index must be positive")
        if self.outcome not in {"applied", "ignored"}:
            raise ValueError("semantic act outcome must be applied or ignored")


__all__ = [
    "ConfirmPendingAct",
    "DialogueAct",
    "DialogueActKind",
    "DialogueExpectation",
    "ExpectationKind",
    "KnowledgeRequestAct",
    "RejectPendingAct",
    "SemanticTurn",
    "SemanticActTrace",
    "SourceSpan",
    "TransferRequestAct",
]
