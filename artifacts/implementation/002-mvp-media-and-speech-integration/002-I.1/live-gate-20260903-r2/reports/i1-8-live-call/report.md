# Отчёт о диалоге `i1-8-live-call`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `OK`
- Ревизия контекста: `2`

## Текстовый контекст

- `user` (`i1-8-live-call:turn-1`): Почему не поднём?
- `assistant` (`i1-8-live-call:turn-1:answer`): Недостаточно подтверждённых фрагментов локальной базы для ответа на ваш вопрос. Предлагаю подключить оператора.

## Диагностика RAG

### Запрос 1

- Текст: Почему не поднём?
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `ollama-embeddinggemma-2026-09-03`
- Embedding-модель: `embeddinggemma`
- Источники: `wiki-chemistry-water, wiki-physics-rayleigh`
- Фрагмент `wiki-chemistry-water-002` из `wiki-chemistry-water`, score `0.1833`
- Фрагмент `wiki-physics-rayleigh-001` из `wiki-physics-rayleigh`, score `0.1692`
- Фрагмент `wiki-chemistry-water-001` из `wiki-chemistry-water`, score `0.1469`

## Переходы FSM

- #1: `idle` → `call_open` (call_open)
- #2: `call_open` → `listening` (call_answered)
- #3: `listening` → `thinking` (utterance_final)
- #4: `thinking` → `offering_transfer` (answer_approved)
- #5: `offering_transfer` → `awaiting_transfer_confirmation` (offer_played)
- #6: `awaiting_transfer_confirmation` → `terminal` (call_ended; причина: OK)

## Ограничения демонстратора

- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.
- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.
