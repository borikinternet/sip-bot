"""Authoritative spoken scenario for the RAG onboarding live workshop gate."""

from __future__ import annotations

from typing import Final


RAG_WORKSHOP_SCENARIO_SPECS: Final[tuple[tuple[str, str, float, float], ...]] = (
    ("turn-1", "Сколько стоит диагностический выезд мастера?", 1.5, 14.5),
    ("turn-2", "А ночью сколько будет стоить?", 0.0, 1.0),
    ("turn-3", "Стоп, а какие данные нужны для заявки?", 5.5, 11.0),
    ("turn-4", "Почему небо днём голубое?", 11.0, 10.5),
    ("turn-5", "Да", 10.5, 10.0),
)


__all__ = ["RAG_WORKSHOP_SCENARIO_SPECS"]
