# Plan-002-I.1: live-call wiring через основной asyncio loop

Уровень: `child plan`  
Статус owner review: `accepted` — owner review завершён `2026-09-03`  
Статус исполнения: `complete`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Карта взаимодействий: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)  
Блокируемый successor: [`plan-002-J-transfer-report-integration.md`](plan-002-J-transfer-report-integration.md)

Дата подготовки: `2026-09-03`

## 1. Цель и проверяемый результат

Устранить `B-002-I-006`/`B-002-J-006`, соединив уже реализованные компоненты карты 4 в один живой SIP-сценарий.
Основной поток приложения работает в одном основном потоке на `asyncio` event loop; существующий Dispatcher является
задачей этого loop и не становится владельцем data-plane payload.

Проверяемый результат:

```text
SIP/RTP PCMU
  → существующие media callbacks и PcmFrame
  → существующие typed input-методы audio/speech owners
  → FinalUserTurn
  → существующий ConversationPipeline/RAG/LLM Facade
  → существующие TTS output/playback owners
  → SIP/RTP PCMU
```

Один чистый вызов должен пройти через этот путь с реальным target SIP/RTP стендом, а обязательные control-события во
время AI-операций должны обрабатываться без ожидания завершения ASR, LLM или TTS. Должен быть создан единственный
обязательный итоговый `report.md`; аудиозапись проектом не создаётся.

## 2. Принцип исправления

Планы `002-A`–`002-H` уже создали typed components и их contracts. Этот plan не создаёт новые semantic owners и не
вводит отдельный «delivery owner».

Для каждого in-process ребра materialization — это вызов typed input-метода получателя:

```text
producer output → consumer input method
```

Если producer и consumer работают в разных потоках, между ними используется bounded thread-safe queue, после чего
поток consumer вызывает свой input-метод. Если оба работают в основном `asyncio` loop, допустим прямой вызов или
локальная `asyncio.Queue`. `asyncio.Queue` нельзя использовать как межпоточечную очередь.

Execution loop и сборка объектов являются процедурной частью application runtime. Они не принимают решений FSM, не
владеют контекстом, не проксируют payload через Dispatcher и не заменяют существующие компоненты.

## 3. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на этот plan | Проверка/stop condition |
|---|---|---|---|
| [`architecture.md`](../architecture.md) | Dispatcher владеет control plane; payload идёт напрямую; основной поток — asyncio loop | Loop вызывает typed input-методы, а Dispatcher получает только control events/results | Payload попал в Dispatcher или callback ждёт AI |
| [`technical-specification.md`](../technical-specification.md) | PCMU/profile берутся из SDP/PJMEDIA; проверяются cancellation, barge-in и protocol events; `report.md` — единственный обязательный результат | Live path использует negotiated profile и финализирует report ровно один раз | Hard-coded media profile, потерянное событие или отсутствующий report |
| [`development-guidelines.md`](../development-guidelines.md) | Typed-first, consumer input method, bounded thread-safe queue между потоками, узкий slice и binary closeout | Для каждого ребра фиксируются точный метод, поток исполнения и тест | Неопределённый input method или частичный closeout |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Фактические output/consumer contracts и corrective evidence должны быть в plan/report; архитектурный gap нельзя обходить молча | Этот successor plan сначала проходит owner review, затем реализуется в указанном write-set | Новый API/ownership без review |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Принятые A–H contracts и direct data-plane edges; cycles имеют cancellation/close/stale policy | I.1 реализует вызовы существующих consumer methods и возвращает edge evidence в Map-I | Ребро не совпадает с актуальной revision |
| [`plan-002-I.0-call-session-orchestration-and-state.md`](plan-002-I.0-call-session-orchestration-and-state.md) | Dispatcher, CallSession и DialogueFSM различны; CallSession владеет per-call lifecycle | CallSession/ApplicationRuntime собирают объекты, но не дублируют FSM/Dispatcher | Второй FSM/Dispatcher или semantic decision в loop |

## 4. Граница задачи

**Входит:**

- запуск одного основного `asyncio` event loop в application runtime;
- выполнение Dispatcher и control event bus как задач основного loop;
- связь SIP adapter events с Dispatcher через существующую control boundary;
- связь команд FSM с существующими методами SIP adapter;
- вызов существующих typed input-методов для ingress, speech, conversation, TTS buffer и SIP egress;
- bounded thread-safe queues там, где producer и consumer находятся в разных потоках;
- lifecycle/cancel/close/stale propagation для всех подключаемых каналов;
- per-turn transcript lifecycle для повторных пользовательских ходов;
- deterministic edge tests, target runtime tests и один live SIP/RTP full-flow gate;
- pre-call readiness gate с последовательным прогревом RAG/embeddings, LLM chat, ASR и TTS до запуска/допуска peer;
- обновление Map-I, J4 evidence, blocker register, registry и backlog после фактического результата.

**Не входит:**

- новый Dispatcher, DialogueFSM, Event Bus, ContextStore или LLM Facade;
- новый универсальный audio/text bus;
- новый semantic decision-maker или новый orchestration-owner бизнес-логики;
- замена существующих A–H contracts без фактического mismatch и отдельного corrective pass;
- изменение PJSUA2/PJMEDIA patch baseline, модели, RAG policy или TTS/ASR-кандидата;
- поддержка нескольких звонков, запись аудио, production hardening и real PBX/operator integration.

**Protected baseline:** один вызов, PCMU, per-call `NegotiatedMediaProfile`, direct data plane, control-only Dispatcher,
локальный Ollama HTTP process boundary, существующие A–H owners, обязательный `report.md`.

## 5. Source-map и write-set

| Область | Текущее состояние | Действие | Допустимый write-set |
|---|---|---|---|
| Application runtime | `ApplicationRuntime` запускает runtime и создаёт `CallComposition`, но не обслуживает живые data edges | Добавить основной asyncio loop, задачи/bridges исполнения и последовательный `WarmupReport` до call admission | `src/sip_bot/runtime.py`, `src/sip_bot/runtime_composition.py` |
| SIP control | `SipMediaAdapter` имеет `dispatch_events`, `event_sink`, `answer`, `hangup`, `transfer`, но live binding не собран | Подключить существующие методы к Dispatcher/FSM без ожидания AI | `src/sip_bot/runtime*.py`, минимальные binding hooks в `src/sip_bot/sip_media/` при необходимости |
| Media ingress | `next_ingress_frame()` возвращает `PcmFrame`, но runtime не вызывает его в живом сценарии | Вызвать его из runtime task/thread bridge и передать frame в `PcmFanOut.publish` | `src/sip_bot/runtime*.py`, `tests/integration/` |
| Speech ingress | `PcmFanOut`, `AsrChunker`, `SpeechIngress`, `StreamingAsrAdapter` существуют; per-turn live driving отсутствует | Соединить их существующими input methods; обеспечить новый assembler scope на каждый turn | `src/sip_bot/runtime*.py`, при фактической необходимости ограниченная corrective правка `src/sip_bot/speech/` |
| Conversation | `ConversationPipeline.submit_final_turn` принимает authoritative payload | Передавать результат живого speech path, не synthetic fixture | `src/sip_bot/runtime*.py`, `tests/integration/` |
| TTS/playback | `TtsOutputBuffer.push`, `MediaPacer`, `PlaybackChannel.pump` и SIP egress существуют; runtime egress не собран | Подать TTS chunks в buffer и вызвать playback pump в pacing task | `src/sip_bot/runtime*.py`, `tests/integration/` |
| Evidence | J4 lanes раздельны | Сохранить edge trace и live full-flow evidence | `artifacts/implementation/.../002-I.1/`, J4 root |

Не менять молча `requirements.md`, ADR, исполненные `001-*`, закрытые component contracts A–H или их evidence. Если
фактический input method не позволяет выполнить обязательное ребро, сохранить raw evidence и остановиться по APG gap,
а не вводить обходной adapter/fallback.

## 6. Реестр фактических input boundaries

Это execution order, а не новый список компонентов.

| Ребро | Producer output | Typed input method consumer | Контекст вызова |
|---|---|---|---|
| `N2→N3` | `PcmFrame` | `PcmFanOut.publish(frame)` | main-loop task после чтения SIP ingress |
| `N3→N5` | `PcmFrame` | VAD через существующий `SpeechIngress.process_frame(frame)` | speech consumer task; VAD не ждёт ASR |
| `N3→N4` | `PcmFrame` | `AsrChunker.push(frame)` | speech/ASR task или bounded worker queue |
| `N4→N7` | `AsrAudioChunk` | `StreamingAsrAdapter.stream(operation, chunks)` | ASR worker; cancellation закрывает iterator/operation |
| `N7→N8` | `AsrHypothesis` | `SpeechIngress.accept_hypothesis(hypothesis)` | ASR result callback/worker bridge |
| `N8→N10a/N9` | `FinalUserTurn` | `ConversationPipeline.submit_final_turn(turn)` и прямой typed FSM input | speech completion path; Dispatcher получает только control observation |
| `N13→N14` | `TtsPcmChunk` | `TtsOutputBuffer.push(chunk)` | TTS worker → output boundary queue/call |
| `N14→N15` | ready `PcmFrame` | `PlaybackChannel.pump()` | playback task по media clock |
| `N15→N2` | paced `PcmFrame` | `SipMediaAdapter.enqueue_egress_frame(frame)` | `PlaybackChannel.send_frame` callback |
| `N1→N9` | `NormalizedSipEvent` | existing Dispatcher/control event input | main-loop control task; local SIP replies remain in adapter |
| `N9→N1` | validated `DialogueCommand` | `SipMediaAdapter.answer/hangup/transfer/...` | command observer/binding; no direct LLM call |

Если фактические signatures отличаются, сначала обновляется этот plan и Map-I checkpoint конкретной ревизией. Название
нового класса не является исправлением несовпадения контрактов.

## 7. Execution slices

| Slice | Действие | Acceptance | Stop condition |
|---|---|---|---|
| I1-1 | Зафиксировать asyncio/thread boundary и exact input methods | Таблица §6 совпадает с фактическими signatures; `asyncio.Queue` не используется между потоками | Неясен владелец lifecycle или тип метода |
| I1-2 | Собрать control binding в основном loop | SIP events доходят до Dispatcher; команды FSM вызывают SIP adapter; local protocol replies не ждут loop/AI | Команда обходит FSM или callback блокируется |
| I1-3 | Собрать media ingress | Negotiated `PcmFrame` из SIP adapter реально доходит до `PcmFanOut.publish` | Нужен новый media contract или frame теряется |
| I1-4 | Собрать speech input на существующих методах | Один или несколько turns проходят `PcmFrame → VAD/endpointing + ASR → FinalUserTurn`; каждый turn имеет свой assembler scope | Final turn не получается, stale hypothesis принимается |
| I1-5 | Подключить direct conversation path | Живой `FinalUserTurn` запускает existing RAG/prompt/LLM path; Dispatcher получает только compact decision/status | Payload попал в bus или LLM получил SIP API |
| I1-6 | Собрать TTS/playback egress | `TtsPcmChunk → TtsOutputBuffer → MediaPacer → PlaybackChannel → SipMediaAdapter` проходит deterministic edge test | Raw chunk попал в RTP или pacing/cancel не определены |
| I1-7 | Проверить cycles и failures | BYE, CANCEL, OPTIONS, re-INVITE/UPDATE, hold/resume, RTP/media failure, barge-in, close, stale и transfer не блокируют loop | Потеря terminal/cancel event или stale action |
| I1-8 | Выполнить target/live gate и синхронизацию | До peer/call admission проходит `WarmupReport`; базовый fresh SIP/RTP вызов проходит full path и создаёт report; Map-I/J получают evidence | Любое обязательное base-path acceptance или warmup stage не доказано |

I1-1–I1-2 и подготовка deterministic tests могут выполняться параллельно с disjoint write-set. I1-3–I1-8 являются
последовательной propagation-цепочкой; каждый следующий slice использует фактический output предыдущего. Heavy ASR,
LLM и TTS probes, а также live SIP/RTP gate выполняет главный executor.

## 8. Модель потоков

```text
main thread
└── asyncio event loop
    ├── Dispatcher/control bus task
    ├── SIP control/poll task
    ├── media ingress task
    ├── lifecycle/timer tasks
    └── bridges to worker threads

ASR worker thread  ← bounded thread-safe queue →  main asyncio loop
TTS worker thread  ← bounded thread-safe queue →  playback task
Ollama process     ← typed LlmFacade HTTP IPC  →  LLM worker/pipeline
```

Worker threads не вызывают напрямую asyncio objects. Для native PJSUA2/PJMEDIA callbacks применяется тот же
thread-safe bridge. Queue является частью конкретной receiving boundary; отдельный универсальный bus для payload не
создаётся.

Основной loop не ждёт завершения inference. `BYE`, `CANCEL`, media failure и другие обязательные control events имеют
короткий путь к локальной SIP reaction и Dispatcher; закрытие соответствующих queues/operations отбрасывает stale
результаты.

## 9. Test/evidence plan

- contract test на каждый exact input method из §6;
- deterministic full path с реальными producer/consumer methods и fake ASR/LLM/TTS providers;
- test, что готовый `FinalUserTurn` не подсовывается в место, где должен работать speech path;
- test двух последовательных user turns с отдельными assembler scopes;
- test межпоточного bounded queue и запрет использования `asyncio.Queue` из worker thread;
- test `TtsOutputBuffer.push` и `PlaybackChannel.pump` до `enqueue_egress_frame`;
- protocol events во время inference: `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume и media failure;
- barge-in с отменой старого TTS/playback и подавлением stale frames;
- transfer с FSM validation и typed SIP result;
- target no-GIL/import/concurrency evidence в согласованном runtime;
- pre-call warmup evidence: RAG index/embedding, structured LLM chat, ASR 8→16 kHz operation, TTS first PCM chunk;
- один clean-start live Baresip call с PCMU, RAG/source IDs, follow-up, barge-in, transfer/unknown-answer и `report.md`.

Evidence должно содержать фактические output/input types, method names, thread/loop context, queue capacities,
sequence/generation, close/cancel reason, commands, exit codes и runtime metadata. Unit-only или synthetic composition
evidence не закрывает I1-8.

## 10. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-I1-001` | весь plan | Owner review этого successor plan не пройден | Любая реализация и J4 resume | project owner | Этот plan, Map-I revision | `resolved: owner review accepted 2026-09-03` |
| `B-002-I1-002` | I1-1–I1-6 | Фактический output не принимается указанным input method consumer | Затронутое ребро и downstream propagation | project owner + affected component owner | Targeted contract test и raw output | `none until triggered` |
| `B-002-I1-003` | I1-2/I1-7 | Основной loop или SIP callback ждёт AI либо теряет protocol event | SIP safety и full live flow | project owner + SIP owner | Protocol-during-inference tests | `none until triggered` |
| `B-002-I1-004` | I1-4 | Нельзя безопасно создать новый transcript scope для следующего turn | Multi-turn full flow | project owner + speech owner | Two-turn target/deterministic test | `none until triggered` |
| `B-002-I1-005` | I1-8 | Live SIP/RTP flow не проходит через ASR→LLM→TTS→SIP | J4, J5 и Map-002 closeout | project owner | Fresh live evidence and report | `resolved: base path live-gate-20260903-r4; corrective full matrix j4-full-live-20260904-r20` |

Зарегистрированный `B-002-I-006`/`B-002-J-006` закрыт для первоначального runtime-wiring gap после выполнения
I1-8 и проверки evidence главным executor: это подтверждено `live-gate-20260903-r4`. Полный набор обязательных
сценариев закрыт `002-J/j4-full-live-20260904-r20`; J4 и последующий J5 closeout приняты.

## 11. Closeout и handoff

Этот plan может получить только `complete` либо `blocked`. Для `complete` требуются:

- фактические input methods и loop/thread boundaries зафиксированы в evidence;
- direct data path проходит без Dispatcher payload hop;
- asyncio main loop, control events и cancellation работают на target runtime;
- один live SIP/RTP вызов проходит полный speech/AI/playback path;
- protocol interruption, barge-in, stale suppression, transfer и report проверены;
- Map-I получила propagation revision с фактическими edges и cycles;
- `B-002-I-006` и `B-002-J-006` переведены в `resolved` только после evidence;
- document registry, task backlog, J4 closeout и parent map синхронизированы.

Если проходит только deterministic wiring, но live path не доказан, plan не получает `complete`: результат фиксируется
как промежуточный evidence, а blocker остаётся открытым. В текущем closeout live path и обязательная scenario matrix
доказаны.

## 12. Execution checkpoint `2026-09-03`

Owner review принят. Реализованы и проверены slices I1-1–I1-6 в deterministic
контуре, а также terminal-event safety slice I1-7:

- добавлен procedural `CallRuntimeWiring` без нового semantic/delivery owner;
- exact input methods §6 материализованы в основном asyncio loop;
- межпоточный ASR bridge использует bounded `queue.Queue`, не `asyncio.Queue`;
- delayed ASR hypothesis после hard endpoint корректно завершает pending turn;
- deterministic runtime test соединяет существующие RAG/LLM/TTS owners и
  прямой paced SIP egress;
- target no-GIL import/runtime test и ранее принятые SIP/media tests проходят;
- выполнен реальный offline ASR/RAG/Ollama/XTTS composition probe после
  прогрева Qwen3.5-9B; его report и TTS WAV сохранены в
  [`002-I.1 evidence`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.1/README.md).
- После сообщения о конкурирующей GPU-нагрузке этот реальный composition probe
  повторён: `status=pass`, `pipeline_errors=[]`,
  `elapsed_from_media_start_ms=72563.658`; повторный JSON, report и TTS WAV
  сохранены в том же evidence root в каталоге `real-ai-retry/`.
- После наблюдения холодного старта добавлен обязательный runtime `warmup`: stages выполняются последовательно до
  запуска peer, а результат сохраняется в live-gate JSON. Проверены реальные RAG embeddings, structured Ollama chat,
  faster-whisper ASR с входом 8 kHz и модельным входом 16 kHz, а также первый XTTS PCM chunk.
- Исправлена boundary-ошибка ASR: backend теперь ресемплирует negotiated mono PCM 8 kHz в требуемые faster-whisper
  16 kHz samples и транскрибирует растущий префикс текущего user turn; hard endpoint/reset начинает следующий turn с
  пустого префикса. Это подтверждено unit/target tests и live evidence.
- `live-gate-20260903-r4/live-i1-gate.json`: `status=pass`, warmup `40373.688 ms`, call-start-to-report
  `11432.893 ms`, `peer_established=true`, `rtp_ingress_established=true`, PCMU/8000/mono, `gil_enabled=false`,
  wiring errors `0`, полный ASR-текст `Почему небо днём кажется голубым?`, source-aware RAG и итоговый `report.md`.

Базовый clean-start live SIP/RTP → ASR → RAG/LLM → TTS → RTP путь теперь доказан. Последующая единая J4 matrix
`002-J/j4-full-live-20260904-r20/j4-full-live.json` также завершилась `pass`: follow-up, barge-in, unknown-answer,
transfer и report присутствуют в одном вызове. `B-002-I-006`, `B-002-J-006`, `B-002-I-007`, `B-002-J-004` и
`B-002-MAP-006` закрыты соответствующим evidence.

## 13. Final execution checkpoint `2026-09-04`

Главный executor принял full live gate r20 после серии диагностических clean-start прогонов. Acceptance: `6/6 true`,
`errors=[]`; SIP/RTP peer established, PCMU/8000/mono подтверждён negotiated profile, target CPython `3.14.7t`
запущен с `gil_enabled=false`. До call admission выполнен последовательный warmup RAG/index, structured LLM, ASR,
XTTS и первого TTS PCM chunk.

В r20 подтверждены: два связанных вопроса с контекстом, `barge_in` и cancellation старого playback, source-aware
RAG answer, unknown-answer с предложением оператора, `Да.` → FSM `user_confirmed` → SIP transfer `100/200`, и ровно
один текстовый `report.md`. Межпоточная граница осталась bounded `queue.Queue`, payload не проходил через Dispatcher.

В ходе corrective passes исправлены только фактически обнаруженные boundary defects: speech-only ASR input и typed
hard-end commit marker, допустимая русская `ё/е`-ревизия, удержание confirmation state до final turn и generation
limit structured response `96→192` после доказанного обрезания JSON. Эти изменения покрыты targeted tests и сохранены
в evidence; новые semantic/delivery owners и скрытые fallback не вводились.

Статус исполнения plan: `complete`. Следующий переход разрешён в J5/Map-002 closeout; самостоятельных blocker-ов
у I.1 не осталось.

После красного r19 выполнен дополнительный corrective pass: `TranscriptAssembler` больше не фиксирует общий префикс
двух последовательных partial ASR-гипотез без явного backend-поля `stable_prefix`. Targeted speech tests, target full
regression и live gate r20 прошли; r19 сохранён как diagnostic evidence.
