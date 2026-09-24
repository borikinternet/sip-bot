# Map-013 closeout: приветствие и короткий prompt

Дата: `2026-09-22`  
Статус: `complete`

## Что изменено

- default skill instruction, prompt template и их версии имеют один источник в `config/constants.py`;
- authoritative runners используют `build_default_prompt_manager()` вместо собственных копий текста;
- точная инструкция `Отвечай коротко.` входит в sufficient-RAG answer path;
- после `CALL_ANSWERED` FSM открывает speech ingress и выдаёт typed `PLAY_GREETING`;
- `ConversationPipeline` синтезирует `CALL_GREETING_TEXT` существующим TTS path без LLM/RAG;
- greeting является отменяемым playback и не повторяется на duplicate answer event.

## Проверки

- Windows regression: `243 passed, 5 skipped`;
- target CPython 3.14.7t: `38 passed`; `sys._is_gil_enabled() == False` после импортов новых границ;
- real AI gate: `013-A/target-20260922-r4`, `status=pass`, first usable `176.215 ms`, final result `884.254 ms`;
- registered full RAG call: `013-B/registered-rag-live-20260922-r3/rag-workshop-full-live.json`, `status=pass`,
  все `rag_workshop.checks=true`;
- live context начинается с assistant turn `Алло.`; FSM trace содержит `call_greeting`;
- live RTP: expected/egress/peer receive `3912/3913/3913` при tolerance 1, loss/underrun/drop/callback error `0`;
- barge-in, follow-up, unknown-answer, transfer и report прошли в том же звонке.

## Исторические corrective runs

- `013-A/r1`: cold Ollama timeout;
- `013-A/r2`: обнаружен и исправлен stale `corpus_chunks` в probe;
- `013-A/r3`: обнаружена и исправлена устаревшая science-positive fixture после смены active corpus;
- `013-B/registered-live-20260922-r1`: greeting/media прошли, но legacy J4 fixture не соответствовала active corpus;
- `013-B/registered-rag-live-20260922-r2`: внутренний звонок прошёл, wrapper ошибочно выбирал четвёртую assistant
  реплику по индексу и после добавления greeting проверял не тот turn;
- `013-B/registered-rag-live-20260922-r3`: lookup исправлен по typed `turn_id`, полный gate зелёный.

Открытых blocker и owner-review вопросов нет.
