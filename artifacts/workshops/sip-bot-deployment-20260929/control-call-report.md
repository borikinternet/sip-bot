# Отчёт о диалоге `call-in-0-a91890ae6dc241f595786140e80edb2d`

## Завершение

- Итоговое состояние FSM: `terminal`
- Причина завершения: `transfer_completed`
- Ревизия контекста: `10`
- Transfer: `completed`
- Результат оператора: `operator_connected`

## Текстовый контекст

- `assistant` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-1:answer`): Я не могу надёжно ответить на этот вопрос по доступной базе знаний. Подключить оператора?
- `user` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-2`): А ночью сколько будет стоить?
- `assistant` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-2:answer`): Я не могу надёжно ответить на этот вопрос по доступной базе знаний. Подключить оператора?
- `user` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-4`): Стоп, а какие данные нужны для заявки?
- `assistant` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-4:answer`): Я не могу надёжно ответить на этот вопрос по доступной базе знаний. Подключить оператора?
- `user` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-7`): Почему небо днем голубое?
- `assistant` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-7:answer`): Я не могу надёжно ответить на этот вопрос по доступной базе знаний. Подключить оператора?
- `user` (`call-in-0-a91890ae6dc241f595786140e80edb2d:turn-8`): Да.

## Диагностика RAG

### Запрос 1

- Текст: Сколько стоит диагностический выезд мастера?
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `telecom-voice-assistants-embeddinggemma-v1`
- Embedding-модель: `embeddinggemma`
- Источники: `telecom-voice-assistants-guide`
- Причина sufficiency: `insufficient_lexical_support`
- Фактический порог решения: `0.35`
- Semantic score: `0.2047`
- Lexical support: `1` / `2`; query terms `5` / min `2`
- Semantic-only / lexical floor: `0.53` / `0.2`
- Фрагмент `telecom-voice-assistants-guide-021-7ba1dcbe935e` из `telecom-voice-assistants-guide`, score `0.2047`
- Фрагмент `telecom-voice-assistants-guide-004-15cbdd8fb7be` из `telecom-voice-assistants-guide`, score `0.1964`
- Фрагмент `telecom-voice-assistants-guide-019-47b0431adca3` из `telecom-voice-assistants-guide`, score `0.1962`
### Запрос 2

- Текст: А ночью сколько будет стоить?
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `telecom-voice-assistants-embeddinggemma-v1`
- Embedding-модель: `embeddinggemma`
- Источники: `telecom-voice-assistants-guide`
- Причина sufficiency: `insufficient_lexical_support`
- Фактический порог решения: `0.35`
- Semantic score: `0.3667`
- Lexical support: `7` / `10`; query terms `23` / min `2`
- Semantic-only / lexical floor: `0.53` / `0.2`
- Фрагмент `telecom-voice-assistants-guide-024-caee581a81a4` из `telecom-voice-assistants-guide`, score `0.3667`
- Фрагмент `telecom-voice-assistants-guide-023-d0e7fade5883` из `telecom-voice-assistants-guide`, score `0.3443`
- Фрагмент `telecom-voice-assistants-guide-030-b93a299820bc` из `telecom-voice-assistants-guide`, score `0.3300`
### Запрос 3

- Текст: Стоп, а какие данные нужны для заявки?
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `telecom-voice-assistants-embeddinggemma-v1`
- Embedding-модель: `embeddinggemma`
- Источники: `telecom-voice-assistants-guide`
- Причина sufficiency: `insufficient_lexical_support`
- Фактический порог решения: `0.35`
- Semantic score: `0.3376`
- Lexical support: `1` / `2`; query terms `5` / min `2`
- Semantic-only / lexical floor: `0.53` / `0.2`
- Фрагмент `telecom-voice-assistants-guide-023-d0e7fade5883` из `telecom-voice-assistants-guide`, score `0.3376`
- Фрагмент `telecom-voice-assistants-guide-024-caee581a81a4` из `telecom-voice-assistants-guide`, score `0.2666`
- Фрагмент `telecom-voice-assistants-guide-029-b1b7564f9cdd` из `telecom-voice-assistants-guide`, score `0.2517`
### Запрос 4

- Текст: Почему небо днем голубое?
- Достаточность: `false`
- Порог / top-k: `0.35` / `3`
- Индекс: `telecom-voice-assistants-embeddinggemma-v1`
- Embedding-модель: `embeddinggemma`
- Источники: `telecom-voice-assistants-guide`
- Причина sufficiency: `insufficient_lexical_support`
- Фактический порог решения: `0.35`
- Semantic score: `0.2046`
- Lexical support: `1` / `2`; query terms `4` / min `2`
- Semantic-only / lexical floor: `0.53` / `0.2`
- Фрагмент `telecom-voice-assistants-guide-030-b93a299820bc` из `telecom-voice-assistants-guide`, score `0.2046`
- Фрагмент `telecom-voice-assistants-guide-027-66214cefb376` из `telecom-voice-assistants-guide`, score `0.1602`
- Фрагмент `telecom-voice-assistants-guide-028-5466d867b7c2` из `telecom-voice-assistants-guide`, score `0.0991`

## Семантические действия

- `call-in-0-a91890ae6dc241f595786140e80edb2d:turn-1` act #1: `knowledge_request` span `0:44` — `applied`; `listening` → `thinking`
- `call-in-0-a91890ae6dc241f595786140e80edb2d:turn-2` act #1: `knowledge_request` span `0:29` — `applied`; `awaiting_transfer_confirmation` → `thinking`
- `call-in-0-a91890ae6dc241f595786140e80edb2d:turn-4` act #1: `knowledge_request` span `0:38` — `applied`; `listening` → `thinking`
- `call-in-0-a91890ae6dc241f595786140e80edb2d:turn-7` act #1: `knowledge_request` span `0:25` — `applied`; `awaiting_transfer_confirmation` → `thinking`
- `call-in-0-a91890ae6dc241f595786140e80edb2d:turn-8` act #1: `confirm_pending` span `0:3` — `applied`; `awaiting_transfer_confirmation` → `transferring`

## Переходы FSM

- #1: `idle` → `call_open` (call_open)
- #2: `call_open` → `playing` (call_greeting)
- #3: `playing` → `listening` (barge_in)
- #4: `listening` → `thinking` (knowledge_request)
- #5: `thinking` → `offering_transfer` (answer_approved)
- #6: `offering_transfer` → `awaiting_transfer_confirmation` (offer_played)
- #7: `awaiting_transfer_confirmation` → `listening` (confirmation_deferred_for_content)
- #8: `listening` → `thinking` (knowledge_request)
- #9: `thinking` → `offering_transfer` (answer_approved)
- #10: `offering_transfer` → `listening` (barge_in)
- #11: `listening` → `thinking` (knowledge_request)
- #12: `thinking` → `offering_transfer` (answer_approved)
- #13: `offering_transfer` → `awaiting_transfer_confirmation` (offer_played)
- #14: `awaiting_transfer_confirmation` → `listening` (confirmation_deferred_for_content)
- #15: `listening` → `thinking` (knowledge_request)
- #16: `thinking` → `offering_transfer` (answer_approved)
- #17: `offering_transfer` → `awaiting_transfer_confirmation` (offer_played)
- #18: `awaiting_transfer_confirmation` → `transferring` (user_confirmed)
- #19: `transferring` → `terminal` (transfer_result; причина: transfer_completed)

## Ограничения демонстратора

- Аудиозапись проектом не создаётся; аудио остаётся ответственностью PBX.
- Отчёт содержит только текст, состояние и диагностические идентификаторы источников.
