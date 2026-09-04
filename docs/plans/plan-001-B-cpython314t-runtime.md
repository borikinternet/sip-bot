# Child plan 001-B: latest stable free-threaded CPython runtime baseline

Уровень: `child plan`  
Статус owner review: `accepted`  
Статус исполнения: `complete`  
Родительская карта: [`Map-001`](plan-001-deadline-feasibility.md)  
Зависимость: `001-A` — закрытый environment baseline с evidence  
Следующий map-gate: `M-G2 runtime gate`

Owner review: `2026-08-27` — child plan принят к execution в рамках общего
распоряжения продолжать работу без новых уточняющих вопросов; точная stable
версия выбирается execution-процедурой и фиксируется provenance.

Создание этого файла было подготовкой к работе и не считалось исполнением
плана. Execution начинается после закрытого `001-A`; runtime и пакеты выбираются
и фиксируются только в пределах описанных slices.

Execution status: `complete`  
Runtime decision: `pass`  
Execution evidence: [`001-B evidence index`](../../artifacts/feasibility/001-B/evidence-index.md) и
[`001-B closeout`](../../artifacts/feasibility/001-B/closeout.md).

## 1. Цель и проверяемый результат

После закрытия `001-A` воспроизводимо установить или собрать **последний стабильный
free-threaded CPython не ниже 3.14** для Ubuntu 24.04 LTS x86_64 в WSL2 и получить
минимальный независимый набор evidence:

1. identity целевого интерпретатора и его executable/build provenance;
2. `Py_GIL_DISABLED == 1` через `sysconfig.get_config_var`;
3. состояние `sys._is_gil_enabled()` до проверяемых стандартных импортов;
4. состояние `sys._is_gil_enabled()` после каждого импортированного модуля из
   явного stdlib manifest и после всей стандартной import-фазы;
5. отсутствие предупреждения об автоматическом включении GIL;
6. controlled-concurrency smoke на stdlib без project native imports;
7. воспроизводимый JSON-evidence с командой, версиями, stdout/stderr,
   exit code, хешем executable и параметрами прогона.

Результат `pass` означает только подтверждённый baseline runtime и его
диагностический smoke. Он не означает совместимость SIP, ASR, LLM, TTS,
аудио-библиотек или production-ready свойства.

## 2. Применимые документы и извлечение правил

| Источник | Извлечённое правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan самодостаточен: scope, source-map/write-set, owner review, audits, slices, blockers, evidence и closeout обязательны | Все обязательные разделы находятся в этом файле; execution начинается только после owner review | APG audit перед запуском | Отсутствует обязательный раздел, owner review или blocker register |
| [`plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md) | `001-B` зависит от `001-A`; он закрывает только runtime/no-GIL baseline и открывает `M-G2` | Не импортировать компоненты до закрытия runtime gate | Evidence `001-A` + `runtime-probe.json` | `001-A` не закрыт или evidence не воспроизводится |
| [`requirements.md`](../requirements.md) | MVP локальный; основной runtime — free-threaded CPython, основной SIP/media формат — PCMU | В этом плане проверяется только базовая среда, без пользовательского сценария и без PCMU | Scope/invariant audit | План начинает реализовывать SIP/media или AI-поведение |
| [`architecture.md`](../architecture.md) | Dispatcher владеет control plane; payload идёт по data plane; runtime не меняет ownership | Probe не создаёт Dispatcher, каналы, FSM или component API | Architecture invariant audit | Появляется компонентный контракт или перенос payload |
| [`technical-specification.md`](../technical-specification.md) | Целевая среда — latest stable free-threaded CPython не ниже 3.14 в Ubuntu 24.04 LTS x86_64; no-GIL проверяется до/после импортов | Acceptance использует фактически выбранный runtime и явные стадии проверки | Runtime identity/import probe | Использован обычный CPython или скрытая подмена baseline |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Main process использует latest stable free-threaded CPython >= 3.14; `Py_GIL_DISABLED`, фактический GIL и warnings проверяются | Проверка остаётся stdlib-only; component isolation не решается здесь | JSON evidence + stderr | `Py_GIL_DISABLED != 1`, GIL включён или есть необъяснённое warning |
| [`tooling-notes.md`](../tooling-notes.md) | Filename/tag недостаточны; нужны import/operation checks и структурированное evidence; host Python не доказывает app runtime | Probe запускается целевым executable; фиксируются import stages и controlled concurrency | Команда probe и artifact set | Evidence содержит только имя `cp314t` без фактических стадий |
| [`roadmap.md`](../roadmap.md) | Дочерний plan исполняется отдельно; deadline не разрешает ослаблять protected baseline | Не расширять plan до native compatibility или demo-flow | Scope and closeout audit | Возникает скрытый fallback или scope expansion |
| [`documentation-process.md`](../documentation-process.md) | Меняется только документ-владелец; дубли заменяются ссылками | Факты runtime синхронизируются владельцу только после фактической проверки | Closeout document list | План объявляет runtime факт без evidence или переписывает чужой owner-документ |

Применимые ADR: `ADR-003`. `ADR-001` не применяется: этот plan не меняет
границу LLM/Dialogue Manager и не добавляет SIP-команды. `ADR-002` не
применяется: в нём не выбирается LLM и не выполняется inference benchmark.

## 3. Scope boundary

### 3.1. Цель

Получить и проверить один воспроизводимый latest stable free-threaded CPython >= 3.14 baseline в целевой
Ubuntu/WSL2-среде без импорта проектных native-зависимостей.

### 3.2. Входит

- проверка зависимости от закрытого `001-A` evidence;
- выбор и фиксация одного способа поставки: reproducible source build или
  reproducible approved artifact;
- установка/сборка выбранного latest stable free-threaded CPython в WSL prefix;
- runtime identity probe;
- проверка `Py_GIL_DISABLED`;
- проверка `sys._is_gil_enabled()` до и после явного списка стандартных
  импортов, после import-фазы и после controlled-concurrency smoke;
- stdlib-only controlled-concurrency smoke без измерения production throughput;
- сохранение reproducible evidence в отдельном root `artifacts/feasibility/001-B/`;
- closeout с решением `pass`, `fail` или `pass_with_observation` для runtime
  gate без выбора component baseline.

### 3.3. Не входит

- импорт или вызов SIP/PJSUA2/PJMEDIA, RTP, ASR, VAD, LLM, TTS, audio или
  другого project/native модуля;
- проверка wheel/ABI совместимости конкретного SIP, ASR, LLM, TTS или audio
  компонента;
- component smoke, media loopback, PCMU, BYE, cancellation, VRAM, latency
  пользовательского сценария или SIP test stand;
- выбор `main process`/`process isolation` для любого компонента;
- создание IPC-контракта, adapter, facade, fallback, compatibility bridge
  или startup-only path;
- изменение Dispatcher, Dialogue FSM, control plane, data plane, lifecycle,
  конфигурации MVP или архитектурных контрактов;
- переход на CPython 3.15t, обычный CPython или Docker-only baseline;
- обновление `requirements.md`, `architecture.md`,
  `technical-specification.md`, `roadmap.md`, ADR, `document-registry.md` или
  `task-backlog.md` в рамках текущей drafting-сессии.

### 3.4. Protected baseline

- основной baseline: latest stable free-threaded CPython >= 3.14;
- authoritative environment: Ubuntu 24.04 LTS x86_64 в WSL2 после evidence
  `001-A`;
- `Py_GIL_DISABLED == 1` и `sys._is_gil_enabled() is False` на всех
  обязательных стадиях probe;
- project native imports запрещены в каждом executable action этого plan;
- красный no-GIL результат не превращается в зелёный выбором обычного
  CPython, `PYTHON_GIL`, пропуском стадии или молчаливым isolation;
- срок/дедлайн не является основанием для изменения protected baseline;
- решения о SIP/ASR/LLM/TTS остаются в `001-C`/`001-C1`–`001-C4` и
  `001-D`.

### 3.5. Dirty-worktree и assumptions

Рабочее дерево на момент drafting было dirty: существующие staged, untracked и
unrelated изменения принадлежат пользователю и сохраняются. Перед execution
`git status --short` сохранён в `artifacts/feasibility/001-B/git-status.txt`;
изменения других срезов с этим plan не смешивались.

Execution write-set и runtime/build paths перечислены в evidence и closeout;
component code, project native imports и изменения архитектурных документов не
выполнялись.

### 3.6. Зависимости и внешние сервисы

- закрытый `001-A` environment evidence;
- доступ к Ubuntu 24.04 LTS WSL2 x86_64 и исходнику/артефакту выбранного
  stable CPython с фиксируемым digest;
- системные инструменты сборки только на execution stage и в рамках проверенного
  `001-A` environment;
- внешние SIP-сервисы, PBX, GPU-модели и network services не требуются.

## 4. Source-map, write-set и запрещённые изменения

### 4.1. Source-map

| Область | Файл/компонент | Текущее состояние | Целевое состояние | Gap | Действие |
|---|---|---|---|---|---|
| Child plan | `docs/plans/plan-001-B-cpython314t-runtime.md` | Self-contained plan подготовлен | Self-contained plan со статусом `accepted` и owner review | Нет runtime evidence | Выполнить S0–S3; не смешивать component work |
| Environment | Ubuntu/WSL2 и evidence `001-A` | `001-A` foundation закрыт | Воспроизводимая целевая среда и captured preflight | Нет | Использовать `001-A` evidence без дублирования |
| Runtime | WSL prefix для выбранного latest stable free-threaded CPython | Runtime 3.14.7 собран и установлен | Один executable с source/artifact provenance и sha256 | Нет | Использовать зафиксированный prefix/executable |
| Probe | `tools/nogil_probe.py` | Stdlib-only probe создан | Import manifest и concurrency result воспроизводимы | Нет | Повторять через wrapper или эквивалентную WSL-команду |
| Runner | `tools/run_nogil_probe.ps1` | Wrapper создан | Передаёт target executable и запускает probe в WSL2 | Нет | Не подменять target обычным CPython |
| Evidence | `artifacts/feasibility/001-B/` | Child evidence создан | JSON, manifest, command, stdout/stderr, exit code и hashes сохранены | Нет | Closeout и evidence index — владельцы runtime facts |
| Tests | `tests/` | Formal test file для этого plan не нужен | Однократный stdlib-only executable probe с повторным запуском | Нет отдельного Regression test lane | Не создавать tests-only helper в этом plan |
| Component boundaries | SIP/ASR/LLM/TTS и будущие adapters | Не исследуются `001-B` | Остаются нетронутыми до `001-C*` | Component import matrix ещё не утверждена | Не импортировать и не принимать isolation decisions |

### 4.2. Допустимый write-set на execution stage

Допустимый write-set ограничен следующими объектами:

- `tools/nogil_probe.py` — новый stdlib-only probe, не импортирующий проект;
- `tools/run_nogil_probe.ps1` — thin runner, который выбирает только заранее
  зафиксированный target executable и evidence root;
- `artifacts/feasibility/001-B/` — только runtime evidence и журналы этого
  child plan;
- WSL install/build prefix выбранного stable free-threaded CPython, путь к которому
  фиксируется в evidence; это не решение о runtime-компонентах проекта.

Исходники CPython, промежуточные build outputs и package cache могут
находиться во внешнем WSL path, если этот path и digest записаны в manifest.
Они не являются основанием для расширения project source-map.

### 4.3. Запрещённые изменения

Запрещено изменять или создавать в этом child plan:

- любые `src/`, `config/`, SIP/media/ASR/LLM/TTS adapters и component tests;
- `docs/requirements.md`, `docs/architecture.md`,
  `docs/technical-specification.md`, `docs/roadmap.md`,
  `docs/document-registry.md`, `docs/task-backlog.md` и ADR;
- `docs/plans/plan-001-deadline-feasibility.md`;
- архитектурные ownership/control-data-plane contracts;
- fallback, isolation, IPC, compatibility path или ослабленный assertion;
- evidence других child plans или общий `baseline-register.md` карты;
- project native imports, даже если импорт кажется «только диагностическим».

Если фактическая проверка требует любой запрещённый объект, срабатывает
[unexpected gap protocol](#11-протокол-неожиданного-gap), а зависимый slice
останавливается.

## 5. Audit владельца поведения и парадигмы реализации

### Статус: применимо только как audit диагностической capability; runtime behavior проекта не меняется

В этом плане нет нового публичного алгоритма SIP, FSM, канала, поколения,
маршрута или transfer outcome. Владельцем наблюдаемого поведения является
диагностическая capability `CPython runtime probe`, а не Dispatcher и не один
из проектных компонентов. Она владеет только входами probe, стадиями импорта,
параметрами controlled-concurrency и форматом evidence на время одного
процесса.

`tools/nogil_probe.py` допустимо реализовать как свободный диагностический
скрипт: у него нет самостоятельного component-specific state, он не меняет
состояние SIP/FSM/channel и не пересекает границу capability. Ему передаются
только scoped параметры probe и evidence output; отмена и observability в
виде exit code/stdout/stderr принадлежат самому диагностическому запуску.
Никакая свободная функция из этого plan не становится production helper и не
исполняет component lifecycle.

Controlled-concurrency smoke является evidence о runtime, а не реализацией
параллелизма приложения. Он не назначает владельца будущих очередей,
блокировок, каналов или worker lifecycle и не делает вывода о потокобезопасности
native-библиотек.

## 6. Owner-review решения

| Вопрос | Решение для этого plan | Последствие для реализации | Статус |
|---|---|---|---|
| Какой runtime является baseline? | Последний стабильный free-threaded CPython не ниже 3.14 | Точная версия определяется execution и записывается в evidence | `resolved` по ADR-003 |
| Где выполняется authoritative probe? | Ubuntu 24.04 LTS x86_64 в WSL2 после `001-A` | Windows host Python не является evidence приложения | `resolved` |
| Можно ли импортировать project/native модули? | Нет, включая SIP, ASR, LLM, TTS, audio и транзитивные native-модули | Import manifest ограничен stdlib; component gate остаётся закрыт | `resolved` |
| Что доказывает controlled concurrency? | Повторяемое завершение фиксированной stdlib-only workload с детерминированным checksum, без exception/deadlock и с GIL disabled до/после | Не измеряется production speed и не принимается component thread-safety | `resolved; smoke accepted for this plan` |
| Какой способ поставки CPython выбрать? | Execution выбирает наиболее быстрый воспроизводимый способ из доступных: stable artifact или source build | Выбранный способ и его ограничения записываются в evidence; отдельного предварительного approval не требуется | `resolved as execution task` |
| Какой exact source/artifact и WSL prefix? | Execution фиксирует фактические URL/path, sha256, build flags и executable после выбора stable runtime | Повторный запуск использует тот же executable; отсутствие provenance — runtime failure | `resolved as evidence requirement` |
| Как трактовать несовпадение `SOABI`/runtime diagnostic? | Не угадывать и не маркировать `pass`; записать gap и запросить owner decision | Возможен только явно согласованный corrective plan | `resolved policy; конкретное решение по факту` |
| Принимается ли обычный CPython как fallback? | Нет. Любой fallback требует owner discussion и, при изменении baseline, ADR/нового plan | Красный результат остаётся красным | `resolved` |
| Принимается ли process isolation для будущего компонента? | Нет решения в `001-B`; это scope `001-C`/`001-D` после native checks | Этот plan не создаёт IPC и не выбирает границы процессов | `resolved as out of scope` |

Execution stage начался после закрытия `001-A` и review самого child plan. Способ
поставки и параметры smoke определены внутри execution slices и зафиксированы в
evidence.

## 7. Process invariant audit

- Срез узкий: один runtime, один stdlib-only probe и один evidence root; он не
  смешивает runtime identity с native compatibility или demo-flow.
- Runtime probe и controlled-concurrency smoke являются релевантными проверками;
  SIP/RTP, ASR, LLM, TTS, FSM, BYE, barge-in, VRAM и latency являются
  нерелевантными для acceptance `001-B` и не должны расширять scope.
- Authoritative environment — WSL2/Ubuntu; host Python используется только
  для document tooling и не считается runtime evidence.
- Все команды execution, версия target executable, source/artifact digest,
  absolute path, stdout/stderr и exit code сохраняются в evidence.
- Execution изменил только registry row этого child plan для фиксации принятия и closeout; backlog и roadmap не
  переписывались. Governance checks выполнены отдельно и зафиксированы в closeout.
- Fallback, compatibility path, `skip`/`xfail`, ослабление assertion и
  tests-only legacy helper не вводятся.
- Никакие production-ready claims не делаются; результат ограничен runtime
  foundation.
- Независимые external build steps могут быть согласованы отдельно, но probe
  и evidence для одного executable выполняются последовательно в чистых
  процессах; параллелизм не скрывает failure.
- Unrelated dirty-worktree changes сохраняются и не входят в write-set.

## 8. Architecture invariant audit

| Инвариант | Результат аудита для `001-B` |
|---|---|
| Dispatcher владеет control plane и Dialogue FSM | Не затрагивается: probe не создаёт и не вызывает Dispatcher/FSM |
| SIP/media callbacks не ждут AI и немедленно обрабатывают BYE | Не проверяется в этом plan; SIP/media imports запрещены, проверка переносится в `001-C1` |
| Audio и крупные text payload идут по data plane | Не затрагивается: probe использует только локальные диагностические значения |
| Закрытие каналов отбрасывает stale producer | Не затрагивается и не имитируется tests-only helper-ом |
| Только final ASR может менять FSM/разрешать TTS | Не затрагивается; ASR и TTS не импортируются |
| Speculative pipeline не делает необратимых действий | Не затрагивается; speculative path не создаётся |
| TTS отменяется при barge-in | Не проверяется в этом plan |
| LLM выдаёт ограниченное решение без SIP-доступа | Не затрагивается; LLM не импортируется |
| SIP/media MVP — PCMU | Не затрагивается; PCMU проверяется в media plan |
| Config находится в `config/constants.py` без скрытых defaults | Не затрагивается; config не создаётся и не меняется |
| Free-threaded CPython — приоритет; native incompatibility не включает GIL | Применяется: проверяется только чистый runtime; native isolation не решается |
| Нет реальных внешних сервисов/PBX/записи аудио | Соблюдается: external SIP/PBX/audio storage не используется |
| Channel lifecycle имеет owner/close/cancel/reclose test | Не затрагивается; controlled-concurrency не является channel lifecycle |

Отсутствие component checks в этом plan является явной границей, а не
утверждением, что компоненты совместимы.

## 9. Узкие implementation slices

Порядок исполнения последовательный. Ниже описан будущий execution; создание
этого файла не выполняет ни один slice.

### `B-001B-S0` — preflight и execution gate

**Цель и границы:** подтвердить закрытый `001-A`, owner review этого plan и
чисто зафиксировать исходное состояние рабочего дерева в evidence. Runtime не
запускать до закрытия preflight.

**Write-set:** только новый child evidence root
`artifacts/feasibility/001-B/` и его `preflight.md`/`git-status.txt`.

**Последовательность:**

1. Проверить наличие завершённого `001-A` evidence.
2. Зафиксировать `git status --short`, WSL distro identity и absolute project
   path; не менять unrelated files.
3. Подтвердить наличие plan review и отсутствие открытых prerequisite blockers.

**Acceptance:** `001-A` закрыт с evidence; preflight содержит дату, команду,
исходный status и ссылку на plan review; запрещённые imports не выполнялись.

**Stop conditions:** отсутствует `001-A`, неразрешён способ поставки, либо
preflight требует изменения protected document.

**Релевантные проверки:** read-only preflight и проверка наличия evidence.

**Синхронизация:** не изменять Map-001, backlog, registry или roadmap; факты
для closeout только записываются в child evidence.

**Следующий slice:** `B-001B-S1` после resolution всех blockers.

### `B-001B-S1` — reproducible install/build latest stable free-threaded CPython

**Цель и границы:** одним воспроизводимым способом получить последний стабильный
free-threaded CPython не ниже 3.14 в
WSL prefix. Этот slice не импортирует ни одного project/native модуля и не
проверяет component compatibility.

**Write-set:** выбранный external WSL prefix; `artifacts/feasibility/001-B/`
для `runtime-manifest.json`, source/artifact metadata, command log и hashes.

**Последовательность:**

1. Зафиксировать source/artifact URL/path, version, sha256, toolchain,
   configure/build flags и target prefix.
2. Выполнить ровно выбранный source-build или approved-artifact procedure.
3. Сохранить absolute path и sha256 полученного executable.
4. Выполнить только минимальную identity command целевым executable; не
   импортировать project/native пакеты.

**Acceptance:** executable запускается в Ubuntu/WSL2; identity сообщает
    CPython версии не ниже 3.14, target x86_64 и free-threaded diagnostic; provenance и
   команда позволяют повторить получение того же runtime.

**Stop conditions:** source/artifact digest не совпадает, executable не
    является free-threaded CPython версии не ниже 3.14, build требует незафиксированного обхода,
   включается GIL или возникает потребность в компонентном native import.

**Релевантные проверки:** runtime identity probe; component smoke не выполняется.

**Синхронизация:** если фактический runtime меняет техническое ограничение,
   остановиться и вынести gap владельцу `technical-specification.md`/ADR-003;
   не редактировать их молча.

**Следующий slice:** `B-001B-S2` после pass identity.

### `B-001B-S2` — identity/import/no-GIL probe

**Цель и границы:** в чистом процессе целевого executable получить стадии
   `Py_GIL_DISABLED` и `sys._is_gil_enabled()` до/после стандартных импортов.

**Write-set:** `tools/nogil_probe.py`,
`tools/run_nogil_probe.ps1` и JSON/log artifacts внутри `001-B`.

**Stdlib manifest:** probe может импортировать только диагностические модули
   stdlib, заранее перечисленные в manifest, например `sys`, `sysconfig`,
   `platform`, `json`, `pathlib`, `threading`, `queue`, `concurrent.futures`,
   `time` и `statistics`. Фактический список и порядок сохраняются в
   evidence; `site`/startup auto-imports отдельно отмечаются. Сторонние
   packages и project modules запрещены.

**Последовательность:**

1. Запустить целевой executable в чистом процессе.
2. Записать `sys.implementation`, `sys.version_info`, `sys.executable`,
   `platform.machine()`, `sysconfig`-значения `SOABI` и `Py_GIL_DISABLED`.
3. Сразу после минимального диагностического bootstrap записать
   `gil_before_stdlib_imports = sys._is_gil_enabled()`.
4. Импортировать manifest по одному модулю и после каждого импорта записывать
   `sys._is_gil_enabled()`.
5. После import-фазы записать `gil_after_stdlib_imports` и весь stderr.

**Acceptance:** `Py_GIL_DISABLED == 1`; version не ниже `3.14`; фактический
GIL `False` до, после каждого обязательного stdlib import и после import-фазы;
stderr не содержит warning об автоматическом включении GIL; process exit code
равен 0; manifest и результаты сохранены.

**Stop conditions:** любое `True`, warning, exception, import вне manifest,
несовпадение version/ABI или невозможность связать result с target executable.

**Релевантные проверки:** import/no-GIL probe в чистом процессе.

**Синхронизация:** не обновлять component matrix и не принимать решение по
   isolation; отрицательный результат передать как blocker в owner review.

**Следующий slice:** `B-001B-S3` после pass всех import stages.

### `B-001B-S3` — controlled-concurrency и reproducible evidence closeout

**Цель и границы:** подтвердить, что тот же target runtime переживает
   ограниченный stdlib-only concurrent workload с детерминированным результатом
   и сохраняет GIL disabled. Это smoke, а не доказательство общей
   потокобезопасности приложения.

**Write-set:** только probe extension и artifacts `001-B`; component code,
   channels и IPC запрещены.

**Предлагаемый controlled workload:** фиксированное число workers, iterations,
   seed/checksum algorithm и repetitions, заданные в manifest до запуска.
   Каждый worker выполняет детерминированную CPU-bound операцию над собственным
   состоянием, встречается на barrier и обновляет проверяемый shared result
   только через явный stdlib synchronization primitive. Probe фиксирует worker
   exceptions, deadlock/timeout, checksum и `gil_before_concurrency`/
   `gil_after_concurrency`. Числа workload являются параметрами smoke, а не
   latency/SLO и требуют owner review.

**Последовательность:**

1. Запустить probe в новом чистом процессе с тем же executable и manifest.
2. Выполнить workload; не использовать SIP/media/AI/native imports.
3. Повторить прогон с теми же параметрами минимум два раза.
4. Сравнить status/checksum/ошибки между повторами; timings сохранить для
   диагностики, но не использовать как скрытый pass threshold.
5. Сохранить JSON, command, stdout, stderr и exit code для каждого прогона.

**Acceptance:** каждый повтор завершён с exit code 0; нет exception, timeout,
deadlock или checksum mismatch; результаты workload детерминированы; GIL
остаётся disabled до и после concurrency; evidence содержит полный manifest и
может быть повторён тем же executable.

**Stop conditions:** недетерминированный checksum, зависание, worker exception,
GIL включился, target executable отличается, либо для smoke нужен любой
проектный/native модуль.

**Релевантные проверки:** controlled-concurrency smoke и evidence consistency.

**Синхронизация:** закрыть только `001-B`; не открывать `001-C` автоматически
   и не объявлять native compatibility.

**Следующий slice:** child closeout и owner decision о переходе к `001-C`.

## 10. Blocker register

Каждый blocker ниже имеет concrete trigger и владелец решения — `project
owner`, если не указано иначе. Необъяснимый красный результат блокирует
зависимый slice; fallback не выбирается автоматически.

### Для `B-001B-S0`

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-001B-001` | `S0` | Нет закрытого `001-A` evidence | Весь child plan | project owner | `001-A` closeout + preflight | `resolved` |
| `B-001B-002` | `S0` | Этот plan не прошёл owner review или открытые решения раздела 6 не закрыты | `S1`–`S3` | project owner | Owner decision record | `resolved` |
| `B-001B-003` | `S0` | Pre-existing dirty-worktree status не зафиксирован | Reproducibility и attribution evidence | executor | `git-status.txt` | `resolved` |

### Для `B-001B-S1`

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-001B-004` | `S1` | Не выбран воспроизводимый source/artifact procedure или не сохранён digest | Получение runtime | executor | `runtime-manifest.json` | `resolved` |
| `B-001B-005` | `S1` | Executable не является free-threaded CPython >= 3.14 или target не Ubuntu/WSL2 x86_64 | `S2`–`S3`, `M-G2` | project owner | Identity probe | `resolved` |
| `B-001B-006` | `S1` | Build/install требует незафиксированного обхода protected baseline | Runtime baseline | project owner; ADR owner при architectural change | Build log + unexpected gap record | `resolved; not triggered` |

### Для `B-001B-S2`

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-001B-007` | `S2` | `Py_GIL_DISABLED != 1` | `M-G2` и весь зависимый native work | project owner | `runtime-probe.json` | `resolved; not triggered` |
| `B-001B-008` | `S2` | `sys._is_gil_enabled()` стал `True` до/после обязательного import или появился automatic-GIL warning | `M-G2` и `S3` | project owner | Per-import stages + stderr | `resolved; not triggered` |
| `B-001B-009` | `S2` | Probe импортировал модуль вне stdlib manifest или target executable не подтверждён | Validity всего evidence | executor; project owner при gap | Import manifest + executable hash | `resolved; not triggered` |

### Для `B-001B-S3`

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-001B-010` | `S3` | Worker exception, timeout, deadlock или checksum mismatch | Runtime closeout | project owner | Repeated concurrency JSON/logs | `resolved; not triggered` |
| `B-001B-011` | `S3` | GIL включился после concurrency или повторы использовали разные executable/manifest | `M-G2` | project owner | Per-run identity/GIL stages | `resolved; not triggered` |
| `B-001B-012` | `S3` | Нет команды, stdout/stderr, exit code, digest или повторяемого evidence | `001-B` closeout | executor | Evidence completeness audit | `resolved` |

Если после owner review и preflight для конкретного slice фактических
блокеров нет, register обновляется evidence-строкой `none`; эта строка не
подменяет текущие открытые blockers до их проверки.

## 11. Test/evidence plan

### 11.1. Что проверяется в этом child plan

| Evidence ID | Проверка | Ожидаемый результат | Root/формат |
|---|---|---|---|
| `E-001B-ENV-001` | Связь с `001-A`, WSL identity и pre-existing status | Environment dependency подтверждена | `preflight.md`, `git-status.txt` |
| `E-001B-ID-001` | CPython identity, version, machine, executable/hash, `SOABI` | Stable free-threaded CPython >= 3.14, provenance записан | `runtime-manifest.json` |
| `E-001B-GIL-001` | `Py_GIL_DISABLED` | Значение `1` | `runtime-probe.json` |
| `E-001B-GIL-002` | GIL до/после каждого stdlib import | Все обязательные значения `False` | `runtime-probe.json` |
| `E-001B-GIL-003` | stderr/warnings | Нет automatic-GIL warning | `stderr/*.log` + JSON summary |
| `E-001B-CONC-001` | Controlled concurrency, два повторных чистых процесса | Exit 0, детерминированный checksum, нет exception/timeout/deadlock | `controlled-concurrency-*.json` |
| `E-001B-REP-001` | Reproducibility audit | Команда, версии, paths, hashes, stdout/stderr и exit code полны | `command.txt` + evidence index |

### 11.2. Команды execution stage

Конкретный абсолютный путь к executable был выбран в execution и записан в
manifest. Ниже приведена фактически выполненная форма запуска; результаты
сохранены в `artifacts/feasibility/001-B/`:

```bash
cd /mnt/c/devel/sip-bot
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/nogil_probe.py
```

Команда повторена три раза с тем же executable и manifest. Runner и WSL
evidence сохраняют фактическую командную строку, environment summary, target
executable hash и exit code; wrapper зафиксирован в `tools/run_nogil_probe.ps1`.

### 11.3. Минимальный evidence contract

`artifacts/feasibility/001-B/` должен содержать не менее:

- `preflight.md` и `git-status.txt`;
- `runtime-manifest.json` с source/artifact digest, toolchain, build flags,
  prefix и executable hash;
- `probe-manifest.json` с явным stdlib import order и concurrency parameters;
- `run-01/`, `run-02/` и `run-03/` с `command.txt`, `stdout.log`, `stderr.log`,
  JSON summary и exit code;
- `evidence-index.md` со статусом каждого `E-001B-*` и ссылками на файлы.

JSON должен сохранять как минимум `plan_id`, UTC timestamps, target OS/arch,
Python identity, `SOABI`, `Py_GIL_DISABLED`, per-stage GIL states, import
manifest, warning summary, concurrency parameters/results, executable path and
sha256, command, stdout/stderr paths и process exit code.

### 11.4. Нерелевантные проверки

Не запускать в рамках acceptance этого plan:

- unit/contract/state-machine tests приложения;
- SIP/RTP integration, PCMU loopback, BYE, fake operator;
- ASR partial/final, LLM structured output, TTS audio/cancellation;
- VRAM, application latency, barge-in и multi-turn context.

Они не являются deferred failure этого plan; они принадлежат последующим
child plans или test-stand plan.

## 12. Deferred evidence conformance

**`not applicable`.** Этот child plan не создаёт тест, который ожидаемо должен
оставаться красным до отдельной corrective-задачи. Он создаёт диагностический
stdlib-only probe и сохраняемое evidence только на execution stage. Формальный
`tests/runtime/...` файл, локальные `skip`/`xfail`, selector или promotion hook
не создаются.

Если execution обнаружит необходимость в постоянном тесте, это будет новым
scope/plan decision с отдельным `evidence_id`, owner, командой deferred-run и
условием promotion; текущий plan не будет маскировать красный probe.

## 13. Legacy/fallback/simplification register

| ID | Что предлагается | Почему это не принимается молча | Как закрывается | Статус |
|---|---|---|---|---|
| `F-001B-001` | Обычный GIL-enabled CPython как «временный» baseline | Нарушает ADR-003 и не доказывает `M-G2` | Owner discussion; при изменении baseline — ADR и новый/обновлённый plan | `prohibited` |
| `F-001B-002` | `PYTHON_GIL=0` или другой флаг вместо проверки фактического GIL | Tag/flag не заменяет `sys._is_gil_enabled()` | Только корректный free-threaded build или owner-approved architectural change | `prohibited` |
| `F-001B-003` | Пропустить import/concurrency stage или ослабить assertion для `pass` | Скрывает неизвестный runtime behavior | Повторить probe или зафиксировать `fail`/blocker | `prohibited` |
| `F-001B-004` | Молчаливо вынести будущую native-зависимость в process isolation | `001-B` не принимает component process boundary | Отдельные `001-C*`/`001-D` и owner decision с IPC contract при необходимости | `out of scope; owner-gated` |
| `F-001B-005` | Сохранить legacy helper только ради удобства smoke | Tests-only legacy path запрещён APG | Удалить/не создавать; использовать один source-of-truth probe | `prohibited` |
| `F-001B-006` | Docker-only или обычный/GIL-enabled CPython вместо Ubuntu/WSL free-threaded baseline | Меняет authoritative baseline | Отдельное owner decision/ADR; не закрывает `001-B` | `out of scope` |

Допустимое упрощение для этого plan только одно: controlled-concurrency — это
ограниченный smoke, а не доказательство общей потокобезопасности или
производительности. Это не ослабляет no-GIL acceptance и не скрывает красный
результат.

## 14. Протокол неожиданного gap

При обнаружении требования, которого нет в source-map, зависимый slice
немедленно останавливается. Executor заполняет запись в evidence и owner
review:

```text
Обнаруженный gap:
Затронутые документы и компоненты:
Почему текущий план нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Нужен ли новый ADR/roadmap/plan-file:
Evidence, команда и exit code:
```

Минимальные примеры:

- Stable free-threaded CPython >= 3.14 нельзя воспроизводимо получить в Ubuntu/WSL2
  среде — не переключаться на обычный CPython и не объявлять `pass`;
- build или import запускает компонентный native-код — не добавлять этот
  import в probe, а передать вопрос в `001-C`/owner review;
- `Py_GIL_DISABLED == 1`, но GIL включается на стандартной import-фазе — не
  маскировать warning и не продолжать к component checks;
- для controlled concurrency нужен adapter, IPC или application channel — не
  создавать его в `001-B`, а оформить новый gap/plan.

До review запрещено вводить adapter, facade, fallback, compatibility bridge,
новый IPC-протокол, скрытый startup path или изменение runtime baseline.

## 15. Execution report и closeout template

Этот раздел заполняется после owner review и фактического execution. До
execution status plan может быть `accepted`, а status execution фиксируется
отдельно.

```text
Plan: 001-B
Уровень: child plan
Родительская Map: Map-001
Статус execution: [complete / blocked]
Owner review: [resolved date, owner, links/evidence]
Зависимость 001-A: [status and evidence path]

Фактические даты и исполненные slices:
- S0:
- S1:
- S2:
- S3:

Фактически изменённые файлы:
- [list; только write-set]
Внешний WSL prefix и executable:
- [absolute path]
Команды, версии и фактические exit codes:
- [list and evidence paths]
Runtime identity:
- CPython version:
- target OS/arch:
- SOABI:
- Py_GIL_DISABLED:
- executable sha256:

GIL stages:
- before stdlib imports:
- after each stdlib import:
- after stdlib import phase:
- after controlled concurrency:
- automatic-GIL warning:

Controlled concurrency:
- manifest parameters:
- repetitions:
- checksum/result:
- exceptions/timeouts/deadlocks:

Evidence index:
- [E-001B-* paths, stdout/stderr, commands, exit codes]
Blocker register:
- [resolved/open IDs and owner decisions]
Unexpected gaps:
- [none or concrete records]
Pre-existing failures / unrelated dirty changes:
- [record; do not attribute to this plan]
Изменённые owner-документы:
- [none, либо только явно разрешённые синхронизации]
Registry/backlog audit:
- document registry: [command/result or pending owner-controlled sync]
- task backlog: [not changed / command/result if changed]

Closeout decision:
- [pass / fail / pass_with_isolation is not valid for this plan]
M-G2 transition:
- [opened only with complete runtime evidence, or blocked]
Следующий узкий шаг:
- [001-C map/plan only after owner review]
Незакрытые дочерние пункты Map-001:
- [001-C, 001-C1..C4, 001-D, 001-E remain open]
```

Для этого child plan итоговый успешный статус — `complete`, а не
`MVP complete` и не `prod-ready complete`. `pass_with_isolation` не является
допустимым итогом `001-B`: этот plan не принимает и не оформляет component
isolation. Любой такой gap остаётся blocker-ом для owner discussion и
последующего child plan.
