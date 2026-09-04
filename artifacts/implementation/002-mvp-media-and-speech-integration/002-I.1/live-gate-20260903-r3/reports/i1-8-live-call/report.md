# Отчёт о диалоге `i1-8-live-call`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `OK`
- Ревизия контекста: `2`

## Текстовый контекст

- `user` (`i1-8-live-call:turn-1`): кажется голубым.
- `assistant` (`i1-8-live-call:turn-1:answer`): Небо кажется голубым из-за явления, называемого рассеянием Рэлея, когда молекулы атмосферы сильнее рассеивают коротковолновую часть видимого света (синий цвет), чем длинноволновую.

## Диагностика RAG

### Запрос 1

- Текст: кажется голубым.
- Достаточность: `true`
- Порог / top-k: `0.35` / `3`
- Индекс: `ollama-embeddinggemma-2026-09-03`
- Embedding-модель: `embeddinggemma`
- Источники: `wiki-physics-rayleigh, wiki-chemistry-water`
- Фрагмент `wiki-physics-rayleigh-001` из `wiki-physics-rayleigh`, score `0.3570`
- Фрагмент `wiki-chemistry-water-002` из `wiki-chemistry-water`, score `0.1796`
- Фрагмент `wiki-physics-rayleigh-002` из `wiki-physics-rayleigh`, score `0.1195`

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
