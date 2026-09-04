# Отчёт о диалоге `real-media-composition-call`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `transfer_completed`
- Ревизия контекста: `3`
- Transfer: `completed`
- Результат оператора: `operator_connected`

## Текстовый контекст

- `user` (`real-media-composition-call:turn-1`): Мы считаем, что это следующий логист.
- `assistant` (`real-media-composition-call:turn-1:answer`): Недостаточно подтверждённых фрагментов локальной базы для ответа на ваш вопрос. Предлагаю подключить оператора.
- `user` (`real-media-composition-call:transfer-confirm`): Да

## Диагностика RAG

### Запрос 1

- Текст: Мы считаем, что это следующий логист.
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `ollama-embeddinggemma-2026-09-03`
- Embedding-модель: `embeddinggemma`
- Источники: `wiki-physics-rayleigh, wiki-chemistry-water`
- Фрагмент `wiki-physics-rayleigh-001` из `wiki-physics-rayleigh`, score `0.1510`
- Фрагмент `wiki-physics-rayleigh-002` из `wiki-physics-rayleigh`, score `0.1439`
- Фрагмент `wiki-chemistry-water-002` из `wiki-chemistry-water`, score `0.1292`

## Переходы FSM

- #1: `idle` → `call_open` (call_open)
- #2: `call_open` → `listening` (call_answered)
- #3: `listening` → `thinking` (utterance_final)
- #4: `thinking` → `offering_transfer` (answer_approved)
- #5: `offering_transfer` → `awaiting_transfer_confirmation` (offer_played)
- #6: `awaiting_transfer_confirmation` → `transferring` (user_confirmed)
- #7: `transferring` → `terminal` (transfer_result; причина: transfer_completed)

## Ограничения демонстратора

- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.
- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.
