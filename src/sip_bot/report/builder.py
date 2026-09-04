"""Deterministic, text-only report construction for a completed call."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sip_bot.context.store import ContextSnapshot
from sip_bot.dialogue.events import TransferResult
from sip_bot.dialogue.fsm import Transition
from sip_bot.retrieval.contracts import KnowledgeContext


@dataclass(frozen=True, slots=True)
class ReportInput:
    call_id: str
    terminal_state: str
    terminal_reason: str
    context: ContextSnapshot
    rag_contexts: tuple[KnowledgeContext, ...] = ()
    transitions: tuple[Transition, ...] = ()
    transfer_result: TransferResult | None = None

    def __post_init__(self) -> None:
        if not self.call_id or not self.terminal_state or not self.terminal_reason:
            raise ValueError("report identity and terminal outcome are required")
        if self.context.call_id != self.call_id:
            raise ValueError("report context call_id does not match report")


class ReportBuilder:
    """Render the report from already-owned state, context and RAG diagnostics."""

    def build(self, value: ReportInput) -> str:
        lines = [
            f"# Отчёт о диалоге `{value.call_id}`",
            "",
            "## Завершение",
            "",
            f"- Итоговое состояние FSM: `{value.terminal_state}`",
            f"- Причина завершения: `{value.terminal_reason}`",
            f"- Ревизия контекста: `{value.context.revision}`",
        ]
        if value.transfer_result is not None:
            lines.extend(
                [
                    f"- Transfer: `{value.transfer_result.status.value}`",
                    f"- Результат оператора: `{value.transfer_result.reason or 'не указан'}`",
                ]
            )
        lines.extend(["", "## Текстовый контекст", ""])
        if value.context.turns:
            for turn in value.context.turns:
                lines.append(f"- `{turn.role}` (`{turn.turn_id}`): {turn.text}")
        else:
            lines.append("- Контекстных ходов нет.")

        lines.extend(["", "## Диагностика RAG", ""])
        if value.rag_contexts:
            for index, context in enumerate(value.rag_contexts, start=1):
                sources = ", ".join(context.source_ids) or "нет"
                lines.extend(
                    [
                        f"### Запрос {index}",
                        "",
                        f"- Текст: {context.query_text}",
                        f"- Достаточность: `{str(context.sufficient).lower()}`",
                        f"- Порог / top-k: `{context.threshold}` / `{context.top_k}`",
                        f"- Индекс: `{context.index_version}`",
                        f"- Embedding-модель: `{context.embedding_model}`",
                        f"- Источники: `{sources}`",
                    ]
                )
                if context.failure:
                    lines.append(f"- Ошибка поиска: `{context.failure}`")
                for hit in context.hits:
                    lines.append(
                        f"- Фрагмент `{hit.chunk_id}` из `{hit.source_id}`, score `{hit.score:.4f}`"
                    )
        else:
            lines.append("- RAG-контекст не передан.")

        lines.extend(["", "## Переходы FSM", ""])
        if value.transitions:
            for transition in value.transitions:
                reason = f"; причина: {transition.reason}" if transition.reason else ""
                lines.append(
                    f"- #{transition.sequence}: `{transition.previous.value}` → "
                    f"`{transition.current.value}` ({transition.event}{reason})"
                )
        else:
            lines.append("- Переходов нет.")

        lines.extend(
            [
                "",
                "## Ограничения демонстратора",
                "",
                "- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.",
                "- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.",
                "",
            ]
        )
        return "\n".join(lines)


class ReportFinalizationError(RuntimeError):
    """The same terminal call was asked to finalize with different content."""


class ReportFinalizer:
    """Write exactly one reproducible report per call and make repeats idempotent."""

    def __init__(self, root: Path, *, builder: ReportBuilder | None = None) -> None:
        self.root = Path(root)
        self.builder = builder or ReportBuilder()

    def finalize(self, value: ReportInput) -> Path:
        destination = self.root / value.call_id / "report.md"
        rendered = self.builder.build(value)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_text(encoding="utf-8") != rendered:
                raise ReportFinalizationError("terminal report already exists with different content")
            return destination
        destination.write_text(rendered, encoding="utf-8")
        return destination

