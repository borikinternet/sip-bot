"""Versioned, source-aware evaluation for a published local RAG index."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns

from .contracts import EmbeddingProvider
from .index import LocalKnowledgeIndex
from .query_builder import KnowledgeQueryBuilder


EVALUATION_SCHEMA_VERSION = "rag-evaluation-v1"
_CASE_KINDS = frozenset({"positive", "paraphrase", "contextual", "negative", "conflict"})


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    kind: str
    question: str
    context: tuple[tuple[str, str], ...]
    expected_sufficient: bool
    expected_any_source_ids: tuple[str, ...]
    expected_top_source_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationSuite:
    schema_version: str
    evaluation_version: str
    corpus_version: str
    index_version: str
    embedding_model: str
    top_k: int
    threshold: float
    cases: tuple[EvaluationCase, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    case_id: str
    kind: str
    question: str
    context: tuple[tuple[str, str], ...]
    passed: bool
    expected_sufficient: bool
    actual_sufficient: bool
    expected_any_source_ids: tuple[str, ...]
    expected_top_source_id: str | None
    source_ids: tuple[str, ...]
    hits: tuple[dict[str, object], ...]
    sufficiency_diagnostics: dict[str, object] | None
    latency_ms: float
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "kind": self.kind,
            "question": self.question,
            "context": [{"turn_id": turn_id, "text": text} for turn_id, text in self.context],
            "passed": self.passed,
            "expected_sufficient": self.expected_sufficient,
            "actual_sufficient": self.actual_sufficient,
            "expected_any_source_ids": list(self.expected_any_source_ids),
            "expected_top_source_id": self.expected_top_source_id,
            "source_ids": list(self.source_ids),
            "hits": list(self.hits),
            "sufficiency_diagnostics": self.sufficiency_diagnostics,
            "latency_ms": self.latency_ms,
            "failures": list(self.failures),
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    status: str
    evaluation_version: str
    evaluation_sha256: str
    corpus_version: str
    index_version: str
    embedding_model: str
    top_k: int
    threshold: float
    passed_cases: int
    total_cases: int
    latency_ms: float
    cases: tuple[EvaluationCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "evaluation_version": self.evaluation_version,
            "evaluation_sha256": self.evaluation_sha256,
            "corpus_version": self.corpus_version,
            "index_version": self.index_version,
            "embedding_model": self.embedding_model,
            "top_k": self.top_k,
            "threshold": self.threshold,
            "passed_cases": self.passed_cases,
            "total_cases": self.total_cases,
            "latency_ms": self.latency_ms,
            "cases": [case.to_dict() for case in self.cases],
        }


def load_evaluation_suite(path: Path) -> EvaluationSuite:
    raw_bytes = Path(path).read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))
    required = {
        "schema_version", "evaluation_version", "corpus_version", "index_version",
        "embedding_model", "top_k", "threshold", "cases",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("evaluation suite has an invalid top-level schema")
    if payload["schema_version"] != EVALUATION_SCHEMA_VERSION:
        raise ValueError("unsupported evaluation schema version")
    if not isinstance(payload["top_k"], int) or payload["top_k"] < 1:
        raise ValueError("evaluation top_k must be positive")
    if not isinstance(payload["threshold"], (int, float)) or not 0 <= payload["threshold"] <= 1:
        raise ValueError("evaluation threshold must be between zero and one")
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("evaluation suite must contain cases")
    cases: list[EvaluationCase] = []
    ids: set[str] = set()
    for position, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise ValueError(f"evaluation case {position} must be an object")
        allowed = {
            "case_id", "kind", "question", "context", "expected_sufficient",
            "expected_any_source_ids", "expected_top_source_id",
        }
        required_case = allowed - {"expected_top_source_id"}
        if not required_case.issubset(raw) or set(raw) - allowed:
            raise ValueError(f"evaluation case {position} has an invalid schema")
        case_id = raw["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("evaluation case IDs must be unique non-empty strings")
        ids.add(case_id)
        if raw["kind"] not in _CASE_KINDS:
            raise ValueError(f"evaluation case {case_id} has an invalid kind")
        if not isinstance(raw["question"], str) or not raw["question"].strip():
            raise ValueError(f"evaluation case {case_id} has an empty question")
        if not isinstance(raw["expected_sufficient"], bool):
            raise ValueError(f"evaluation case {case_id} has invalid expected_sufficient")
        context: list[tuple[str, str]] = []
        if not isinstance(raw["context"], list):
            raise ValueError(f"evaluation case {case_id} context must be a list")
        for turn in raw["context"]:
            if not isinstance(turn, dict) or set(turn) != {"turn_id", "text"}:
                raise ValueError(f"evaluation case {case_id} has invalid context")
            context.append((turn["turn_id"], turn["text"]))
        expected_sources = raw["expected_any_source_ids"]
        if not isinstance(expected_sources, list) or not all(isinstance(item, str) and item for item in expected_sources):
            raise ValueError(f"evaluation case {case_id} has invalid expected sources")
        expected_top = raw.get("expected_top_source_id")
        if expected_top is not None and (not isinstance(expected_top, str) or not expected_top):
            raise ValueError(f"evaluation case {case_id} has invalid expected top source")
        cases.append(
            EvaluationCase(
                case_id=case_id,
                kind=raw["kind"],
                question=raw["question"],
                context=tuple(context),
                expected_sufficient=raw["expected_sufficient"],
                expected_any_source_ids=tuple(expected_sources),
                expected_top_source_id=expected_top,
            )
        )
    return EvaluationSuite(
        schema_version=payload["schema_version"],
        evaluation_version=payload["evaluation_version"],
        corpus_version=payload["corpus_version"],
        index_version=payload["index_version"],
        embedding_model=payload["embedding_model"],
        top_k=payload["top_k"],
        threshold=float(payload["threshold"]),
        cases=tuple(cases),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def evaluate_suite(
    suite: EvaluationSuite,
    index: LocalKnowledgeIndex,
    provider: EmbeddingProvider,
    *,
    query_builder: KnowledgeQueryBuilder | None = None,
) -> EvaluationReport:
    if index.metadata.corpus_version != suite.corpus_version:
        raise ValueError("evaluation/index corpus_version mismatch")
    if index.index_version != suite.index_version:
        raise ValueError("evaluation/index index_version mismatch")
    if index.embedding_model != suite.embedding_model:
        raise ValueError("evaluation/index embedding_model mismatch")
    builder = query_builder or KnowledgeQueryBuilder()
    started = monotonic_ns()
    results: list[EvaluationCaseResult] = []
    for case in suite.cases:
        case_started = monotonic_ns()
        # Mirror the production pipeline: old dialogue is retrieval input only
        # when the current turn is incomplete without it.  Prompt history is a
        # separate concern and must not contaminate a new explicit topic.
        retrieval_context = case.context if builder.requires_dialogue_context(case.question) else ()
        query = builder.build(case.question, context=retrieval_context)
        context = index.query(
            query,
            provider,
            top_k=suite.top_k,
            threshold=suite.threshold,
            context_id=f"eval-{case.case_id}",
        )
        failures: list[str] = []
        if context.sufficient != case.expected_sufficient:
            failures.append("sufficiency")
        if case.expected_any_source_ids and not set(case.expected_any_source_ids).intersection(context.source_ids):
            failures.append("expected_source")
        top_source = context.hits[0].source_id if context.hits else None
        if case.expected_top_source_id is not None and top_source != case.expected_top_source_id:
            failures.append("expected_top_source")
        results.append(
            EvaluationCaseResult(
                case_id=case.case_id,
                kind=case.kind,
                question=case.question,
                context=case.context,
                passed=not failures,
                expected_sufficient=case.expected_sufficient,
                actual_sufficient=context.sufficient,
                expected_any_source_ids=case.expected_any_source_ids,
                expected_top_source_id=case.expected_top_source_id,
                source_ids=context.source_ids,
                hits=tuple(
                    {"chunk_id": hit.chunk_id, "source_id": hit.source_id, "score": hit.score}
                    for hit in context.hits
                ),
                sufficiency_diagnostics=(
                    {
                        "reason": context.sufficiency_diagnostics.reason,
                        "configured_threshold": context.sufficiency_diagnostics.configured_threshold,
                        "effective_threshold": context.sufficiency_diagnostics.effective_threshold,
                        "semantic_only_threshold": context.sufficiency_diagnostics.semantic_only_threshold,
                        "lexical_semantic_floor": context.sufficiency_diagnostics.lexical_semantic_floor,
                        "top_semantic_score": context.sufficiency_diagnostics.top_semantic_score,
                        "top_lexical_support": context.sufficiency_diagnostics.top_lexical_support,
                        "required_top_lexical_support": context.sufficiency_diagnostics.required_top_lexical_support,
                        "eligible_query_terms": context.sufficiency_diagnostics.eligible_query_terms,
                        "minimum_query_terms": context.sufficiency_diagnostics.minimum_query_terms,
                    }
                    if context.sufficiency_diagnostics is not None
                    else None
                ),
                latency_ms=(monotonic_ns() - case_started) / 1_000_000,
                failures=tuple(failures),
            )
        )
    passed = sum(result.passed for result in results)
    return EvaluationReport(
        status="pass" if passed == len(results) else "fail",
        evaluation_version=suite.evaluation_version,
        evaluation_sha256=suite.sha256,
        corpus_version=suite.corpus_version,
        index_version=suite.index_version,
        embedding_model=suite.embedding_model,
        top_k=suite.top_k,
        threshold=suite.threshold,
        passed_cases=passed,
        total_cases=len(results),
        latency_ms=(monotonic_ns() - started) / 1_000_000,
        cases=tuple(results),
    )
