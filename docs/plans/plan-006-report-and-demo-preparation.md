# Map-006: подготовка доклада и демонстрационного пакета

Уровень: `map`  
Идентификатор: `Map-006`  
Статус: `complete — corrective 006-D closed by target r6 on 2026-09-05`
Родитель: [`roadmap.md`](../roadmap.md)  
Предшественник: [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md)  
Дата подготовки: `2026-09-04`

## 1. Цель и проверяемый результат

Подготовить основанный на фактическом evidence пакет для конференционного доклада и воспроизводимой демонстрации.
Пакет должен объяснять архитектуру и применимость технологий, показывать ограничения MVP и позволять повторить
демонстрационный сценарий на чистом запуске.

Результат Map-006:

- inventory источников и evidence с проверенными ссылками;
- русскоязычный черновик доклада/сценария выступления;
- runbook запуска, прогрева, clean-start rehearsal и проверки артефактов;
- отдельный список подтверждённых свойств, ограничений и неподтверждённых production claims;
- лицензии и attribution requirements явно отмечены в публикационном checklist;
- пакет не изменяет runtime, модели, typed boundaries или защищённую архитектуру.

## 2. Применимые документы и материализованные правила

| Источник | Правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Доклад отражает только назначение и границы MVP: один русский SIP-разговор, RAG, barge-in, transfer, report | Narrative и demo-flow не обещают production scale/PBX | Traceability matrix | Содержательный тезис противоречит требованиям |
| [`architecture.md`](../architecture.md) | Dispatcher/FSM владеют control plane; audio и большие text payload идут по direct data plane; LLM не управляет SIP напрямую | В докладе показывается фактическая ownership/topology | Architecture claim audit | Новый или искажённый boundary |
| [`technical-specification.md`](../technical-specification.md) | PCMU, per-call media profile, no-GIL, warmup, RAG, report и 20 GB guard являются техническими ограничениями | Runbook и technical claims ссылаются на ТЗ | Config/evidence cross-check | Утверждение не подтверждается кодом/evidence |
| [`licensing-policy.md`](../licensing-policy.md) | Код, модели, corpus, voices и outputs имеют раздельные условия; веса не включаются автоматически | Publication checklist и notices не смешивают лицензии | License/source inventory | Неизвестное обязательство выдано за разрешённое |
| [`development-guidelines.md`](../development-guidelines.md) | Evidence-backed claims, no silent simplification, binary closeout, owner/source discipline | Каждый тезис получает источник или маркируется как limitation | Evidence index и APG audit | Неподтверждённый обязательный claim |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Операционный документ материализует применимые правила, scope, source-map, tests, blockers и closeout | Map и child plans остаются самодостаточными | Этот документ и child closeouts | Новый owner-review вопрос/категория 4 |
| [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md) | r7 сохранён как historical diagnostic evidence; r10 остаётся upstream TTS-integrity evidence, а Map-006 corrective закрыт r6 | Current downstream claims и compact-demo evidence обновлены по r6; r7/r10 не перезаписываются | Source-index и Map-006 closeout | Противоречие между claims и evidence |

## 3. Граница Map-006

**Входит:**

- inventory требований, архитектурных claims, моделей/runtime, лицензий, команд и final evidence;
- report narrative и presentation-neutral talk outline на русском языке;
- воспроизводимый demo runbook для Ubuntu 24.04/WSL2, CPython 3.14.7t/no-GIL, warmup и clean-start run;
- requirement→evidence traceability, known limitations и честное описание не достигнутой latency-цели;
- publication checklist без включения весов моделей в репозиторий;
- проверка ссылок, путей, команд и document/task registry.

**Не входит:**

- изменение кода, моделей, конфигурационных констант, SIP/RTP/API contracts или тестового стенда;
- новый benchmark, новый GPU run, исправление runtime-дефектов и production hardening;
- выбор лицензии исходного кода проекта без отдельного решения владельца;
- выпуск GitHub-релиза, публикация материалов или создание внешнего hosted service;
- обещания MOS/SLO/масштабирования, которых нет в evidence.

**Protected baseline:** Map-005 r7 как историческое evidence, Map-002-I revision 21, закрытые ADR, CPython 3.14.7t/no-GIL, Qwen3.5-9B,
Ollama HTTP IPC, faster-whisper ASR, XTTS-v2, PCMU/8000/mono, Baresip recording policy и единственный обязательный
итоговый `report.md` звонка.

## 4. Source-map и write-set

| Область | Источник | Действие | Write-set |
|---|---|---|---|
| Evidence inventory | `docs/requirements.md`, `docs/architecture.md`, `docs/technical-specification.md`, `docs/plans/*`, `artifacts/implementation/*` | Собрать ссылки и фактические значения без копирования нормативных текстов | `artifacts/report-preparation-20260904/source-index.md` |
| Demo runbook | `tools/`, `config/`, Map-005 r10 baseline и Map-006 r6 evidence; r7 historical baseline | Описать preflight, warmup, запуск, сценарий и проверку артефактов | `artifacts/report-preparation-20260904/demo-runbook.md` |
| Demo input timing | `tools/demo_fixture_timing.py`, `tools/j4_full_live_gate.py`, r6 fixture metadata | Сократить искусственные паузы, сохранив все обязательные user turns и barge-in | `tools/demo_fixture_timing.py`, `tools/j4_full_live_gate.py`, `tests/unit/test_demo_fixture_timing.py` |
| Report narrative | Source-index, requirements, architecture, licensing, final evidence | Создать русскоязычный докладный черновик и outline выступления | `artifacts/report-preparation-20260904/report-draft.md` |
| Publication checklist | `docs/licensing-policy.md`, dependency/model/corpus evidence | Перечислить notices, ссылки, отсутствие весов и unresolved license choice | `artifacts/report-preparation-20260904/publication-checklist.md` |
| Map closeout | This map and child plans | Зафиксировать результаты, blockers и next calendar gate | `artifacts/report-preparation-20260904/closeout.md` |

Общие документы `docs/*`, код, configuration и закрытые evidence roots не изменяются. Registry/backlog/roadmap
синхронизируются только главным executor-ом после выполнения child plans.

## 5. Interaction topology

Map-006 не добавляет runtime edges. Он читает уже закрытые связи:

```text
requirements/architecture/TЗ/licensing
        ↓
Map-005 r10 TTS baseline + Map-002/001 evidence + closed 005-E corrective gate; current downstream package refreshed by r6
        ↓
source-index + requirement/evidence matrix
        ↓
report-draft + demo-runbook + publication-checklist
        ↓
owner-facing conference package
```

Доклад и runbook — производные документы; они не становятся владельцами требований, архитектуры, конфигурации или
лицензий. Если фактический evidence расходится с документом-владельцем, claims не «исправляются» в черновике:
фиксируется gap и проверяется необходимость owner review.

## 6. Child graph и порядок

| ID | Child plan | Узкая цель | Зависимости | Допустимый параллелизм | Результат |
|---|---|---|---|---|---|
| `006-A` | [`plan-006-A-evidence-inventory.md`](plan-006-A-evidence-inventory.md) | Собрать traceability и factual inventory | Map-005 r7 | Параллельно B | `source-index.md` |
| `006-B` | [`plan-006-B-demo-runbook.md`](plan-006-B-demo-runbook.md) | Описать воспроизводимый запуск и демонстрацию | Map-005 r7, `001-S` | Параллельно A | `demo-runbook.md` |
| `006-C` | [`plan-006-C-conference-report-draft.md`](plan-006-C-conference-report-draft.md) | Сформировать докладный черновик и publication checklist | A, B | После A/B | `report-draft.md`, `publication-checklist.md` |
| `006-D` | [`plan-006-D-demo-input-timing-corrective.md`](plan-006-D-demo-input-timing-corrective.md) | Сократить искусственные паузы в Baresip input fixture без потери сценария | Map-006 package, Map-005 r10 baseline | После C; live gate main-executor sequential | Compact fixture profile, 7/7 live checks, stereo recording и audio audit |

Подготовка A/B не использует GPU и может идти параллельно. C выполняется после их handoff. Общая синхронизация
документов и registry/backlog выполняется main executor-ом последовательно.

## 7. Owner-review решения и stop conditions

Новых предметных решений для подготовки evidence-backed черновика нет: формат делается нейтральным к числу слайдов,
длительности доклада и площадке. Эти параметры могут быть уточнены позднее без изменения технического пакета.

| ID | Триггер | Действие | Статус |
|---|---|---|---|
| `B-006-001` | Нельзя подтвердить обязательный technical/demo claim существующим evidence | Не выдавать claim за факт; остановить соответствующий child и зарегистрировать gap | `none until triggered` |
| `B-006-002` | Обнаружено противоречие с requirements/architecture/TЗ/ADR | Остановить публикационный claim и проверить owner document | `none until triggered` |
| `B-006-003` | Для публикации нужен новый license decision | Оставить checklist open и остановить только release action, не report drafting | `none until triggered` |
| `B-006-004` | Registry/backlog audit не проходит | Исправить синхронизацию до closeout | `none until triggered` |

Не являются blocker-ами этой карты: отсутствие выбранной лицензии проекта, отсутствие точной длительности доклада,
отсутствие новых GPU measurements и не достигнутый latency target, если они явно обозначены в пакете.

## 8. Test/evidence plan

- все локальные Markdown-ссылки и существующие paths проверены;
- source-index содержит источник каждого числового/архитектурного/лицензионного claim;
- runbook содержит exact commands из финального evidence и предупреждение о warmup/GPU/disk prerequisites;
- report отдельно показывает achieved scenarios, known limitations и out-of-scope properties;
- publication checklist не объявляет проект юридически готовым к публикации при незавершённом выборе project license;
- после Markdown-изменений запущены `python tools/check_document_registry.py` и, при изменении backlog,
  `python tools/check_task_backlog.py`.

## 9. Closeout criteria

Map-006 получает `complete`, когда A–D имеют собственные closeout, report/runbook/checklist/source-index созданы,
каждый обязательный тезис имеет traceability, registry audit проходит, а upstream Map-005 закрыта после `005-E`.
Эти условия выполнены; r7 остаётся историческим diagnostic evidence и не используется как доказательство текущей
полноты TTS. Новая функция и новая архитектура для Map-006 не требуются.

## 10. Execution status

На дату подготовки child plans `006-A → 006-B → 006-C` имели собственные closeout, а map-level package был закрыт по
r10 как upstream TTS evidence. После явного owner-запроса добавлен corrective child `006-D` для сокращения искусственных пауз input fixture.
После освобождения диска `006-D` выполнен target r6: compact fixture, 7/7 checks, Baresip stereo recording и
audio audit прошли. Новых архитектурных boundary или category-4 вопросов не заявлено.

## 11. Фактический closeout

`006-A`, `006-B`, `006-C` и corrective `006-D` имеют binary `complete` child closeouts. Подготовлены
[`source-index.md`](../../artifacts/report-preparation-20260904/source-index.md), [`demo-runbook.md`](../../artifacts/report-preparation-20260904/demo-runbook.md),
[`report-draft.md`](../../artifacts/report-preparation-20260904/report-draft.md), [`publication-checklist.md`](../../artifacts/report-preparation-20260904/publication-checklist.md)
и [`Map-006 closeout`](../../artifacts/report-preparation-20260904/closeout.md). Target r6 подтвердил compact
fixture, полный SIP/RTP сценарий, Baresip stereo recording и отсутствие прежнего mid-stream TTS пропадания;
registry/backlog синхронизированы после этого closeout. Project license, редактура и публикация остаются
отдельными действиями.
