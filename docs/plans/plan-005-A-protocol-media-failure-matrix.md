# Plan 005-A: матрица SIP/media-протокола и отказов

Уровень: `child plan`  
Идентификатор: `005-A`  
Статус owner review: `accepted — owner review принят 2026-09-04`  
Статус исполнения: `complete`  
Родительская карта: [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md)  
Дата подготовки: `2026-09-04`

## 1. Цель и проверяемый результат

Проверить уже реализованный SIP/media owner на обязательные протокольные реакции и отказовые пути, не допуская
ожидания Dispatcher, ASR, LLM, TTS или отчёта. Проверка должна дать воспроизводимую матрицу событий, media counters,
timestamps, exit codes и raw Baresip evidence для одного локального вызова.

Минимальный результат: `SipMediaAdapter` отвечает на применимые SIP-события локально, публикует нормализованное
прикладное событие после протокольной реакции, сохраняет PCMU/8 kHz/mono contract, корректно закрывает media и
повторное закрытие идемпотентно. Live-прогоны дополнительно оставляют исходные Baresip `enc`/`dec` WAV.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Один локальный русский SIP-разговор, PCMU, локальные AI и локальный test peer; runtime бота не пишет аудио, но test stand сохраняет запись | Не добавлять PBX/multi-call; live peer recording идёт в evidence | Baresip live matrix и artifact manifest | Внешний сервис или bot-side recording |
| [`architecture.md`](../architecture.md) | SIP protocol reaction принадлежит SIP/media adapter; Dispatcher получает compact application event; media payload идёт напрямую | Callback не ждёт AI, новый delivery-owner не создаётся | Event timing и ownership audit | Ожидание AI или новый semantic owner |
| [`technical-specification.md`](../technical-specification.md) | PCMU/8000/mono, per-call negotiated profile, protocol events не зависят от модели | Не подменять negotiated profile и не использовать global defaults | SDP/profile и RTP evidence | Codec/profile mismatch |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Map-I revision 21 — authoritative typed edges и cycles; SIP reactions локальны | Проверяются существующие `poll`, `dispatch_events`, `next_ingress_frame`, `enqueue_egress_frame` без изменения edge | Contract/source audit | Фактический output не принимается consumer |
| [`plan-001-S-voip-test-stand.md`](plan-001-S-voip-test-stand.md) | Approved local Baresip peer/fake operator, PCMU and loopback | Используется только копия approved config; закрытый plan не меняется | Peer version/config/codec evidence | Peer contract не воспроизводится |
| [`development-guidelines.md`](../development-guidelines.md) | Узкий slice, typed-first, existing owner, no silent fallback, corrective pass и binary closeout | Исправлять только adapter/test write-set; красный тест сначала классифицировать и повторить | APG audit, targeted/regression/contract | Category 4 gap или неполное evidence |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan обязан иметь source-map, owner audit, invariants, blocker register, test/evidence и closeout | Этот файл самодостаточен и не разрешает execution до owner review | Структурный audit | Отсутствует обязательный блок |

Уже принятые решения повторно не переоткрываются: один вызов, Baresip peer, PJSUA2/PJMEDIA patches, PCMU, control/data
plane, no-GIL runtime и отсутствие PBX являются protected baseline карты 5.

## 3. Граница задачи

**Входит:**

- deterministic protocol matrix для `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume, RTP timeout и
  media failure;
- проверка SIP reaction во время представленной долгой операции без запуска тяжёлого inference;
- PCMU/profile и двусторонний RTP smoke на актуальном Baresip peer;
- idempotent close/re-close, close во время ingress/egress и нормализация application events;
- включение Baresip `sndfile` на per-run копии peer config и сохранение raw `enc`/`dec` WAV для live checks;
- corrective fixes только в существующем SIP/media owner или тестах, если это ошибка текущего write-set.

**Не входит:** новый SIP/RTP стек, изменение `Map-002-I`, PBX, новый protocol owner, изменение PJSUA2 patches,
второй вызов, model inference, stereo post-processing (его владелец — `005-D`), production recording/retention.

**Protected baseline:** закрытые `001-*`, `002-*`, `Map-002-I revision 21`, `config/constants.py`, approved Baresip
candidate и существующие typed contracts.

**Предположения:** target execution выполняется в Ubuntu/WSL на CPython 3.14.7t; live peer доступен; перед запуском
проверяется свободное место не менее 20 ГБ. Baresip recording — внешний test-stand artifact, не runtime state бота.

## 4. Source-map и write-set

| Область | Файл/символ | Текущее состояние | Действие в plan | Write-set |
|---|---|---|---|---|
| SIP adapter | `src/sip_bot/sip_media/adapter.py` | Live lifecycle/protocol baseline pass | Менять только доказанный defect | Только затронутые existing methods |
| Protocol contracts | `src/sip_bot/sip_media/protocol_events.py` | Normalized events существуют | Не менять типы; исправление только при доказанном defect | Existing symbols only |
| Target integration tests | `tests/integration/test_map005_protocol_media.py` | Нет | Создать deterministic/live matrix | Новый файл |
| Probe | `tools/map005_protocol_probe.py` | Нет | Создать bounded peer scenario runner | Новый файл |
| Per-run stand config/evidence | `artifacts/implementation/002-system-testing-and-demo-readiness/005-A/` | Нет | Копия config, raw logs, enc/dec WAV, manifests | Только собственный evidence root |

Запрещено менять `tests/integration/conftest.py`, существующий `tools/j4_*`, закрытые evidence roots, `config/`, ADR,
registry/backlog и чужие child-plan files. Общие документы синхронизирует только главный executor после handoff.

## 5. Interaction topology и propagation

Используются следующие существующие границы:

```text
Baresip peer ⇄ SIP/RTP ⇄ SipMediaAdapter
SipMediaAdapter.poll()/dispatch_events()
  → normalized protocol/application event → Dispatcher/DialogueFSM/CallSession
SipMediaAdapter.next_ingress_frame()/enqueue_egress_frame()
  ⇄ direct PcmFrame data plane
```

`BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume и media failure проверяются в том же call scope, где
может выполняться длительная операция. Протокольный ответ не проходит через Dispatcher. Новый typed edge не вводится;
при несовпадении фактического output и consumer работа останавливается как APG gap, а не маскируется адаптером.

## 6. Audit владельца поведения и парадигмы реализации

Владелец протокольного поведения — существующий `SipMediaAdapter`, потому что он владеет PJSUA2 endpoint/call,
transaction reaction, negotiated media и media lifecycle. Тестовый probe только подаёт stimulus и читает evidence.
Новый helper не получает право менять SIP/FSM state. Baresip `sndfile` владеет только записью test-peer media, а не
runtime бота; stereo derivative не принадлежит этому plan.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Нужен ли новый SIP/media owner или новый protocol stack? | Нет, используется существующий adapter и approved Baresip peer | Только existing methods и tests | `resolved by Map-005` |
| Допустима ли запись live media? | Да, только на стороне Baresip test peer в evidence; bot runtime не пишет | Raw `enc`/`dec` обязательны для live checks | `resolved by owner decision 2026-09-04` |
| Принят ли этот child plan к execution? | Групповой owner review child plans `005-A`–`005-D` принят 2026-09-04 | Отдельное согласование этого файла не является дополнительным gate | `resolved by grouped owner review` |

Новых предметных owner decisions нет; третий пункт является обязательным APG execution gate, а не повторным вопросом о
закрытом архитектурном решении.

## 8. Process invariant audit

| Инвариант | Materialized action | Evidence |
|---|---|---|
| Узкий slice/no silent scope | Только protocol/media matrix и raw stand recording | Source-map и diff audit |
| Typed-first/owner behavior | Используются существующие typed events/profile/frame методы | Contract tests и source audit |
| Control/data plane | SIP reactions/control events отделены от PCM | Event trace и payload audit |
| No hidden fallback | Не запускается альтернативный SIP stack/codec | Candidate manifest и failure record |
| Corrective pass | Красный тест классифицируется, исправляется в scope, повторяется targeted+regression+contract | Raw output и rerun |
| Binary closeout | Только `complete` или `blocked` | Closeout и blocker register |

## 9. Architecture invariant audit

- SIP response на `BYE`/`CANCEL`/`OPTIONS`/`re-INVITE`/`UPDATE` не зависит от AI и Dispatcher.
- `PcmFrame` остаётся на direct data plane; Dispatcher получает только compact normalized events.
- Один call scope, negotiated PCMU/8000/mono и явное close/re-close сохраняются.
- Baresip recording не становится частью `ContextStore`, `report.md` или `data/dialogues/<call_id>/`.
- Existing PJSUA2/PJMEDIA patches и CPython 3.14.7t не заменяются.

## 10. Implementation slices

### A1 — deterministic protocol matrix

Создать deterministic fake/stub сценарии для обязательных SIP methods, долгой операции, повторного close и event
ordering. Acceptance: каждая применимая реакция имеет observed response/event, terminal transitions идемпотентны,
не возникает ожидания AI.

### A2 — target Baresip protocol/media run

Запустить один сценарий на approved peer, проверить SDP-derived profile, PCMU/RTP counters и protocol logs. Acceptance:
peer/version/codec/profile/exit code сохранены; отсутствующие stimulus явно отмечены как deferred, а не pass.

### A3 — live recording evidence

Запустить per-run копию peer config с `sndfile`, проверить появление полного `enc` и `dec` WAV от media start до cleanup,
их metadata и mapping относительно peer role. Acceptance: raw files не пусты, не обрезаны без объяснения, hashes и
recording manifest сохранены. Объединённый stereo файл создаётся в `005-D`.

### A4 — corrective pass и handoff

При красном результате определить category 1–4, исправить только approved write-set для category 1/2, повторить
затронутые tests и regression/contract suite. Handoff содержит diff, commands, exit codes, evidence, blockers и
следующий шаг; главный executor повторно проверяет всё перед closeout.

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец | Evidence/condition promotion | Статус |
|---|---|---|---|---|---|---|
| `B-005-A-001` | весь plan | Child owner review не пройден | Любая реализация/execution | project owner | Этот файл и review message | `resolved 2026-09-04` |
| `B-005-A-002` | A2/A3 | Baresip peer или `sndfile` не даёт воспроизводимый live stimulus/recording | Live protocol/recording claim | main executor/project owner | Raw logs, version/config, owner-approved promotion | `none until triggered` |
| `B-005-A-003` | A1–A4 | Требуется новый/изменённый boundary, SIP owner, codec или patch | Зависимый slice и propagation | project owner | APG gap + updated map/ADR | `none until triggered` |
| `B-005-A-004` | A2–A4 | Красный тест остаётся category 4 после corrective pass | Affected acceptance и map closeout | project owner | Raw output, correction attempts, blocker condition | `none until triggered` |

Низкое место на диске ниже 20 ГБ и занятая GPU проверяются перед релевантным запуском и повторяются после изменения
внешнего состояния; сами по себе они не превращаются в архитектурный blocker.

## 12. Test plan и evidence

```text
Target runtime: /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
Deterministic: python -m pytest -q tests/integration/test_map005_protocol_media.py
Target/live: python tools/map005_protocol_probe.py --scenario matrix --output-root <new-005-A-root>
Regression: python -m pytest -q tests/unit tests/contract tests/integration
```

Evidence обязан содержать command, executable, version, stdout/stderr, exit code, SIP event trace, media profile,
RTP counters, raw Baresip peer log, raw `enc`/`dec` files, recording manifest и status каждой проверки. Skipped test не
является pass.

## 13. Fallback/deferred register

| Что | Причина | Ограничение | Promotion | Статус |
|---|---|---|---|---|
| Deterministic protocol stimulus вместо внешнего live stimulus | Baresip не обязан воспроизводить каждый failure path | Явно маркируется deterministic; live claim не делается | Отдельный воспроизводимый peer evidence | `allowed by Map-005` |
| Alternative SIP stack/codec/fallback | Не нужен | Запрещён без нового owner review | Новый plan/ADR | `none` |
| Stereo derivative | Не является SIP protocol behavior | Выполняется только `005-D`, raw tracks сохраняются | D evidence | `deferred to 005-D` |

## 14. Execution report и closeout

Execution date: `2026-09-04`.

Фактический diff ограничен новым deterministic test, live probe и собственным evidence root; existing SIP/media owner,
approved PJSUA2/PJMEDIA patches, contracts и закрытые документы не менялись.

Acceptance:

- A1: `tests/integration/test_map005_protocol_media.py` — `5 passed` на target `CPython 3.14.7t`;
- A2/A3: `map005_protocol_probe.py` — `status=pass`, `OPTIONS` получил `SIP/2.0 200 OK`, call answered,
  remote `BYE` observed, active call cleared, `callback_errors=0`;
- negotiated profile: `PCMU`, payload `0`, `8000 Hz`, mono, `ptime=20 ms`, `160` samples / `320` PCM bytes per frame;
- media evidence: `25` ingress и `25` egress frames, `8000` bytes в каждом направлении, без dropped frames;
- raw Baresip recording: [`dec.wav`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/live-20260904-r1/recordings/dump-2026-09-04-13-58-04-dec.wav) — `0.400 s`,
  [`enc.wav`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/live-20260904-r1/recordings/dump-2026-09-04-13-58-04-enc.wav) — `0.520 s`, оба `PCM16/8000 Hz/mono`, hashes
  и manifest находятся в [`map005-a-live.json`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/live-20260904-r1/map005-a-live.json);
- target unit/contract regression: `104 passed, 2 skipped`; skipped tests не относятся к A live claim и не выдаются за pass;
- no corrective source change was required; deterministic, target and live evidence согласованы.

Live stimulus, который Baresip не воспроизвёл в этом bounded run (`CANCEL` до ответа, peer-originated hold/resume и RTP
timeout/transport failure), оставлен deferred. Их deterministic callback/normalization coverage есть в A1; live claim по ним
не делается. `egress_underruns=25` в этом запуске объясняется отсутствием TTS producer в protocol-only probe и передан в
`005-C`, не классифицирован как A failure.

Evidence и команды: [`live-20260904-r1`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/live-20260904-r1/), [`deterministic-results.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/deterministic-results.md),
[`commands.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/commands.md), [`closeout.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-A/closeout.md).

`005-A` получает `complete` только если весь scope и обязательные tests доказаны собственным evidence. При category-4
blocker статус только `blocked`; частичные статусы запрещены. Закрытый child передаёт результат в Map-005 и `005-D`,
но не объявляет карту 5 закрытой.
