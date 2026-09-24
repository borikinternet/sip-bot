# Карта 9: опциональная исходящая SIP-регистрация для мастер-класса

Уровень документа: `map`  
Идентификатор: `Map-009`  
Статус: `complete` — owner review принят `2026-09-13`, все child plans и map-level gates исполнены по APG  
Дата подготовки: `2026-09-13`  
Родитель: [`roadmap.md`](../roadmap.md)  
Предшественники: [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md), закрытые карты 4–7  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21

## 1. Цель и проверяемый результат

Добавить в SIP-бот опциональную исходящую SIP-регистрацию на локальном registrar/PBX, чтобы на мастер-классе можно
было показать два режима:

1. **прямой demo/loopback-режим** — регистрация выключена, текущий вызов по прямому SIP URI продолжает работать;
2. **режим зарегистрированного SIP-абонента** — бот выполняет `REGISTER` на локальном FreeSWITCH, поддерживает
   регистрацию в течение работы и принимает входящий вызов, направленный PBX на зарегистрированный endpoint.

Здесь «исходящая регистрация» означает SIP `REGISTER`, а не исходящий пользовательский вызов. Возможность выполнить
исходящий вызов на прямой URI уже существует и этой картой не переопределяется.

Проверяемый результат карты:

- регистрация выключена по умолчанию и не меняет текущий direct-URI путь;
- при явном включении SIP-адаптер формирует account/registrar configuration и проходит digest-auth регистрацию на
  локальном registrar;
- состояние регистрации, expiry, refresh, ошибка регистрации и unregister представлены typed control events;
- обязательные ответы на SIP-транзакции и lifecycle звонка не зависят от Dispatcher, LLM, ASR или TTS;
- после успешной регистрации входящий вызов из локального FreeSWITCH проходит тот же approved SIP/media и AI path;
- workshop runbook позволяет участнику включить или выключить регистрацию без изменения кода;
- отказ регистрации не маскируется молчаливым переходом в direct-URI или другим fallback.

## 2. Почему это карта, а не один plan-file

Работа содержит три самостоятельные acceptance boundaries с разными владельцами и write-set, а после красного C4 —
отдельный corrective child plan:

1. контракт конфигурации и account lifecycle при выключенной/включённой регистрации;
2. фактический SIP `REGISTER`, digest authentication, refresh/unregister и нормализация событий PJSUA2;
3. interop с локальным FreeSWITCH и воспроизводимый сценарий мастер-класса;
4. исправление inbound answer/readiness lifecycle без расширения scope зарегистрированного стенда.

Поэтому карта порождает следующие child plans; corrective plan добавлен после фактического blocker evidence:

- `009-A` — optional registration profile, configuration contract и disabled-path regression;
- `009-B` — PJSUA2 registration lifecycle, status events и target protocol evidence;
- `009-C` — локальный FreeSWITCH registrar/route, входящий вызов и workshop runbook;
- corrective slice `009-C2/R4.1` — включение уже принятого Baresip `sndfile` recording path в registered full-AI
  replay, сохранение raw `enc`/`dec` и stereo artifact.

Зависимость исполнения: `009-A → 009-B → 009-C`; внутри `009-C` promotion C4/C6 зависит от `009-C1`. Подготовка локального FreeSWITCH fixture может идти параллельно
с `009-A` только при disjoint write-set; acceptance регистрации и интеграционный gate остаются последовательными.

## 3. Применимые документы и материализованные правила

| Источник | Точная применимая формулировка | Влияние на Map-009 | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Бот работает через обычный SIP-звонок, поддерживает lifecycle/transfer и один параллельный разговор; PBX не реализуется внутри проекта | Реализуется SIP endpoint capability для локального workshop registrar, но не внутренняя PBX | SIP/FreeSWITCH scenario matrix | Требуется PBX logic, multi-call или production routing |
| [`architecture.md`](../architecture.md) | `SIP adapter` владеет SIP-сигнализацией, SDP, RTP и protocol reaction; Dispatcher владеет semantic state; media/data plane не проходит через Dispatcher | Registration lifecycle остаётся внутри SIP adapter; наружу уходят только компактные control events; PCM/data path не меняется | Ownership/source audit, typed event tests | Требуется отдельный registration manager без самостоятельного lifecycle или PCM через bus |
| [`technical-specification.md`](../technical-specification.md) | Вся конфигурация MVP хранится в `config/constants.py`; production secret store и реальные внешние сервисы не входят в MVP | Registration profile и default-off policy фиксируются там; только локальный FreeSWITCH/test credentials, без production secret infrastructure | Config import/tests, git/secrets audit | Требуется vault, env-based production policy или внешний service integration |
| [`development-guidelines.md`](../development-guidelines.md) | Typed-first, owner behavior, bounded control channels, explicit lifecycle/cancel/close, corrective pass и binary closeout обязательны | `RegistrationProfile`/status event и lifecycle states должны быть явными; красный protocol test исправляется и повторяется | Contract/target tests, raw evidence, closeout | Новый API/boundary gap после corrective pass |
| [`development-guidelines.md`](../development-guidelines.md) | Несовместимые native-компоненты проверяются в target free-threaded runtime; общий config/docs и integration gates изменяет main executor | PJSUA2 no-GIL baseline из `001-C1` используется без переоткрытия; target protocol gate выполняется главным executor | Runtime/import/lifecycle evidence | Новый native incompatibility или protected baseline change |
| [`documentation-process.md`](../documentation-process.md) | Один владелец факта, ссылки вместо дублирования; после Markdown запускается document registry audit | Карта владеет планом работ, техническое ТЗ — правилами config, runbook — командами пользователя, evidence — фактами исполнения | Registry audit and source-map audit | Дублирующий или конфликтующий source of truth |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) rev21 | SIP protocol reaction выполняется немедленно в adapter callback/transaction context; прикладные события нормализуются и передаются наверх | `REGISTER`/401/407/200/timeout/expiry обрабатываются adapter-ом; Dispatcher получает нормализованный статус и не является обязательным ответчиком | Protocol trace and event contract | Протокольный ответ требует ожидания AI/control plane |
| [`plan-001-C1-sip-pjsua2-pjmedia.md`](plan-001-C1-sip-pjsua2-pjmedia.md) | Принят PJSUA2/PJMEDIA baseline с обязательными patch/no-GIL условиями | Не заменять VoIP stack; проверить регистрацию на том же patched target baseline | Target import/operation evidence | Нужен новый SIP framework или новый patch |
| [`plan-001-S-voip-test-stand.md`](plan-001-S-voip-test-stand.md) | Baresip stand использует прямые loopback URI без registrar и подтверждает PCMU/BYE/transfer | Existing direct mode остаётся regression lane; registration interop получает отдельный local FreeSWITCH stand | Existing stand regression plus new registrar evidence | Direct mode перестал проходить без registration |
| [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md) | Приняты `VAD_MODE=2` и `ENDPOINT_HARD_MS=520`; speech boundary не меняется без отдельной карты | Registration map не меняет VAD/endpointing/ASR/TTS contracts | Existing full-flow regression | Попытка решить registration issue через speech path |
| [`user-guide.md`](../user-guide.md) | Current user path — accepted rehearsal runner; отдельного внешнего launcher пока нет | `009-C` расширяет workshop instructions, но не выдаёт registration за production daemon | Runbook/evidence links | Нужен публичный daemon launcher вне scope карты |

## 4. Граница задачи

### Входит

- флаг `SIP_REGISTRATION_ENABLED`, выключенный по умолчанию;
- registrar URI, SIP identity, username, password/credential placeholder и registration expiry как статические
  constants;
- typed registration profile и registration state, не смешанные с media profile и call state;
- создание account с регистрационными параметрами при включённом режиме;
- SIP digest authentication через возможности PJSUA2/PJSIP;
- первичный `REGISTER`, refresh до expiry, обработка отказа/timeout и unregister при штатном shutdown;
- нормализованные control events `registration_started`, `registration_succeeded`, `registration_failed`,
  `registration_expiring`, `registration_refreshed`, `registration_unregistered` с call-independent scope;
- readiness/admission policy для включённого режима;
- regression текущего direct-URI режима при выключенной регистрации;
- локальный FreeSWITCH registrar и dialplan/route, достаточные для workshop;
- входящий зарегистрированный вызов с PCMU и один полный answer/follow-up/report сценарий;
- workshop runbook, evidence, registry/backlog synchronization и closeout.

### Не входит

- реализация PBX, call-center logic или распределение звонков между сотрудниками;
- несколько registrar-ов, outbound proxy failover, SIP forking и multi-account operation;
- TLS/SRTP, production certificate management и внешний secret vault;
- production-grade retry orchestration, HA, service manager, monitoring и multi-call scaling;
- изменение PCMU/RTP framing, VAD, ASR, LLM, RAG, TTS, Dialogue FSM или report semantics;
- автоматический fallback от включённой, но неуспешной регистрации к direct URI;
- подключение к реальному внешнему провайдеру; acceptance выполняется на локальном FreeSWITCH;
- превращение `python -m sip_bot` в production daemon — это отдельная задача launcher-а.

### Protected baseline

- PJSUA2/PJMEDIA и обязательные no-GIL patches из `001-C1`;
- `SipMediaAdapter`, `SipMediaConfig`, `NormalizedSipEvent`, existing call/media lifecycle и per-call negotiated profile;
- direct-URI loopback и Baresip stand из `001-S`;
- один active call и текущие `Dispatcher`/`CallSession`/`DialogueFSM` owners;
- `config/constants.py` как источник статической конфигурации;
- PCMU/8000/mono, RTP/media data plane и approved AI path;
- WebRTC VAD mode 2 и hard endpoint 520 ms;
- правило: protocol reaction не ожидает Dispatcher/AI, а PCM не идёт через Event Bus.

## 5. Текущее состояние и gap

| Область | Текущее состояние | Gap Map-009 |
|---|---|---|
| PJSUA2 account | `SipMediaAdapter.start()` создаёт account с `idUri` | `registrarUri`, credentials и registration lifecycle не задаются |
| Исходящий call | `make_call(peer_uri)` вызывает прямой SIP URI | Не относится к REGISTER и должен остаться рабочим в disabled mode |
| Incoming call | Adapter умеет принять входящий вызов и ответить | Нужен зарегистрированный endpoint и local FreeSWITCH route |
| Config | Статические значения находятся в `config/constants.py` | Нет optional registration profile и явной credential policy |
| Test stand | Baresip loopback без registrar | Нужен local FreeSWITCH registrar/interop lane |
| Control plane | Нормализованные call/media events существуют | Нет typed call-independent registration status contract |
| User operation | Есть demo-runner и artifact runbook | Нет короткой workshop procedure для включения registration |

## 6. Interaction topology и typed boundaries

Регистрация является частью control plane SIP adapter-а. Она не переносит аудио и не создаёт нового пути к Event Bus для
полезной нагрузки.

```text
config/constants.py
        │ RegistrationProfile (default disabled)
        ▼
SIP/media adapter ── SIP REGISTER / 401/407 / 200 / refresh / unregister ──> local FreeSWITCH registrar
        │
        └── RegistrationEvent ──bounded control event──> Main Dispatcher / runtime readiness

Incoming SIP INVITE from FreeSWITCH
        ▼
existing SipMediaAdapter → existing negotiated PCMU/RTP/media boundary → existing AI/dialogue path
```

### 6.1. Boundary table

| Ребро | Output | Consumer input method | Контекст вызова | Checkpoint |
|---|---|---|---|---|
| `constants → SIP adapter` | `RegistrationProfile` | `SipMediaAdapter.configure/start(profile)` или эквивалентный typed constructor input | До создания PJSUA2 account; profile immutable for one runtime | `009-A1` |
| `PJSUA2 account → adapter` | native registration callback/status | adapter-owned registration lifecycle handler | В native SIP callback; обязательная protocol reaction не ждёт Dispatcher | `009-B1` |
| `adapter → runtime/Dispatcher` | `RegistrationEvent` | existing bounded control event sink/queue | Вне native callback; registration status не становится DialogueFSM semantic action автоматически | `009-B2` |
| `runtime readiness → call admission` | `RegistrationReadiness`/typed status | launcher/runtime admission check | До финального `200 OK` входящего call только если registration mode включён и aggregate AI readiness завершена; до этого допускается `180` | `009-B3`/`009-C1` |
| `FreeSWITCH → SIP adapter` | SIP `INVITE` и explicit `180` | существующий incoming-call callback | После `registration_succeeded`; `180` отправляется сразу, media path unchanged до `200` | `009-C1` |
| `readiness gate → SIP adapter` | explicit `200` или `503` | `answer()`/`reject()` вне native callback | `200` только после ready/warmup; failure не делает direct fallback | `009-C1` |
| `registered call → existing pipeline` | `PcmFrame` и существующие control events | существующие consumer input methods | Negotiated profile из SDP/PJMEDIA; без нового registration-specific audio edge | `009-C2` |

Для одного основного `asyncio` loop допустимы прямой вызов или `asyncio.Queue`; для callback/разных потоков сохраняется
bounded thread-safe queue; новый IPC не нужен. Registration event не должен содержать PCM, transcript, RAG fragments или
пароль.

## 7. Audit владельца поведения и парадигмы реализации

- `SipMediaAdapter` владеет account registration lifecycle, потому что именно он владеет PJSUA2 account, SIP callbacks,
  transaction response и shutdown последнего native объекта.
- `RegistrationProfile` является конфигурационным value object; он не владеет retry thread, call state или credentials
  storage lifecycle.
- `RuntimeCoordinator`/будущий launcher владеет admission/readiness policy: включённый registration mode не допускает
  входящий call до успешной регистрации. Это policy исполнения, а не дополнительный SIP protocol owner.
- `Dispatcher` получает status для control-plane наблюдения и orchestration, но не отвечает на `REGISTER` и не управляет
  digest challenge.
- `DialogueFSM` не меняется: registration status не является пользовательским ходом и не должен попадать в LLM prompt.
- Local FreeSWITCH fixture владеет только registrar/PBX test environment; он не становится частью runtime бота.

## 8. Source-map и write-set карты

| Область | Источник/файл | Целевое действие | Владелец | Write-set |
|---|---|---|---|---|
| Config contract | `config/constants.py`, `src/sip_bot/config.py` | Добавить default-off registration constants и typed mapping | `009-A` | Registration symbols only; existing constants unchanged |
| SIP account | `src/sip_bot/sip_media/adapter.py` и при необходимости `protocol_events.py` | Materialize account registration and lifecycle callbacks | `009-B` | Existing SIP adapter registration symbols and typed events |
| Runtime readiness/admission | `src/sip_bot/runtime.py`, `src/sip_bot/runtime_wiring.py` | Runtime-scoped single-flight warmup, explicit background trigger and incoming-call wait | `009-C2` | No call-scoped warmup; no duplicate operation; `180` precedes final admission |
| Inbound answer/readiness corrective | `src/sip_bot/sip_media/adapter.py`, `src/sip_bot/runtime_wiring.py` | Explicit `180 → warmup/readiness → 200/503`, cancellation/stale handling | `009-C1` | Corrective plan write-set; no AI/media ownership change |
| Contract tests | `tests/unit/`, `tests/contract/`, `tests/integration/` | Disabled-path, profile validation, status mapping, refresh/unregister tests | `009-A`/`009-B` | New targeted tests only |
| Local registrar | New workshop/test-stand files under `tools/` or `artifacts/implementation/009-optional-sip-registration/` | FreeSWITCH local fixture, account/dialplan and deterministic commands | `009-C` | Own stand/evidence root; no PBX production code |
| Workshop guide | `docs/user-guide.md` or dedicated workshop runbook | Add only accepted registration steps and links | main executor/`009-C` | User-operation section only; no duplicate protocol design |
| Architecture/TЗ | `docs/architecture.md`, `docs/technical-specification.md` | Synchronize after evidence: optional account registration and readiness policy | main executor | Owner sections only |
| Registry/backlog/roadmap | `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md` | Record map/status/next step and checks | main executor | Sequential documentation sync |

Protected from modification: Map-I typed media/data topology, existing direct-URI behavior, historical feasibility evidence,
AI/speech components, unrelated workshop/presentation files and existing artifact roots.

## 9. Дочерние планы, зависимости и порядок

| ID | Plan-file | Назначение | Зависимости | Acceptance boundary | Status |
|---|---|---|---|---|---|
| `009-A` | `plan-009-A-registration-config-contract.md` | Default-off profile, config mapping, public demo credential и disabled-path regression | Map-008, current SIP baseline | Existing direct mode remains unchanged; profile validation and config tests pass | `complete` |
| `009-B` | `plan-009-B-pjsua2-registration-lifecycle.md` | PJSUA2 account registration, digest auth, refresh/expiry/unregister, status events and readiness | `009-A`, `001-C1` | Target protocol evidence and typed registration lifecycle pass; no call admission before readiness when enabled | `complete` |
| `009-C` | `plan-009-C-freeswitch-workshop-integration.md` | Local FreeSWITCH registrar/route, registered incoming call, workshop commands and evidence | `009-B`, local stand preparation | Registration-enabled call completes approved scenario; disabled direct lane regresses; runbook reproducible | `complete` |
| `009-C1` | `plan-009-C1-inbound-answer-readiness-gate.md` | Corrective inbound SIP answer lifecycle and asynchronous AI readiness gate | `009-C` blocker evidence | Explicit `180 → 200/503`, no native abort, cancellation/stale contract and C4 promotion | `complete` |
| `009-C2` | `plan-009-C2-runtime-readiness-coordination.md` | Runtime-scoped single-flight warmup, event-driven registered incoming composition и accepted Baresip recording path | `009-C1`, owner decision 2026-09-13 | `ApplicationRuntime.start()` не прогревает; registered full-AI replay создаёт composition по фактическому call id и сохраняет raw/stereo recording | `complete` |

Общие документы, config constants и final integration gates изменяет главный executor последовательно. `009-A` и
`009-B` могут готовить deterministic tests параллельно только после фиксации preceding typed contract; actual target
registration и FreeSWITCH live gate выполняются последовательно.

## 10. Owner-review решения

### 10.1. Уже решено предыдущими документами или текущим указанием владельца

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Должна ли регистрация быть обязательной? | Нет, это optional capability для мастер-класса | `SIP_REGISTRATION_ENABLED=False` по умолчанию | `resolved by owner instruction` |
| Должен ли сохраниться direct-URI путь? | Да, он нужен для текущего demo и regression | Disabled mode не задаёт registrar и не требует REGISTER | `resolved by protected baseline` |
| С каким PBX проверять регистрацию? | С локальным FreeSWITCH, без реального внешнего провайдера | `009-C` создаёт отдельный local registrar/route | `resolved by workshop scope` |
| Нужно ли менять AI/media path? | Нет | После успешной регистрации используется существующая SIP/RTP/AI composition | `resolved by architecture` |
| Должна ли registration status попадать в LLM/FSM? | Нет | Только runtime/control observation and admission policy | `resolved by ownership audit` |

### 10.2. Новые вопросы, требующие решения владельца

| Вопрос | Рекомендуемое решение | Почему это влияет на реализацию | Статус |
|---|---|---|---|
| Что делать, если registration включена, но registrar недоступен или регистрация истекла? | Не принимать входящий call и оставить readiness=false; не переходить автоматически в direct-URI | Определяет startup/admission state machine и предотвращает незаявленный fallback | `resolved: owner decision accepted 2026-09-13` |
| Где хранить workshop SIP password, учитывая публичный GitHub? | Типовой конфиг содержит явно помеченный публичный демонстрационный пароль и коммитится; production credentials и secret store в scope не входят | Конфиг остаётся единственным источником настроек MVP и воспроизводимым материалом мастер-класса; пароль не должен ошибочно восприниматься как production secret | `resolved: owner decision accepted 2026-09-13` |

Owner review подтвердил оба рекомендуемых решения; новых вопросов на уровне карты не остаётся. Выбор retry interval,
expiry refresh margin и точных имён typed event может быть закрыт child plan в рамках SIP standard/PJSUA2 evidence и не
должен повторно выноситься на review без противоречащего результата.

## 11. Process invariant audit

| Инвариант | Действие в Map-009 | Evidence |
|---|---|---|
| APG materialization | Каждый child plan получает source-map, write-set, owner audit, blocker register, test plan и closeout | Child plans и map gate |
| Typed-first | Registration profile/status/readiness — явные typed values/events; details dictionary не используется как скрытый контракт | Contract tests и event schema |
| Owner behavior | Registration lifecycle принадлежит SIP adapter; admission policy — runtime/launcher; FSM не поглощает registration | Source/ownership audit |
| Protocol independence | REGISTER challenge/response и mandatory replies не ждут Dispatcher/AI | Native callback trace и timing evidence |
| Bounded control | Межпоточный status exchange использует bounded thread-safe queue; PCM/data path не меняется | Queue/source audit |
| No silent fallback | Registration failure при enabled mode не переводит систему в direct mode | Negative integration test |
| No simplification | Не закрывать map только unit-test-ом; нужны target SIP и FreeSWITCH interop evidence | Target/live gate |
| Corrective pass | Любой красный тест сохраняется с raw output, классифицируется, исправляется и повторяется | Evidence and closeout |
| Binary closeout | Child plans закрываются только `complete` или `blocked`; partial/foundation claims запрещены | Child closeouts/map gate |
| Documentation | После изменения Markdown запускать registry audit; общие документы синхронизирует main executor | `check_document_registry.py` |

## 12. Architecture invariant audit

| Инвариант | Затронутая граница | Проверка |
|---|---|---|
| SIP adapter owns protocol | PJSUA2 account → registrar | Registration callback/source audit |
| Dispatcher is not SIP transaction responder | Registrar challenge/reply | Protocol timing and callback evidence |
| Control/data plane separation | Registration status vs PCMU/RTP | Forbidden-payload tests and source audit |
| Direct URI remains valid | Disabled config → existing account/call path | Existing Baresip loopback regression |
| Readiness precedes admission only when enabled | registration/runtime readiness → incoming call admission | Shared coordinator state matrix and FreeSWITCH scenario |
| Warmup is runtime-scoped | runtime coordinator → admission gate | `start()` no-heavy-work test; single-flight and running/not-started evidence |
| Per-call media remains negotiated | Registered INVITE → SDP/PJMEDIA | PCMU/profile evidence |
| Existing lifecycle/stale/cancel rules remain | Registered call → AI pipeline | Existing integration regression |
| No new owner without behavior/lifecycle | Registration profile/event and runtime readiness | Owner audit |

## 13. Implementation slices

| Срез | Цель | Исполнитель | Acceptance | Следующий шаг |
|---|---|---|---|---|
| `A1` | Зафиксировать registration profile, default-off policy и public demo credential contract | `009-A`; deterministic preparation may be delegated with disjoint write-set | Config import/validation tests; production secret absent from evidence | `A2` |
| `A2` | Проверить disabled direct-URI regression и profile edge cases | `009-A` | Existing direct mode remains pass; invalid enabled profile fails explicitly | `B1` |
| `B1` | Materialize PJSUA2 account registrar/auth parameters | `009-B` | Target no-GIL import/start/close and account configuration evidence | `B2` |
| `B2` | Implement registration callbacks, refresh/expiry/unregister and typed status events | `009-B` | Deterministic status mapping plus target registrar transaction trace | `B3` |
| `B3` | Apply enabled-mode readiness/admission policy | `009-B` | No call admission before successful registration; no silent direct fallback | `C1` |
| `C1` | Prepare local FreeSWITCH registrar and workshop account/route | `009-C` | Fresh local stand, exact commands and no real external PBX | `C2` |
| `C2` | Execute corrective runtime-readiness coordination and event-driven registered composition, then run registered incoming call through existing PCMU/RTP/AI path | `009-C2`/main executor | `ApplicationRuntime.start()` is non-blocking; exact incoming ID is composed; shared readiness and full registered call pass | `C2.1` |
| `C2.1` | Complete the already accepted Baresip recording boundary for the registered full-AI replay | `009-C2/R4.1`/main executor | Raw `enc`/`dec`, validated stereo artifact and manifest are present; no bot-side recording boundary is introduced | `C3` |
| `C3` | Validate disabled mode, error mode and documentation | `009-C`/main executor | Both modes tested, failure visible, workshop runbook reproducible | Map closeout |

## 14. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-009-A-001` | `009-A` | Нельзя добавить default-off profile без нарушения config constants policy | Registration configuration | project owner | Config/source audit and APG gap | `none until triggered` |
| `B-009-A-002` | `009-A` | Credential handling требует нового production secret store или второго обязательного runtime config source | `009-A` and downstream | project owner | Gap record and owner decision | `resolved: owner decision accepted 2026-09-13; public demo credential in committed constants is allowed` |
| `B-009-B-001` | `009-B` | PJSUA2 baseline не exposes required registrar/auth lifecycle without new native patch/API boundary | Registration implementation | project owner | Target probe and APG gap | `none until triggered` |
| `B-009-B-002` | `009-B` | Registration callback/status не может быть represented as typed control event without changing protected Map-I contract | Status propagation | project owner | Contract/source audit | `none until triggered` |
| `B-009-B-003` | `009-B` | Enabled-mode failure policy remains unresolved | Readiness/admission | project owner | Owner-review decision | `resolved: owner decision accepted 2026-09-13; readiness=false and no direct fallback` |
| `B-009-C-001` | `009-C` | Local FreeSWITCH cannot provide reproducible registrar/auth/route on target environment | Workshop integration | project owner | Stand preflight and raw logs | `none until triggered` |
| `B-009-C-002` | `009-C` | Registered call breaks existing negotiated media or AI path | Map-009 closeout | project owner | Fresh registered-call evidence and corrective pass | `none until triggered` |
| `B-009-C-004` | `009-C` | Existing inbound `SipMediaAdapter._on_incoming_call` passed target PJSIP an invalid `statusCode=0` via `CallOpParam(True)`, causing native abort before answer/media | `009-C` C4 and Map-009 closeout | project owner | `registered-call-r2.json` historical evidence; corrective `009-C1` and fresh `registered-call-r7.json` | `resolved: 009-C1 closeout 2026-09-13; superseded by no open protocol defect` |
| `B-009-C-006` | `009-C`/`009-C2` | Full-AI registered replay had adapter-generated `call-in-0` but a pre-created composition `j4-full-live-call`; the test order did not follow incoming `CALL_STARTED` lifecycle | Full-AI registered C4 and Map-009 closeout | `009-C2` corrective plan: buffer `CALL_STARTED`, compose with actual id, replay typed event; escalate only if protected API change is proven | `resolved: target r15 uses actual call-in-0 and passes` |
| `B-009-MAP-001` | map gate | Work requires external PBX, TLS/secret vault, multi-call scaling, new IPC or protected boundary change | Map-009 and dependents | project owner | APG §6 gap record | `none until triggered` |

Красный результат в approved write-set сначала проходит corrective protocol и не становится blocker автоматически.
Category-4 blocker регистрируется только после доказанного API/architecture gap или внешней невозможности получить
обязательное evidence.

## 15. Test plan и evidence

### `009-A`

- config import на host и target free-threaded runtime;
- `SIP_REGISTRATION_ENABLED=False` сохраняет current direct-URI behavior;
- profile validation: empty registrar, invalid URI, invalid expiry, missing credentials при enabled mode;
- negative assertion: password не попадает в `RegistrationEvent`, logs или evidence JSON;
- target `Py_GIL_DISABLED`/`sys._is_gil_enabled()` до и после imports.

### `009-B`

- deterministic mapping SIP status/challenge/expiry в typed registration states;
- target PJSUA2 account creation, registration, refresh, unregister и shutdown;
- registrar unavailable/auth failure/expiry path;
- repeated close и cancellation без зависания main asyncio loop;
- direct-mode regression и existing call/media regression;
- raw SIP/adapter logs, typed events, exit codes, runtime/GIL manifest.

Target runtime: patched CPython `3.14.7t` и existing PJSUA2/PJMEDIA environment. Heavy GPU inference не нужен; если
target scenario одновременно требует AI composition, он выполняется главным executor после освобождения GPU и warmup.

### `009-C`

- local FreeSWITCH starts from a fresh stand configuration;
- account registration succeeds with explicit local credentials;
- FreeSWITCH routes an incoming call to the registered bot endpoint;
- negotiated PCMU/8000/mono and existing SIP/media profile are preserved;
- approved full-flow scenario completes without changing speech/AI components;
- registration-disabled direct-URI lane still passes;
- workshop command sequence, logs, failure instructions and evidence paths are reproducible.

Для live acceptance сохраняются raw FreeSWITCH/Baresip/PJSUA2 logs, registration trace, SIP/media profile, scenario
manifest и итоговый `report.md`. Пароли и authentication headers в evidence не записываются.

## 16. Fallback/deferred register

| Вариант | Разрешение | Ограничение |
|---|---|---|
| Registration disabled | Разрешён и является default | Это direct-URI mode, не доказательство REGISTER |
| Direct-URI fallback при enabled registration failure | Запрещён молча | Может быть добавлен только отдельным owner decision; текущая рекомендация — не добавлять |
| Local FreeSWITCH instead of external PBX | Разрешён для workshop | Не выдаётся за external-provider compatibility |
| Plain local workshop credentials | Разрешены как явно помеченный публичный demo credential в коммитимом типовом конфиге | Не выдавать его за production credential, не переносить production secrets в репозиторий и не писать пароль в logs/evidence |
| TLS/SRTP/secret vault | Deferred | Отдельная production/security map |
| Multi-registrar/failover | Deferred | Не входит в single-call workshop scope |

## 17. Map-level acceptance и closeout

Map-009 получает статус `complete` только если:

1. `009-A`, `009-B` и `009-C` имеют собственные APG-compliant binary closeout со статусом `complete`;
2. registration default-off regression доказана на существующем direct-URI пути;
3. registration-enabled target evidence показывает успешные auth, refresh/expiry и штатный unregister либо честно
   фиксирует доказанный scope их поддержки;
4. ошибка registration в enabled mode видна пользователю/оператору через readiness/status и не превращается в скрытый
   direct fallback;
5. local FreeSWITCH workshop scenario принимает входящий вызов на зарегистрированный endpoint;
6. negotiated PCMU/RTP и весь существующий AI/data path остаются без новых boundary обходов;
7. в репозитории присутствует только явно помеченный публичный demo credential из типового конфига; production secrets
   отсутствуют в исходных evidence/logs и public artifacts;
8. каждый красный результат имеет raw output, corrective pass или category-4 blocker;
9. `docs/user-guide.md`, `architecture.md`, `technical-specification.md`, registry, backlog, roadmap и evidence index
   синхронизированы;
10. ограничения local workshop scope и отсутствие production launcher явно указаны.

## 18. Execution report и closeout — 2026-09-13

`009-A`, `009-B`, `009-C1` и `009-C2` имеют собственные binary closeout со статусом `complete`; `009-C` также закрыт
после финальной синхронизации. Direct-URI regression и enabled registration failure/no-fallback подтверждены ранее
`C5` contract evidence. Свежий clean-start target r15 подтвердил полный registered path:

- target `3.14.7 free-threading`, `gil_enabled=false`;
- runtime readiness `ready`, cold aggregate warmup `26 303.471 ms`, `ApplicationRuntime.start()` не выполнял heavy warmup;
- фактический incoming `call-in-0`, `180 → readiness → 200`, registration enabled;
- negotiated `PCMU/8000/mono`, `ptime=20 ms`, peer RTP `6292 transmit / 1850 receive`, без overflow, callback errors и
  `egress_underruns`;
- полный existing AI/report scenario: follow-up, barge-in, unknown-answer/offer-transfer, operator transfer и report;
- Baresip `sndfile`: raw `enc`/`dec`, [`conversation-stereo.wav`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/recordings/conversation-stereo.wav)
  и [`recording-manifest.json`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/recordings/recording-manifest.json),
  mapping `left=user_to_bot`, `right=bot_to_user`;
- все scenario checks r15, включая `stereo_recording_present`, имеют значение `true`, exit code `0`.

Изменения, run commands, тесты и результаты перечислены в closeout `009-C2`; исторические r1–r14 сохранены и не
перезаписывались. Внешний PBX, production launcher, TLS/secret vault и multi-call scope по-прежнему не заявляются.

Карта закрыта бинарно: `complete`.

## 19. Closeout contract для будущих изменений

После исполнения Map-009 closeout обязан перечислить фактически изменённые файлы и symbols, профиль registration и
его default, target runtime/GIL evidence, direct-mode regression, SIP registration/refresh/unregister trace, FreeSWITCH
stand configuration и logs, registered-call scenario, credential redaction, corrective passes, pre-existing failures,
deferred evidence с owner/condition promotion, registry/backlog audit и итоговые workshop commands. Статус карты
меняется на `complete` только после закрытия всех child plans и выполнения map-level acceptance; при category-4 gap —
только `blocked`.
