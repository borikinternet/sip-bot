# Plan-002-I.0: call-session orchestration и композиция существующих owners

Уровень: `child plan` под `Map-002-I` и Map-002
Статус owner review: `accepted` — owner clarification и composition scope приняты `2026-09-03`
Статус исполнения: `complete` — execution, corrective pass и composition evidence закрыты `2026-09-03`
Родительская карта: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)
Родительская supermap: [`roadmap.md`](../roadmap.md)

## 1. Цель и проверяемый результат

Устранить архитектурный gap между существующими компонентами карты 4 и
сквозным call lifecycle, не смешивая концептуально разные классы и не вводя
новый process boundary.

Результат I.0:

- один `Dispatcher` остаётся центральным владельцем последовательной обработки
  control plane и содержит не более одного активного `CallSession`;
- `Dispatcher`, `CallSession` и `DialogueFSM` являются разными классами и
  объектами даже если для MVP будут размещены в одном Python-модуле;
- `CallSession` является per-call composition/ownership object: связывает
  `call_id`, FSM, scoped channels, component handles, cancellation generations,
  context/report lifecycle и SIP/media session;
- `DialogueFSM` сохраняет владение семантическим состоянием диалога и
  разрешёнными действиями, а `RuntimeCoordinator` — низкоуровневым runtime и
  channel lifecycle, если это подтверждено реализацией;
- состояние живого диалога и внутренний контекст не выдаются за один и тот же
  объект: live FSM state принадлежит FSM, а контекст и необязательный журнал —
  `ContextStore`; единственный обязательный итоговый артефакт — `report.md`;
- появляется deterministic application composition одного звонка вокруг
  существующих owners, достаточная как lifecycle/control baseline для
  successor runtime wiring, но не являющаяся доказательством live
  SIP→AI→SIP path;
- подтверждённая способность PJSUA2/PJMEDIA обслуживать несколько звонков
  сохраняется как future-compatible baseline, но multi-call execution не
  добавляется в MVP.

## 2. Граница задачи

### Входит

- typed object model `Dispatcher → active CallSession → component owners`;
- один active-call slot с явным reject/close/re-entry поведением;
- композиция уже принятых A–H contracts и каналов в один call lifecycle;
- использование существующего контекстного владельца и финализация обязательного
  `report.md` после authoritative turn/decision/terminal outcome;
- cancellation и stale-result propagation при remote protocol event, media
  failure, barge-in, transfer и terminal close;
- deterministic contract/integration tests и target no-GIL import/runtime checks;
- Map-I propagation revision и handoff обратно в `002-J/J4`.

### Не входит

- поддержка нескольких одновременных разговоров в application logic;
- изменение PJSUA2/PJMEDIA patch baseline или создание отдельного conference
  bridge на звонок;
- новая event bus, payload routing через Dispatcher или второй LLM IPC;
- изменение Dialogue FSM semantics, SIP protocol reaction или RAG policy без
  отдельного gap;
- production HA, restart/recovery и масштабирование общей GPU-нагрузки;
- запуск J4 full demo matrix до закрытия собственного acceptance I.0.

### Protected baseline

- один process-local Dispatcher и один разговор в рамках MVP;
- Dispatcher передаёт только control events/commands; PCM, streams и крупные
  текстовые payload идут по direct data plane;
- SIP adapter отвечает на обязательные SIP/media события локально и не ждёт
  Dispatcher, ASR, LLM, TTS или отчёт;
- FSM исполняет только validated structured decisions;
- закрытие call/channel делает результаты старого поколения безвредными;
- C3 остаётся внешним Ollama process через HTTP IPC;
- PJSUA2/PJMEDIA остаются принятым patched baseline.

## 3. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на I.0 | Проверка/stop condition |
|---|---|---|---|
| [`architecture.md`](../architecture.md) | Control plane принадлежит Dispatcher; payload не транзитирует Dispatcher | Composition связывает control handles, а data channels остаются прямыми | Architecture audit; payload через Dispatcher — blocker |
| [`technical-specification.md`](../technical-specification.md) | `report.md` — единственный обязательный итоговый артефакт; `conversation.jsonl` допустим как внутренний журнал | Нужно проверить lifecycle контекста и однократную финализацию отчёта | Report/context lifecycle tests; отсутствие обязательного отчёта — blocker |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Новые узлы, рёбра и ownership сначала фиксируются в карте; typed boundary передаётся итерационно | I.0 обновляет topology и contract revision до J4 | Map-I propagation checkpoint обязателен |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM предлагает, FSM проверяет и исполняет | CallSession не даёт AI прямого SIP access | Negative action-bypass tests |
| [`development-guidelines.md`](../development-guidelines.md) | Узкий slice, disjoint write-set, corrective pass, binary closeout, no silent simplification | I.0 не расширяет J молча; красные тесты исправляются до blocker | Targeted/regression/contract evidence; partial closeout запрещён |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Архитектурный/API gap выносится в отдельный plan после owner review | I.0 является explicit successor для B-002-J-005 | Owner review, blocker register и closeout |

## 4. Owner review

| Вопрос | Решение/рекомендация | Последствие | Статус |
|---|---|---|---|
| Допустим ли один Dispatcher и один активный разговор? | Да; это scope MVP и не ограничивает объектную модель | Dispatcher имеет один `active_session`, но не смешивает классы | `resolved: owner decision 2026-09-03` |
| Должны ли Dispatcher и CallSession быть разными классами/объектами? | Да; концептуально это разные сущности. Для MVP допускается один файл | Не создавать отдельный процесс/loop только ради разделения классов | `resolved: owner decision 2026-09-03` |
| Где разместить классы? | Рекомендация: первоначально co-locate в одном модуле, сохранив отдельные классы; точный модуль — implementation detail I.0 | Не вводить новый внешний boundary из-за размещения в файле | `resolved in principle; implementation check` |
| Может ли PJSUA2/PJMEDIA вести несколько звонков? | Да; PJSUA2 поддерживает несколько `Call`, local target default `maxCalls=4`; общий primary conference bridge | Multi-call остаётся за пределами MVP; I.0 сохраняет `call_id`-scoped mapping | `resolved by preflight evidence` |
| Кто владеет live dialogue state? | `DialogueFSM` владеет semantic state/transitions; `CallSession` владеет per-call composition и lifecycle references; Dispatcher владеет active-session slot и ordering | Не дублировать FSM state в ContextStore и не превращать Dispatcher в FSM | `resolved in principle; implementation acceptance` |
| Кто владеет `conversation.jsonl`? | `ContextStore`; append-only authoritative text history | Report читает snapshot/diagnostics, но не становится владельцем журнала | `resolved by current implementation` |
| Нужен ли обязательный `state.json`? | Нет; такого входного требования нет. `DialogueFSM` владеет live semantic state, `ContextStore` — контекстом и, при необходимости, внутренним `conversation.jsonl`; обязательным результатом является `report.md` | I.0 не добавляет schema/restore для `state.json`; проверяет bounded context lifecycle и финализацию отчёта | `resolved: owner clarification 2026-09-03` |
| Нужен ли multi-call execution сейчас? | Нет; библиотечная capacity проверяется, но MVP остаётся single-call | Не расширять tests/demo до нескольких вызовов | `resolved: scope boundary` |

## 5. Текущее состояние и source-map

| Область | Файл/объект | Сейчас | Целевое состояние I.0 | Допустимый write-set |
|---|---|---|---|---|
| Dispatcher | `src/sip_bot/control/dispatcher.py` | Очередь и подписка на bus, ссылка на `fsm`; нет application composition | `Dispatcher` создаёт/закрывает один `CallSession`, маршрутизирует control без payload | `src/sip_bot/control/dispatcher.py` |
| CallSession | `src/sip_bot/control/dispatcher.py` или согласованный соседний модуль | Отсутствует как отдельный класс | Typed per-call aggregate с lifecycle, generation и component references | `src/sip_bot/control/dispatcher.py` или один явно выбранный модуль |
| Dialogue FSM | `src/sip_bot/dialogue/fsm.py` | Владельцем live semantic state фактически является FSM | Сохраняет transitions/validation; получает session-scoped handles, не теряет cancellation semantics | Только корректирующие изменения, если нужны для typed composition |
| Runtime lifecycle | `src/sip_bot/runtime.py`, `src/sip_bot/control/lifecycle.py` | RuntimeCoordinator владеет `CallScope` и channel handles; ApplicationRuntime — bootstrap | Не дублировать resource lifecycle в CallSession; определить delegation boundary | Только если acceptance обнаружит реальный ownership mismatch |
| SIP/media | `src/sip_bot/sip_media/adapter.py` | Application adapter хранит один `_CallContext`; local protocol reactions работают | Подключён к session через `call_id`; multi-call mapping не реализуется | Только composition adapter hooks, без смены SIP baseline |
| Context history | `src/sip_bot/context/store.py` | In-memory turns + optional append-only `conversation.jsonl` | ContextStore предоставляет bounded context; журнал остаётся необязательным внутренним артефактом | `src/sip_bot/context/store.py` |
| Report | `src/sip_bot/report/builder.py` | Deterministic builder/finalizer для J1–J3 | Читает согласованные context/session snapshots после terminal outcome | Не менять report semantics без необходимости |
| Data channels | `src/sip_bot/media/`, `src/sip_bot/speech/`, `src/sip_bot/tts/`, `src/sip_bot/playback/` | Component boundaries приняты A–H | Session открывает/закрывает их через typed control, payload идёт direct | Только composition wiring/tests, не менять закрытые component contracts |
| Tests/evidence | `tests/`, `artifacts/.../002-I.0/` | J1–J3 deterministic evidence; live SIP-driven wiring отсутствует | Contract, lifecycle, clean-start composition preflight и target evidence | `tests/unit`, `tests/contract`, `tests/integration`, I.0 evidence root |

## 6. Объектная модель и ответственность

### 6.1. Existing Dispatcher

В коде уже существует `Dispatcher` — один process-local объект, который владеет порядком control-plane
обработки, подпиской на bus и ссылкой на единственный активный `CallSession`.
Он не становится вторым FSM и не принимает на себя payload.

I.0 не создаёт второй Dispatcher и не переписывает существующий Dispatcher с
нуля. План добавляет к нему только отсутствующую application composition
функциональность и проверяет, что существующий control contract сохраняется.

При `CALL_OPEN` Dispatcher создаёт session либо принимает уже созданную session
через typed boundary. При terminal/close Dispatcher сначала инициирует
idempotent close session, затем допускает следующий чистый call scope. Пока
старый scope не закрыт, повторное использование его `call_id` или generation
запрещено.

### 6.2. CallSession

`CallSession` — отдельный объект per-call composition. Он не заменяет
`DialogueFSM` и не принимает semantic decisions. Его ответственность:

- хранить `call_id` и scoped references на SIP/media, speech, context, LLM, TTS,
  transfer и report owners;
- открывать/закрывать direct data channels по командам Dispatcher/FSM;
- хранить session-level cancellation/generation handles;
- направлять asynchronous results к правильному consumer и отбрасывать stale
  result после close;
- выдавать checkpoint hooks для context/report persistence;
- агрегировать terminal outcome, не скрывая исходное protocol/application event.

`CallSession` не должен вызывать тяжёлое inference синхронно из Dispatcher или
SIP callback и не должен превращать text/audio payload в bus event.

### 6.3. Existing DialogueFSM

В коде уже существует `DialogueFSM`. FSM остаётся владельцем semantic `DialogueState`, transition guards,
`operation_id`, разрешённых `DialogueCommand` и решения о `answer`/`clarify`/
`offer_transfer`/`transfer`/`hangup`. Его объект может находиться в том же
модуле, что и Dispatcher/CallSession, но ownership не объединяется.

### 6.4. Ответственности, которые нельзя смешивать

| Состояние/артефакт | Владелец | Назначение |
|---|---|---|
| Live dialogue state | `DialogueFSM` | Текущее semantic state, transition trace, operation/generation guards |
| `conversation.jsonl` | `ContextStore` | Append-only текстовая история authoritative turns, retrieval diagnostics и решений |
| `report.md` | `ReportBuilder`/finalizer | Единственный обязательный внешний артефакт после завершения звонка |

`CallSession` связывает эти владельцы и инициирует lifecycle hooks, но не
становится скрытым владельцем их данных. `conversation.jsonl` остаётся
необязательным внутренним журналом; отдельный обязательный `state.json` не
вводится.

## 7. Interaction topology и propagation

I.0 уточняет Map-I после owner decision и не создаёт скрытых рёбер.
Предварительно добавляется логический узел `N9a CallSession` внутри процесса:

```text
SIP/media + component control events
                │
                ▼
        N9 Main Dispatcher  ⇄  N9a CallSession
                │                    │
                │                    ├─ direct data channels → speech/context/LLM/TTS/playback
                │                    ├─ lifecycle → RuntimeCoordinator/CallScope
                │                    └─ checkpoint → ContextStore/report
                ▼
        N9 Dialogue FSM
```

Это логический boundary классов и ownership, а не новый process, event bus или
payload hop. После реализации I.0 в Map-I должны быть зафиксированы:

- typed `CallSession` creation/close/terminal commands;
- session-scoped `call_id`, channel generation и cancellation identity;
- направление `Dispatcher ⇄ CallSession ⇄ component owner` для control plane;
- прямые data-plane edges, которые session только открывает/закрывает;
- checkpoint edge `CallSession → ContextStore` и report read edge после terminal;
- re-entry/remote protocol event во время LLM/TTS/transfer;
- propagation revision и corrective pass, если фактические типы отличаются от
  этого candidate description.

## 8. Implementation slices

| Slice | Цель | Исполнитель | Acceptance | Stop condition |
|---|---|---|---|---|
| `I0-1` | Зафиксировать object model и typed session contract | Main executor; deterministic preparation допускается субагенту | Contract tests различают существующие Dispatcher, новый CallSession и существующую FSM; один active-session slot | Нужен новый неутверждённый boundary |
| `I0-2` | Реализовать session composition/lifecycle вокруг A–H owners | Main executor; disjoint code preparation допускается субагенту | Open/answer/close/terminal/re-entry, channel generations и stale suppression проходят tests | Компонентный API не позволяет безопасно собрать lifecycle без изменения protected baseline |
| `I0-3` | Закрыть context/report lifecycle | Main executor | Контекст доступен для follow-up, внутренний журнал при включении не ломает lifecycle, а `report.md` финализируется ровно один раз после terminal outcome | Обязательный report edge не имеет typed owner или не проходит acceptance |
| `I0-4` | Подключить deterministic full composition до J4 boundary | Main executor | One clean-start session связывает SIP event, FSM, speech/text, RAG/LLM/TTS controls, transfer/report hooks | Обязательный edge не имеет typed owner или падает acceptance |
| `I0-5` | Выпустить Map-I propagation и handoff | Main executor | Map-I revision updated, blocker register/evidence/registry/backlog synchronized | Фактический output расходится с candidate contract и corrective pass не закрывает gap |

Независимая подготовка fixtures, contract tests и статический анализ может идти
параллельно при disjoint write-set. Запуск native inference, live SIP/RTP и
финальная интеграционная проверка выполняются главным executor.

## 9. Process invariant audit

| Правило | Применимость | Материализация в I.0 |
|---|---|---|
| Узкий проверяемый slice | Применимо | I.0 ограничен composition gap; multi-call и production hardening исключены |
| Typed-first и single owner | Применимо | Dispatcher/CallSession/FSM/ContextStore имеют разные роли и typed boundaries |
| Disjoint delegation | Применимо | Субагенту могут быть переданы только отдельные tests/fixtures/evidence; protected docs и Map-I меняет main |
| Lock retry | Применимо к dependency preparation | Package-manager lock не является немедленным blocker; повторять после случайной задержки |
| Main owns heavy GPU/live final evidence | Применимо | I.0 subagent не запускает heavy inference; main принимает final runtime evidence |
| Красный результат → corrective pass | Применимо | Ошибка реализации/fixture исправляется в write-set; category-4 gap регистрируется отдельно |
| Упрощения запрещены | Применимо | Не вводить fake-only обход для объявления composition complete; FakeOperator остаётся только J1–J3 seam |
| Child plan closeout binary | Применимо | I.0 закрывается только `complete` или `blocked`, не partial/foundation |

## 10. Architecture invariant audit

- PJSUA2/PJMEDIA callback не ждёт application composition; local protocol
  reaction выполняется независимо от session orchestration.
- Один primary PJMEDIA bridge допускается и не заменяется отдельными bridge-ами
  для каждого call; future call mapping строится по `call_id`.
- Dispatcher не переносит `PcmFrame`, `AsrAudioChunk`, `FinalUserTurn`,
  `AnswerTextChunk` или RAG fragments.
- `FinalUserTurn` остаётся authoritative data-plane payload; FSM получает
  необходимый typed вход, но Event Bus не становится текстовым транспортом.
- LLM Facade остаётся единственным владельцем Ollama HTTP IPC; CallSession
  обращается к фасаду через typed interface.
- Только FSM валидирует structured decision перед transfer/hangup/answer
  command; CallSession не принимает semantic action по свободному тексту.
- `ContextStore` не владеет live FSM transitions; он получает checkpoint и
  сохраняет текстовые/context artifacts.
- Close/terminal invalidates all session channel generations; stale results are
  dropped and cannot reach a new session.

## 11. Test plan и evidence

### Unit/contract

- object identity/ownership: отдельные Dispatcher, CallSession и DialogueFSM;
- один active session, duplicate call, terminal/re-entry и idempotent close;
- session-scoped channel generation, cancellation и stale result suppression;
- control-only Event Bus и negative test на payload bypass;
- bounded context lifecycle, optional `conversation.jsonl` journal и
  однократная финализация обязательного `report.md`; аудио не сохраняется;
- FSM action validation и отсутствие прямого SIP action из CallSession/LLM text.

### Integration/target

- approved local `001-S` stand, PCMU and protocol callbacks;
- target `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`, CPython 3.14.7t,
  `Py_GIL_DISABLED=1`, `sys._is_gil_enabled() is False` before/after imports;
- live component composition without waiting in SIP callback;
- J4 handoff preflight: source-aware RAG answer, follow-up/context, barge-in,
  unknown-answer/offer-transfer, explicit transfer, report and clean close;
- command ledger with stdout/stderr, exit codes, runtime/model metadata and
  evidence IDs.

### PJSUA2 capacity boundary

The already executed no-GIL local preflight is recorded in
[`pjsua-capacity-probe.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/pjsua-capacity-probe.md).
It proves library configuration capability, not multi-call application
execution. I.0 acceptance must not claim multi-call support from that probe.

## 12. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-I0-002` | I0-2 | Фактическое component API не позволяет собрать session без protected-baseline change | I0 composition | project owner + affected owner | targeted contract evidence + APG gap | `none until triggered` |
| `B-002-I0-003` | I0-4 | Обязательный end-to-end edge не имеет typed producer/consumer/lifecycle | J4 and Map-002 closeout | project owner | Map-I propagation revision | `none until triggered` |

Ошибки текущей реализации или fixture сначала получают raw output и
corrective pass. Они не становятся owner blocker до проверки категории
результата. Capability PJSUA2 multi-call не является blocker для single-call MVP.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| `none` | — | — | — | `none` |
| Multi-call execution | Не требуется MVP; capacity нужна для архитектурной проверки | Оставлено за scope, без fake claim о поддержке | `TASK-005`/future scale plan | `deferred` |

## 14. Closeout criteria и handoff

I.0 получает `complete` только если:

- обязательный `report.md` формируется ровно один раз после terminal outcome,
  а внутренний context lifecycle не смешивается с live FSM state;
- отдельные Dispatcher/CallSession/DialogueFSM classes/objects проходят
  contract tests;
- deterministic one-call composition реально связывает принятые A–H
  contracts, lifecycle, cancellation, stale policy, transfer и report hooks;
  live invocation SIP/media/speech/playback input methods остаётся отдельным
  successor scope `002-I.1`;
- persistence artifacts различаются и проверены;
- target no-GIL/import, deterministic regression и relevant SIP/RTP checks
  зелёные;
- Map-I получила новую propagation revision с typed edges/cycles/owners;
- J получает handoff и может начать только после закрытия I.0.

Если owner review или обязательный API boundary не закрыты, I.0 фиксируется
`blocked` с конкретным blocker/evidence; `partial`, `foundation` и
`arch-ready` не используются.

## 15. Execution report и closeout

I.0 закрыт статусом `complete` после выполнения полного собственного scope:

- существующие `Dispatcher` и `DialogueFSM` сохранены, добавлен отдельный
  per-call `CallSession`; второй Dispatcher/FSM и новый IPC не создавались;
- deterministic contract/integration path подтвердил active-session slot,
  shared `CallScope`, direct payload handoff, cancellation/stale suppression,
  context lifecycle и однократную финализацию `report.md`;
- реальный составной answer path `RAG → LlmFacade → XTTS → PCM` прошёл на
  локальном Ollama/XTTS и создал сохраняемый WAV-артефакт;
- реальный media/speech path `faster-whisper → VAD/endpointing →
  FinalUserTurn → RAG → LLM → XTTS → fake transfer → report` прошёл на
  patched C2 binding, target free-threaded CPython 3.14.7t и с
  `sys._is_gil_enabled() == False`;
- host regression: `109 passed, 3 skipped` (host-only отсутствие Baresip),
  target regression: `112 passed`, включая live SIP/RTP;
- output-schema corrective pass в LLM boundary и transfer-owner corrective
  pass закрыты без ослабления assertions.

`I.0` имеет статус `complete` только в пределах собственного deterministic
composition scope. Его evidence не утверждает, что live SIP ingress и paced
TTS egress уже подключены к speech/AI owners: это отдельный successor scope
`002-I.1`, поэтому `B-002-I-006`/`B-002-J-006` остаются открытыми.

Evidence: [`implementation-checkpoint.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/implementation-checkpoint.json),
[`real-composition-pass-20260903/real-composition.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/real-composition-pass-20260903/real-composition.json),
[`real-media-composition-pass2-20260903/real-media-composition.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/real-media-composition-pass2-20260903/real-media-composition.json).

I.0 передаёт `002-J` закрытую composition boundary. J4 component/composition
lanes выполнены главным executor, но full live SIP-driven acceptance остановлен
на `B-002-J-006`: отдельный application driver для SIP ingress и paced TTS
egress не материализован. Карта 4 не закрывается до снятия blocker и J5 evidence.
