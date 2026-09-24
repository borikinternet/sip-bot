# План 009-C2: общая координация прогрева runtime и динамический registered-call replay

Уровень документа: `child corrective plan`  
Идентификатор: `009-C2`  
Статус: `complete` — owner decision принят `2026-09-13`, R1–R5 и corrective R4.1 исполнены по APG  
Родитель: [`plan-009-C-freeswitch-workshop-integration.md`](plan-009-C-freeswitch-workshop-integration.md)  
Карта: [`plan-009-optional-sip-registration.md`](plan-009-optional-sip-registration.md)  
Дата подготовки: `2026-09-13`

## 1. Цель и проверяемый результат

Устранить ошибочную классификацию `B-009-C-006` как предметного архитектурного blocker-а и исправить порядок
registered full-AI replay. Одновременно materialize согласованную политику readiness:

- `ApplicationRuntime.start()` не выполняет тяжёлый прогрев и возвращает управление SIP/control plane быстро;
- прогрев является свойством всего runtime, а не текущего звонка;
- внешний launcher/оператор может заранее запустить один общий background warmup;
- если вызов пришёл при `RUNNING`, он ожидает уже идущую операцию;
- если warmup ещё не запускался, входящий вызов может инициировать ту же единственную runtime-операцию как fallback,
  но не создаёт собственного прогрева;
- одновременные запросы используют одну операцию (single-flight), а не запускают прогрев повторно;
- при `READY` входящий call сразу допускается после `180`, при успешном завершении warmup отправляется `200`, при
  ошибке — `503`;
- в registered replay `CallSession`/`CallComposition`/`CallRuntimeWiring` создаются по фактическому
  adapter-generated `CALL_STARTED.call_id`, а событие не переписывается.
- test-peer Baresip сохраняет полный media-сеанс через штатный `sndfile`: raw `enc`/`dec` остаются первичными
  артефактами, а из них строится проверенный stereo WAV с явным mapping каналов.

Проверяемый результат: один clean-start registered full-AI replay проходит через `180 → readiness → 200`, полный
существующий SIP/RTP/AI/report path и фактический `call_id`; отдельные тесты подтверждают ready/running/not-started/
failed/cancelled состояния и отсутствие тяжёлой работы внутри `ApplicationRuntime.start()`.

## 2. Решения владельца, зафиксированные этим планом

| Вопрос | Решение | Последствие |
|---|---|---|
| Должен ли сервис синхронно прогревать модели при старте? | Нет | `ApplicationRuntime.start()` только запускает runtime; тяжёлый warmup не входит в его критический путь |
| Кто владеет warmup? | Runtime-scoped coordinator | Warmup не принадлежит `CallSession`, `IncomingCallReadinessGate` или конкретному SIP-вызову |
| Что делает входящий звонок при `NOT_STARTED`? | Запрашивает общую операцию `ensure_ready()` | Допускается lazy fallback только как аварийный случай, без per-call warmup и без дублирования |
| Что делает звонок при `RUNNING`? | Ждёт тот же single-flight result | Второй warmup не запускается |
| Как использовать Event Bus? | Публиковать компактные typed readiness events для наблюдателей | Каноническое состояние и ожидание хранятся в coordinator; потеря уведомления не должна терять readiness |
| Как исправить `call-in-0`/`j4-full-live-call`? | Перестроить порядок теста по реальному `CALL_STARTED` | ID не подменяется, новые SIP/FSM/data-plane boundaries не вводятся |

## 3. Materialized rules из документов второго типа

| Источник | Применимое правило | Влияние | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) §0.4, §3, §5 | Кодовая corrective work с отдельными acceptance boundaries получает self-contained child plan с source-map, write-set, invariants, blocker register, tests и closeout | План разделён на узкие runtime, gate, harness и evidence slices | APG audit в этом файле и closeout | Новый protected-baseline change или owner decision |
| [`development-guidelines.md`](../development-guidelines.md) §2 | Поведение владеет объект с самостоятельными данными, invariants и lifecycle; процедурное связывание само по себе не создаёт владельца | Coordinator владеет состоянием/операцией warmup; bootstrap replay остаётся orchestration harness | Owner/lifecycle audit и unit tests | Новый владелец, дублирующий Dispatcher/FSM или SIP adapter |
| [`development-guidelines.md`](../development-guidelines.md) §3 | Typed-first; direct in-process payload не маршрутизируется универсальным delivery owner; межпоточные границы — bounded thread-safe queue | Readiness — typed state/event; audio/text path не меняется; Event Bus несёт только компактный control event | Contract/source audit | Raw dict как authoritative API или data-plane через bus |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Субагент не принимает архитектурных решений; общие документы и integration gates изменяет main executor | Этот plan исполняется главным executor; при делегировании write-set остаётся disjoint | Diff/handoff audit | Неизолируемый write-set или новый архитектурный вариант |
| [`development-guidelines.md`](../development-guidelines.md) §6, §6.1 | Lazy native/model operation не должна впервые выполняться на критическом пути без явной admission policy; красный test/fixture result сначала исправляется corrective pass | Warmup вынесен в runtime coordinator; harness mismatch считается corrective test-order defect, пока не доказано обратное | State matrix, no-startup-warmup test, registered replay | Доказанный внешний/API gap после corrective attempts |
| [`development-guidelines.md`](../development-guidelines.md) §7–§9 | Нет silent fallback/упрощения; child plan закрывается только `complete` или `blocked`; docs/registry/backlog синхронизируются main executor | Не переписывать call id и не закрывать C по SIP-only evidence; closeout только после full-AI replay | Full evidence, registry/backlog audits | Только concrete category-4 blocker |
| [`architecture.md`](../architecture.md) §§1–2.2 | Dispatcher/FSM владеют control semantics, SIP adapter — protocol reaction; `180` локален, `200` только после readiness; data plane идёт напрямую | Gate получает coordinator result и вызывает только `answer()`/`reject()`; композиция строится на реальном session id | Architecture/source audit | Изменение Dispatcher/FSM/SIP ownership |
| [`technical-specification.md`](../technical-specification.md) §§2, 4, 6 | Readiness использует тот же typed working boundary, SIP polling не блокируется, media не открывается до `200` | Shared warmup выполняет RAG/LLM/ASR/TTS stages вне event loop; failure/stale/cancel сохраняются | Focused and target tests | Warmup только import-only или late `200` |
| [`plan-005-D-rehearsal-evidence-closeout.md`](plan-005-D-rehearsal-evidence-closeout.md), [`plan-005-E-tts-playback-integrity-corrective.md`](plan-005-E-tts-playback-integrity-corrective.md) | Baresip test peer владеет recording; штатный `sndfile` даёт raw `enc`/`dec`, stereo derivative обязателен, mapping и trailing padding фиксируются в manifest | Registered full-AI replay должен сохранять raw tracks и производный `conversation-stereo.wav`; runtime не получает новую audio-recording boundary | `sndfile` output, stereo builder, manifest and audio audit | Нельзя получить оба raw track или пройти metadata/mapping audit после corrective pass |
| [`decisions/ADR-004-control-plane-event-bus.md`](../decisions/ADR-004-control-plane-event-bus.md) | Event Bus process-local, bounded, control-only и не заменяет Dispatcher/data plane | Публиковать readiness notifications без PCM/text/RAG; coordinator не считает событие единственным источником истины | Bus payload and drop-policy tests | Второй bus без ADR или data payload |
| [`documentation-process.md`](../documentation-process.md) | Один устойчивый владелец информации; execution result не заменяет owner document | Policy synchronised в architecture/TЗ/guidelines, status — в map/C plan/registry/backlog | Registry audit | Дублирующие conflicting statements |

## 4. Граница, protected baseline и assumptions

### Входит

- runtime-scoped `ReadinessCoordinator` с состояниями `NOT_STARTED`, `RUNNING`, `READY`, `FAILED`;
- single-flight запуск одного aggregate warmup, общий результат для всех ожидающих callers и явный background trigger;
- compact typed readiness notifications через существующий process-local `ControlEventBus`;
- перевод `IncomingCallReadinessGate` с call-owned `warmup()` на coordinator-owned `ensure_ready()`;
- event-driven registered harness: сначала фактический `CALL_STARTED`, затем composition/wiring с его ID;
- cold/running/ready/failure/cancel tests и clean-start registered full-AI evidence;
- per-run Baresip `sndfile` recording с raw `enc`/`dec` и stereo derivative в artifacts;
- синхронизация архитектуры, ТЗ, development guidelines, user guide, Map-009, parent C, registry и backlog.

### Не входит

- новый SIP/RTP stack, изменение PJSUA2/PJMEDIA, SDP/PCMU/media framing или Dispatcher/FSM semantics;
- multi-call scaling, production service manager, persistent readiness database или secret store;
- повторный универсальный event bus: используется существующий [`src/sip_bot/control/event_bus.py`](../../src/sip_bot/control/event_bus.py);
- автоматический CPU/model/GIL fallback;
- передача PCM, transcript, RAG fragments или answer text через Event Bus;
- изменение accepted direct-URI path и исторических evidence.

### Protected baseline

- `CallSession`, `CallComposition`, Dispatcher и DialogueFSM остаются разными существующими объектами;
- SIP adapter первым локально отправляет `180`, `answer()`/`reject()` материализуют `200`/`503` explicit status codes;
- один active call, target free-threaded CPython, PCMU/8 kHz/mono и negotiated per-call media profile;
- existing RAG/LLM/ASR/TTS warmup stages и typed boundaries используются без подмены stub/fake;
- current Control Event Bus semantics (bounded, non-blocking, возможная потеря notification) не изменяются.

## 5. Source-map и write-set

| Область | Файл/символ | Текущее состояние | Целевое состояние | Write-set |
|---|---|---|---|---|
| Runtime readiness | `src/sip_bot/runtime.py`: `ApplicationRuntime`, новые coordinator/state types | `warmup()` вызывается синхронно caller-ом; нет single-flight state | Быстрый `start()`, shared coordinator, explicit background trigger, state/snapshot/events | runtime readiness symbols only |
| Control notification | `src/sip_bot/runtime.py` или узкий runtime events module; existing `control/event_bus.py` | Нет typed readiness event | Compact `RuntimeReadinessEvent` для observers; bus mechanics unchanged | New typed event/coordinator publication only |
| Admission | `src/sip_bot/runtime_wiring.py`: `IncomingCallReadinessGate` | При cold call вызывает переданный `warmup()` | Ожидает coordinator `ensure_ready()`; call cancellation не отменяет global warmup | Gate constructor/state/tests only |
| Registered orchestration | `tools/freeswitch_workshop/registered_full_rehearsal.py`, `tools/j4_full_live_gate.py` hooks | Composition создан до incoming `CALL_STARTED` | Bootstrap buffers event, creates exact-ID composition/wiring, replays event | Workshop harness and narrow reusable hooks |
| Recording evidence | `tools/freeswitch_workshop/registered_full_rehearsal.py`, existing `tools/map005_stereo_recording.py` | Registered peer config не включает `sndfile`; result помечает `audio_recording=false` | Per-run raw Baresip `enc`/`dec` plus validated stereo derivative and manifest | Recording wrapper and focused tests only |
| Runtime tests | `tests/unit/test_incoming_answer_readiness.py`, new runtime coordinator tests | Gate tests mock direct warmup callback | Tests cover state, single-flight, non-blocking start and event publication | Focused tests only |
| Integration tests | `tests/integration/test_runtime_wiring.py`, new/related registered workshop test | Static composition ID accepted; no dynamic incoming composition assertion | Exact adapter ID, event replay, terminal/cancel and no late answer | Integration tests only |
| Owner documents | `docs/architecture.md`, `docs/technical-specification.md`, `docs/development-guidelines.md`, `docs/user-guide.md` | Wording implies synchronous pre-call/start warmup and call-owned callback | Runtime-scoped non-blocking warmup policy and explicit trigger/fallback | Related sections only |
| Operational docs | Map-009, parent C, registry, backlog, closeout/evidence | `B-009-C-006` open owner blocker | Corrective execution, then resolved if evidence passes | Main executor sequential sync |

Protected from modification: SIP adapter protocol implementation, PJSUA2/PJMEDIA patches, media/speech/AI owner code,
existing direct J4 semantics, old evidence roots and unrelated presentation/workshop files.

## 6. Ownership and interaction topology

```text
operator/launcher ── start_background() ─┐
                                         ▼
                                  RuntimeReadinessCoordinator
                                  state + single-flight task
                                         │
       RuntimeReadinessEvent ────────────┴──> existing ControlEventBus observers
                                         │
incoming CALL_STARTED after 180 ──> IncomingCallReadinessGate
                                         │ await same readiness result
                                         ├── READY  ──> SIP adapter.answer() → 200
                                         ├── RUNNING ──> await shared operation
                                         ├── NOT_STARTED ──> start shared operation
                                         └── FAILED ──> SIP adapter.reject(503)
```

Coordinator owns only runtime warmup lifecycle/state and does not own SIP, FSM, dialogue, media or payload delivery.
The gate owns only the pending incoming-call admission lifecycle. A terminal event cancels that call's wait, but must not
cancel the shared runtime warmup, because that operation is not owned by the call.

The registered replay ordering is:

```text
adapter receives INVITE
  → adapter sends 180 and emits CALL_STARTED(actual_id)
  → bootstrap retains compact event
  → runtime.compose_call(actual_id, owners)
  → create wiring/gate for actual_id
  → replay CALL_STARTED to wiring/gate
  → await shared readiness
  → answer 200 and continue existing media/AI path
```

## 7. Implementation slices

| Slice | Action | Depends on | Acceptance |
|---|---|---|---|
| `R1` | Implement coordinator state, snapshot, single-flight execution, explicit background trigger and typed bus notifications | None | `start()` does not warm; concurrent callers share one operation; success/failure state is observable |
| `R2` | Rebind `IncomingCallReadinessGate` to coordinator and retain terminal/stale behavior | `R1` | ready/running/not-started/failed/cancel tests; caller cancellation does not duplicate/cancel global warmup |
| `R3` | Refactor registered harness to buffer `CALL_STARTED` and create exact-ID composition/wiring after event | `R2` | No ID rewrite; composition ID equals adapter ID; existing Dispatcher/FSM receive only matching events |
| `R4` | Run target registered warm/cold admission and full-AI replay; preserve logs/recording/report | `R3`, free GPU, clean stand | Full registered scenario and readiness timing pass; recording path is exercised or its concrete failure is passed to R4.1 |
| `R4.1` | Enable the accepted Baresip `sndfile` path for the registered peer, retain raw tracks and build stereo artifact | `R4` | `enc`/`dec` WAV exist, metadata is PCMU-decoded PCM16/8000 mono, stereo mapping and manifest pass; full result reports `audio_recording=true` |
| `R5` | Synchronize owner documents, close `B-009-C-006` if R4 passes, update registry/backlog and audits | `R4` | Parent C and Map-009 status/evidence are factual; registry/backlog/git checks pass |

Actual heavy GPU inference and target full-AI replay are main-executor work. No subagent may claim GPU acceptance from a
mock or import-only result.

## 8. Blocker register

| ID | Trigger | What it blocks | Evidence/promotion | Status |
|---|---|---|---|---|
| `B-009-C2-001` | Existing runtime/API cannot expose one shared warmup result without changing protected Dispatcher/SIP boundaries | R1/R2 | Source/test evidence and owner review if protected change is unavoidable | `none until triggered` |
| `B-009-C2-002` | Existing Control Event Bus cannot carry compact readiness event without changing its accepted control-only contract | R1 | Typed bus contract evidence and owner review | `none until triggered` |
| `B-009-C2-003` | Registered event cannot be buffered/replayed through an existing typed consumer boundary without changing protected call lifecycle | R3 | Target/source evidence after corrective harness attempt | `none until triggered` |
| `B-009-C2-004` | Target FreeSWITCH/AI environment prevents full registered replay after R1–R3 corrective attempts | R4/R5 | Raw logs, exit codes, clean-start rerun and external cause | `resolved: R4 target r15 pass` |
| `B-009-C2-005` | Target Baresip cannot load the already accepted `sndfile` module or cannot produce both raw media tracks after the approved recording corrective pass | R4.1/Map-009 closeout | Module/version/config logs, raw peer output, focused retry and exact missing API/environment evidence | `resolved: R4.1 target r15 produced enc/dec and stereo pass` |

Ошибки порядка harness, fixture, private test hook и реализации в разрешённом write-set не являются blocker: они требуют
corrective pass. Существующий `B-009-C-006` не считается новым owner decision после принятия этого плана; он будет закрыт как
test-order corrective result, если R3/R4 дадут требуемое evidence. Если фактически потребуется изменение protected
application API, исполнение останавливается до owner review.

## 9. Required tests and evidence

- unit: coordinator state transitions, explicit trigger, single-flight identity, failure, retry policy and no warmup in
  `ApplicationRuntime.start()`;
- unit/integration: gate observes `180`-backed pending event, waits shared result, answers once, rejects failure and does
  not answer after terminal call event;
- contract: `RuntimeReadinessEvent` is bounded typed control data; Event Bus never receives bytes, PCM, transcript, RAG or
  answer payload;
- integration: incoming event is buffered before composition, exact `call_id` is used to create session/context/wiring and
  event is replayed once; no event reaches a mismatched Dispatcher session;
- target: registered FreeSWITCH/Baresip clean-start, registration trace, `180 → readiness → 200/503`, negotiated PCMU/RTP,
  raw Baresip `enc`/`dec` and stereo recording, full existing AI/report scenario, runtime/GIL and exit-code evidence;
- documentation: no statement claims that `ApplicationRuntime.start()` synchronously performs heavy warmup; runbook tells
  operator when to trigger background warmup and what happens if a call arrives before completion.

## 10. Stop conditions and closeout

Остановиться можно только при:

1. concrete protected-boundary/API gap после corrective attempt и raw evidence;
2. внешней невозможности target evidence после повторных safe attempts;
3. новом owner decision, которого нет в этом плане.

При успешном R4 план закрывается `complete` с closeout, changed files, tests, target commands, timing, evidence и
registry/backlog audit. При category-4 blocker — `blocked` с owner, evidence и condition promotion. `partial`/`foundation`
status не используется.

## 11. Execution report и closeout — 2026-09-13

### R1–R3: реализация и локальные проверки

- Добавлен runtime-scoped `RuntimeReadinessCoordinator`: состояния `NOT_STARTED/RUNNING/READY/FAILED`, одна
  single-flight операция, явный `start_background()`, общий результат для ожидающих вызовов и независимость от
  отмены конкретного incoming call.
- `ApplicationRuntime.start()` не выполняет тяжёлую работу; `IncomingCallReadinessGate` использует coordinator и
  сохраняет немедленный `180`, ожидание общей readiness-операции и явный `200/503`.
- Registered harness сначала буферизует фактический `CALL_STARTED`, затем создаёт `CallComposition` и wiring с его
  `call-in-0` и один раз воспроизводит typed event; подмена идентификатора удалена.
- Узкие unit/contract проверки прошли: `8 passed`; компиляция target no-GIL Python прошла. В evidence сохранены
  исторические красные прогоны r1–r10 и диагностические corrective passes.

### R4: target evidence (AI/readiness path)

Исторический clean-start cold target r13:
[`registered-j4-full-live.json`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r13/registered-j4-full-live.json)
сохраняется как диагностический результат порядка harness. Авторитетный повтор после подключения записи — target r15:
[`registered-j4-full-live.json`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/registered-j4-full-live.json)

Итог r15: `pass`, exit code `0`. Существенные факты:

- target: `3.14.7 free-threading`, `gil_enabled=false`, runtime readiness=`ready`;
- warmup завершён за `26 303.471 ms`; `ApplicationRuntime.start()` был выполнен до этого отдельно и не содержал
  warmup-критического пути;
- один registered incoming call: фактический `call_id=call-in-0`, `180 → readiness → 200`, registration enabled;
- PCMU/8000/mono, `ptime=20 ms`, peer RTP `6292 transmit / 1850 receive`, `rtp_ingress_established=true`;
- adapter media: `6280` ingress/egress frames, zero overflow/closed drops/callback errors, `egress_underruns=0`;
- WebRTC VAD: `602` speech decisions, `610` nonzero PCM frames, hard endpoints около `520–540 ms`;
- существующий AI/report path: `18` ASR hypotheses, `5` final turns, `39` TTS chunks, `1663` emitted TTS frames;
- сценарий содержит follow-up, barge-in, unknown-answer offer, transfer и финальный `report.md`; `stale_hypotheses=0`,
  wiring errors=`0`.
- R4.1: Baresip `sndfile` загрузился и записал raw `enc`/`dec`; stereo derivative и manifest прошли metadata/hash/
  mapping audit. `audio_recording=true`, длительность stereo `125.84 s`; оба raw track сохранены в `recordings/raw`.
- `tts_output.dropped_tail_bytes=11606` относится к явному завершению вызова после transfer, не к overflow:
  `dropped_overflow_bytes=0`, `pending_frames=0`, `egress_underruns=0`; это соответствует принятой cancellation/close
  policy из Map-005 и не является потерей mid-stream ответа.

Отдельный media-only diagnostic [`registered-call-diagnostic-r12.json`](../../artifacts/implementation/009-optional-sip-registration/009-C/registered-call-diagnostic-r12.json)
зафиксировал рабочий двунаправленный RTP на исправленном стенде. Причина первоначального нулевого ingress была
стендовой: Docker bridge адрес считался локальным и RTP proxy рекламировал контейнерный адрес. Для workshop bridge
включён `bypass_media=true`, поэтому FreeSWITCH остаётся SIP registrar/route, а RTP идёт напрямую между WSL peer и
ботом; SIP/RTP код приложения не менялся.

### R4.1/R5: recording corrective pass и APG/documentation closeout

`R4.1` переиспользовал принятый `sndfile` path из Map-005: per-run peer config с `module sndfile.so` и `snd_path`,
сохранил raw `enc`/`dec`, затем вызвал `tools/map005_stereo_recording.py` с mapping `left=user_to_bot`,
`right=bot_to_user`. Артефакты: [`registered-j4-full-live.json`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/registered-j4-full-live.json),
[`conversation-stereo.wav`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/recordings/conversation-stereo.wav),
[`recording-manifest.json`](../../artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/recordings/recording-manifest.json).

Изменены только относящиеся к плану области: runtime readiness implementation/tests, registered rehearsal hooks,
Baresip recording wrapper/tests, FreeSWITCH workshop route, user guide и плановые документы. `docs/user-guide.md` теперь
описывает runtime-scoped readiness, cold/full registered command, `--prewarm` и recording artifacts; warmup не
представлен как синхронный `ApplicationRuntime.start()`. Registry, backlog, roadmap, parent plan и Map-009
синхронизированы. Исторические evidence не перезаписывались.

Все blockers этого child plan, включая `B-009-C2-005`, закрыты evidence; `B-009-C-006` снят corrective pass-ом и
target evidence. Новый protected-boundary/API gap не обнаружен, owner review не требуется. План закрыт бинарно:
`complete`.
