# 002-G closeout

Статус: `complete`.

Approved scope реализован и проверен. Real-provider gate G3/G4 выполнен main executor после изолированного
deterministic execution; Ollama остаётся отдельным локальным процессом через существующий HTTP IPC.

## Реализовано

- backend-neutral typed contracts для chat stream, structured decision, status, cancel и embedding;
- stdlib Ollama HTTP client на существующей `127.0.0.1` HTTP boundary, с `/api/chat` и `/api/embed`;
- NDJSON decoder, поддержка `message.content` и `generate`-style `response`, JSON/schema validation;
- mapping malformed response, transport error и timeout в typed error/status без успешного результата;
- cancellable single-use `ChatOperation`, закрытие HTTP stream и suppression stale chunks/results;
- `LatencyTrace` с точками `final_user_turn → request → first stream/usable output → final result/cancel`;
- embedding через тот же фасад, но отдельной typed operation с фактическими F `EmbeddingRequest/EmbeddingResponse`;
- deterministic fake HTTP/backend tests для каждого реализованного behavior.
- main-only real-provider probe: `/api/embed` построил индекс из 6 фрагментов, positive/negative retrieval прошли,
  `/api/chat` вернул structured `answer` с source-aware контекстом;
- corrective generation settings: `think=false`, `temperature=0.1`, `num_predict=96`; first usable output —
  `282.8241 ms`, final result — `1230.582814 ms` от final user turn.

## Изменённые файлы

- `src/sip_bot/llm/__init__.py`
- `src/sip_bot/llm/types.py`
- `src/sip_bot/llm/telemetry.py`
- `src/sip_bot/llm/ollama_client.py`
- `src/sip_bot/llm/facade.py`
- `tests/unit/test_llm_facade.py`
- `tests/contract/test_llm_http.py`
- evidence-файлы в `artifacts/implementation/002-mvp-media-and-speech-integration/002-G/`

## Проверки

- G targeted: `7 passed`, exit `0`;
- host unit + contract regression: `80 passed`, exit `0`;
- compileall: exit `0`;
- host import: exit `0`;
- target CPython `3.14.7t` import: exit `0`, `gil_enabled=false`;
- Ollama/model/GPU probe: pass; подробности и digests — `real-provider-probe.json`.

## Unresolved blocker/gate

- native cancellation acknowledgement остаётся ограничением C3: клиентский HTTP stream close доказан, отдельный
  server-side ack не заявляется.

Это ограничение не блокирует G: stale-result suppression и client-side stream close проверены. `B-002-G-002` и
`B-002-G-003` закрыты real-provider evidence; новый fallback или изменение IPC не вводились.
