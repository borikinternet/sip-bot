# Map-001: Scope freeze и feasibility к демонстратору 25 сентября

Уровень: `map`  
Статус: `complete`

Родительская roadmap: [`roadmap.md`](../roadmap.md)

Дата начала: 2026-08-26  
Жёсткий deadline демонстратора: 2026-09-24  
Дата доклада: 2026-09-25

Это map-level документ, а не исполняемый plan-file. Owner review структуры карты завершён 2026-08-26. Теперь можно
создавать child plan-файлы, но их execution stage начинается только после отдельного согласования каждого child plan.

## 1. Цель и проверяемый результат

К 27 августа получить согласованную карту feasibility и набор узких дочерних планов, а к 31 августа — закрыть их
последовательно подтверждённым минимальным набором runtime и компонентов:

- Ubuntu 24.04 LTS x86_64 в WSL2 доступна как основная Linux-среда;
- последняя доступная стабильная free-threaded-сборка CPython не ниже 3.14 выбирается и устанавливается воспроизводимо;
- для SIP/media, ASR, LLM и TTS есть по одному рабочему baseline-кандидату;
- для каждой критичной native-зависимости принято решение `main process` или `process isolation`;
- найден путь к локальному SIP/RTP loopback с PCMU;
- результаты каждого дочернего плана сохранены в отдельном evidence root под `artifacts/feasibility/` и позволяют
  открыть media/test-stand plan 1 сентября.

Этот map-file не пытается закрыть весь MVP и не утверждает baseline заранее. Он задаёт порядок снятия неопределённости,
которая может сорвать календарный план.

## 2. Scope boundary

### Входит

- классификация feasibility как карты, а не узкого среза;
- декомпозиция на узкие child plan-файлы и фиксация порядка их исполнения;
- owner review структуры карты и каждого child plan до его execution stage;
- общий контракт evidence, blocker register, process/architecture audit и closeout для дочерних планов;
- синхронизация roadmap, ADR, технического задания, backlog, registry и evidence по фактическому результату.

### Не входит

- выполнение дочерних feasibility-планов до их отдельного согласования;
- полноценная реализация SIP-бота;
- обучение, fine-tuning или подбор большого набора моделей;
- семантический turn detector и speculative LLM path;
- полноценный crawler/indexer русской Википедии;
- production packaging, HA, многосессионность и реальные PBX/операторы;
- перенос всей системы в Docker;
- попытка доказать production-ready no-GIL для каждого возможного Python-пакета;
- объединение runtime, native compatibility, SIP/media и AI smoke в один безымянный прогон.

### Protected baseline

- основной процесс остаётся на выбранной стабильной free-threaded-сборке CPython не ниже 3.14;
- несовместимый native runtime изолируется процессом, а не включает GIL всему приложению;
- SIP/media callbacks не зависят от завершения LLM;
- аудио и текстовый payload не проходят через Dispatcher;
- deadline не является основанием для молчаливого нарушения архитектурных инвариантов.

### Предположения о рабочем дереве

До появления кода изменения относятся к документам, plan-file, tools и evidence. Unrelated changes сохраняются. Перед
первой кодовой правкой зафиксировать `git status --short`.

## 3. Извлечённые правила

| Источник | Правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`roadmap.md`](../roadmap.md) | После 31 августа расширения demo-path запрещены | Кандидаты и cuts должны быть заморожены до 31 августа | Scope freeze record | Нет baseline для обязательного demo-flow |
| [`requirements.md`](../requirements.md) | Один русский SIP-разговор, context, barge-in, transfer и отчёт | Эти функции остаются acceptance boundary | Demo matrix | Предлагаемое упрощение ломает обязательный сценарий |
| [`architecture.md`](../architecture.md) | Dispatcher/control plane отдельно от data plane | Feasibility не должна подменять каналы глобальной очередью | Architecture audit | Кандидат требует LLM в SIP callback или payload через Dispatcher |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Основной процесс — последняя доступная стабильная free-threaded-сборка CPython не ниже 3.14 | Проверяем `Py_GIL_DISABLED` и фактический GIL | Runtime probe | GIL включается после критичного импорта без допустимой isolation |
| [`tooling-notes.md`](../tooling-notes.md) | Filename `cp314t` недостаточен, нужны import/operation checks | Evidence содержит состояние GIL по стадиям | JSON evidence | Есть только tag без поведения |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Различать map и child plan; каждому executable пункту дать self-contained APG и blocker register | Map-001 не разрешает выполнение child plans до owner review | Map/child-plan audit | Смешаны уровни или отсутствует child-plan contract |

## 4. Owner-review решения

| Вопрос | Текущее решение | Последствие | Статус |
|---|---|---|---|
| Какой Python? | Последняя доступная стабильная free-threaded-сборка CPython не ниже 3.14, Ubuntu 24.04 LTS x86_64 | Точную версию выбрать при execution и зафиксировать в evidence | `resolved` |
| Где работают несовместимые native-модули? | В отдельном локальном процессе | Нужен явный IPC adapter; основной процесс остаётся no-GIL | `resolved` |
| Нужен ли speculative LLM? | Нет, не в deadline-critical demo-path | LLM вызывается после финального пользовательского хода | `resolved` |
| Какой endpointing? | VAD + фиксированный soft/hard threshold | Semantic endpointing откладывается | `resolved` |
| Какой объём базы знаний? | Curated русский набор по естественным наукам | Runtime crawler/indexer не входит в этот slice | `resolved` |
| Какой SIP baseline? | PJSUA2/PJMEDIA проверяется первым; fallback не запускается автоматически | При провале сначала owner discussion; только затем возможен отдельный fallback plan | `resolved; fallback owner-gated` |
| Какова политика кандидатов? | Один основной кандидат на компонент; конкретный stable/local candidate выбирается в соответствующем execution plan; следующий проверяется только после провала предыдущего и owner decision | Не вести параллельный перебор кандидатов и не менять baseline молча | `resolved; selection task-owned` |
| Разрешён ли безопасный параллелизм? | Да, для независимого drafting/read-only analysis и disjoint write-set; зависимые execution gates и GPU-heavy checks последовательны | Main executor интегрирует результат и выполняет общий audit | `resolved` |
| Каковы deadline-cuts? | Cuts из roadmap 13.3 приняты для демонстрационного scope | Они не разрешают ослаблять acceptance внутри обязательного demo-flow | `resolved for demo scope` |

## 4.1. Почему это карта, а не узкий срез

Первоначальный «срез 1» объединял как минимум пять независимых acceptance-контуров: Linux-среду, free-threaded
runtime, native compatibility, SIP/media и четыре AI-контура. Каждый контур имеет собственные команды, зависимости,
критерии отказа и owner decisions. Поэтому его нельзя исполнять одним потоком как единый benchmark.

Особенно это относится к no-GIL-проверке: версия CPython, факт запуска free-threaded runtime, поведение после каждого
критичного импорта и поведение после операций компонента — разные проверки с разными failure modes. Импорт ASR не
заменяет проверку PJSUA2, а успешный запуск LLM не доказывает безопасность TTS или SIP callback path.

## 4.2. Карта дочерних планов

Структура карты согласована, а child plan-файлы созданы по отдельности. Каждый child plan должен быть самодостаточным
и иметь собственный APG, source-map, blocker register, test/evidence plan, реестр упрощений и closeout. Создание файла
не открывает его execution stage: для каждого плана требуется отдельное plan review.

| ID child plan | Узкая цель | Зависит от | Минимальный результат | Текущий статус |
|---|---|---|---|---|
| `001-A` | Закрыть Linux/WSL2 environment baseline: Ubuntu, пользователь, filesystem, GPU/CUDA и системные зависимости | — | Воспроизводимая команда входа и environment evidence | `complete` |
| `001-B` | Установить и проверить выбранную стабильную free-threaded-сборку CPython не ниже 3.14 без project native imports | `001-A` | Runtime identity, disabled GIL и controlled-concurrency evidence | `complete` |
| `001-C` | Разложить native compatibility по компонентам и выбрать метод проверки каждого | `001-B` | Утверждённая matrix child plans, а не общий smoke | `complete` |
| `001-C1` | Проверить SIP/PJSUA2/PJMEDIA import, callback/media operation и BYE responsiveness | `001-B`, `001-C`, `001-S` для peer-dependent slices | SIP/media candidate decision или isolation gap | `complete; candidate decision pass` |
| `001-C2` | Проверить выбранный ASR import, partial/final operation и cancellation boundary | `001-B`, `001-C` | ASR candidate decision или isolation gap | `complete; candidate decision pass` |
| `001-C3` | Проверить выбранный LLM import, one-question inference, VRAM и cancellation boundary | `001-B`, `001-C` | LLM candidate decision или isolation gap | `complete; candidate decision pass_with_isolation` |
| `001-C4` | Проверить выбранный TTS import, русский audio operation и cancellation boundary | `001-B`, `001-C` | TTS candidate decision или isolation gap | `complete; candidate decision pass` |
| `001-D` | Свести подтверждённые candidate decisions и проверить совместимость process boundaries | `001-C1`–`001-C4` | Baseline register с явными main-process/isolation границами | `complete; synthesis result pass` |
| `001-E` | Закрыть feasibility и подготовить следующие implementation gates; test-stand plan вынесен в `001-S` | `001-D` и применимые component closeouts | Map closeout, evidence index и следующий plan, прошедший plan review | `complete` |

`001-C` — самостоятельная карта карт. Для каждого компонента был задан отдельный порядок и критерий остановки;
результаты C1–C4 теперь передаются в `001-D` только по собственным closeout/evidence. Stable release, build и прочие
candidate details остаются в соответствующих child plans.

## 4.3. Map-level gates

| Gate | Условие открытия | Условие закрытия | Что запрещено до закрытия | Статус |
|---|---|---|---|---|
| M-G1 decomposition review | Структура `001-A`–`001-E` согласована | Owner review завершён, source-of-truth и сроки не противоречат roadmap | Исполнение child plan-файлов | `closed 2026-08-26` |
| M-G2 runtime gate | `001-A` и `001-B` закрыты evidence | CPython/no-GIL baseline подтверждён | Native imports и component smoke | `closed 2026-08-27` |
| M-G3 component gate | `001-C` и все применимые `001-C*` закрыты | Для каждого компонента есть baseline/isolation decision | Общая интеграция и выбор «на глаз» | `closed 2026-08-27` |
| M-G4 feasibility closeout | `001-D` имеет evidence | `001-E` фиксирует baseline register и следующий plan; следующий plan получил owner review | Media/test-stand implementation | `closed 2026-09-02` |

`001-A` закрыт статусом `complete` в пределах environment scope 2026-08-27: Ubuntu/WSL2, user, Linux source root, GPU/CUDA visibility,
disk threshold и generic tooling имеют собственное evidence. `001-B` также закрыт: CPython 3.14.7 free-threaded runtime
и stdlib-only no-GIL smoke воспроизводимо подтверждены. Component imports и operation smoke C1–C4 выполнены в их
собственных child plans; `001-D` и `001-E` имеют synthesis/closeout evidence. Следующий implementation plan получил
owner review 2026-09-02, поэтому Map-001 закрыта статусом `complete`.

## 5. Source-map

| Область | Файл/компонент | Текущее состояние | Целевое состояние | Действие |
|---|---|---|---|---|
| Python runtime | WSL/Ubuntu и `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` | Ubuntu 24.04.4 LTS, default user `sipbot` и runtime 3.14.7t проверены | Воспроизводимая stable free-threaded-сборка CPython >=3.14 с disabled GIL | `001-A`/`001-B` evidence |
| SIP/media | PJSUA2/PJMEDIA `2.17` + approved `001-S` peer | C1/stand lifecycle, PCMU и BYE evidence pass | SIP adapter implementation и application callback affinity | Использовать C1 patches и `001-S`; integration deferred |
| ASR | `faster-whisper==1.2.1`, large-v3 pinned revision | C2 import/operation/partial/final/close pass after exact patch | Application VAD/assembler/endpointing | Использовать C2 patch; integration deferred |
| LLM | Qwen3.5-9B GGUF Q4_K_M + Ollama `0.33.1` | C3 structured answer/VRAM/timing/cancel evidence pass_with_isolation | Full context/RAG/action FSM integration | Existing local HTTP IPC; no new bridge |
| TTS | XTTS-v2 `v2.0.3` + exact dependency patches | C4 import/operation/PCMU/cancel evidence pass | Real playback/barge-in integration | Preserve patches and disabled optional paths |
| Test evidence | `artifacts/feasibility/` | `001-A`–`001-E` и `001-S` evidence roots созданы; raw evidence disjoint | Implementation evidence root is next plan's responsibility | Не создавать новые roots без reviewed plan |
| Planning/backlog | `docs/roadmap.md`, `docs/task-backlog.md` | Deadline добавлен, TASK-001 `in_progress` | Map/child-plan gate отражён как planning state | Синхронизировать после каждого plan/child closeout |

## 5.0. Audit владельца поведения и парадигмы реализации

Неприменимо к map-level документу: Map-001 не добавляет и не изменяет runtime-алгоритм, public API, SIP-состояние,
FSM, channel generation или payload ownership. Такой audit обязателен в `001-C1`–`001-C4` и других child plans перед
их execution stage.

## 5.1. Process invariant audit

- Срез ограничен feasibility и не реализует поведение бота «на всякий случай».
- Зависимые execution gates выполняются последовательно; независимые drafting/read-only analysis могут выполняться
  параллельно только при раздельном write-set, отсутствии общего mutable state и наличии финального main-executor audit.
- GPU-heavy component checks и проверки, конкурирующие за один runtime/VRAM, выполняются последовательно; параллелизм не
  используется как способ скрыть незакрытый blocker.
- Для каждого среза ниже есть явный blocker register; необъяснённый красный результат останавливает зависимую работу.
- Релевантные проверки отделяются от нерелевантных; отсутствие теста не считается прохождением.
- В этом plan-file не создаются deferred tests, marker-ы или локальные `skip`/`xfail`; deferred evidence policy для этого
  среза явно `not applicable`.
- Registry и backlog синхронизируются при изменении Markdown и статуса задачи.
- Ни одна дата не оправдывает ослабление проверки, изменение protected baseline или молчаливое добавление fallback.

## 5.2. Architecture invariant audit

- Feasibility не переносит audio/text payload через Dispatcher и не связывает SIP callbacks с ожиданием LLM.
- SIP/media lifecycle проверяется независимо от AI-контуров; BYE должен иметь отдельный smoke path.
- Выбранная stable free-threaded-сборка CPython >=3.14 остаётся baseline main process; native incompatibility разрешается только явной process isolation.
- Кандидат не получает прямого права менять SIP-состояние: решения LLM остаются структурированным input для Dispatcher/FSM.
- PCMU, один разговор, локальный fake operator и отсутствие записи аудио сохраняются как protected demo invariants.
- В feasibility-срезе не вводятся новые facade/adapter/IPC-протоколы молча; если они нужны, срабатывает unexpected gap protocol.

## 5.3. Unexpected gap protocol

Если проверка выявляет неучтённую архитектурную работу, зависимый шаг немедленно останавливается и фиксируется:

```text
Обнаруженный gap:
Затронутые документы и компоненты:
Почему текущий plan нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Нужен ли новый ADR/roadmap/plan-file:
```

Запрещено продолжать за счёт скрытого fallback, startup-only path, ослабления acceptance или подмены целевого runtime.

## 5.4. Правило упрощений

Молчаливое намеренное упрощение запрещено. Cuts из раздела 13 `roadmap.md` — это заранее принятые границы
демонстрационного scope, а не разрешение ухудшать обязательный сценарий внутри него. Любое дополнительное упрощение должно
быть owner-approved и иметь запись в реестре ниже, владельца и corrective path. Красный результат нельзя превращать в
`pass` заменой теста, снижением assertion или неоговорённым fallback.

## 6. Map milestones, not execution slices

Разделы 6.1–6.5 — календарные milestones карты. Они не разрешают выполнять перечисленные проверки одним общим
потоком. Для фактической работы сначала создаются и согласуются `001-A`–`001-E`, применимые планы `001-C1`–`001-C4`
и отдельный unblock-plan `001-S` для локального VoIP-стенда.

### 6.1 Scope freeze record — 26 августа

Зафиксировать одну страницу с ответами на вопросы:

- какой именно демонстрационный сценарий показываем;
- какие функции считаются обязательными;
- какие функции явно отложены;
- какие кандидаты проверяются первыми;
- какие условия приводят к немедленному переходу на fallback.

Результат: запись в `artifacts/feasibility/scope-freeze.md` и синхронизация `roadmap.md`, `task-backlog.md` и
`document-registry.md`.

### 6.2 Environment inventory — 26–27 августа

Проверить и зафиксировать:

- Windows, WSL2, Ubuntu-дистрибутив, Docker Desktop и доступность GPU;
- свободное место и доступ к исходникам из Linux filesystem;
- возможность установить системные зависимости без зависимости от реального PBX;
- состояние рабочего дерева до начала кодовых изменений.

Если Ubuntu user distro отсутствует, это является инфраструктурным блокером первого дня, а не поводом менять
архитектуру на Docker-only.

### 6.3 Stable free-threaded CPython probe — 27–28 августа

Сделать минимальный probe, который сохраняет:

1. версию Python и архитектуру;
2. `sys._is_gil_enabled()` до импортов;
3. состояние после каждого критичного импорта;
4. состояние после минимальной операции компонента;
5. `Py_GIL_DISABLED` и диагностические признаки runtime;
6. результат controlled-concurrency smoke.

Недостающие native wheels допустимо собирать или проверять в отдельном child process. Автоматическое включение GIL
в основном процессе считается отрицательным результатом.

### 6.4 Candidate smoke matrix — 28–30 августа

Для каждого кандидата выполняется только минимальный сценарий, достаточный для решения:

| Контур | Минимальная проверка | Что измеряем | Решение |
|---|---|---|---|
| SIP/media | локальный вызов, answer/hangup, PCMU loopback, BYE | lifecycle и media path | main process или isolation/fallback |
| ASR | короткий русский PCMU/PCM фрагмент | partial/final, скорость, память | baseline или fallback |
| LLM | один вопрос по естественным наукам | structured decision, VRAM, время первого токена | baseline или fallback |
| TTS | короткий русский ответ | первый аудиофрагмент, формат, отмена | baseline или fallback |
| Operator fake | локальный принимающий endpoint | transfer и возврат control-события | обязательный стендовый элемент |

Каждая проверка должна завершаться одним из трёх статусов: `pass`, `pass_with_isolation`, `fail`. Исследование без
решения и без evidence не считается выполненным.

### 6.5 Feasibility closeout — 31 августа

До конца дня сформировать baseline register:

- версии и лицензии выбранных компонентов;
- команды запуска и минимальные зависимости;
- границы процессов и IPC, если isolation нужна;
- ориентировочные latency/VRAM/CPU результаты;
- известные ограничения и конкретные fallback-решения;
- список запрещённых до доклада расширений.

После closeout новые компоненты не исследуются, если они не закрывают обязательный demo-flow или не устраняют
зафиксированный blocker.

### 6.6. Обязательный map-level blocker register

Эта таблица фиксирует блокеры карты и milestones. Каждый child plan обязан иметь собственный register; его отсутствие
нельзя компенсировать строкой из этой таблицы. Статус `open` означает, что milestone нельзя закрыть до выполнения
проверки или owner decision. Статус `resolved` допускает закрытие только при наличии evidence.

| Срез | ID | Проверяемый триггер | Что блокируется | Владелец | Evidence/решение | Текущий статус 27 августа |
|---|---|---|---|---|---|---|
| 6.1 Scope freeze | `B-6.1-001` | Не утверждён обязательный demo-flow и список cuts | Весь deadline plan | project owner | Owner response 2026-08-26 + roadmap/Map-001 | `resolved` |
| 6.1 Scope freeze | `B-6.1-002` | Cut затрагивает обязательный сценарий, а не production-only функцию | Конкретный cut и все зависимые slices | project owner | Owner response 2026-08-26 + roadmap diff | `resolved` |
| 6.2 Environment | `B-6.2-001` | Ubuntu user provisioning не завершён или default user не воспроизводится | Runtime probe и все native smoke | project owner | `environment.md`; sipbot/default-user/sudo probes | `resolved` |
| 6.2 Environment | `B-6.2-002` | Не подтверждены GPU/CUDA, Linux filesystem и системные зависимости | Выбор и запуск baseline | project owner | `001-A` environment inventory/closeout | `resolved 2026-08-27` |
| 6.3 Python/no-GIL | `B-6.3-001` | Нет воспроизводимой stable free-threaded-сборки CPython >=3.14 | Основной runtime | project owner | `001-B` runtime evidence/closeout | `resolved 2026-08-27` |
| 6.3 Python/no-GIL | `B-6.3-002` | Критичный import/operation включает GIL в main process | Соответствующий компонент и его dependent slices | project owner | C1/C2/C4 exact patches; C3 explicit isolation | `resolved 2026-08-27` |
| 6.3 Python/no-GIL | `B-6.3-003` | Native build требует обхода protected baseline | Данный кандидат | project owner | Patch/isolation decisions сохранены; protected main baseline не обходился | `not triggered; constraints recorded` |
| 6.4 Candidate smoke | `B-6.4-001` | SIP/media не проходит локальный answer/hangup/PCMU/BYE smoke | Media/test-stand gate | project owner | C1 + `001-S` lifecycle/PCMU/BYE evidence | `resolved 2026-08-27` |
| 6.4 Candidate smoke | `B-6.4-002` | ASR/LLM/TTS не даёт минимальный наблюдаемый результат | Answer-path slices | project owner | C2/C3/C4 component evidence + baseline decision | `resolved 2026-08-27` |
| 6.4 Candidate smoke | `B-6.4-003` | VRAM/latency не позволяют выбрать baseline даже с разрешённой isolation | AI contour и deadline demo | project owner | C3 VRAM/timing pass_with_isolation; C2/C4 timings recorded; concurrency deferred | `resolved for individual candidates; contention deferred` |
| 6.5 Feasibility closeout | `B-6.5-001` | Для обязательного контура нет baseline или явно принятого fallback | Переход к 1 сентября | project owner | E baseline for selected components; integrated VAD/RAG/application flow deferred explicitly в Map-002 | `resolved 2026-09-02` |
| 6.5 Feasibility closeout | `B-6.5-002` | Нет команды, версии, exit code или сохранённого evidence | Доверие к feasibility result | project owner | E evidence index + child command/raw-output paths | `resolved 2026-08-27` |
| 6.5 Feasibility closeout | `B-6.5-003` | Дата 31 августа пропущена без owner decision по scope | Следующий календарный gate | project owner | Current date 2026-08-27; deadline not missed | `not triggered` |

## 7. Map-level test/evidence contract

Ниже задан только общий формат. Команды и acceptance конкретной проверки разрабатываются в соответствующем child plan
и не считаются готовыми к execution до его plan review.

Минимальный evidence-пакет под `artifacts/feasibility/`:

- `scope-freeze.md` — граница демонстратора;
- `environment.md` — фактическое окружение и версии;
- `runtime-probe.json` — CPython/no-GIL probe;
- `candidate-matrix.md` — результаты SIP/ASR/LLM/TTS smoke;
- `001-E/baseline-register.md` — выбранные версии, режимы, process boundaries и fallback;
- `001-E/closeout.md` — решение feasibility и открытые риски.

Проверки для acceptance этой карты:

1. registry/backlog audits проходят;
2. каждый child plan имеет собственный runtime/process/import/operation evidence contract;
3. SIP/media smoke не требует PBX и показывает PCMU/lifecycle только после согласования `001-C1`;
4. каждый обязательный AI-контур имеет отдельный baseline/isolation child result;
5. ни один результат не обозначен как `pass` без команды запуска и наблюдаемого результата;
6. map-level и child-level blocker registers закрыты либо имеют явный decision по результату выполнения;
7. карта не объявлена `complete`, пока дочерние планы не закрыты своими evidence и closeout.

## 8. Stop conditions

Работа по текущему slice останавливается для решения владельца, если:

- к 27 августа нет доступной Ubuntu user distro или воспроизводимого эквивалента;
- к 28 августа нет доказательства выбранной stable free-threaded-сборки CPython >=3.14 и поведения GIL;
- к 31 августа PJSUA2/PJMEDIA не проходит минимальный SIP/media smoke;
- к 31 августа отсутствует baseline хотя бы для одного из ASR/LLM/TTS;
- native-компонент включает GIL в main process, а isolation не проверена;
- кандидат требует реальный PBX, облачный сервис или запись аудио;
- исправление начинает расширять обязательный demo-flow вместо устранения блокера.

При stop condition фиксируется причина и работа останавливается. Fallback или изменение scope не выбираются автоматически:
сначала требуется owner decision и, если меняется архитектурный boundary, отдельный plan/ADR. Бесконечное продолжение
исследования после контрольной даты не допускается.

## 9. Реестр fallback и упрощений

Ниже перечислены согласованные scope boundaries. Они не разрешают ослаблять обязательные проверки и не могут
добавляться молча во время исполнения; это границы deadline scope, а не скрытые упрощения реализации.

| Что введено | Почему допустимо для MVP | Как ограничено | Где закрывается | Владелец | Статус |
|---|---|---|---|---|---|
| Native-пакет несовместим с no-GIL | Сохраняет выбранный runtime baseline, но требует отдельного решения | Child process и узкий IPC adapter | Отдельный ADR/child plan после owner discussion | project owner | `approved policy; owner-gated` |
| Streaming ASR нестабилен | Позволяет показать распознавание без смены пользовательского сценария | Короткие чанки с partial/final агрегацией | Speech pipeline slice; streaming upgrade — follow-up | project owner | `approved demo scope` |
| Retrieval слишком дорог | Достаточно для заранее ограниченной естественно-научной базы | Небольшой заранее подготовленный индекс | Knowledge-base implementation slice; расширение — follow-up | project owner | `approved demo scope` |
| Контекст слишком велик | Сохраняет multi-turn демонстрацию | Rolling transcript и детерминированный файл-снимок | Dialogue implementation slice; summary model — follow-up | project owner | `approved demo scope` |
| Семантический endpointing не готов | Позволяет показать смену хода в срок | VAD и фиксированный soft/hard timeout | Speech pipeline slice; semantic detector — follow-up | project owner | `approved demo scope` |
| Реальный оператор недоступен | Внешняя КЦ не входит в проект | Локальный fake operator endpoint | Media/test-stand slice; real PBX integration — out-of-scope | project owner | `approved demo scope` |

## 10. Execution report template

При закрытии plan-file заполнить:

- фактические даты и исполненные slices;
- команды и версии окружения;
- выбранные SIP/ASR/LLM/TTS baseline;
- компоненты, оставшиеся в main process, и изолированные процессы;
- отрицательные результаты и причины отказа;
- ссылки на evidence;
- изменения в `task-backlog.md` и следующий plan-file;
- остаточные риски к 24 сентября.
