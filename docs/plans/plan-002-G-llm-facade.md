# Plan-002-G: typed LLM Facade и Ollama HTTP boundary

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-03`  
Статус исполнения: `complete` — deterministic implementation, corrective configuration и real Ollama evidence закрыты `2026-09-03`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Создать внутренний typed `LLM Facade`, который скрывает Ollama HTTP IPC от остальных компонентов, поддерживает
authoritative chat stream, typed structured decision/status/cancellation и отдельную embedding operation для RAG. Фасад
не выбирает skill/prompt policy, не владеет corpus/index и не даёт модели SIP API. Он должен отдельно фиксировать время
от получения финального пользовательского хода до первого/финального результата модели.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | LLM отвечает в рамках локального контекста и поддерживает диалог | Facade передаёт exact typed request and stream | Chat contract/integration | Consumer calls Ollama directly |
| [`architecture.md`](../architecture.md) | C3 — отдельный process через HTTP; Dispatcher не проксирует payload | Один внешний process boundary и прямой text data plane | HTTP/process evidence | Новый IPC без decision |
| [`technical-specification.md`](../technical-specification.md) | Facade covers inference, stream, decision, timeout/cancel and embeddings | Public API is typed and backend-neutral | Contract tests | External JSON leaks to consumers |
| [`ADR-001-llm-and-dialogue-manager.md`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM proposes, FSM executes | Structured decision validated by E | Decision tests | Model controls SIP |
| [`plan-001-C3-llm-primary.md`](plan-001-C3-llm-primary.md) | Ollama HTTP process baseline accepted | Preserve existing IPC and limitations | C3 evidence | Process boundary silently changed |
| [`plan-002-F-skill-prompt-context.md`](plan-002-F-skill-prompt-context.md) | RAG sends typed embedding/query and source-aware request | Facade exposes embedding without owning retrieval | F/G contract | Embedding operation bypasses facade |

## 3. Граница задачи

**Цель:** internal facade API, HTTP request/stream decoding, timeouts, cancellation, structured result mapping and typed
embedding operation.

**Входит:** `LlmRequest`, `LlmStreamEvent`, `StructuredDecision`, `InferenceStatus`, `CancelRequest`,
`EmbeddingRequest/Response`, latency timestamps, HTTP client/process lifecycle and deterministic fake backend.

**Не входит:** prompt templates/skills/RAG search/index, FSM transitions, SIP, ASR/TTS, model training, direct model
selection policy beyond config constant and no production service hardening.

**Protected baseline:** local Ollama process, HTTP IPC from C3, main app free-threaded runtime, no direct consumer access
to Ollama API, one conversation, stale results closed by channel.

**Предположения:** `002-F` validates request payload and sources; C3 Ollama process is available for sequential heavy
inference probe; exact current stable model/embedding versions remain configuration/evidence, not hard-coded plan claims.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Facade API | `src/sip_bot/llm/facade.py`, `types.py` | Feasibility API only | Internal typed chat/embed/cancel/status | No app API | Define minimal typed interface |
| HTTP transport | `src/sip_bot/llm/ollama_client.py` | C3 evidence only | Stream decoder and timeout/cancel mapping | No application client | Wrap existing HTTP boundary |
| Metrics | `src/sip_bot/llm/telemetry.py` | No app timing | final-turn→request→first-result→complete timestamps | Required report metric | Add structured diagnostics |
| Tests | `tests/unit/test_llm_facade.py`, `tests/contract/test_llm_http.py` | Отсутствуют | Fake HTTP/stream and cancellation tests | No fixtures | Create deterministic backend |
| Evidence | `artifacts/.../002-G/` | Отсутствует | HTTP, latency, VRAM/model metadata and cancel evidence | No app evidence | Create at execution |

Допустимый write-set: `src/sip_bot/llm/`, LLM unit/contract tests и own evidence root. Changes to Ollama, model files,
prompt manager, FSM and SIP adapter are prohibited. `config/constants.py` may receive only facade-related constants in a
contract propagation change.

## 5. Interaction topology и propagation контрактов

`N10a → N11` sends typed `LlmRequest`; `N10b → N11` sends `EmbeddingRequest`; `N9 → N11` sends `CancelRequest` and
approval/lifecycle control. `N11 → N12` maps typed requests to Ollama HTTP; `N12 → N11` maps JSON/stream into
`LlmStreamEvent`, `EmbeddingResponse`, `InferenceStatus` and error/cancel outcomes. Text stream goes directly to TTS path
only after E approval; structured decision returns via control plane to Dispatcher/FSM.

When a call/channel closes or barge-in occurs, facade closes the HTTP stream/cancel handle and emits cancellation outcome;
late chunks are not published to a closed consumer channel. HTTP timeout is not converted into a successful decision.

## 6. Audit владельца поведения и парадигмы реализации

Facade owns transport mapping, operation lifecycle, stream cancellation and typed diagnostics. Prompt manager owns request
semantics; FSM owns action approval. HTTP decoder may be a pure parser, but it cannot update FSM or bypass facade lifecycle.
The external Ollama process remains a separate owner/runtime boundary.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Сохраняем ли C3 отдельным процессом через HTTP? | Да | Не добавлять новый IPC; preserve tested limitations | `resolved` |
| Нужна ли embedding operation в том же facade? | Да, как отдельная typed operation | F не обращается к Ollama напрямую | `resolved` |
| Кто владеет prompt/RAG semantics? | `002-F`; facade только transport/inference | API consumers do not depend on Ollama JSON | `resolved` |
| Как отменять HTTP inference? | Закрытие/cancel request и stale-result suppression; hard process kill не объявляется гарантированным | Cancellation outcome is explicit | `resolved with C3 limitation` |
| Какие точные model versions? | Избираются execution evidence/config; план не требует invented version pin | Results record actual versions | `resolved: no fixed version requirement` |

## 8. Process invariant audit

- Public API is typed and backend-neutral.
- Chat and embedding calls use the same controlled HTTP boundary but remain distinct operations.
- Deterministic fake backend tests precede GPU-heavy probe; no GPU run is delegated.
- Latency report starts at final user turn and records model first-result/complete timings.
- Any external protocol change creates a gap and stops the slice.

## 9. Architecture invariant audit

- No consumer directly imports or calls Ollama API.
- Dispatcher receives structured decision/status, not large prompt/response payload.
- Facade never executes SIP/transfer/hangup.
- Cancellation closes the relevant channel and suppresses stale result.
- Free-threaded main process/no-GIL or explicit C3 process boundary remains visible in evidence.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| G1 | Define typed chat/embed/status/cancel contracts | Contracts match Map-I and F output | Fields cannot express cancel/error/source operation |
| G2 | Implement fake HTTP stream decoder and timeout/cancel mapping | Unit/contract tests pass without Ollama | External JSON leaks or timeout becomes success |
| G3 | Connect existing Ollama HTTP process | Chat and embed operations return typed results | C3 IPC mismatch or process lifecycle unexplained |
| G4 | Capture final-turn→first-result/complete latency and model metadata | Evidence distinguishes request and generation time | Timestamp origin ambiguous |
| G5 | Handoff to H/J and update Map-I | TTS receives only approved text stream; E receives decision | Data/control plane mismatch |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-G-001` | весь plan | Child plan не прошёл owner review | Facade implementation | project owner | APG review | `resolved — owner review accepted 2026-09-03` |
| `B-002-G-002` | G3 | Existing C3 HTTP process contract cannot be consumed by typed facade | Answer/RAG paths | project owner + C3 owner | `real-provider-probe.json`: `/api/embed` + `/api/chat` pass | `resolved — real local Ollama HTTP boundary accepted 2026-09-03` |
| `B-002-G-003` | G4 | Cannot measure final-turn-to-result interval | Report latency claim | project owner | `real-provider-probe.json` and `LatencyTrace` | `resolved — first usable 282.8241 ms, final result 1230.582814 ms` |

## 12. Test plan и evidence

- typed request/response schema and no raw Ollama types in consumer tests;
- fake streaming chunks, final decision, malformed response, timeout and cancellation;
- embedding request/response through facade with vector length/operation metadata;
- real local Ollama chat and embedding probe, executed sequentially by main executor;
- close HTTP stream during inference and prove stale result is not published;
- record `t_final_user_turn`, `t_request`, first stream event, first usable fragment, final result, cancel/timeout and
  actual model/runtime/VRAM metadata.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Cancellation by closing HTTP stream | C3 provides this practical boundary | Does not claim hard model interruption; stale result must still be suppressed | G3/G4 and report | `approved with limitation` |
| Alternate inference backend | Not needed for current baseline | Requires separate owner review/ADR | New plan | `forbidden by default` |
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete; owner review accepted; deterministic execution, corrective configuration, real provider evidence и propagation
закрыты 2026-09-03`. Closeout передаёт H typed answer/playback input, J decision/latency evidence, F embedding operation
result and Map-I revision `7`. C3 limitation — отсутствие server-side cancellation acknowledgement — сохранена явно;
client-side close и stale-result suppression проверены.
