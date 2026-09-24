# Карта 021: конференционный web-demo с заменой RAG и SIP-звонком

Уровень: `map`
Статус: `in_progress` — local web/RAG/SIP contracts и Ollama/FreeSWITCH prerequisites подтверждены; registered browser gate deferred
Родительская roadmap: [`roadmap.md`](../roadmap.md)
Зависимость: [`Map-020`](plan-020-freeswitch-webrtc.md) для browser SIP over WSS/DTLS-SRTP
ADR: [`ADR-006`](../decisions/ADR-006-conference-web-rag-session-routing.md)

## 1. Цель и проверяемый результат

Собрать в отдельном корневом каталоге `demo-web/` простой web-интерфейс и backend для конференционной
демонстрации SIP-бота.

Проверяемый результат: посетитель открывает страницу, видит текущий RAG и примеры вопросов, может загрузить один
локальный `.md`, `.txt` или текстовый `.pdf` размером не более `640 KiB`, дождаться подготовки session-scoped индекса, получить
назначенный caller ID и позвонить browser SIP-клиентом на существующую очередь FreeSWITCH `mod_callcenter`.
Когда звонок доходит до односессионного бота, PJSUA2 выбирает корпус по caller ID, загружает подготовленный индекс
между `180 Ringing` и `200 OK`, после чего звонок обслуживается обычным runtime-путём.

## 2. Почему это карта, а не один срез

Задача содержит независимые acceptance boundaries:

1. web session/upload/status и heartbeat;
2. metadata, chunking, embeddings, публикация и удаление RAG-артефакта;
3. caller ID propagation PJSUA2 и call-scoped readiness/load до `200 OK`;
4. browser UI, QR, greeting и вызов через Map-020;
5. зарегистрированный сквозной gate через `mod_callcenter`.

Они затрагивают frontend, backend, retrieval lifecycle, SIP/media boundary и live evidence, поэтому должны исполняться
отдельными child plans. Создание этой карты не разрешает их execution.

## 3. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Локальные ASR/LLM/TTS/RAG, русский голосовой диалог, один разговор, SIP и отчёт остаются границами MVP | Web-demo только предоставляет вход в существующий call path | Demo call с ответом и report | Web UI начинает заменять dialogue/runtime owners |
| [`architecture.md`](../architecture.md) | Control plane отделён от data plane; PCM, ASR/TTS и RAG payload не идут через Dispatcher/Event Bus | WebSocket переносит только status/heartbeat; SIP media остаётся у FreeSWITCH/PJSUA2 | Contract tests и topology audit | Аудио или крупный текст маршрутизируется через control bus/websocket |
| [`technical-specification.md`](../technical-specification.md) | `180 → readiness → 200/503`, negotiated media и readiness до допуска вызова | На bot agent leg RAG load добавляется в существующий readiness boundary; browser caller leg уже отвечает при входе в `mod_callcenter` | Incoming-call readiness tests и live trace | `200 OK` agent leg отправлен до готовности выбранного call-scoped path |
| [`development-guidelines.md`](../development-guidelines.md) | Узкие slices, typed-first ownership, bounded queues, target no-GIL, corrective pass и честный deferred evidence | Каждый child plan имеет owner, write-set, blocker register и evidence | APG audit и test reports | Красный acceptance замаскирован или scope расширен молча |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Карта обязана иметь source-map, topology, owner review, child plans, blockers, tests, fallback и closeout | Структура этой карты и дочерних планов | Document registry/backlog audits | Child plan выполняется без review или собственного acceptance |
| [`documentation-process.md`](../documentation-process.md) | Один факт имеет один документ-владелец; новые архитектурные решения фиксируются ADR | ADR-006 владеет session-scoped routing decision, карта — execution scope | Registry audit и ссылочная проверка | Дублирующее или противоречащее описание остаётся активным |
| [`ADR-004`](../decisions/ADR-004-control-plane-event-bus.md) | Event Bus process-local и control-only | Registry/status не превращаются в event-bus payload | Bus rejection/contract tests | `FinalUserTurn`, PCM или index vectors попали в bus |
| [`ADR-006`](../decisions/ADR-006-conference-web-rag-session-routing.md) | FreeSWITCH owns call queue; caller ID selects prepared RAG; one bot session | No second call queue or bot replica | Session/caller/RAG correlation trace | Missing caller mapping silently selects stale custom corpus |
| [`Map-020`](plan-020-freeswitch-webrtc.md) | WSS/REGISTER/ICE/DTLS-SRTP browser path is a separate dependency | Local WSL browser call is already evidenced; this map consumes the transport contract and does not rework WebRTC | Map-020 B evidence and 021-E correlation | Browser transport is claimed ready without registered evidence |

## 4. Граница карты

### Входит

- отдельный каталог `demo-web/` с frontend и backend;
- логотипы как переданные demo-assets;
- QR-код на выданный URL этой страницы;
- временные `session_id` и уникальные `caller_id`;
- WebSocket ping-pong с heartbeat около 5 секунд;
- загрузка одного `.md`/`.txt`/текстового `.pdf` до `640 KiB`;
- metadata корпуса: заголовок, описание темы и примеры вопросов;
- deterministic normalization/chunking и embeddings через существующий RAG-контур;
- session-scoped registry и подготовленный index artifact;
- обновление описания страницы через `rag_ready` status event;
- browser SIP call на существующую очередь `mod_callcenter`;
- caller ID extraction в PJSUA2 и выбор call-scoped RAG;
- ожидание загрузки индекса между `180 Ringing` и `200 OK` на отдельной SIP agent leg бота;
- сохранение текущего `answer → callcenter` поведения: browser caller получает `200 OK` при входе в очередь и слышит
  `moh-sound`, пока bot agent leg готовится;
- dynamic greeting с именем «Василиса» и темой текущего RAG;
- удаление ожидающего корпуса при смерти heartbeat и активного корпуса после terminal SIP event;
- fallback на базовый RAG при отсутствии живого custom mapping;
- тесты и evidence для offline, contract, target/no-GIL и registered live path.

### Не входит

- production-аутентификация, роли, secret management и hardening;
- параллельные bot-инстансы и больше одного активного разговора;
- новая очередь в backend;
- изменение владельца очереди `mod_callcenter`;
- перенос аудио через web-backend или WebSocket;
- реализация собственного SIP/WebRTC stack или изменение transport scope Map-020;
- обязательное удаление уже активного корпуса по смерти browser heartbeat;
- публичное размещение сайта без отдельно выданного URL и решения по сети.

### Protected baseline

- existing `Dispatcher`/`DialogueFSM` ownership и control/data plane separation;
- `mod_callcenter` как единственный владелец call queue;
- `MAX_CONCURRENT_CALLS=1` и односессионный bot runtime;
- existing `180 → readiness → 200/503` SIP admission behavior;
- PCMU/RTP, ASR/VAD/LLM/TTS boundaries и report closeout;
- existing Map-012 RAG corpus/index lifecycle contracts;
- Map-020 browser WSS/DTLS-SRTP scope;
- unrelated dirty-worktree changes, включая Map-019/Map-020 documents.

### Demo-approved simplifications

- no authentication in closed conference network;
- browser-visible SIP demo credentials are allowed by owner decision;
- temporary shared local registry is acceptable;
- fallback to the baseline RAG is allowed for missing/stale custom mapping;
- no production durability guarantee for queue/session state.

## 5. Текущее состояние и gaps

- Existing RAG package/index lifecycle and real embedding path are available from Map-012.
- Existing PJSUA2 adapter has normalized incoming SIP events and readiness gate, but caller ID propagation into the
  routing contract must be explicitly verified.
- Existing greeting path is interruptible and constants-backed; it needs a per-call topic-aware text input for «Василиса».
- Existing FreeSWITCH `mod_callcenter` queue is the accepted call-order owner.
- Map-020 local WSL A/B evidence confirms the browser transport contract; target-server 020-C remains separate and is
  not required to claim that the local WSS endpoint is configured.
- WSL is now in mirrored mode with LAN interface `192.168.1.74`; FreeSWITCH `RTP-IP`, `Ext-RTP-IP`, `SIP-IP` and
  `Ext-SIP-IP` are all pinned to that address. This removes the earlier TCP-only forwarder limitation, but the
  Windows Hyper-V inbound policy still needs an elevated LAN rule for WSS and the RTP range on the phone path.
- `demo-web/` now contains the aiohttp sidecar, session registry, upload/preparation path, frontend state machine and
  supplied logo/photo assets.
- Current local rehearsal inputs are staged: page `http://192.168.1.74:8080/`, direct mirrored WSS
  `wss://192.168.1.74:7443`, queue target `sip:7100@192.168.1.74`; the final conference hostname/certificate can
  replace them later.

## 6. Source-map и write-set

| Область | Файл/компонент | Текущее поведение | Целевое поведение | Допустимый write-set | Gap/действие |
|---|---|---|---|---|---|
| Web application | `demo-web/` | Каталога нет | Frontend, backend, assets и local runbook | New files below `demo-web/` | Create in 021-A/D |
| RAG preparation | `src/sip_bot/retrieval/{corpus,builder,index,evaluation}.py` | Existing strict corpus/chunk/index lifecycle | Reuse without bypass; add only adapter needed for uploaded session artifact | New adapter/tests; existing contracts protected | 021-B audit first |
| LLM metadata | `src/sip_bot/llm/`, `src/sip_bot/prompt/` | Typed local Ollama facade and prompts | Structured metadata generation with bounded input/output | New demo prompt/schema/tests; no direct Ollama web call | 021-B |
| Session registry | New `demo-web/backend/` or shared local module | None | `session_id`, `caller_id`, status, heartbeat, corpus path and lifecycle | New registry implementation/tests | 021-A/B |
| SIP identity | `src/sip_bot/sip_media/{adapter,protocol_events}.py` | Normalized events do not yet expose accepted routing field | Propagate stable caller ID from PJSUA2 to call-start event | Narrow typed field/details and contract tests | 021-C; no free-form SIP control |
| Readiness | `src/sip_bot/runtime_wiring.py`, `runtime_readiness.py` | Runtime warmup before answer | Add selected prepared index load to call-scoped readiness | Narrow methods/tests only | 021-C |
| Composition | `runtime_composition.py`, `conversation_pipeline.py` | Retrieval owner can be composed per call | Bind loaded index and topic greeting to call | Per-call owner path; no global mutation | 021-C |
| Config | `config/constants.py`, `src/sip_bot/config.py` | Static config source | Demo size/heartbeat/paths/greeting template/QR URL contract | Add constants only if required; no env fallback | 021-A/B/C |
| Browser SIP | Map-020/FreeSWITCH | WSS path is separate map | Consume browser client/caller-ID contract | No Map-020 config edits from this map | 021-D |
| Evidence | `artifacts/implementation/021-web-rag-sip-demo/` | Root absent | Per-slice raw outputs and closeouts | New evidence root only | All plans |
| Tests | `tests/{unit,contract,integration}/` | No web demo tests | Session/RAG/routing/readiness/live checks | New focused tests; preserve existing tests | All plans |

Protected from this map: unrelated modified files, Map-019/Map-020 plan contents, FreeSWITCH server configuration owned by
the external WebRTC agent, and existing artifacts outside the new evidence root.

## 7. Interaction topology и propagation contracts

Interaction revision proposed for this map: `web-rag-session-I1`.

```text
Browser page
  ├─ HTTP upload/status ──> Web demo backend
  ├─ WebSocket status/heartbeat <──> Session/Status owner
  └─ SIP over WSS ──> FreeSWITCH mod_sofia/mod_callcenter
                         └─> PJSUA2 bot call
                              ├─ caller_id ──> NormalizedSipEvent
                              ├─ 180 ──> call-scoped RAG registry lookup/load
                              └─ 200 ──> existing Dialogue/FSM/media path
```

| Edge | Producer | Typed input/consumer | Payload | Owner/lifecycle | Checkpoint |
|---|---|---|---|---|---|
| E1 | Browser upload | Backend `submit_upload()` | bounded file bytes + session ID | upload owner; temporary file until validation | extension/size/encoding |
| E2 | RAG preparation | Status owner `publish_status()` | typed `RagPreparationStatus` | backend session registry | `preparing/ready/failed` |
| E3 | Backend | Browser WebSocket status sink | compact JSON status | WebSocket owner; heartbeat scoped | `rag_ready` updates metadata/button |
| E4 | Browser heartbeat | Backend `touch_session()` | session ID + timestamp | session owner; 5 s cadence | stale lease cleanup |
| E5 | Backend registry | PJSUA2/runtime `resolve_caller_rag()` | caller ID → immutable artifact metadata/path | registry owner; wait/active/terminal | atomic lookup |
| E6 | PJSUA2 callback | `NormalizedSipEvent` consumer | caller ID and call details | SIP adapter; call lifecycle | `call_started` trace |
| E7 | Readiness gate | `load_call_rag()` | immutable prepared index | readiness/composition owner | before `200 OK` |
| E8 | FSM/pipeline | existing greeting/TTS path | approved topic greeting text | dialogue/pipeline owner | no PCM through control bus |
| E9 | SIP terminal event | registry `release_call_rag()` | call ID/caller ID/reason | active-call owner | cleanup after terminal |

The web boundary carries status and control metadata only. PCM, RTP, ASR chunks, TTS chunks, `FinalUserTurn`,
`SemanticTurn` and vectors do not cross the Dispatcher/Event Bus or browser WebSocket.

## 8. Audit владельца поведения и парадигмы реализации

| Поведение | Владелец | Основание и граница данных | Lifecycle |
|---|---|---|---|
| Web session/heartbeat | `WebSessionRegistry` | Owns session ID, caller ID lease and last-seen; never owns SIP state | page open → stale/closed |
| Upload and RAG build | `RagPreparationCoordinator` | Owns validation, metadata, chunk/index build and publication; does not own call FSM | upload → ready/failed |
| Caller-to-RAG mapping | `RagSessionRegistry` | Owns immutable mapping and state transition waiting/active/released | ready → terminal call |
| SIP protocol and caller ID | `SipMediaAdapter` | Owns PJSUA2 callback conversion and bounded SIP replies | INVITE → terminal |
| Pre-answer load | `IncomingCallReadinessGate`/runtime coordinator | Owns only bot agent-leg admission/readiness; does not own dialogue semantics | agent-leg 180 → load → 200/503 |
| Dialogue and greeting | `DialogueFSM`/`ConversationPipeline` | Existing owners remain authoritative; greeting text is a compact command/data input | call answered → playback/terminal |
| Call queue | FreeSWITCH `mod_callcenter` | Existing external owner of ordering and waiting callers | call offered → agent bridge |

No free function or hidden startup-only path may replace these owners. If backend and bot are separate processes, the
shared registry is a typed file/IPC boundary; the child plan must choose and test exactly one mechanism.

## 9. Process invariant audit

| Rule | Applicability | Materialized decision/check |
|---|---|---|
| Narrow slices and controlled write-set | applicable | 021-I/A/B/C/D/E have separate write-sets and acceptance |
| Typed-first and owner behavior | applicable | typed session/status/registry/SIP fields; owners listed in §8 |
| Boundaries and propagation | applicable | `web-rag-session-I1`, E1–E9 and contract checkpoints in §7 |
| One-call concurrency | applicable | no bot replicas; FreeSWITCH queue remains external owner |
| Target runtime/no-GIL | applicable for bot and embedding/LLM workers | target `CPython 3.14.7t`; web-only host checks may be separate but cannot change bot baseline |
| Test/evidence and red-result corrective pass | applicable | raw output, category classification and rerun required per child plan |
| Deferred evidence | applicable where browser/target server unavailable | stable evidence ID, owner, command and promotion condition required |
| Fallback rules | applicable | baseline RAG fallback is explicit owner-approved demo simplification, not hidden behavior |
| Dirty worktree preservation | applicable | no reset/checkout; unrelated changes remain outside write-set |
| Documentation sync | applicable | registry/backlog audits after Markdown changes |

## 10. Architecture invariant audit

| Invariant | Boundary | Verification/evidence |
|---|---|---|
| FreeSWITCH `mod_callcenter` is sole call queue | Browser/FreeSWITCH | live caller order, caller-leg `200 + moh-sound`, and bot one-call-at-a-time trace |
| Caller ID is the SIP routing key | PJSUA2 → normalized event → registry | contract test plus live caller-ID correlation |
| Agent-leg `180` precedes call-scoped RAG load and agent-leg `200` | SIP adapter/readiness | event timestamps, caller-leg queue media and failure path |
| RAG is call-scoped, not globally mutated | registry → composition/pipeline | two sequential caller fixtures and cleanup assertions |
| WebSocket carries no audio or model payload | browser/backend/control boundaries | payload allowlist and negative contract tests |
| Dynamic greeting uses existing TTS/playback path | FSM → pipeline → playback | greeting command/input trace and barge-in regression |
| Active corpus survives browser heartbeat loss until SIP terminal | session/active call lifecycle | lifecycle test with dead websocket during active call |
| Missing mapping falls back only to approved baseline | registry/readiness | stale caller fixture and greeting/RAG trace |
| Existing UDP/PCMU/runtime baseline stays green | existing SIP/media tests | full regression plus registered live gate |

## 11. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Нужна ли вторая backend call queue? | Нет, используется `mod_callcenter` | Backend не принимает решение о порядке SIP-звонков | `resolved` |
| Сколько bot-инстансов? | Один, sequential | Никакого scale-out и concurrent RAG memory | `resolved` |
| Чем связывать browser и RAG? | SIP URI user-part caller ID, назначенный web-сессии | PJSUA2 обязан нормализовать URI user-part и передать его дальше | `resolved` |
| Что делает heartbeat? | Удаляет ожидающий mapping при смерти; active call держится до terminal event | Не нужен ESL-based queue cancellation для обязательного scope | `resolved` |
| Что при отсутствии mapping? | Fallback на базовый RAG и generic/topic greeting | Устаревший custom index не используется | `resolved` |
| Лимит файла? | Только размер, `640 KiB`; расширение `.md`/`.txt`/`.pdf` | PDF должен содержать выделяемый текст; OCR не входит в demo scope | `resolved` |
| Какой greeting? | «Я ассистент Василиса. Готова ответить на вопросы по теме …» | Existing greeting/playback path получает per-call text | `resolved` |
| URL/точный WSS endpoint? | Логотип и фото получены в `demo-web/frontend/assets/`; URL и точный endpoint будут переданы позже | QR/live UI closeout пока блокируется только внешними параметрами | `open: URL/endpoint` |
| Где живёт shared registry? | Общий локальный каталог на одной машине/ОС, атомарная публикация manifest/index | Backend и bot читают один immutable prepared artifact; отдельная IPC-служба не нужна | `resolved` |
| Что слышит caller в очереди? | Caller leg отвечает через dialplan `answer` до `callcenter`; очередь проигрывает `moh-sound` | Bot-leg `180` не является browser ringback и не должен использоваться для локального ringback | `resolved` |
| Какой pre-answer bound? | `15 s` от bot-leg `180` до готовности/ответа | При превышении не отправлять `200`; agent leg завершается через существующий failure path, очередь остаётся владельцем retry/ordering | `resolved` |
| Какой web backend? | Python `aiohttp` sidecar в локальном demo runtime | Один процесс даёт HTTP/static/upload/WebSocket; bot runtime и shared-artifact contract не меняются | `resolved` |

Открытые вопросы блокируют только зависимые slices. Они не разрешают молча выбрать новый IPC, public deployment или
production security path.

## 12. Child plans и порядок исполнения

| План | Результат | Зависимость | Evidence root | Review |
|---|---|---|---|---|
| [`021-I`](plan-021-I-web-rag-boundary-map.md) | Boundary map `web-rag-session-I1`, typed edges и caller-ID propagation contract | Map-020 facts/read-only audit | `artifacts/implementation/021-web-rag-sip-demo/I/` | `complete` |
| [`021-A`](plan-021-A-web-session-upload.md) | Web session, WebSocket heartbeat, upload/status API и frontend state | 021-I | `.../A/` | `complete` |
| [`021-B`](plan-021-B-rag-preparation-publication.md) | Metadata, chunking, embeddings, atomic prepared index and registry | 021-I, 021-A | `.../B/` | `in_progress` |
| [`021-C`](plan-021-C-caller-id-rag-readiness.md) | PJSUA2 caller ID, registry lookup, 180→load→200, cleanup and greeting input | 021-I, 021-B, Map-020 SIP contract | `.../C/` | `in_progress` |
| [`021-D`](plan-021-D-conference-ui-sip-flow.md) | Logos, QR, RAG description/questions, button and browser call | 021-A/B, Map-020 browser contract | `.../D/` | `in_progress` |
| [`021-E`](plan-021-E-registered-end-to-end-gate.md) | Full conference scenario through `mod_callcenter` and one bot session | 021-A–D, Map-020 B/C | `.../E/` | `blocked` |

Map-level execution gate: 021-I/A/B/C/D must be complete; 021-E must pass the registered call scenario. No child plan
may claim `complete` without its own acceptance, blocker register, evidence and closeout.

## 13. Implementation slices и правила исполнения

1. **021-I** — source audit and typed boundary revision; no code changes except approved contract tests/fixtures.
2. **021-A** — session/upload/status foundation under `demo-web/`; no SIP/RAG runtime mutation.
3. **021-B** — use existing corpus/index lifecycle; publish immutable artifacts atomically; do not mutate active call state.
4. **021-C** — add the narrowest caller-ID and call-scoped readiness path; preserve `mod_callcenter`, one-call slot and
   existing protocol replies. A failed load must follow the explicitly approved baseline fallback or a documented blocker.
5. **021-D** — integrate the browser client from Map-020; no own SIP stack and no audio proxy.
6. **021-E** — perform clean registered gate, then sync owners/docs/backlog. Browser/live evidence unavailable on the host
   becomes deferred evidence with raw command and promotion condition, not a green result.

Primary executor owns the map. Subagents may execute only after child plan review and only within its write-set. Native
PJSUA2/FreeSWITCH changes remain with the SIP owner; web/RAG code cannot edit their configs outside a reviewed handoff.

## 14. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/снятие | Статус |
|---|---|---|---|---|---|---|
| B-021-1 | 021-A/D | Final conference hostname absent; local rehearsal URL is staged | Final public QR/UI closeout | project owner | supplied final URL | `open — local QR active` |
| B-021-2 | 021-A/B | WebSocket/backend runtime not available in target environment | session/status execution | primary executor | runtime/import probe and selected library | `resolved locally; target deployment still deferred` |
| B-021-3 | 021-C | PJSUA2/FreeSWITCH caller-ID preservation not live-proven | RAG routing live gate | SIP owner | normalized contract exists; registered trace required | `open` |
| B-021-4 | 021-C/E | Local Map-020 browser SIP contract incomplete | browser registered gate | WebRTC owner | local WSS/browser evidence in `E/live-wsl-freeswitch-20260923.md` | `resolved for local transport; verify queue/bot correlation in 021-E` |
| B-021-5 | 021-B/C | Shared registry topology differs from same-host assumption | cross-process lookup/load | project owner | same-host atomic artifact publication/read evidence | `resolved locally; live process trace pending` |
| B-021-6 | 021-E | Corpus load exceeds the `15 s` bot-leg pre-answer window | agent-leg `200 OK` admission | project owner/SIP owner | measured timeout and existing `503`/retry trace without wrong RAG | `resolved by owner decision; verify in 021-C/E` |

No blocker may be converted into a silent fallback. Each red result follows the corrective-pass protocol before becoming a
category-4 architectural blocker.

## 15. Test plan и evidence

### Mandatory deterministic/contract checks

- session ID/caller ID uniqueness and reload semantics;
- WebSocket heartbeat, stale lease and active-call retention;
- file extension (`.md`/`.txt`/text-based `.pdf`) and exact `640 KiB` boundary;
- metadata schema, topic/questions status update and `rag_ready` transition;
- deterministic corpus normalization/chunk/index publication and failure-preserving atomic replacement;
- registry mapping, caller lookup, missing mapping fallback and terminal cleanup;
- PJSUA2 caller ID propagation into `NormalizedSipEvent`;
- caller-leg `200 + moh-sound` while queued, then bot agent-leg `180 → RAG load → 200` ordering and the `15 s` timeout path;
- dynamic Василиса greeting through existing TTS/playback and barge-in;
- no web/control-plane payload contains PCM, vectors or unbounded text;
- existing regression suite remains green.

### Live/evidence checks

- Map-020 local WSL WSS/REGISTER/ICE/DTLS-SRTP evidence is present before 021-E;
- one default-RAG browser call through `mod_callcenter`;
- one custom-RAG browser call with caller-ID correlation and topic greeting;
- two sequential custom calls prove index isolation and cleanup;
- closed/reloaded page produces stale mapping cleanup and approved baseline fallback;
- caller waits in `mod_callcenter`, bot handles exactly one active call;
- RTP/media, report, errors, drops and underrun counters remain clean.

Target runtime: bot and native/inference checks use project CPython `3.14.7t` with GIL disabled; web-only checks use the
selected local backend runtime but must not alter the bot runtime contract. Evidence root:
`artifacts/implementation/021-web-rag-sip-demo/`.

## 16. Fallback/deferred register

| Что | Причина | Ограничение | Принимающий документ | Статус |
|---|---|---|---|---|
| Baseline RAG при отсутствующем custom mapping | Explicit conference-demo owner decision | Не использовать stale custom metadata; trace fallback | 021-C/E closeout | `approved demo fallback` |
| No auth / browser-visible demo SIP credentials | Closed conference network and demo-only scope | Not production-ready; no public security claim | Map-021 closeout | `approved demo simplification` |
| Deferred browser/live gate until Map-020 | External WebRTC transport dependency | Raw evidence and promotion command required | 021-E closeout | `deferred until dependency` |
| External page URL | User will provide final conference URL later | Local QR currently uses `http://192.168.1.74:8080/`; replace asset/config when final URL arrives | 021-D/E closeout | `open — local rehearsal resolved` |

No other fallback is approved. In particular, no second bot instance, no hidden CPU/direct model path and no backend call
queue may be introduced.

## 17. Map-level closeout

Map-021 can be closed only when:

- 021-I/A/B/C/D/E have individual `complete` closeouts;
- browser call uses the accepted Map-020 transport and FreeSWITCH `mod_callcenter` queue;
- custom caller ID selects the correct prepared RAG and two sequential calls show no cross-session leakage;
- caller hears queue `moh-sound` after caller-leg `200`; bot agent-leg `180 → load → 200` and terminal cleanup are evidenced;
- `rag_ready` updates UI metadata and enables the button;
- dynamic Василиса greeting matches the selected/current topic;
- default and custom user flows both work;
- existing regression, target runtime and registered live gates are recorded;
- document registry and backlog audits pass;
- all deferred findings and remaining conference limitations are explicit.

Until these conditions are met, status remains `in_progress` or `deferred` as supported by evidence; the map must
not be called complete because the web page exists or an isolated browser call works.

## 18. Execution report и closeout

Первый execution pass выполнен локально. Созданы `demo-web/backend` и `demo-web/frontend`, session registry с
атомарным `caller_id → artifact` mapping, `rag_ready` WebSocket status, upload limit `640 KiB`, supplied assets,
caller-ID propagation в `NormalizedSipEvent`, call-scoped loader и admission ordering `180 → load → 200/503`.

Проверки:

- `$env:PYTHONPATH='src;demo-web'; .venv\Scripts\python.exe -m pytest -q demo-web/tests` — `7 passed`;
- `$env:PYTHONPATH='src;demo-web'; .venv\Scripts\python.exe -m pytest -q tests/unit/test_incoming_answer_readiness.py tests/unit/test_sip_media.py` — `18 passed`;
- combined demo/SIP selector — `25 passed`;
- backend import probe: CPython `3.14.3`, `aiohttp 3.14.3`;
- `compileall` и `node --check demo-web/frontend/app.js` — exit `0`.

Live local checks now pass: the existing Ubuntu WSL Ollama `0.33.1` exposes both required models, typed metadata
generation works, and the real coordinator published/self-loaded a `768`-dimension index. Debian WSL FreeSWITCH is
active with direct mirrored-LAN WSS `:7443`, SIP/WS bindings, `mod_callcenter` queues and all advertised SIP/RTP
addresses pinned to `192.168.1.74`; an in-WSL SIP-over-WSS upgrade returned HTTP `101`. Evidence:
[`B/live-ollama-20260923.md`](../../artifacts/implementation/021-web-rag-sip-demo/B/live-ollama-20260923.md) and
[`E/live-wsl-freeswitch-20260923.md`](../../artifacts/implementation/021-web-rag-sip-demo/E/live-wsl-freeswitch-20260923.md).

The remaining gate is now the actual phone/LAN call scenario: the page/QR/SIP config and direct mirrored FreeSWITCH
advertising are staged, while a host-elevated Hyper-V firewall rule and external-device WSS/RTP check remain. A browser
→ `mod_callcenter` → one-bot trace with caller-ID/RAG correlation has not yet been registered. Next slice: execute 021-E
with baseline plus two sequential corpora; later replace the local IP QR with the final conference URL.
