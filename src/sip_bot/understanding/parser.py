"""Deterministic Russian fast path for semantic turn segmentation."""

from __future__ import annotations

import re

from sip_bot.speech.contracts import FinalUserTurn

from .contracts import (
    ConfirmPendingAct,
    DialogueExpectation,
    ExpectationKind,
    KnowledgeRequestAct,
    RejectPendingAct,
    SemanticTurn,
    SourceSpan,
    TransferRequestAct,
)


PARSER_VERSION = "ru-semantic-turn-v1"

_POSITIVE = re.compile(
    r"^\s*(?:да|конечно|подтверждаю)\b"
    r"(?:\s*,?\s*(?:соедините|переведите|подключите)"
    r"(?:\s+меня)?(?:\s+с\s+оператором)?)?",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"^\s*(?:нет|отмена|не\s+(?:надо|нужно))\b"
    r"(?:\s*,?\s*спасибо)?"
    r"(?:\s*,?\s*не\s+(?:надо|нужно))?",
    re.IGNORECASE,
)
_TRANSFER_REQUEST = re.compile(
    r"^\s*(?:пожалуйста\s*,?\s*)?"
    r"(?:(?:переведите|соедините|подключите)(?:\s+меня)?(?:\s+(?:с|к|на))?\s+"
    r"(?:оператор(?:ом|у|а)?|человек(?:ом|у|а)?)|"
    r"(?:я\s+)?хочу\s+(?:поговорить|соединиться)\s+с\s+(?:оператором|человеком))"
    r"(?:\s*,?\s*пожалуйста)?\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_RESIDUAL_CONNECTOR = re.compile(
    r"(?:[\s,.;:!?—-]+)*(?:(?:но|а)\s+сначала|но|а|и)\b[\s,.;:!?—-]*",
    re.IGNORECASE,
)
_LEADING_DELIMITERS = re.compile(r"[\s,.;:!?—-]+")


class SemanticTurnParser:
    """Interpret final text without owning call state or side effects."""

    version = PARSER_VERSION

    def parse(self, turn: FinalUserTurn, expectation: DialogueExpectation) -> SemanticTurn:
        if not isinstance(turn, FinalUserTurn):
            raise TypeError("semantic parser accepts FinalUserTurn only")
        if not isinstance(expectation, DialogueExpectation):
            raise TypeError("semantic parser requires DialogueExpectation")

        text = turn.text
        diagnostics: list[str] = []
        acts = []

        if expectation.kind is ExpectationKind.TRANSFER_CONFIRMATION:
            control = self._confirmation_prefix(text)
            if control is not None:
                accepted, control_span, residual_span = control
                acts.append(
                    ConfirmPendingAct(control_span, has_following_content=residual_span is not None)
                    if accepted
                    else RejectPendingAct(control_span)
                )
                diagnostics.append("confirmation_prefix:positive" if accepted else "confirmation_prefix:negative")
                if residual_span is not None:
                    acts.append(
                        KnowledgeRequestAct(
                            residual_span,
                            text[residual_span.start : residual_span.end],
                        )
                    )
                    diagnostics.append("residual:knowledge_request")
                return SemanticTurn(turn, expectation, tuple(acts), self.version, tuple(diagnostics))
            diagnostics.append("confirmation:ambiguous_as_content")

        content_span = self._trimmed_span(text, 0, len(text))
        assert content_span is not None  # FinalUserTurn already rejects blank text.
        # The expectation only gives meaning to short contextual answers.
        # A self-contained operator request remains an explicit command while
        # confirmation is pending and must not fall through to RAG.
        if _TRANSFER_REQUEST.fullmatch(text):
            acts.append(TransferRequestAct(content_span))
            diagnostics.append("explicit_transfer_request")
        else:
            acts.append(KnowledgeRequestAct(content_span, text[content_span.start : content_span.end]))
            diagnostics.append("default:knowledge_request")
        return SemanticTurn(turn, expectation, tuple(acts), self.version, tuple(diagnostics))

    def _confirmation_prefix(self, text: str) -> tuple[bool, SourceSpan, SourceSpan | None] | None:
        candidates = ((True, _POSITIVE.match(text)), (False, _NEGATIVE.match(text)))
        for accepted, match in candidates:
            if match is None:
                continue
            raw_end = match.end()
            suffix = text[raw_end:]
            if suffix and suffix[0].isalnum():
                continue
            residual = self._residual_span(text, raw_end)
            if residual is None:
                control = self._trimmed_span(text, match.start(), len(text))
                assert control is not None
                return accepted, control, None
            # A bare word followed only by whitespace and another word is
            # ambiguous (for example, "нет ли ..."); do not execute it.
            separator = text[raw_end : residual.start]
            if not re.search(r"[,.;:!?—-]", separator) and not re.search(
                r"\b(?:но|а|и)\b", separator, re.IGNORECASE
            ):
                continue
            control = self._trimmed_span(text, match.start(), raw_end)
            assert control is not None
            return accepted, control, residual
        return None

    @staticmethod
    def _trimmed_span(text: str, start: int, end: int) -> SourceSpan | None:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return SourceSpan(start, end) if start < end else None

    @staticmethod
    def _residual_span(text: str, start: int) -> SourceSpan | None:
        suffix = text[start:]
        connector = _RESIDUAL_CONNECTOR.match(suffix)
        if connector is not None:
            start += connector.end()
        else:
            delimiters = _LEADING_DELIMITERS.match(suffix)
            if delimiters is not None:
                start += delimiters.end()
        return SemanticTurnParser._trimmed_span(text, start, len(text))


__all__ = ["PARSER_VERSION", "SemanticTurnParser"]
