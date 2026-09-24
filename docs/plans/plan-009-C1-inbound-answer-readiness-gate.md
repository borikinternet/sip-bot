# Plan 009-C1: inbound answer и readiness gate

Уровень: `child corrective plan`  
Идентификатор: `009-C1`  
Статус: `complete` — все slices исполнены, evidence и audits пройдены `2026-09-13`  
Родитель: [`plan-009-C-freeswitch-workshop-integration.md`](plan-009-C-freeswitch-workshop-integration.md)  
Карта: [`plan-009-optional-sip-registration.md`](plan-009-optional-sip-registration.md)  
Дата: `2026-09-13`

## 1. Цель и проверяемый результат

Исправить обязательный registered-incoming-call gate, остановленный на `B-009-C-004`, и materialize согласованное
поведение для холодного AI runtime:

```text
incoming INVITE
    └─ SIP adapter немедленно отвечает 180 Ringing
       └─ main asyncio loop запускает readiness/warmup вне native callback
          ├─ runtime уже ready → явный 200 OK
          ├─ warmup завершён → явный 200 OK
          └─ warmup завершён ошибкой → явный 503, без 200 и без direct fallback
```

После `200 OK` PJSUA2/PJMEDIA может открыть negotiated media и существующий speech/AI path. Пока звонок находится в
provisional state, media/AI pipeline не считается запущенным. Если удалённая сторона присылает `CANCEL`, `BYE`,
transport/media failure или иной terminal event во время warmup, SIP adapter отвечает в своём протокольном контексте,
readiness task отменяется или помечается stale, а результат warmup не имеет права ответить на уже закрытый звонок.

## 2. Materialized rules

| Источник | Правило/решение | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| [`development-guidelines.md`](../development-guidelines.md) §3 | Прямой in-process boundary материализуется вызовом typed input-метода получателя; delivery-owner не создаётся без самостоятельного поведения | Readiness gate — самостоятельный lifecycle/decision owner; SIP answer остаётся методом adapter | Unit/integration state tests | Новый delivery/facade без собственного lifecycle |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Dispatcher и native callbacks не блокируются тяжёлой работой; lock сам по себе не blocker | Warmup выполняется вне native callback и не блокирует main event loop; протокол продолжает poll | Async gate test и target registered-call probe | Warmup блокирует callback/event loop |
| [`development-guidelines.md`](../development-guidelines.md) §6 | Lazy model provider прогревается тем же рабочим typed boundary; неполный результат не readiness | Использовать существующий `ApplicationRuntime.warmup()` и его stages, а не import-only probe | Ready/cold/failure tests | Warmup только импортирует модель или скрывает ошибку |
| [`development-guidelines.md`](../development-guidelines.md) §6.1 | Ошибка реализации текущего write-set исправляется corrective pass, а не регистрируется как blocker | Исправить `CallOpParam(True)` и повторить target gate | Target stderr/exit code и rerun | Только доказанный protected/external API gap |
| [`development-guidelines.md`](../development-guidelines.md) §8 | Child plan закрывается только `complete` или `blocked` | Closeout только после inbound SIP/RTP evidence и regression | Plan closeout | `partial`/`foundation` status запрещён |
| [`architecture.md`](../architecture.md) §2.2 | SIP adapter сам выполняет обязательную protocol reaction; Dispatcher/AI не являются обязательными для ответа | `180` — локально и немедленно; `200`/`503` — explicit adapter methods из main loop | Protocol event/status assertions | Ответ зависит от Dispatcher или LLM |
| [`technical-specification.md`](../technical-specification.md) §4 | `answer()` является SIP command; protocol events не ждут AI | Adapter materializes explicit status code, не использует boolean constructor как SIP status | Fake PJSUA2 contract test | `statusCode=0` или native abort |
| [`plan-009-optional-sip-registration.md`](plan-009-optional-sip-registration.md) | Enabled registration failure оставляет readiness=false и не включает direct fallback | Warmup failure отвечает `503`; direct URI не активируется | Failure-path test | Молчаливый fallback |
| Явное решение владельца `2026-09-13` | Сначала `180`, затем проверка/прогрев LLM и обязательных внешних компонентов, после готовности `200` | Incoming call остаётся provisional до readiness; ready path пропускает warmup | Gate state matrix | Ответ `200` до readiness |

## 3. Граница и protected baseline

### Входит

- явная передача PJSUA2 status codes `180`, `200`, `503` через `CallOpParam.statusCode`;
- incoming call provisional state и idempotent explicit answer/reject;
- `IncomingCallReadinessGate` на основном `asyncio` loop с cancellable/stale policy;
- адаптация `CallRuntimeWiring` к существующему `ApplicationRuntime.ready/warmup` без передачи PCM или больших текстов через
  Dispatcher;
- deterministic unit/integration tests и повтор registered FreeSWITCH/Baresip C4.

### Не входит

- новый SIP stack, новый PBX, PRACK/100rel policy, early-media audio или multi-call scaling;
- изменение LLM/RAG/ASR/TTS компонентов и их существующих warmup stages;
- автоматический fallback на direct URI, CPU, другую модель или обычный GIL runtime;
- полный внешний launcher/production service.

### Protected baseline

- `SipMediaAdapter` владеет PJSUA2 call и локальной protocol reaction;
- `ApplicationRuntime` владеет aggregate readiness через существующий `warmup_report`;
- `CallRuntimeWiring`/gate владеет только процедурным main-loop handoff и pending-admission lifecycle;
- Dispatcher/FSM получает `CALL_STARTED` и `CALL_ANSWERED`, но не отвечает на `180`/`200` в native callback;
- аудио и текст остаются direct data-plane edges; в control plane идут только компактные typed events/commands;
- один звонок, PCMU/8 kHz/mono, target free-threaded CPython.

## 4. Source-map и write-set

| Область | Файл/компонент | Текущее поведение | Целевое поведение | Write-set |
|---|---|---|---|---|
| SIP answer | `src/sip_bot/sip_media/adapter.py` | `CallOpParam(True)` даёт target `statusCode=0` и abort | Explicit `CallOpParam()` + `statusCode`; incoming 180, public 200/503 | SIP answer/context helpers и связанные event details |
| SIP contract | `src/sip_bot/sip_media/protocol_events.py` | Таблица описывает обычный INVITE 200, но не provisional admission | Typed local reply для provisional `180` | Reply value/helper only |
| Readiness gate | `src/sip_bot/runtime_wiring.py` | `CALL_STARTED` сразу попадает в Dispatcher; нет pending warmup admission | Optional gate observes incoming event, schedules warmup, answers/rejects only after completion | New gate class and wiring hook |
| Runtime API | `src/sip_bot/runtime.py` | Sync `warmup()` only | Existing sync warmup remains authoritative; async caller runs it off-loop when supplied | Only minimal doc/API addition if required |
| Target probe | `tools/freeswitch_workshop/registered_call_probe.py` | Calls incoming path without readiness/180 assertions | Waits for 180, performs deterministic readiness handoff, then verifies 200/media | Probe assertions/evidence only |
| Tests | `tests/unit/`, `tests/integration/` | No explicit incoming provisional/answer contract | Status-code, ready/cold/failure/cancel/stale tests | New focused tests only |
| Owner docs | `docs/architecture.md`, `docs/technical-specification.md`, `docs/user-guide.md` | Warmup wording implies only pre-SIP admission | Distinguish provisional 180 from final 200 admission | Related additions, no duplicate component design |
| Governance | Map-009, C plan, registry/backlog | C4 blocked by B-009-C-004 | C1 corrective plan resolves blocker, C4 rerun promotion | Main executor only |

Protected from modification: accepted model/runtime baselines, Dispatcher/FSM semantics, media profile/PCMU conversion,
existing successful outgoing gates, historical evidence and unrelated presentation/workshop files.

## 5. Interaction topology и ownership

| Edge | Plane | Producer → consumer | Typed boundary | Owner/lifecycle |
|---|---|---|---|---|
| incoming INVITE → 180 | SIP protocol | PJSUA2 incoming callback → remote endpoint | `CallOpParam.statusCode=180` | SIP adapter, immediate/local |
| adapter → main loop | control | adapter event queue → wiring | `NormalizedSipEvent(CALL_STARTED)` with `answer_pending=true`, plus queued `PROTOCOL_REPLY(180)` | adapter emits; wiring observes outside callback |
| readiness request | control/procedural | gate → existing `ApplicationRuntime.warmup` | zero-argument callable returning `WarmupReport` | gate owns task; heavy sync action runs off-loop |
| ready result → adapter | control | gate → `SipMediaAdapter.answer()` | explicit `CallOpParam.statusCode=200` | adapter owns SIP response; gate owns admission decision |
| failed result → adapter | control | gate → `SipMediaAdapter.reject(503)` | explicit `CallOpParam.statusCode=503` | same pending call, no fallback |
| terminal SIP event → gate | control | adapter → gate | `REMOTE_CANCEL`/`REMOTE_HANGUP`/`CALL_ENDED`/failure | gate cancels task and drops stale completion |

The gate does not route audio, transcripts, RAG fragments or answer text. It is justified as a component only because it
owns an asynchronous pending-call lifecycle, cancellation and the final admit/reject decision.

## 6. Owner decisions

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Когда посылать 180? | Немедленно при принятии incoming INVITE, до readiness/warmup | Caller получает provisional response; native callback не ждёт AI | `resolved by owner instruction 2026-09-13` |
| Когда посылать 200? | Только после `runtime.ready` или успешного полного warmup existing stages | Media/dialogue admission начинается после readiness | `resolved by owner instruction 2026-09-13` |
| Что делать при cold runtime? | Запустить тот же aggregate warmup вне native callback/main-loop blocking | LLM/RAG/ASR/TTS прогреваются до 200 | `resolved by owner instruction 2026-09-13` |
| Что делать при warmup failure? | Явный `503 Service Unavailable`; direct fallback запрещён | Вызов не становится установленным | `resolved by existing Map-009 policy` |
| Что делать при remote terminal event во время warmup? | Локальная SIP reaction сохраняется; pending work cancel/stale-check; результат не отвечает и не открывает media | Закрытый call не получает поздний 200 | `resolved by architecture/lifecycle` |

Новых owner-review вопросов нет: статусы и failure policy наследуют уже принятые решения и прямое указание владельца.

## 7. Implementation slices и acceptance

| Slice | Действие | Исполнитель | Acceptance |
|---|---|---|---|
| C1-1 | Добавить explicit status-code helper, provisional 180, pending incoming state и public answer/reject | main executor | Fake contract доказывает `180`, `200`, `503`; ни один inbound answer path не создаёт `statusCode=0` |
| C1-2 | Добавить `IncomingCallReadinessGate` и wiring hook | main executor | ready/cold/failure/cancel/stale matrix; warmup не выполняется в native callback и не блокирует loop |
| C1-3 | Обновить registered workshop probe и deterministic evidence | main executor | 180 наблюдаем, после readiness приходит 200, registered call достигает media без abort |
| C1-4 | Запустить targeted/regression/target gate, обновить docs/map/registry/backlog | main executor | Relevant tests green, C4 promotion evidence, registry/backlog check pass |

Тяжёлый GPU inference из этого corrective plan не запускается в deterministic slices. Полный AI gate выполняется главным
executor отдельно при наличии свободной GPU; отсутствие свободной GPU требует wait/retry, а не CPU/fake pass.

## 8. Blocker register

| ID | Trigger | Что блокируется | Evidence/condition promotion | Status |
|---|---|---|---|---|
| `B-009-C1-001` | PJSUA2 explicit `CallOpParam.statusCode` не позволяет передать 180/200/503 даже в target binding | C1-1 и C4 | Native API evidence и отдельный protected-boundary review | `none until triggered` |
| `B-009-C1-002` | Existing `ApplicationRuntime.warmup` нельзя безопасно вызвать off-loop без изменения accepted AI/native ownership | C1-2 | Reproducible thread/runtime evidence и owner review | `none until triggered` |
| `B-009-C1-003` | Remote terminal event не может be observed/cancelled before warmup completion | C1-2/C4 | Target protocol trace proving unavoidable race | `none until triggered` |
| `B-009-C1-004` | Registered C4 still aborts or fails media after corrective answer path | Map-009 closeout | Fresh sanitized target evidence after corrective pass | `none until triggered` |

Ошибки реализации/теста в текущем write-set не являются blocker и требуют corrective pass. Child plan не закрывается
до повторения затронутых tests и target evidence.

## 9. Required evidence and closeout

Обязательны:

- deterministic fake-PJSUA trace с порядком `180 → warmup → 200`;
- ready path без warmup и cold path с warmup;
- failed warmup → `503`, no `200`, no direct fallback;
- cancellation/terminal during warmup → no late answer/media and no unhandled task;
- target registered FreeSWITCH/Baresip C4 с `exit_code=0`, no PJSIP assertion, PCMU/8 kHz/mono media evidence;
- targeted и full relevant regression на host/target runtime по применимости;
- обновлённые C4 blocker handoff, Map-009, C plan, architecture, technical specification, user guide, registry и backlog;
- `python tools/check_document_registry.py` и `python tools/check_task_backlog.py` после Markdown changes.

Closeout status is `complete` only after all slices and acceptance pass. If a category-4 API/environment gap is proven,
status is `blocked` with concrete evidence and promotion condition. Partial/foundation status is forbidden.

## 10. Execution closeout — 2026-09-13

Все четыре slices закрыты. Реализовано и проверено:

- `SipMediaAdapter` отправляет на входящий `INVITE` явный `180 Ringing`, а финальные `200 OK` и `503 Service
  Unavailable` создаются через явный `CallOpParam.statusCode`; ошибочный `CallOpParam(True)` удалён из inbound answer path;
- `IncomingCallReadinessGate` наблюдает `CALL_STARTED` после provisional reply, выполняет aggregate `warmup` через
  `asyncio.to_thread`, пропускает уже готовый runtime, отвечает `200` только после готовности, при ошибке отвечает `503`,
  а при terminal event отменяет или отбрасывает устаревший результат;
- wiring не блокирует native callback или основной `asyncio` loop тяжёлым прогревом; media/data plane и Dispatcher не
  получили новых обходных границ;
- registered FreeSWITCH/Baresip target probe повторён после corrective pass: [`registered-call-r7.json`](../../artifacts/implementation/009-optional-sip-registration/009-C/registered-call-r7.json).

Evidence target gate `r7`:

- exit code `0`, статус `pass`, FreeSWITCH `1.10.12`, patched free-threaded CPython `3.14.7t`, `py_gil_disabled=1`,
  `gil_enabled_at_finish=false`;
- все проверки pass: registration/auth, входящий registered call, `180` до `200`, media start, `PCMU/8000/mono`,
  sanitised evidence;
- `ingress_dropped_overflow=0`, `egress_dropped_overflow=0`, `egress_underruns=0`, `callback_errors=0`;
- профиль вызова получен из `pjmedia.stream_info`: `ptime=20 ms`, `frame_size=160 samples`, `frame_bytes=320`.

Contract/regression evidence:

- `python -m pytest tests/unit/test_incoming_answer_readiness.py tests/unit/test_sip_media.py tests/integration/test_runtime_wiring.py tests/integration/test_map005_protocol_media.py -q` — `28 passed`;
- `python -m pytest -q` — `183 passed, 5 skipped`;
- `python tools/check_document_registry.py` — `PASS` (`actual=65`, `registry_rows=65`, missing/extra/duplicates `0`);
- `python tools/check_task_backlog.py` — `PASS` (`12` unique tasks);
- `git diff --check` — `PASS`.

The target probe uses an explicit deterministic readiness handoff after observing `180`; actual cold-start aggregate GPU
warmup is covered by the gate's ready/cold/failure/cancel tests and is intentionally not repeated as a second heavy target
run in this corrective closeout. The production launcher must provide the same `is_ready`/`warmup` callbacks; a `200` before
that gate remains invalid. Historical `registered-call-r2.json` is retained as the original blocker evidence.
