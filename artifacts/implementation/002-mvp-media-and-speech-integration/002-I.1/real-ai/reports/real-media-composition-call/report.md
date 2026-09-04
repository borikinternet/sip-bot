# Отчёт о диалоге `real-media-composition-call`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `BYE`
- Ревизия контекста: `1`

## Текстовый контекст

- `user` (`real-media-composition-call:turn-1`): Продолжение следует...

## Диагностика RAG

### Запрос 1

- Текст: Продолжение следует...
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `ollama-embeddinggemma-2026-09-03`
- Embedding-модель: `embeddinggemma`
- Источники: `wiki-chemistry-water, wiki-astronomy-mars, wiki-physics-rayleigh`
- Фрагмент `wiki-chemistry-water-002` из `wiki-chemistry-water`, score `0.1539`
- Фрагмент `wiki-astronomy-mars-002` из `wiki-astronomy-mars`, score `0.1351`
- Фрагмент `wiki-physics-rayleigh-002` из `wiki-physics-rayleigh`, score `0.1319`

## Переходы FSM

- #1: `idle` → `call_open` (call_open)
- #2: `call_open` → `listening` (call_answered)
- #3: `listening` → `thinking` (utterance_final)
- #4: `thinking` → `listening` (invalid_decision)
- #5: `listening` → `terminal` (remote_hangup; причина: BYE)

## Ограничения демонстратора

- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.
- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.
