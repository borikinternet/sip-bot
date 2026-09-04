# Plan-001-E: feasibility closeout и открытие следующего плана

Уровень: `child plan`  
Статус исполнения: `complete`  
Родительская карта: [Map-001](plan-001-deadline-feasibility.md)  
Зависимости: закрытые `001-A`–`001-D`, включая `001-C1`–`001-C4` и D evidence-backed synthesis  
Следующий переход: отдельно reviewed child plans Map-002 после закрытия `M-G4`

Owner review принят `2026-08-27`. E исполнен `2026-08-27`; owner review следующего implementation plan принят
`2026-09-02`. Итоговый пакет находится в [`artifacts/feasibility/001-E/`](../../artifacts/feasibility/001-E/), а
`M-G4` закрыт этим review.

Создание этого файла является только подготовкой closeout. Он не объявляет feasibility закрытой, не выбирает новые
компоненты и не разрешает media/test-stand implementation без фактического evidence, map-gate review и review
следующего плана.

## 1. Цель и проверяемый результат

Цель — после `001-D` закрыть feasibility-карту `Map-001` честным, воспроизводимым и проверяемым пакетом:

- полный evidence index с provenance каждого обязательного контура;
- map-gate matrix для `M-G1`–`M-G4` и child-level blockers;
- финальный baseline register с версиями, лицензиями, командами, process boundaries, latency/VRAM/CPU observations и
  explicit fallback/isolation decisions;
- отдельный blocker protocol, который не скрывает отсутствующие результаты и owner decisions;
- closeout с остаточными gaps, deferred evidence и reviewed следующим plan для media/test-stand.

`001-E` не выполняет новый candidate research. После closeout новые компоненты или режимы допускаются только если они
закрывают обязательный demo-flow или конкретный зафиксированный blocker и получили отдельный owner review.

Ожидаемый результат исполнения — `artifacts/feasibility/001-E/` с `evidence-index.md`, `map-gates.md`,
`blocker-register.md`, `baseline-register.md`, `closeout.md` и `next-plan-approval.md`. Это закрывает feasibility
handoff, но не объявляет production-ready и не закрывает media/test-stand implementation.

## 2. Применимые документы и извлечённые правила

| Источник | Извлечённое правило | Влияние на `001-E` | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Closeout обязан содержать фактические files/commands/results, blockers, deferred owners, next step и корректный статус | E не может заменить отсутствующее evidence claim-ом о готовности | Closeout audit | Нет evidence index, blocker register, deferred fields или reviewed next plan |
| [`plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md) | `001-E` зависит от D; M-G4 открывает отдельный media/test-stand plan только после baseline/closeout | E проверяет map gates, а не исполняет следующий этап | Gate matrix и E closeout | Нет D evidence, обязательного baseline или следующего plan, прошедшего plan review |
| [`roadmap.md`](../roadmap.md) | До 31 августа feasibility закрывает baseline; после closeout новые компоненты не исследуются без demo/blocker reason | E фиксирует freeze и запрет расширений | Baseline register + scope/freeze record | Новый компонент добавлен без обязательного-flow/blocker и owner decision |
| [`requirements.md`](../requirements.md) | Обязательны локальный русский один-звонок flow, context, barge-in, transfer и report; real external services/audio recording вне scope | E проверяет наличие feasibility path к обязательным контурам, не production quality | Requirements-to-evidence index | Обязательный contour отсутствует или scope нарушен |
| [`architecture.md`](../architecture.md) | Dispatcher/control plane отдельно от direct data plane; stale channel/cancel/lifecycle semantics обязательны | D map должен быть закрыт и проиндексирован, но E его не переписывает без decision | Architecture closeout audit | Boundary не доказана или требует молчаливого нового IPC/facade |
| [`technical-specification.md`](../technical-specification.md) | Latest stable free-threaded CPython >= 3.14, PCMU 8 kHz mono, local ASR/LLM/TTS, no audio recording, structured LLM action | Baseline register должен содержать эти protected facts либо blocker | Technical evidence mapping | Hidden default, cloud dependency, GIL main process или отсутствующий format result |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | Dialogue Manager валидирует structured LLM action и владеет SIP/FSM | E не принимает plain-text model result как control evidence | C3/D evidence + architecture audit | LLM boundary невалидируема |
| [`ADR-002`](../decisions/ADR-002-llm-model-selection.md) | LLM остаётся proposed до сопоставимой проверки; structured output, VRAM, latency и cancellation важнее карточки модели | E фиксирует ровно доказанный candidate/decision; не закрывает ADR-002 «на глаз» | C3 + D baseline records | Нет exact candidate/runtime/VRAM/latency evidence |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Main process no-GIL проверен фактически; incompatible native component — explicit isolated process | E индексирует GIL/import/operation and process decision | B/C/D evidence | Automatic GIL enable или isolation без owner decision |
| [`001-A`–`001-D`](plan-001-A-environment-baseline.md) | Child evidence disjoint, owner-gated, с command/version/stdout/stderr/exit code | E является reconciliation owner для map closeout, не владельцем raw evidence | Child closeout index | Raw evidence missing, conflicting or overwritten |

## 3. Граница задачи

```text
Цель:
  Закрыть feasibility Map-001, составить evidence index и map-gate decision, подготовить следующий plan.

Входит:
  Reconcile A–D evidence; baseline register; gate matrix; blocker protocol; deferred evidence register;
  fallback/simplification register; requirements/architecture/process audit; closeout и next-plan approval.

Не входит:
  Новые benchmark/candidate searches, установка пакетов, изменение runtime/source/config, реализация SIP/RTP стенда,
  Dispatcher/FSM/ASR/LLM/TTS, production packaging, real PBX, cloud service, audio recording и multi-call.

Protected baseline:
  latest stable free-threaded CPython >= 3.14/no-GIL в main process; explicit isolation для несовместимого native runtime;
  Dispatcher владеет control plane; direct audio/text data plane; PCMU 8 kHz mono;
  один русский локальный разговор, local curated KB/fake operator, context/report и отсутствие audio recording.

Предположения о рабочем дереве:
  A–D raw evidence принадлежит своим plans и read-only для E. Drafting write-set — только этот файл.
  Missing/conflicting evidence считается blocker; pre-existing failures и out-of-scope findings перечисляются явно.

Зависимости и внешние сервисы:
  Только локальные evidence roots и зафиксированные engineering decisions. Следующий plan остаётся отдельным артефактом.
```

## 4. Source-map, write-set и запрещённые изменения

### 4.1. Source-map

| Область | Источник | Текущее состояние | Целевое состояние E | Действие |
|---|---|---|---|---|
| Map gates | `plan-001-deadline-feasibility.md` | M-G1–M-G4 закрыты после owner review следующей карты | Явная строка condition/open/closed для каждого gate | Сверить child closeouts и owner decisions |
| Environment/runtime | `artifacts/feasibility/001-A-environment-baseline/`, `001-B/` | Environment и runtime foundation закрыты evidence | Indexed OS, GPU/disk, CPython/no-GIL provenance | Не переписывать raw evidence |
| Native candidates | `artifacts/feasibility/native-compatibility/C1..C4/` и C closeouts | Component evidence disjoint и owner-gated | Candidate matrix с status, boundary, license, command и failure reason | Только индексировать фактические файлы |
| D synthesis | `artifacts/feasibility/001-D/` | Boundary map принят и закрыт D execution | Reviewed process/thread/control/data map и residual gaps | Проверить D acceptance, не менять его silently |
| Requirements/architecture | `requirements.md`, `architecture.md`, `technical-specification.md`, ADR | Нормативные owner-documents | Requirement → evidence → status mapping и contradictions list | Owner review для любого фактического изменения |
| E outputs | `artifacts/feasibility/001-E/` | Созданы и проверены 2026-08-27, hand-off обновлён после review 2026-09-02 | Index, gate matrix, blocker register, baseline, closeout, next approval | Использовать пакет как закрытый feasibility hand-off |
| Next plan | `plan-002-mvp-media-and-speech-integration.md` и `Map-002-I` | Map-002 и Map-002-I созданы и reviewed 2026-09-02; child plans имеют отдельные gates | Отдельные Map-002 child plans с scope/evidence/gates | Не запускать child plan без собственного review |

### 4.2. Write-set

Фактический write-set execution stage: `artifacts/feasibility/001-E/**` и явно синхронизированные owner-documents,
названные в closeout; raw evidence roots A–D, code, tools, config и next-plan file не изменялись.

Зарезервированный write-set execution stage:

- `artifacts/feasibility/001-E/**` — только index, gate decisions, baseline, blocker protocol, closeout и next-plan approval;
- при owner-approved synchronization — ссылки или изменения только в owner-documents, названные closeout; E не меняет
  `roadmap.md`, `task-backlog.md`, `document-registry.md`, `architecture.md`, `technical-specification.md` или ADR молча;
- raw evidence roots A–D, code, tools, config и будущий next-plan file не являются write-set E.

### 4.3. Запрещённые изменения

- Подмена missing/failed evidence словами `verified`, `pass` или `baseline`.
- Новый candidate, runtime, dependency, fallback, compatibility bridge или IPC без отдельного owner-approved plan/ADR.
- Перезапись raw stdout/stderr, command, exit code, hashes и child closeout.
- Изменение process/thread/control/data boundary в D без нового evidence и review.
- Исполнение media/test-stand, SIP/RTP, FSM, AI, context/report или production работы в E.
- Тихое расширение demo-flow, реальный PBX/cloud/operator, запись аудио, multi-call или Docker-only bot.
- Безымянные local `skip`/`xfail`, suppression marker, сниженный assertion или подмена deferred evidence зелёным статусом.

## 5. Audit владельца поведения и парадигмы реализации

`001-E` не добавляет runtime behavior и не меняет product ownership. Его capability — документальное закрытие карты,
которым владеют project owner и executor в рамках plan governance; для этого не создаются public functions, service
objects, facade или adapter.

| Объект аудита | Владелец поведения | Парадигма | Что проверяет E | Запрет |
|---|---|---|---|---|
| Dialogue/FSM/SIP semantic behavior | Main Dispatcher / Dialogue FSM | Owner-object/service contract из architecture и ADR-001 | D mapping и отсутствие прямого LLM SIP access | Не реализовывать и не переопределять FSM в closeout |
| Channel/payload lifecycle | Component/channel owner | Bounded channel capability с close/cancel/stale semantics | Наличие D evidence и residual gap | Не вводить общий queue или новый payload bridge |
| Native process boundary | Component owner + project owner | Main process или explicit isolated service только по evidence | Связь C/GIL/operation result с D decision | Не выбирать boundary по convenience |
| Feasibility evidence reconciliation | Project owner / plan executor | Immutable record aggregation; pure normalization допустима только без product semantics | Provenance, status, gate and owner decision | Свободная функция не получает доступа к FSM/SIP/channel state |
| Next-plan ownership | Owner следующего plan | Отдельный child plan с собственным APG | Scope, dependency, acceptance и approval record | E не становится implementation owner следующего этапа |

Если closeout обнаружит, что для next plan нужен новый публичный алгоритм, facade, IPC или component owner, E фиксирует
unexpected gap и останавливает переход; он не создаёт временную функцию.

## 6. Owner-review решения

Статус исполнения этого файла — `complete`; owner review следующего implementation plan получен 2026-09-02.

| ID | Вопрос | Требуемое решение | Последствие | Статус |
|---|---|---|---|---|
| `OR-E-001` | Все A–D closeouts и raw evidence доступны, не противоречат и имеют provenance? | Проверить это по evidence index; missing остаётся blocker | Без этого E не закрывается | `resolved as closeout check` |
| `OR-E-002` | Закрыты ли M-G2 и M-G3? | Определить по фактическим runtime/component decisions; `fail` получает explicit path или остаётся blocked | M-G4 не открывается | `resolved as closeout check` |
| `OR-E-003` | Действительно ли D control/data map сохраняет protected architecture? | Проверить D map и открыть gap/ADR только при фактическом нарушении | Нельзя открыть media/test-stand при нарушении | `resolved as architecture audit` |
| `OR-E-004` | Есть ли baseline для SIP/media, ASR, LLM, TTS и fake operator? | Свести фактические `pass`/`pass_with_isolation`; fallback не придумывать | Нет baseline → closeout blocked | `resolved as evidence task` |
| `OR-E-005` | Какие deferred evidence остаются после feasibility? | Индексировать только фактические записи с `evidence_id`, task, scope, owner, gap, promotion | Closeout status отражает residual gap | `resolved as closeout task` |
| `OR-E-006` | Какой следующий plan открыть? | Подготовить отдельный media/speech integration plan package из roadmap; scope и acceptance должны быть описаны до его execution | Без созданного и отдельно reviewed plan следующий этап не начинается | `resolved as hand-off task` |
| `OR-E-007` | Какой финальный статус Map-001? | Вывести из acceptance и blockers; не объявлять `prod-ready` | Статус синхронизируется owner-документом | `resolved as closeout task` |

## 7. Process invariant audit

Execution audit завершён; планирование не подменяет component evidence, а E индексирует уже полученные результаты.

- E является reconciliation/closeout slice после D, а не новым benchmark или implementation slice.
- Каждый обязательный claim имеет source evidence ID, exact command, version/runtime, stdout/stderr, exit code и owner.
- `pass`, `pass_with_isolation`, `fail`, `blocked`, `deferred` и `out-of-scope` не смешиваются.
- Map-level gates не закрываются одной строкой E, если child-level blocker или owner decision ещё open.
- Факты требований, архитектуры и runtime остаются у owner-documents; E хранит index и ссылку.
- Pre-existing failures, unrelated dirty-worktree findings и out-of-scope задачи отделяются от обязательного demo-flow.
- Deadline не разрешает ослабить test/evidence contract или добавить hidden fallback.
- Deferred policy использует стабильный ID и promotion; local `skip`/`xfail` запрещены.
- Registry/backlog commands выполняются после owner-approved synchronization; результаты фиксируются в E closeout.

## 8. Architecture invariant audit

| Инвариант | Closeout evidence | Условие принятия | Если отсутствует |
|---|---|---|---|
| Dispatcher владеет control plane/FSM/SIP semantic commands | D map, ADR-001 mapping, structured C3 result | Нет прямого LLM/SIP пути | Blocker `B-001E-004` |
| SIP/media callback не ждёт AI/report и BYE responsive | C1/D lifecycle evidence или явный next-plan obligation | Callback/close policy наблюдаема | Проверка application contour deferred в Map-002 |
| Audio и крупный text payload идут direct data plane | D control/data map и channel ownership | Dispatcher не транзит payload | Проверка application contour deferred в Map-002 |
| Closed channel drops stale producer, no reuse, idempotent close | D evidence или deferred record с promotion | Не маскируется отсутствием integrated test | Deferred в Map-002; E не заявляет application integration |
| Only authoritative final ASR changes FSM and permits TTS | Architecture/technical contract + C2/D mapping | Provisional path не action-authoritative | Answer-path gate blocked |
| Speculative path no irreversible action | Roadmap cut или evidence-backed restriction | Transfer/hangup only via Dispatcher | Gap/owner decision |
| Barge-in cancels TTS and prevents mixed generations | C4/D cancellation evidence or next-plan evidence record | Feasibility claim отделён от future integration | Demo-path blocker |
| LLM structured decision and no SIP address control | C3 JSON/action evidence + ADR-001 | Dispatcher validates action/target | LLM baseline not closed |
| PCMU 8 kHz mono | C1/media evidence and technical mapping | Format explicit | SIP/media baseline blocked |
| Main process no-GIL; isolation explicit | B/C/D GIL and process evidence | No automatic GIL enable in main | Runtime/component blocker |
| Local-only one-call scope, no audio recording | Requirements/roadmap scope record | No real external service or recording claim | Scope gap |
| Channel owner/close/cancel/re-close exists | D matrix and lifecycle evidence | Every boundary has owner | Architecture closeout blocked |

E only confirms D’s map and records residual obligations. It does not promote a `deferred` integrated test to `pass`.

## 9. Implementation slices

### E-001 — Evidence intake and requirements index

Собрать ссылки на A–D evidence, child closeouts и owner decisions. Для каждого обязательного demo requirement создать
строку `requirement → evidence → status → owner → gap/promotion`. Missing or conflicting records блокируют E.

### E-002 — Map-gate matrix

Проверить `M-G1`–`M-G4`, включая child-level dependencies, exact open/closed condition, evidence link и owner decision.
Нельзя закрыть M-G2/M-G3 только потому, что документ создан; M-G4 открывается лишь после D acceptance.

### E-003 — Baseline and blocker closeout

Сформировать финальный baseline register и отдельный blocker register. Для каждого contour записать version/license,
command/dependencies, process boundary, IPC note, latency/VRAM/CPU observations, status и refusal reason. Красный или
неполный result сохраняется как blocker.

### E-004 — Deferred/fallback and unexpected-gap review

Проверить каждую deferred record на обязательные поля, promotion и owner; отделить approved roadmap cuts от fallback.
Любое новое architectural gap оформить по протоколу и остановить зависимый переход.

### E-005 — Next-plan hand-off

Подготовить next-plan approval для media/test-stand: scope, protected baseline, dependencies, acceptance, evidence root,
blocker protocol и owner. E не создаёт сам next-plan и не начинает его execution.

### E-006 — Feasibility closeout

Сохранить `closeout.md` с фактическими датами, командами, версиями, statuses, pre-existing failures, out-of-scope
findings, deferred owners, residual risks, map status и ссылкой на approved next plan.

## 10. Отдельный blocker register этого child plan

Этот register является отдельным от Map-001 и A–D. Он не закрывается отсутствием сообщения об ошибке; после каждой
проверки должна быть evidence/owner decision или явный статус `open`.

### E-001/E-002

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001E-001` | A–D closeout/evidence missing, overwritten или conflicting | Весь E и M-G4 | project owner | `evidence-index.md`, child closeouts, raw paths | `resolved` |
| `B-001E-002` | M-G2 или M-G3 не имеют условий закрытия и owner decision | M-G4 и next plan | project owner | `map-gates.md` + decision record | `resolved` |

### E-003

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001E-003` | Full application contour lacks integrated runtime evidence | Feasibility completeness / map-ready status | executor/project owner | Component baseline есть; application contours явно deferred в следующий implementation map и не входят в scope E | `resolved as explicit out-of-scope hand-off` |
| `B-001E-004` | D map не доказывает process/thread/control/data ownership или нарушает invariant | M-G4 и next implementation | project owner + architecture owner | D evidence + gap/ADR; violation не обнаружено | `resolved for map synthesis` |

### E-004

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001E-005` | Deferred record не содержит `evidence_id/task/scope/owner/gap/promotion` | Closeout status | plan owner | Deferred register + promotion plan | `resolved` |
| `B-001E-006` | Fallback/simplification не имеет owner, scope или corrective path | Closeout и dependent plan | project owner | Fallback register + decision | `resolved` |
| `B-001E-007` | Обнаружен новый adapter/facade/IPC/architecture boundary | Зависимый slice | project owner | Unexpected gap record, ADR/new plan | `not triggered` |

### E-005/E-006

| ID | Триггер | Что блокируется | Владелец решения | Evidence/решение | Статус |
|---|---|---|---|---|---|
| `B-001E-008` | Нет конкретного reviewed next plan и его acceptance/evidence root | M-G4 hand-off | executor/project owner | `next-plan-approval.md`; Map-002 и Map-002-I owner review accepted 2026-09-02 | `resolved 2026-09-02` |
| `B-001E-009` | Нет command/version/exit code/raw output или audit result для closeout claim | Доверие к feasibility result | executor + project owner | E evidence index и executed audits | `resolved` |
| `B-001E-010` | Дата/дедлайн пропущены без owner decision по scope или status | Map status и next gate | project owner | Roadmap/backlog decision | `not triggered` |

Если конкретный slice после execution не имеет blockers, register получает отдельную строку `none` с evidence link.
`none` не закрывает соседний slice и не заменяет open child blocker.

## 11. Test plan и evidence

На drafting stage не выполнялись tests, audits, registry/backlog checks и candidate commands. В execution stage E
проверил полноту уже полученного evidence, а не запускал новый component smoke.

### 11.1. Evidence index contract

Каждая запись должна содержать:

- `evidence_id`, `source_plan`, artifact path и owner;
- exact command, working directory, runtime/version, candidate/version/license;
- stdout path, stderr path, exit code, timestamp, hash/digest при наличии;
- observed status, process boundary, thread/task claim, cancellation/lifecycle result;
- map gate, requirement, decision reference, gap и promotion condition;
- классификацию `pre-existing`, `out-of-scope`, `deferred` или `required`.

### 11.2. Closeout lanes

| Lane | Проверка | Acceptance |
|---|---|---|
| Evidence integrity | Paths, command, version, raw output, exit code и status | Каждая запись воспроизводима или явно blocked |
| Requirement coverage | 1-call, Russian, PCMU, partial/final ASR, answer, context, barge-in, unknown/transfer, report/no-audio | Каждая обязательная граница имеет evidence или blocker |
| Runtime/process | Фактическая stable CPython version >= 3.14, no-GIL, native imports/operations, main/isolation decisions | Main-process claim не содержит automatic GIL enable |
| Architecture | Dispatcher, direct payload, channel lifecycle, authoritative final ASR, structured LLM action | D map согласован, no silent new boundary |
| Map gates | M-G1–M-G4 and child plans | Gate status grounded in evidence/owner decision |
| Owner hand-off | Next plan scope, acceptance, evidence root, owner and approval | Следующий plan можно открыть без устного контекста |

### 11.3. Минимальный финальный evidence package

Под `artifacts/feasibility/` должны быть доступны или явно проиндексированы:

- `scope-freeze.md`;
- `environment.md` и `001-A` inventory;
- `001-B/runtime-probe.json` и reproducibility records;
- C1–C4 component roots и `candidate-matrix.md`;
- D process/thread matrix, control/data map и baseline draft;
- E `baseline-register.md`, `evidence-index.md`, `map-gates.md`, `blocker-register.md`, `closeout.md` и
  `next-plan-approval.md`.

Отсутствующий файл может быть заменён только явной ссылкой на owner-approved другой path; silent rename не допускается.

## 12. Deferred evidence semantics

Deferred evidence — это именованный gap с владельцем и promotion, а не зелёный тестовый исход. Каждая запись обязана
содержать буквально следующие поля: `evidence_id`, `task`, `scope`, `owner`, `gap`, `promotion`. Local `skip`/`xfail`
не создаются и не учитываются как закрытие.

| evidence_id | task | scope | owner | gap | promotion |
|---|---|---|---|---|---|
| `DEFER-001E-INTEGRATION-001` | `TASK-001 / media-test-stand plan` | Сквозной SIP/RTP, BYE, PCMU, barge-in, transfer и report после feasibility | owner следующего plan + project owner | Feasibility evidence не является полной реализацией/demo evidence | Approved media/test-stand child plan, deterministic stand smoke, saved logs and exit codes; затем promotion в обычный integration gate |
| `DEFER-001E-CHANNEL-001` | `TASK-001 / channel lifecycle plan` | Stale producer, close/re-close и generation behavior в реальном application channel | channel owner + project owner | D component evidence не заменяет application state-machine/integration evidence | Contract/state-machine tests и SIP/RTP scenario с channel IDs; ссылка из test-stand closeout |
| `DEFER-001E-LATENCY-001` | `TASK-001 / answer-path plan` | E2E turn latency 200–500 ms и component breakdown на target machine | answer-path owner + project owner | Feasibility synthesis может иметь observations, но не полноценный call-path measurement | Real selected components on deterministic stand, timestamp schema, raw run logs and latency report; promotion в latency gate |

Обязательный baseline без evidence не может быть deferred ради закрытия M-G4: в таком случае child plan остаётся
`blocked`, а owner decision должен явно изменить scope.

## 13. Реестр fallback и упрощений

| Что | Почему допустимо | Как ограничено | Где закрывается | Владелец | Статус |
|---|---|---|---|---|---|
| Native isolation | Сохраняет выбранную stable free-threaded-сборку CPython >=3.14 main process при доказанной несовместимости | Только C/D evidence, explicit process boundary и owner-approved IPC follow-up | D decision + next plan/ADR | project owner | `owner-gated` |
| Неисполнение speculative path в deadline demo | Roadmap section 13.3 разрешает authoritative final path | Provisional ASR не меняет FSM/TTS; partial ASR всё ещё сохраняется | Speech/answer plan | project owner | `approved scope cut` |
| Fixed VAD endpointing | Разрешённый deadline cut вместо semantic turn detector | Soft/hard thresholds configuration and evidence remain required | Speech plan | project owner | `approved scope cut` |
| Curated KB и local fake operator | Сохраняют обязательный локальный demo-flow | Не выдаются за full Wikipedia crawler или real contact center | Knowledge/media plan | project owner | `approved scope cut` |
| Latency 200–500 ms как measurable target, не hard pass | Roadmap допускает демонстрацию с честной разбивкой | Correct timestamps and cause analysis remain mandatory | Answer/integration plan | project owner | `approved scope boundary` |
| CPU-only, Docker-only bot, alternate candidate, hidden bridge или weakened assertion | Не утверждено и нарушает protected baseline | Не допускается без owner decision + new plan/ADR | Unexpected gap protocol | project owner | `forbidden` |

E не добавляет fallback и не превращает отрицательный результат в `pass`. Каждое дополнительное упрощение требует owner,
scope, rationale, corrective path и отдельного evidence.

## 14. Unexpected gap protocol

Если evidence index, gate matrix или D map обнаруживает неучтённую архитектурную работу, переход немедленно останавливается
и создаётся запись:

```text
gap_id:
Обнаруженный gap:
Затронутые документы, components и map gates:
Какое evidence отсутствует/противоречит:
Почему M-G4 или next plan нельзя открыть:
Возможные варианты:
Рекомендуемый вариант:
Нужен ли новый ADR/roadmap/child plan:
Владелец решения:
Условие promotion/снятия blocker:
Дата и ссылка на owner review:
```

Типичные E gaps: несовпадающие версии/команды, missing exit code, отсутствие C contour, D claim без source evidence,
неопределённый IPC, automatic GIL enable, новый candidate или next plan, который предполагает неописанный public owner.
До review запрещены hidden fallback, startup-only path, новый adapter/facade/IPC и ослабление acceptance.

Начальный статус на drafting stage: `none observed`; execution должен подтвердить это evidence, а не наследовать строку.

## 15. Execution и closeout

### Условия начала

1. `001-A`–`001-C` и все `001-C1`–`001-C4` имеют завершённые closeout с evidence.
2. `M-G2` и `M-G3` закрыты собственными evidence; `fail` имеет explicit owner-approved path или блокирует E.
3. `001-D` имеет accepted evidence index, process/thread matrix, control/data map и residual blocker review.
4. Этот plan получил отдельный owner review; создание файла не является approval.
5. Следующая Map-002 имеет reviewed scope и owner decision; её child plans всё равно требуют отдельных owner reviews.

### Порядок исполнения

`E-001 → E-002 → E-003 → E-004 → E-005 → E-006`.

E-001/002 только индексируют факты; E-003 не выбирает новые кандидаты; E-004 останавливает неожиданную архитектурную
работу; E-005 оформляет следующий plan package и отправляет его на отдельное plan review; E-006 фиксирует final status.
Execution commands и audits выполнены после owner review.

### Closeout acceptance

- каждый обязательный contour имеет evidence-backed `pass`/`pass_with_isolation` или явно закрытый owner-approved
  fallback/isolation path;
- `evidence-index.md` содержит command, version, raw output, exit code, status, owner и map gate для каждой записи;
- `map-gates.md` отдельно показывает M-G1, M-G2, M-G3 и M-G4, а child blockers не скрыты map-level строками;
- `baseline-register.md` содержит версии/лицензии, process/thread boundary, IPC note, latency/VRAM/CPU observations,
  known limitations, fallback decisions и forbidden expansions;
- requirement/architecture/process audits завершены с перечислением pre-existing failures и out-of-scope findings;
- deferred records имеют `evidence_id/task/scope/owner/gap/promotion`, local `skip`/`xfail` отсутствуют;
- `next-plan-approval.md` содержит конкретное имя/цель следующего plan, scope, dependencies, evidence root, blockers,
  owner и дату/ссылку письменного решения;
- `closeout.md` назначает `complete`, если scope E и hand-off acceptance выполнены, либо `blocked` при конкретном
  незакрытом blocker; `prod-ready complete` не используется.

### Handoff и статус

При успешном E closeout feasibility Map-001 может быть помечена как `complete` после owner approval следующего
media/test-stand plan. Это не разрешает все последующие планы автоматически. При missing baseline, unresolved blocker
или неподтверждённом next plan статусом child plan был бы `blocked`, а closeout содержал бы concrete owner и promotion
condition. В текущем execution этот файл имеет статус `complete`, а `M-G4` закрыт после review следующей карты.
