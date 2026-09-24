"""Deterministic Russian query preparation for semantic retrieval."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

try:  # Optional on the host; the capability is recorded explicitly.
    from razdel import tokenize as _razdel_tokenize
except ImportError:  # pragma: no cover - exercised by capability test
    _razdel_tokenize = None

try:  # Optional on the host; the capability is recorded explicitly.
    import pymorphy3 as _pymorphy3
except ImportError:  # pragma: no cover - exercised by capability test
    _pymorphy3 = None


QUERY_POLICY_VERSION = "ru-natural-science-v2"
_TOKEN_FALLBACK = re.compile(r"(?u)[A-Za-zА-Яа-яЁё0-9]+(?:[./^+−-][A-Za-zА-Яа-яЁё0-9]+)*|°[CFК]")
_NEGATIONS = frozenset({"не", "нет", "без"})
# Versioned service-word policy. Content-bearing question words remain signals;
# conversational wrappers and generic request verbs do not inflate lexical
# support that they can never satisfy in the source fragment.
_STOP_WORDS = frozenset(
    {
        "а", "и", "но", "да", "же", "ли", "в", "во", "на", "из", "к", "ко", "по", "с", "со", "у",
        "о", "об", "от", "до", "для", "при", "над", "под", "между", "за", "про", "как-то", "это",
        "мне", "могу", "можешь", "можете", "мочь", "можно", "пожалуйста", "скажите", "сказать",
        "расскажите", "вы", "ты", "привет", "здравствуйте", "какой", "какого", "какая", "какое",
    }
)
_CONTEXT_REFERENCES = frozenset(
    {"он", "она", "оно", "они", "это", "этот", "тот", "такой", "там", "туда", "тогда", "ещё"}
)


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    authoritative_text: str
    normalized_text: str
    embedding_text: str
    lexical_terms: tuple[str, ...]
    phrases: tuple[str, ...]
    policy_version: str
    context_turn_ids: tuple[str, ...]


def _is_special(token: str) -> bool:
    return bool(
        re.search(r"\d|[/^+−-]|°", token)
        or (re.search(r"[A-Za-z]", token) and re.search(r"[А-Яа-яЁё]", token))
    )


class KnowledgeQueryBuilder:
    """Own query normalization, bounded context and explainable terms."""

    def __init__(self, *, max_context_chars: int = 1800, max_phrase_tokens: int = 4) -> None:
        self.max_context_chars = max_context_chars
        self.max_phrase_tokens = max_phrase_tokens
        self._morph = _pymorphy3.MorphAnalyzer() if _pymorphy3 is not None else None

    @property
    def capabilities(self) -> dict[str, bool | str]:
        return {
            "razdel": _razdel_tokenize is not None,
            "pymorphy3": self._morph is not None,
            "policy_version": QUERY_POLICY_VERSION,
        }

    def requires_dialogue_context(self, text: str) -> bool:
        """Return whether a user turn is incomplete without recent dialogue.

        Retrieval must not let an earlier topic dominate a new, explicit
        question.  The MVP keeps context only for short conjunction-led turns
        and explicit anaphora; prompt composition still receives the complete
        bounded conversation independently.
        """

        if not isinstance(text, str) or not text.strip():
            raise ValueError("query text must be non-empty")
        raw_tokens = self._tokens(text)
        normalized = tuple(self._normalize_token(token) for token in raw_tokens)
        content = tuple(token for token in normalized if token and token not in _STOP_WORDS)
        lowered = text.strip().casefold()
        return bool(
            any(token in _CONTEXT_REFERENCES for token in normalized)
            or (lowered.startswith(("а ", "и ")) and len(content) <= 5)
            or (
                lowered.endswith("?")
                and normalized
                and normalized[0] == "сколько"
                and 1 < len(content) <= 3
            )
        )

    def build(self, text: str, *, context: Iterable[tuple[str, str]] = ()) -> KnowledgeQuery:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("query text must be non-empty")
        tokens = self._tokens(text)
        normalized_tokens = [self._normalize_token(token) for token in tokens]
        normalized_tokens = [token for token in normalized_tokens if token]
        normalized = " ".join(normalized_tokens)
        context_items = tuple(context)
        context_tail = " ".join(value.strip() for _, value in context_items if value.strip())
        if len(context_tail) > self.max_context_chars:
            context_tail = context_tail[-self.max_context_chars :]
        embedding_text = normalized if not context_tail else f"{context_tail}\nТекущий вопрос: {normalized}"
        context_tokens = [self._normalize_token(token) for token in self._tokens(context_tail)] if context_tail else []
        retrieval_tokens = [*context_tokens, *normalized_tokens]
        terms = tuple(
            dict.fromkeys(
                token for token in retrieval_tokens if token and (token not in _STOP_WORDS or token in _NEGATIONS)
            )
        )
        phrases = tuple(dict.fromkeys(self._phrases(normalized_tokens)))
        return KnowledgeQuery(
            authoritative_text=text,
            normalized_text=normalized,
            embedding_text=embedding_text,
            lexical_terms=terms,
            phrases=phrases,
            policy_version=QUERY_POLICY_VERSION,
            context_turn_ids=tuple(turn_id for turn_id, _ in context_items),
        )

    def _tokens(self, text: str) -> list[str]:
        text = unicodedata.normalize("NFKC", text)
        # razdel intentionally separates letters and digits in strings such as
        # H2O or 10^3.  Scientific tokens are retrieval-bearing data, so use
        # the protected tokenizer whenever the fallback lexer sees one.  For
        # ordinary text we still use razdel when it is available.
        fallback_tokens = _TOKEN_FALLBACK.findall(text)
        if any(_is_special(token) for token in fallback_tokens):
            return fallback_tokens
        if _razdel_tokenize is not None:
            return [item.text for item in _razdel_tokenize(text) if _TOKEN_FALLBACK.fullmatch(item.text)]
        return fallback_tokens

    def _normalize_token(self, token: str) -> str:
        lowered = unicodedata.normalize("NFKC", token).casefold()
        if _is_special(lowered) or token in {"°C", "°F", "°К"}:
            return lowered
        if self._morph is None or not re.search(r"[а-яё]", lowered):
            return lowered
        parsed = self._morph.parse(lowered)
        return parsed[0].normal_form if parsed else lowered

    def _phrases(self, tokens: list[str]) -> list[str]:
        result: list[str] = []
        for size in range(2, min(self.max_phrase_tokens, len(tokens)) + 1):
            result.extend(" ".join(tokens[pos : pos + size]) for pos in range(len(tokens) - size + 1))
        return result


def query_capabilities() -> dict[str, bool | str]:
    return KnowledgeQueryBuilder().capabilities
