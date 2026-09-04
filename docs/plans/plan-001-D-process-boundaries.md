# Plan-001-D: синтез process/thread boundaries и control/data plane

Уровень: `child plan`  
Статус исполнения: `complete`  
Родительская карта: [Map-001](plan-001-deadline-feasibility.md)  
Зависимости: закрытые `001-A`, `001-B`, `001-C` и все применимые `001-C1`–`001-C4`  
Следующий map-gate: `M-G4 feasibility closeout` через `001-E`

Owner review принят 2026-08-27. План исполнен 2026-08-27; фактический результат и все сводные артефакты находятся в
[`001-D evidence root`](../../artifacts/feasibility/001-D/closeout.md). Синтез не запускает runtime и не меняет
component evidence: он фиксирует только подтверждённые входами process/thread и control/data boundaries.

## 1. Цель и проверяемый результат

Цель — после закрытия `001-A`–`001-C` свести независимые результаты среды, runtime и native compatibility в одну
проверяемую карту исполнения. Синтез должен показать:

- для каждого реально проверенного компонента статус `pass`, `pass_with_isolation` или `fail`;
- допустимую process boundary и, только если это доказано, thread/task boundary внутри процесса;
- владельца каждого control-plane события, команды, data-plane канала и lifecycle операции;
- где payload идёт напрямую между producer и consumer, а где допускается только control metadata;
- какие решения закрыты evidence, какие требуют owner decision и какие передаются в `001-E` или следующий plan;
- baseline register без выбора кандидата «на глаз» и без превращения отсутствующего evidence в `pass`.

Результат исполнения — отдельный evidence root `artifacts/feasibility/001-D/` с индексом источников, матрицей
process/thread boundaries, картой control/data plane, черновиком baseline register, реестром gaps и closeout.
Сам `001-D` не создаёт runtime-код и не закрывает media/test-stand plan.

## 2. Применимые документы и извлечённые правила

| Источник | Извлечённое правило | Влияние на `001-D` | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan обязан иметь scope, source-map/write-set, owner review, audits, slices, отдельный blocker register, evidence, deferred policy и closeout | Все эти блоки являются обязательными; карта не считается исполнением | APG audit и closeout этого файла | Любой обязательный блок отсутствует или boundary утверждена без evidence |
| [`plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md) | `001-D` зависит от `001-C1`–`001-C4` и сводит их результаты перед `001-E` | Не запускать D по одному map-level описанию C | A–C closeout index и owner decisions | Любой зависимый child plan не закрыт или не имеет reproducible evidence |
| [`requirements.md`](../requirements.md) | MVP локальный, один русский SIP-разговор, PCMU, context, barge-in, transfer; внешние сервисы и запись аудио вне scope | Boundary map сохраняет demo invariants и не расширяет scope | Requirements-to-evidence mapping | Предложенная граница требует cloud, real PBX, audio recording или multi-session |
| [`architecture.md`](../architecture.md) | Dispatcher владеет control plane; audio/text payload идут по data plane напрямую; закрытие канала отбрасывает stale result | D фиксирует ownership и transport semantics, но не вводит новый канал | Architecture invariant audit + component evidence | Payload должен проходить через Dispatcher или callback ждёт AI |
| [`technical-specification.md`](../technical-specification.md) | Main process — latest stable free-threaded CPython >= 3.14; PCMU 8 kHz mono; native incompatibility изолируется отдельным process | Только evidence `001-B`/`001-C*` открывает main/isolation label | Runtime/import/operation/lifecycle records | GIL включён в main process или isolation выбрана без решения владельца |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | Dialogue Manager владеет FSM и semantic SIP commands; LLM возвращает structured decision | LLM/inference boundary не получает SIP-доступ | Structured action and owner mapping | LLM или свободный helper меняет SIP/FSM напрямую |
| [`ADR-002`](../decisions/ADR-002-llm-model-selection.md) | LLM shortlist proposed; structured output, VRAM, latency и cancellation должны быть измерены | D принимает только exact candidate/runtime из C3 evidence и owner review | C3 evidence + decision record | Модель или runtime выбран без сопоставимого результата |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Проверяются `Py_GIL_DISABLED` и `sys._is_gil_enabled()` до/после import и operation; automatic GIL enable — failure | Process boundary не выводится из filename или import-only probe | B/C GIL stages и operation evidence | Нет фактического GIL/lifecycle evidence или main process включает GIL |
| [`001-A`–`001-C`](plan-001-A-environment-baseline.md) | Каждый child имеет собственный write-set, evidence root и owner-gated hand-off | D только читает их closeout и индексирует provenance | Child closeout, path ownership, evidence index | D переписывает child evidence или подменяет open blocker общей строкой |

## 3. Граница задачи

```text
Цель:
  Синтезировать доказанные process/thread boundaries и control/data plane для выбранных кандидатов после A–C.

Входит:
  Приём и проверка A–C closeout; нормализация статусов; process/thread matrix;
  карта control/data plane; baseline register; owner review; gaps, blockers и hand-off в 001-E.

Не входит:
  Запуск probes, установка/сборка пакетов, выбор не проверенного кандидата, реализация runtime,
  Dispatcher/FSM/SIP/media/AI-кода, новый IPC/facade/adapter, media/test-stand и end-to-end demo.

Protected baseline:
  latest stable free-threaded CPython >= 3.14 в main process; несовместимый native runtime только в явно зафиксированном отдельном процессе;
  Dispatcher владеет control plane; audio/text payload не проходят через Dispatcher;
  PCMU 8 kHz mono, один разговор, локальный fake operator и отсутствие записи аудио.

Предположения о рабочем дереве:
  На drafting stage меняется только этот plan-file. Existing dirty worktree и pre-existing evidence не переписываются.
  Отсутствующий evidence считается gap, а не разрешением на предположение.

Зависимости и внешние сервисы:
  Только локальные evidence roots A–C и owner decisions. Реальные PBX, cloud API и внешняя операторская инфраструктура
  не требуются и не могут появиться в этом плане.
```

## 4. Source-map, write-set и запрещённые изменения

### 4.1. Source-map

| Область | Источник | Текущее состояние | Целевое состояние для D | Действие |
|---|---|---|---|---|
| Environment | `001-A`, `artifacts/feasibility/001-A-environment-baseline/` | Environment foundation закрыт 2026-08-27 | Подтверждённые OS, source placement, GPU/disk и dependency facts | Читать closeout и ссылаться на конкретные evidence IDs |
| Runtime | `001-B`, `artifacts/feasibility/001-B/` | CPython `3.14.7t`, Ubuntu/WSL2 и disabled GIL подтверждены 2026-08-27 | Фактическая stable CPython version, GIL stages и concurrency result | Принять только reproducible runtime evidence |
| Native compatibility | `001-C`, `001-C1`–`001-C4`, child evidence roots | C1/C2/C4 — `pass` в проверенных main-process путях; C3 — `pass_with_isolation` через local HTTP IPC | На каждый компонент один status, candidate ID, process boundary и evidence link | Сверить disjoint roots, команды, версии, exit code и failure reason |
| Process/thread model | `docs/architecture.md`, C operation/lifecycle evidence | C3 isolation через owner-approved local HTTP IPC подтверждена; callback/thread affinity и часть channel boundaries остаются открытыми | Матрица `main/isolated/undecided` и `thread/task/undecided` с обоснованием | Не интерпретировать общую архитектуру как runtime evidence |
| Control plane | `docs/architecture.md`, ADR-001, A–C lifecycle evidence | Ownership нормативно описан, component callback facts открыты | Таблица event/command owner, producer, consumer, wait policy и cancel path | Проверить BYE/callback responsiveness и отсутствие ожидания AI |
| Data plane | `docs/architecture.md`, C operation/lifecycle evidence | Direct channels нормативно описаны, concrete channel boundaries не выбраны | Таблица payload, producer, consumer, format, boundedness, close/stale policy | Оставить `undecided`, если format/close/IPC не доказаны |
| D outputs | `artifacts/feasibility/001-D/` | Созданы и проверены 2026-08-27 | `evidence-index.md`, `process-thread-boundary-matrix.md`, `control-data-plane-map.md`, `baseline-register-draft.md`, `unexpected-gaps.md`, `closeout.md` | Передать evidence и deferred gaps в `001-E` |

### 4.2. Write-set

Фактический write-set execution stage D: только `artifacts/feasibility/001-D/**`; этот plan-file изменяется отдельно
только при owner-approved plan/document synchronization.

Зарезервированный write-set будущего execution stage:

- `artifacts/feasibility/001-D/**` — только сводные evidence, индексы и closeout этого child plan;
- при owner-approved document synchronization — только конкретные owner-documents, названные в closeout, после отдельного
  review; D не получает право молча менять `roadmap.md`, `architecture.md`, `technical-specification.md`, ADR,
  `task-backlog.md` или `document-registry.md`;
- никакие C1–C4 roots и файлы A/B не являются write-set D.

### 4.3. Запрещённые изменения

- Любой runtime/source/config/test code, `config/constants.py`, SIP/FSM/AI adapter или test stand.
- Перезапись `001-A`, `001-B`, `001-C`, `001-C1`–`001-C4`, их raw outputs или evidence roots.
- Создание shared global queue, facade, compatibility bridge, startup-only path или нового IPC protocol.
- Назначение main process, thread, task, process isolation или IPC boundary при `missing`, `fail` или `undecided` evidence.
- Запуск fallback-кандидата до первичного `fail` и письменного owner decision.
- Использование CPU-only, Docker-only или другого SIP/AI стека как скрытой замены protected baseline.
- Удаление, переименование или «очистка» pre-existing файлов и dirty worktree.

## 5. Audit владельца поведения и парадигмы реализации

`001-D` не добавляет публичный runtime-алгоритм. Его deliverable — evidence-backed document capability; свободные
функции, меняющие FSM, SIP state, channel generation, route или transfer outcome, в этом плане не создаются.

| Поведение/capability | Владелец | Почему это owner | Допустимая парадигма | Запрет |
|---|---|---|---|---|
| State transitions и semantic SIP commands | `Main Dispatcher / Dialogue FSM` | Только он владеет состоянием разговора и проверкой structured action | Метод/операция owner-объекта с scoped cancellation и observability | Helper или inference service не меняет FSM/SIP напрямую |
| SIP signaling, media callbacks и обязательный BYE response | `SIP adapter` | Это граница протокольного runtime и его callback lifecycle | Adapter/service component; конкретный thread affinity только по evidence | Dispatcher не ждёт AI; D не создаёт новый adapter |
| PCM/RTP media channels | `Media ingress/egress` и владелец соответствующего bounded channel | У канала должны быть producer, consumer, format, close и stale policy | Channel capability/service boundary | Аудио через Dispatcher или общий mutable buffer |
| ASR/LLM/TTS operation и cancellation | Соответствующий inference/audio service из C1–C4 | Component owns native lifecycle, resource usage and cancellation | Runtime/service object с scoped dependency | Свободная функция с hidden global runtime |
| Evidence normalization | `001-D` evidence index | Это не продуктовая semantics и не channel ownership | Pure transformation возможна только для immutable records | Не использовать pure helper как обход архитектурной границы |

Если для process isolation потребуется отдельный IPC owner, это не «временный helper»: такой owner, контракт и lifecycle
фиксируются через unexpected gap, owner review и отдельный plan/ADR до исполнения.

## 6. Owner-review решения

Статус этого файла — execution result `pass`; ниже зафиксированы вопросы, которые нельзя закрыть общими архитектурными
словами, и результаты их проверки.

| ID | Вопрос | Предлагаемое правило до review | Последствие | Статус |
|---|---|---|---|---|
| `OR-D-001` | Закрыты ли `001-A`, `001-B`, `001-C` и `001-C1`–`001-C4` полным evidence? | Проверить child closeouts и индекс как часть D execution | D открывается только при наличии необходимых входов | `resolved as execution check` |
| `OR-D-002` | Какие C-результаты допускают `main process`? | Синтезировать по фактическим GIL/import/operation/lifecycle evidence | `pass_with_isolation` не считать main-process result | `resolved as engineering task` |
| `OR-D-003` | Какова thread/task affinity каждого callback/operation? | Вывести только из evidence и фактического API; неизвестное оставить `undecided` | Недоказанная affinity блокирует соответствующий hand-off | `resolved as evidence task` |
| `OR-D-004` | Нужна ли process isolation и какой IPC нужен? | Определить по результатам C-планов; isolation не выбирать автоматически. Новый IPC/архитектурный boundary передать на owner review только при фактической необходимости | Возможен отдельный IPC plan/ADR по gap protocol | `resolved as conditional gap rule` |
| `OR-D-005` | Нужны ли изменения owner-documents? | Определить по фактическому finding и синхронизировать с владельцем соответствующего документа | D не является владельцем runtime-факта | `resolved as documentation-process task` |
| `OR-D-006` | Как классифицировать любой `fail`/missing baseline? | Оставить `fail`/`blocked`, не превращать в fallback; replacement/isolation обсуждать только если finding этого требует | `001-E` отражает остаточный gap | `resolved as closeout rule` |
| `OR-D-007` | Можно ли открыть `001-E`? | Да после acceptance D и закрытия обязательных входов; решение фиксируется в hand-off | Иначе hand-off остаётся `blocked` | `resolved as gate check` |

## 7. Process invariant audit

Execution audit завершён; его evidence index и closeout находятся в `artifacts/feasibility/001-D/`. Это pass только
для synthesis boundary, не для full integration или production readiness.

- D является узким synthesis slice после A–C и не объединяет component smoke с интеграцией.
- `001-C1`–`001-C4` исполняются и закрываются последовательно согласно `001-C`; D читает их результаты, а не
  конкурирует за runtime/GPU.
- Каждый boundary claim имеет source evidence ID, command, version, stdout/stderr, exit code и owner decision reference.
- Relевантные A–C evidence отделены от нерелевантных e2e, RAG, MOS-CQ и production claims.
- Факт среды/runtime/component имеет одного owner-документа; D хранит ссылку и synthesis, а не дублирует нормативное
  требование.
- Никакой date/deadline не разрешает ослабить acceptance или добавить fallback.
- Deferred evidence не создаёт локальных `skip`/`xfail`; status `deferred` остаётся незакрытым до promotion.
- Registry/backlog audit выполняется после owner-approved document synchronization; результат фиксируется в closeout и
  не подменяет component evidence.

## 8. Architecture invariant audit

| Инвариант | Что D обязан получить от evidence | Если доказательства нет |
|---|---|---|
| Dispatcher владеет control plane и Dialogue FSM | ADR-001/architecture mapping и отсутствие прямого SIP-доступа у LLM | `undecided`, blocker `B-001D-004` |
| SIP/media callback не ждёт ASR/LLM/TTS/report и BYE обрабатывается немедленно | C1 callback/BYE operation evidence с bounded wait | Нельзя утвердить callback boundary |
| Audio и крупный text payload идут по data plane напрямую | Channel/operation evidence и payload ownership | Не придумывать queue/IPC; gap |
| Закрытие канала отбрасывает stale producer, channel не переиспользуется | C operation/lifecycle/cancel evidence или явное следующее test gate | Boundary остается `undecided` |
| Только authoritative final ASR меняет FSM и разрешает TTS | Architecture/technical contract; provisional path не имеет action authority | Speculative result не может быть promoted |
| Speculative path не делает transfer/hangup/irreversible action | C/architecture decision или явный scope cut | Запретить claim о speculative boundary |
| Barge-in отменяет playback, новый ответ не смешивается со старым | TTS cancellation/lifecycle evidence | D не открывает answer-path hand-off |
| LLM возвращает ограниченный structured decision | C3 structured JSON evidence и ADR-001 validation owner | LLM action boundary `blocked` |
| PCMU 8 kHz mono сохраняется | C1/media result и technical specification | Нельзя считать media baseline закрытым |
| Main process остаётся no-GIL; incompatible native runtime изолирован | B/C GIL stages и process decision | `fail` или owner-gated isolation, не `pass` |
| Нет real external service, PBX logic или audio recording | Scope review и evidence path inventory | Изменение scope требует owner review |
| Каждый channel имеет owner, close, cancel и re-close semantics | Component lifecycle evidence и direct owner mapping | Следующий plan/blocker |

### 8.1. Шаблон boundary matrix

| Компонент | Process candidate | Thread/task candidate | Control plane | Data plane | Evidence ID | Claim status |
|---|---|---|---|---|---|---|
| SIP adapter/media callbacks | `main` / `isolated` / `undecided` | `thread` / `asyncio` / `undecided` | events, commands, BYE response | PCMU/PCM direct path | from C1 | `open until evidence` |
| Dispatcher/Dialogue FSM | `main` | serialized owner execution | all semantic transitions | no payload transit | architecture + future contract | `protected invariant` |
| ASR/VAD/Transcript Assembler | `main` / `isolated` / `undecided` | `thread` / `task` / `undecided` | final/endpoint/cancel events | PCM and partial/final text | from C2 + next plan | `open until evidence` |
| LLM/retrieval | `main` / `isolated` / `undecided` | `task` / `thread` / `undecided` | structured result/cancel | final text/context direct to owner | from C3 | `open until evidence` |
| TTS/playback | `main` / `isolated` / `undecided` | `task` / `thread` / `undecided` | approve/cancel/close | approved text and PCM direct | from C4 | `open until evidence` |

`undecided` — корректный результат синтеза, если нужное evidence ещё не получено. Он не является скрытым fallback и
не открывает implementation.

## 9. Implementation slices

### D-001 — Intake и gate proof A–C

Проверить owner-approved closeout каждого dependency, целостность ссылок и отсутствие пересечения write-set. Результат:
`input-evidence-index.md` и список входных gaps. При любом missing field D останавливается.

### D-002 — Process/thread boundary synthesis

Для каждого C1–C4 сопоставить candidate ID, status, GIL state, operation, cancellation, lifecycle, process boundary и
только доказанную thread/task affinity. `pass_with_isolation` получает отдельную строку с process owner и фактическим
IPC status; неизвестное получает `undecided`.

### D-003 — Control/data plane map

Свести event/command table Dispatcher, SIP adapter и Dialogue FSM с payload table для PCM, ASR text, approved answer и
retrieval context. Для каждого канала зафиксировать owner, format, boundedness, close, stale-result и cancellation.
Новый канал или IPC contract не проектируется; нехватка факта уходит в gap.

### D-004 — Reconciliation, blocker и fallback review

Сверить synthesized matrix с protected invariants, map gates, ADR и roadmap cuts. Разделить `pass`, `pass_with_isolation`,
`fail`, `blocked`, `deferred`; ни один красный результат не меняется заменой assertion. Заполнить baseline draft и
unexpected-gap records.

### D-005 — D closeout и hand-off в E

Сформировать evidence index, process/thread matrix, control/data map и closeout. Передать в `001-E` только записи с
конкретными ссылками и owner decisions. Если хотя бы один обязательный contour не имеет baseline или owner-approved
fallback/isolation, hand-off имеет статус `blocked`.

## 10. Отдельный blocker register этого child plan

Этот register не заменяет registers `Map-001` и A–C. Статусы ниже отражают выполненный D-synthesis; residual deferred
items не маскируются строкой `none`.

### D-001

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001D-001` | Нет closeout/evidence хотя бы одного A–C dependency | Весь D | project owner | Dependency closeout + input index | `resolved for current inputs; verify in D-001` |

### D-002

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001D-002` | C result lacks import/operation/GIL/cancel/lifecycle fields или process boundary | Boundary matrix и baseline register | project owner + component owner | C structured evidence | `resolved for current inputs; verify normalization in D-002` |
| `B-001D-003` | `pass_with_isolation` не имеет owner decision о process/IPC boundary | Promotion в main/isolation baseline | project owner | C3 closeout, ADR-002 и architecture owner decision | `resolved 2026-08-27; existing HTTP IPC accepted` |

### D-003

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001D-004` | Синтез требует нового queue, adapter, facade, IPC или payload через Dispatcher | Control/data map и зависимый plan | project owner | `unexpected-gaps.md` | `not triggered` |
| `B-001D-005` | Не доказаны close/stale/cancel semantics канала | Channel boundary promotion | component owner | `unexpected-gaps.md` и следующий integration plan | `deferred by scope` |

### D-004/D-005

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001D-006` | Boundary claim противоречит ADR/architecture или вводит silent fallback | D closeout и `001-E` | project owner | Owner decision/ADR or gap record | `not triggered` |
| `B-001D-007` | Нет command/version/stdout/stderr/exit code/path для записи evidence | Доверие к synthesis | executor + project owner | Evidence index completeness | `resolved for D; source commands retained in A–C roots` |
| `B-001D-008` | Обязательный contour имеет `fail`/`blocked` без owner-approved path | `001-E` и M-G4 | project owner | Baseline/fallback/isolation decision | `not triggered` |

Если после execution фактических blockers для отдельного slice нет, его register получает явную строку `none` с
evidence link. Общее `none` без slice-level проверки недействительно.

## 11. Test plan и evidence

В D runtime-проверки не запускаются и пакеты не устанавливаются: D использует уже завершённые команды и manifest из
A–C. Синтез не изобретает новый общий benchmark и не перепроверяет GPU.

### 11.1. Evidence contract

Каждая строка synthesis index обязана содержать:

- `source_plan` и стабильный `evidence_id` из A/B/C;
- exact command, working directory, runtime/version, candidate ID и process boundary;
- stdout, stderr, exit code, timestamp и raw-file path;
- operation, cancellation, close/re-close, stale-result и GIL observations, если они заявлены;
- `status`: `pass`, `pass_with_isolation`, `fail`, `blocked` или `deferred`;
- owner decision reference и следующий gate.

### 11.2. Проверочные lanes

| Lane | Что проверяет | Acceptance |
|---|---|---|
| Input integrity | A–C closeout, paths, hashes/versions и write-set | Все обязательные inputs доступны и attributed |
| Boundary reconciliation | Один component status и process label на contour | Нет claim без evidence; `undecided` явно виден |
| Control/data audit | Event/command/payload ownership и no-Dispatcher payload | Payload direct, control semantic, wait/cancel policy записаны |
| Protected baseline | latest stable free-threaded CPython >= 3.14/no-GIL, PCMU, one call, local fake operator, no audio recording | Нарушение остаётся blocker |
| Handoff completeness | Output files, owner decisions и next gate | `001-E` может открыть только evidence-backed hand-off |

## 12. Deferred evidence semantics

Deferred evidence не является успешной проверкой и не может скрываться local `skip`/`xfail`. До promotion запись должна
содержать все поля `evidence_id`, `task`, `scope`, `owner`, `gap`, `promotion` и ссылку на фактический результат.

| evidence_id | task | scope | owner | gap | promotion |
|---|---|---|---|---|---|
| `DEFER-001D-THREAD-001` | `TASK-001 / следующий media-test-stand plan` | Integrated callback/thread/task affinity и bounded BYE во время component operation | project owner + media owner | C operation evidence не доказывает интегрированную scheduling/lifecycle boundary приложения | Owner-approved media/test-stand plan, отдельный SIP/RTP smoke, сохранённые logs и close/re-close evidence; затем ссылка из M-G4 |
| `DEFER-001D-IPC-001` | `TASK-001 / C3 HTTP IPC contract` | Проверка достаточности существующего bounded HTTP IPC для request/result, cancellation и close между main и isolated process | project owner + isolated-component owner | C3 уже имеет рабочую локальную HTTP boundary; D не должен придумывать новый IPC protocol | Зафиксировать existing contract и его владельцев в D; новый plan/ADR нужен только при обнаружении конкретного gap |
| `DEFER-001D-CHANNEL-001` | `TASK-001 / media/test-stand` | Реальное stale-producer suppression и idempotent close нового канала в сквозном стенде | project owner + channel owner | A–C component smoke может быть локальным и не доказывать сквозной generation lifecycle | Contract/state-machine test и SIP/RTP evidence с channel IDs, close/re-close и stale result; promotion в обычный regression lane |

Если gap относится к обязательному process/data boundary, D status остаётся `blocked`, даже если deferred запись создана.

## 13. Реестр fallback и упрощений

| Что | Основание | Ограничение | Где закрывается | Статус |
|---|---|---|---|---|
| Native component в отдельном процессе | ADR-003 и Map-001 допускают isolation | Только после C evidence и owner decision; GIL-enabled module не импортируется в main | D decision + существующий C3 HTTP IPC contract | `C3 selected; owner-approved` |
| Speculative LLM/retrieval не входит в deadline-critical path | Roadmap section 13.3 | Финальное решение только по authoritative final ASR; provisional result не меняет FSM/TTS | Answer-path plan | `approved scope cut, not a boundary result` |
| VAD + fixed soft/hard endpoint вместо semantic detector | Roadmap/Map-001 | Не уменьшает требования к final ASR, cancel и barge-in | Speech pipeline plan | `approved scope cut` |
| Curated KB и local fake operator | MVP deadline scope | Не заменяет local retrieval/transfer evidence | Knowledge/media plans | `approved scope cut` |
| CPU-only, Docker-only, alternate SIP/AI candidate или hidden compatibility bridge | Не согласованы | Не превращаются в pass или fallback | Owner review + new plan/ADR | `forbidden` |

В этом drafting step новые fallback и intentional simplification не вводятся.

## 14. Unexpected gap protocol

При обнаружении неучтённой архитектурной работы зависимый slice немедленно останавливается и создаётся запись:

```text
gap_id:
Обнаруженный gap:
Затронутые документы и компоненты:
Какое evidence отсутствует или противоречит:
Почему текущий plan нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Владелец решения:
Нужен ли новый ADR/roadmap/plan-file:
Условие снятия blocker:
```

Классическими unexpected gaps для D являются новый IPC protocol, shared queue, facade/adapter, необходимость менять
Dispatcher ownership, GIL включение в main process или расхождение C evidence. До review запрещены fallback, startup-only
path, ослабление assertion и изменение protected document.

Результат execution: unexpected architecture gap, требующий остановки D, не обнаружен; известные ограничения вынесены
в `unexpected-gaps.md` как deferred или non-blocking findings.

## 15. Execution и closeout

### Условия начала

1. `001-A` имеет environment closeout.
2. `001-B` имеет reproducible latest stable free-threaded CPython/no-GIL closeout и открывает `M-G2`.
3. `001-C` и `001-C1`–`001-C4` имеют owner review, disjoint evidence roots и component closeout.
4. Для каждого обязательного контура есть `pass` или owner-approved `pass_with_isolation`; `fail` остаётся blocker.
5. Этот plan получил отдельный owner review; текущий файл сам по себе его не заменяет.

### Порядок исполнения

`D-001 → D-002 → D-003 → D-004 → D-005`; новый component smoke не добавляется. Все boundary claims получили ссылку
на evidence, а owner decision для C3 — явную запись.

### Closeout acceptance

- `artifacts/feasibility/001-D/evidence-index.md` разрешает открыть каждый claim без устного контекста;
- matrix имеет ровно одну строку на компонент, явный process status и `thread/task` status или `undecided`;
- control/data map не проводит audio/large text через Dispatcher и имеет owner/format/close/cancel policy;
- main/isolation boundary подтверждена evidence или явно оставлена blocked; неизвестность не названа fallback;
- blocker registers закрыты evidence/owner decision или hand-off имеет статус `blocked`;
- deferred records заполнены требуемыми полями и не замаскированы `skip`/`xfail`;
- fallback/simplification register отражает только owner-approved cuts;
- closeout указывает фактические команды, версии, pre-existing failures, out-of-scope findings и следующий `001-E`.

### Handoff

`001-D` передаёт `001-E` evidence-backed baseline draft, boundary matrix, control/data map, residual blockers и owner
decisions. D имеет статус исполнения `complete`; synthesis result — `pass`. `001-E` не открывается автоматически и требует собственного owner review. M-G4 этим
closeout ещё не закрывается.
