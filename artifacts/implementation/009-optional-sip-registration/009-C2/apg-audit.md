# APG-аудит Map-009 / 009-C2

Дата: `2026-09-13`  
Исполнитель проверки: main executor

## Объём

Проверены операционные документы и источники правил, относящиеся к corrective execution:

- `docs/architectural-planning-gate.md`;
- `docs/development-guidelines.md`;
- `docs/requirements.md`, `docs/architecture.md`, `docs/technical-specification.md`;
- `docs/documentation-process.md` и `docs/user-guide.md`;
- `docs/plans/plan-009-optional-sip-registration.md`;
- `docs/plans/plan-009-C-freeswitch-workshop-integration.md`;
- `docs/plans/plan-009-C2-runtime-readiness-coordination.md`;
- принятые recording boundaries Map-005 (`plan-005-A`, `plan-005-D`, `plan-005-E`).

## Materialized rules и результат применения

| Правило | Как применено | Evidence |
|---|---|---|
| APG требует self-contained plan, source-map, write-set, invariants, blocker register, tests и binary closeout | `009-C2` дополнен corrective slice `R4.1`; closeout оставлен в плане, а map/parent/registry/backlog синхронизированы | plan `009-C2`, этот audit |
| Статус child plan может быть только `complete` или `blocked`; partial/foundation closeout запрещён | После R1–R4 был сохранён `in_progress`; `complete` выставлен только после R4.1, R5 и финальных проверок | plan `009-C2` §11 |
| Ошибка реализации/fixture сначала исправляется в approved write-set; owner blocker регистрируется только при category-4 gap | Несовпадение call id исправлено event-driven composition; отсутствие recording path исправлено через уже принятый Baresip `sndfile`; API/PBX gap не возник | r15, blocker register |
| Event Bus остаётся control-only; PCM/recording не проходят через Dispatcher | `sndfile` работает на Baresip test peer; приложение не сохраняет audio и не добавляет audio edge | r15 peer log, source-map |
| Между component boundaries используется фактический typed lifecycle; composition создаётся по реальному `CALL_STARTED.call_id` | Буферизован `CALL_STARTED`, создан `call-in-0`, событие воспроизведено один раз | r15 `registered-j4-full-live.json` |
| Baresip recording path из Map-005 даёт raw `enc`/`dec`, stereo строится производным helper-ом с явным mapping и padding policy | Registered peer получает per-run `sndfile` и `snd_path`; raw tracks сохранены, stereo/manifest проверены | `recordings/raw/`, `conversation-stereo.wav`, `recording-manifest.json` |
| Heavy GPU gate выполняется главным executor в target free-threaded runtime | Full registered r15 запущен target CPython `3.14.7t`; `gil_enabled=false`; GPU evidence получен main executor | r15 runtime/readiness evidence |

## Scope и protected baseline

- Изменения ограничены runtime readiness coordinator, registered rehearsal harness, Baresip test-peer recording,
  focused tests и связанными operational documents.
- PJSUA2/PJMEDIA protocol/media implementation, Dispatcher/FSM semantics, accepted direct-URI path, AI components и
  исторические artifacts не переписывались.
- `ApplicationRuntime.start()` не прогревает модели; cold fallback использует одну runtime-scoped single-flight
  readiness operation, а не call-scoped warmup.
- Запись принадлежит Baresip test peer и является artifact стенда; runtime-состояние и `report.md` остаются текстовыми.

## Проверки

Команды, выполненные в target Ubuntu-24.04:

```text
python -m py_compile tools/freeswitch_workshop/registered_full_rehearsal.py tools/j4_full_live_gate.py
python -m pytest -q tests/unit/test_runtime_readiness.py tests/unit/test_incoming_answer_readiness.py tests/unit/test_registered_recording.py tests/unit/test_map005_recording.py
```

Результаты:

- target compile: `pass`;
- focused tests: `12 passed`;
- clean-start registered full-AI r15: `pass`, exit code `0`;
- readiness: `ready`, cold aggregate warmup `26 303.471 ms`;
- registered call: actual `call-in-0`, `180 → readiness → 200`;
- media: `PCMU/8000/mono`, `ptime=20 ms`, peer RTP `6292 transmit / 1850 receive`;
- media error counters: `callback_errors=0`, `egress_underruns=0`, overflow/closed drops `0`;
- scenario checks: follow-up, barge-in, unknown-answer/offer-transfer, operator transfer, report и
  `stereo_recording_present` — `true`;
- recording: raw `enc`/`dec`, stereo `125.84 s`, metadata/hash/mapping audit — `pass`.

## Blockers и closeout

`B-009-C-006` закрыт target evidence после перехода на фактический incoming call id. `B-009-C2-004` и
`B-009-C2-005` также закрыты r15. Новых protected-boundary, external API или owner-review gaps не обнаружено.

`Map-009`, `009-C` и `009-C2` имеют бинарный статус `complete`. Deferred остаются только заранее определённые
production concerns: внешний PBX, TLS/SRTP, secret vault, multi-call, production launcher и scaling.
