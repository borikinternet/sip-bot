# Отчёт о диалоге `i1-8-live-call`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `OK`
- Ревизия контекста: `2`

## Текстовый контекст

- `user` (`i1-8-live-call:turn-1`): Почему небо днём кажется голубым?
- `assistant` (`i1-8-live-call:turn-1:answer`): Небо днём кажется голубым, потому что молекулы атмосферы рассеивают коротковолновую часть видимого света сильнее длинноволновой. Это явление называют рассеянием Рэлея.

## Диагностика RAG

### Запрос 1

- Текст: Почему небо днём кажется голубым?
- Достаточность: `true`
- Порог / top-k: `0.35` / `3`
- Индекс: `ollama-embeddinggemma-2026-09-03`
- Embedding-модель: `embeddinggemma`
- Источники: `wiki-physics-rayleigh, wiki-astronomy-mars`
- Фрагмент `wiki-physics-rayleigh-001` из `wiki-physics-rayleigh`, score `0.5866`
- Фрагмент `wiki-astronomy-mars-002` из `wiki-astronomy-mars`, score `0.2727`
- Фрагмент `wiki-astronomy-mars-001` из `wiki-astronomy-mars`, score `0.2189`

## Переходы FSM

- #1: `idle` → `call_open` (call_open)
- #2: `call_open` → `listening` (call_answered)
- #3: `listening` → `thinking` (utterance_final)
- #4: `thinking` → `playing` (answer_approved)
- #5: `playing` → `listening` (playback_finished)
- #6: `listening` → `terminal` (call_ended; причина: OK)

## Ограничения демонстратора

- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.
- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.
