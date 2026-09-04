# Plan: S — локальный VoIP/RTP тестовый стенд

Уровень: `child plan` (implementation-support plan)  
Статус исполнения: `complete`  
Stand result: `pass`  
Родительская карта: [`Map-001: Scope freeze и feasibility к демонстратору 25 сентября`](plan-001-deadline-feasibility.md)  
Связанный component plan: [`001-C1: PJSUA2/PJMEDIA`](plan-001-C1-sip-pjsua2-pjmedia.md)  
Родительская roadmap: [`roadmap.md`](../roadmap.md)  
Дата подготовки: 2026-08-27  
Owner review: `2026-08-27` — план принят к исполнению в рамках распоряжения продолжать работу.

## Цель и проверяемый результат

Создать воспроизводимый локальный SIP/RTP стенд, который разблокирует peer-dependent проверки `001-C1` и позднее
позволит тестировать один демонстрационный разговор без внешнего PBX или реального оператора.

Стенд должен доказать отдельными сценариями:

1. установление, answer и normal hangup одного SIP-вызова;
2. реальный RTP-медиапуть с PCMU, 8 kHz, mono;
3. отправку `BYE` во время контролируемой длительной операции на стороне DUT;
4. перевод на второго локального SIP-участника, представляющего fake operator.

Итогом является не production PBX и не часть SIP-адаптера бота, а набор локальных peer-процессов, конфигураций,
сценариев и evidence, которыми можно повторно запускать acceptance-проверки.

## Границы

Входит:

- локальный SIP peer для проверки PJSUA2/PJMEDIA;
- отдельный локальный peer fake operator;
- SIP/RTP loopback, контролируемые паузы, остановка потока и отправка `BYE`;
- PCMU как обязательный codec, без скрытого codec fallback;
- сценарий transfer на fake operator;
- deterministic media fixture, генерируемый или передаваемый без записи пользовательского разговора;
- команды запуска, конфигурации, версии и текстовое evidence.

Не входит:

- реальный PBX, внешняя SIP-регистрация или облачные сервисы;
- изменение production SIP adapter, Dispatcher, Dialogue FSM или data/control-plane контрактов;
- запись пользовательского аудио;
- больше одного параллельного разговора;
- production-grade NAT, security, HA и нагрузочное тестирование.

## Source-map и candidate policy

### Источники фактов

- [`requirements.md`](../requirements.md) — один локальный разговор, PCMU и отсутствие аудиозаписи;
- [`architecture.md`](../architecture.md) — SIP/media ownership, direct data plane и control-plane границы;
- [`technical-specification.md`](../technical-specification.md) — конфигурационные константы и timing boundaries;
- [`001-C-native-compatibility-map.md`](plan-001-C-native-compatibility-map.md) — порядок component gates и запрет
  автоматического fallback;
- [`001-C1-sip-pjsua2-pjmedia.md`](plan-001-C1-sip-pjsua2-pjmedia.md) — конкретные peer-dependent acceptance lanes.

### Основной candidate

Первый и единственный candidate стенда — **Baresip**, установленный из доступного stable-пакета Ubuntu 24.04 LTS.
Точная версия, набор модулей и способ запуска фиксируются в execution evidence; версия не зашивается в этот plan заранее.
Baresip используется только как внешний к DUT test peer и fake operator, а не как новый основной VoIP-стек проекта.

Если Baresip не даёт наблюдаемый SIP/RTP/PCMU сценарий, execution останавливается с concrete blocker. SIPp, Asterisk,
Sofia-SIP, PJSUA CLI или самописный peer не запускаются автоматически: каждый такой вариант требует отдельного owner
decision и candidate record.

## Write-set

Разрешённый write-set этого execution:

```text
docs/plans/plan-001-S-voip-test-stand.md
artifacts/feasibility/001-S-voip-test-stand/
tools/feasibility/voip_test_stand_probe.py
```

Разрешены также локальные установки пакетов и конфигурации вне репозитория в user-owned WSL paths, если они нужны для
воспроизводимого стенда и записаны в evidence. Не разрешены изменения `src/`, `config/`, production tools,
`docs/architecture.md`, `docs/technical-specification.md`, ADR и чужих evidence roots без отдельного docs sync.

Стенд не хранит SIP credentials, если они не нужны локальному loopback; если временные credentials окажутся
необходимы, они создаются в WSL по стандартной процедуре, хранятся вне репозитория, а их файл добавляется в `.gitignore`.

## Owner-review решения

| ID | Вопрос | Решение | Последствие | Статус |
|---|---|---|---|---|
| `S-DEC-001` | Какой test peer запускать первым? | Baresip из Ubuntu 24.04 LTS stable package | Другие кандидаты не запускаются автоматически | `resolved by current plan` |
| `S-DEC-002` | Нужен ли внешний PBX? | Нет; вызов и fake operator полностью локальны | Реальная PBX-логика остаётся вне scope | `resolved by requirements` |
| `S-DEC-003` | Какой codec обязателен? | PCMU, 8 kHz, mono | Negotiation другого codec не считается pass | `resolved by requirements` |
| `S-DEC-004` | Можно ли писать аудио? | Нет; допустим только deterministic in-memory/generated fixture | Пользовательские записи не появляются в evidence | `resolved by requirements` |
| `S-DEC-005` | Что делать при провале Baresip? | Остановить стенд и провести owner discussion | Fallback не запускается молча | `resolved by process policy` |
| `S-DEC-006` | Может ли стенд менять production contracts? | Нет | Он только создаёт внешний peer и evidence | `resolved by scope` |

## Узкие execution slices

### S-S0 — preflight и candidate freeze

Проверить WSL2/Ubuntu baseline, доступность свободного места, наличие Baresip в stable package index, версию и
необходимые модули. Зафиксировать `git status --short`, команды, package provenance и exact write-set.

Acceptance: candidate manifest заполнен, Baresip запускается в отдельном локальном процессе, peer endpoints не
используют внешний SIP/PBX.

### S-S1 — минимальный SIP lifecycle

Запустить два локальных peer endpoint-а или peer и DUT, установить один вызов, принять его, завершить normal hangup и
зафиксировать SIP event sequence. Ошибки регистрации не маскировать повторным запуском другого стека.

Acceptance: `INVITE → answer → connected → BYE → cleanup` наблюдаемы, без user audio recording.

### S-S2 — PCMU/RTP loopback

Настроить PCMU 8 kHz mono и deterministic media fixture. Зафиксировать SDP/payload type, RTP counters, направление и
факт доставки в DUT media path. Остановка потока и отсутствие пакетов должны быть различимы в evidence.

Acceptance: реальный PCMU path подтверждён, codec mismatch не превращён в pass.

### S-S3 — BYE во время занятой обработки

Во время заранее заданного long-operation window отправить `BYE` со стороны peer. Зафиксировать timestamps отправки,
получения callback/сигнала, ответа и cleanup. Стенд не определяет production upper bound: он только делает сценарий
воспроизводимым; сопоставление с ориентиром 200–500 ms остаётся ответственностью `001-C1`/latency plan.

Acceptance: сценарий воспроизводимо создаёт `BYE` в нужном окне и позволяет C1 проверить, что callback не ждёт AI.

### S-S4 — fake operator и transfer

Запустить второго локального peer как fake operator. Подтвердить отдельным сценарным вызовом, что перевод достигает
оператора, оператор принимает вызов, а исходный dialog/channel закрывается согласно C1 contract. Это не реализует
перевод в боте и не меняет SIP ownership.

Acceptance: transfer event sequence и cleanup имеют текстовое evidence.

### S-S5 — closeout

Собрать manifest, конфигурации без секретов, команды запуска, stdout/stderr, exit codes, event logs и blocker status.
Проверить document registry и task backlog после синхронизации документов. Обновить `001-C1` только owner-approved
docs sync-ом; не объявлять C1 pass только по успешному стенду.

## Blocker register

| ID | Slice | Trigger | Что блокируется | Статус |
|---|---|---|---|---|
| `S-B-001` | S0 | Baresip отсутствует в доступном stable package index или не запускается | Весь stand execution | `resolved 2026-08-27` |
| `S-B-002` | S0–S2 | Нельзя включить/доказать PCMU 8 kHz mono | PCMU и C1 S2 | `resolved 2026-08-27` |
| `S-B-003` | S1 | Нет наблюдаемого answer/hangup lifecycle | S1–S4 | `resolved 2026-08-27` |
| `S-B-004` | S3 | Нельзя воспроизводимо отправить BYE во время long operation | S3 и C1 S4 | `resolved 2026-08-27` |
| `S-B-005` | S4 | Baresip не позволяет воспроизводимо представить fake operator/transfer | S4 | `resolved 2026-08-27` |
| `S-B-006` | S0–S5 | Появился fallback, внешний сервис, запись аудио или изменение production contract без review | Текущий slice | `open by policy` |
| `S-B-007` | S0–S5 | Evidence неполно: нет версии, команды, exit code, event sequence или failure reason | Closeout | `resolved 2026-08-27` |

## Evidence contract

```text
artifacts/feasibility/001-S-voip-test-stand/
├── preflight.md
├── candidate-manifest.json
├── commands.md
├── lifecycle.json
├── pcmu.json
├── bye.json
├── transfer.json
├── evidence-index.md
├── redaction.md
└── closeout.md
```

Каждый JSON содержит `plan`, `candidate`, `runtime`, `stage`, exact `command`, `status`, `exit_code`, stdout/stderr,
event timestamps, blocker/stop condition и owner decision reference. `pcmu.json` дополнительно содержит negotiated
codec/payload type/sample rate/channels и counters. Аудиофайлы не создаются.

## Execution result — 2026-08-27

`S-S0`–`S-S5` выполнены с результатом `pass`. Полный closeout и structured evidence находятся в
[`artifacts/feasibility/001-S-voip-test-stand/closeout.md`](../../artifacts/feasibility/001-S-voip-test-stand/closeout.md).

| Slice | Result | Evidence |
|---|---|---|
| S-S0 preflight/candidate freeze | `pass` | `preflight.md`, `candidate-manifest.json` |
| S-S1 lifecycle | `pass` | `lifecycle.json` |
| S-S2 PCMU/RTP | `pass` | `pcmu.json`: PCMU/8000/1, RTP counters 201/200, DUT capture 200 frames / 64000 bytes |
| S-S3 remote BYE | `pass` | `bye.json`: 10 s busy fixture active, remote disconnect before local hangup, loopback interval 0.453 ms |
| S-S4 fake operator/transfer | `pass` | `transfer.json`, `transfer.operator.log` |
| S-S5 evidence/closeout | `pass` | `commands.md`, `evidence-index.md`, `redaction.md`, `closeout.md` |

Наблюдавшийся `501 Not Implemented` для self-registration ожидаем: стенд работает прямыми loopback SIP URI без
регистратора. Он не блокирует tested call paths. Fallback, внешний PBX и audio recording не использовались.

## Process and architecture audit

| Инвариант | Применение | Статус до execution |
|---|---|---|
| Dispatcher не является медиатранзитом | Стенд лишь передаёт media в DUT; он не встраивается в Dispatcher | `preserved and verified` |
| SIP callback не ждёт AI | S3 только генерирует timing scenario; проверка callback принадлежит C1 | `preserved and verified by bounded peer scenario` |
| Один channel и явное закрытие | Каждый test scenario имеет собственный process/context и cleanup | `required` |
| PCMU не подменяется | Codec mismatch блокирует acceptance | `preserved` |
| Нет внешнего PBX и recordings | Только loopback/fake operator и generated/deterministic fixture | `preserved` |
| Fallback не запускается молча | Один Baresip candidate; альтернативы требуют owner decision | `preserved` |

## Execution report / closeout template

```text
Plan: 001-S
Статус исполнения: complete | blocked
Stand result: pass | fail
Owner review: 2026-08-27

Candidate/version/modules:
Runtime:
Commands/evidence:
- S0:
- S1:
- S2:
- S3:
- S4:
- S5:

Acceptance:
- lifecycle:
- PCMU:
- BYE:
- transfer:

Blockers:
Resolved:
Open:
Fallback/recording/external PBX: none
Следующий шаг:
```

`pass` означает, что все четыре стендовых сценария доказаны. При `blocked` или `fail` C1 получает concrete blocker,
но альтернативный VoIP-stack не выбирается автоматически.
