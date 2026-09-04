# Отчёт о диалоге `real-composition-call`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `BYE`
- Ревизия контекста: `1`

## Текстовый контекст

- `user` (`real-composition-call:turn-1`): Почему небо днём кажется голубым?

## Диагностика RAG

### Запрос 1

- Текст: Почему небо днём кажется голубым?
- Достаточность: `true`
- Порог / top-k: `0.35` / `3`
- Индекс: `ollama-embeddinggemma-2026-09-03`
- Embedding-модель: `embeddinggemma`
- Источники: `wiki-physics-rayleigh, wiki-astronomy-mars`
- Фрагмент `wiki-physics-rayleigh-001` из `wiki-physics-rayleigh`, score `0.6060`
- Фрагмент `wiki-astronomy-mars-002` из `wiki-astronomy-mars`, score `0.2737`
- Фрагмент `wiki-astronomy-mars-001` из `wiki-astronomy-mars`, score `0.2322`

## Переходы FSM

- #1: `idle` → `call_open` (call_open)
- #2: `call_open` → `listening` (call_answered)
- #3: `listening` → `thinking` (utterance_final)
- #4: `thinking` → `listening` (invalid_decision)
- #5: `listening` → `terminal` (remote_hangup; причина: BYE)

## Ограничения демонстратора

- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.
- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.
