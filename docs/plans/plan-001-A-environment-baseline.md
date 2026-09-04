# Plan: 001-A — Environment baseline Ubuntu 24.04/WSL2

Уровень: `child plan`  
Статус owner review: `accepted`  
Статус исполнения: `complete`  
Родительская карта: [`Map-001`](plan-001-deadline-feasibility.md)  
Зависимости: нет; открывает `001-B` только после собственного closeout  

Owner review: `2026-08-27` — план прочитан и принят к execution в рамках распоряжения продолжать работу без новых
уточняющих вопросов; технические детали остаются execution-задачами.

Этот документ является self-contained child plan для environment boundary карты `Map-001`. Создание файла было только
планированием; последующее execution `001-A` зафиксировано в отдельном evidence root. Project runtime, CPython, native
imports и модели в `001-A` не запускаются.

## Цель и результат

Цель — закрыть воспроизводимый baseline Linux-среды для последующих feasibility-планов:

- Ubuntu 24.04 LTS x86_64 работает в WSL2;
- default user — `sipbot`, вход и разрешённый sudo-путь воспроизводимы без утечки секрета;
- согласован canonical source placement в Linux filesystem, не зависящий от `/mnt/c`;
- из Ubuntu подтверждена видимость NVIDIA GPU и CUDA driver/toolkit layer, а состояние каждой части явно
  различено;
- зафиксированы свободное и общее место на host- и Linux-filesystem, включая canonical source filesystem;
- инвентаризированы и при необходимости подготовлены минимальные базовые системные зависимости;
- сохранён reproducible inventory с командами, версиями, архитектурой, exit code, stdout/stderr и временем проверки.

Ожидаемый результат исполнения — отдельный evidence root
`artifacts/feasibility/001-A-environment-baseline/` с inventory и closeout. Для Linux source path используется
`/home/sipbot/src/sip-bot` как рабочий default; фактический canonical path фиксируется execution evidence.

Имеющееся [`artifacts/feasibility/environment.md`](../../artifacts/feasibility/environment.md) используется как
bootstrap evidence: оно подтверждает уже сделанные проверки Ubuntu/user provisioning, но не закрывает этот plan.
В частности, из него не следует, что CUDA видна из Ubuntu, source checkout находится в Linux filesystem или базовые
системные зависимости воспроизводимы.

`001-A` не закрывает `Map-001`, не устанавливает выбранную stable free-threaded-сборку CPython >=3.14 и не проверяет её free-threaded поведение. Эти
проверки принадлежат `001-B`. Он также не импортирует и не запускает SIP/PJSUA2/PJMEDIA, ASR, VAD, LLM, TTS,
audio/native modules или их project adapters; такие проверки принадлежат `001-C` и `001-C*`.

## Применимые документы и извлечённые правила

| Источник | Правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | MVP работает локально в Linux/WSL, целевой GPU — NVIDIA RTX 5060 Ti, внешние cloud/PBX-сервисы и запись аудио не входят | Проверяется только доступность среды и оборудования; пользовательский сценарий не исполняется | WSL/GPU/disk inventory | Целевая Ubuntu/WSL или локальная GPU-среда не подтверждена |
| [`architecture.md`](../architecture.md) | Control plane и data plane разделены; Dispatcher не является транзитом payload | Environment setup не добавляет каналов, adapter-ов или runtime-поведения | Architecture invariant audit ниже | Для закрытия среды предлагается изменение ownership, Dispatcher или IPC-контракта |
| [`technical-specification.md`](../technical-specification.md) | Первичный baseline — Ubuntu 24.04 LTS x86_64 в WSL2; конфигурация проекта будет в `config/constants.py`; native incompatibility не допускается в main process | Фиксируются OS/WSL facts и hand-off prerequisites; `config/constants.py` и project runtime не создаются | OS/config boundary inventory | Требуется смена основного OS/runtime baseline или скрытый native fallback |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM не управляет SIP напрямую, Dialogue Manager владеет состоянием разговора | План не создаёт LLM/SIP поведения и не меняет владельцев | Owner/architecture audit | Environment decision начинает выдавать модели прямой SIP-доступ |
| [`ADR-002`](../decisions/ADR-002-llm-model-selection.md) | LLM выбирается после измерений на RTX 5060 Ti и с учётом конкуренции за VRAM | Фиксируются GPU name, driver, memory и CUDA visibility, но модели не скачиваются и не импортируются | GPU/CUDA evidence | Отсутствие GPU скрывается за CPU-only подменой или выбирается модель до component benchmark |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Main process должен быть на выбранной stable free-threaded-сборке CPython >=3.14; несовместимые native-компоненты изолируются явно | 001-A только сохраняет environment prerequisite; runtime identity, GIL и native compatibility остаются в 001-B/001-C* | Scope audit и hand-off gate | В plan добавляется CPython probe или native import |
| [`Map-001`](plan-001-deadline-feasibility.md) | `001-A` — отдельный child plan без зависимостей; его результатом является воспроизводимая команда входа и environment evidence | Evidence имеет собственный root, а bootstrap не считается closeout | Child-level blocker register и closeout | План объявляет `001-A` закрытым по одному bootstrap-файлу |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan обязан иметь scope, source-map/write-set, audits, slices, blockers, evidence, fallback register и closeout | Все обязательные блоки находятся в этом файле; создание плана не запускает execution stage | Полный APG audit | Есть отсутствие обязательного блока или незаписанный blocker |
| [`documentation-process.md`](../documentation-process.md) | У факта должен быть один документ-владелец; после Markdown-изменения нужен registry audit | Этот plan владеет только своим execution contract; registry/backlog/roadmap не переписываются в текущем draft | Governance action после draft | Факт среды дублируется как новый нормативный источник или registry выдаётся за проверенный |
| [`tooling-notes.md`](../tooling-notes.md) | WSL Ubuntu — authority для GPU/runtime evidence; Docker не заменяет WSL; команда и exit code обязательны | Inventory снимается из Ubuntu и сохраняет raw evidence; Docker-only путь не вводится | Evidence manifest | Проверка выполнена только в Docker/Windows или потерян фактический exit code |

## Граница задачи

### Входит

- read-only re-probe уже подготовленных WSL/Ubuntu/user facts;
- фиксация dirty worktree и границы отдельного evidence write-set;
- выбор и проверка Linux-side source placement после owner review;
- inventory GPU/CUDA visibility из Ubuntu и host/Linux disk capacity;
- inventory базовых OS/tooling dependencies и проверка их воспроизводимости;
- сохранение команд, версий, архитектуры, exit codes, stdout/stderr, статуса и redaction notes;
- явная передача результата в `001-B`, без исполнения 001-B.

### Не входит

- установка, сборка или probe CPython >=3.14, проверка `Py_GIL_DISABLED`, `sys._is_gil_enabled()` и
  controlled concurrency;
- импорт, установка или operation smoke SIP/PJSUA2/PJMEDIA, RTP, ASR, VAD, LLM, TTS, audio/native modules и
  project adapters;
- выбор baseline-кандидата, model download, inference, VRAM benchmark модели, SIP/RTP loopback или fake operator;
- реализация `config/constants.py`, Dispatcher, Dialogue FSM, channel, IPC, facade, fallback или compatibility
  bridge;
- запуск project runtime, тестового SIP/RTP стенда, Docker-based replacement среды или cloud service;
- изменение требований, архитектуры, technical specification, ADR, parent Map, roadmap, backlog, registry или
  существующего bootstrap evidence;
- запись, хранение или перенос аудио и секретов.

### Protected baseline

- Авторитетная среда — Ubuntu 24.04 LTS x86_64 в WSL2. Docker остаётся только peer/test-stand lane и не является
  заменой Ubuntu.
- Основной runtime baseline родительской карты — latest stable free-threaded CPython >= 3.14; этот plan его не
  устанавливает и не подменяет обычным CPython или CPU-only вариантом.
- Default user — `sipbot`; исправление user provisioning не выполняется молча.
- Canonical source root должен находиться в Linux filesystem под `/home/sipbot/src/sip-bot`, но не под `/mnt/c`.
  Если позже появится source content, его checkout/revision фиксируются повторным probe.
- NVIDIA passthrough и CUDA visibility проверяются из Ubuntu; отсутствие CUDA не превращается автоматически в
  CPU fallback.
- Существующие пользовательские изменения сохраняются; evidence пишется только в назначенный root после фиксации
  исходного состояния.

### Предположения о dirty worktree

Текущий worktree не считается чистым. По состоянию чтения присутствуют пользовательские `.idea/`, `.codex/`,
`.gitignore`, `artifacts/`, `docs/` и `tools/` изменения/файлы. Это не повод их удалять, перемещать или включать в
write-set этого plan. Перед execution сохранён `git status --short`; если позже появится Linux checkout, его
revision/status фиксируются отдельным повторным probe. Нельзя автоматически синхронизировать незакоммиченные
Windows-изменения в Linux source root: при такой необходимости сначала нужен owner decision.

### Зависимости и внешние сервисы

- Host Windows с WSL2 и Ubuntu-24.04, а также установленный host NVIDIA driver являются инфраструктурными
  зависимостями.
- Для inventory системных пакетов может потребоваться доступ к согласованным Ubuntu package repositories. Это не
  является cloud inference или внешней SIP/PBX-зависимостью.
- Для 001-A не требуются реальные PBX, SIP peer, model registry, cloud API или внешний оператор.
- `001-B` зависит от закрытого source/filesystem и базового OS inventory; `001-C`/`001-C*` дополнительно зависят
  от component-specific packages и GPU evidence, но эти зависимости в 001-A не импортируются.

## Source-map и write-set

| Область | Файл/компонент | Текущее состояние | Целевое состояние | Gap | Действие в 001-A |
|---|---|---|---|---|---|
| WSL/Ubuntu identity | `Ubuntu-24.04` через WSL2 | Bootstrap сообщает Ubuntu 24.04.4 LTS, WSL2 и systemd; самостоятельный child evidence ещё отсутствует | Воспроизводимая команда входа показывает distro, release, kernel/WSL mode и architecture | Нужна повторная проверка с raw exit code | Выполнить A-001 и сохранить identity evidence |
| Default user/sudo | `sipbot`, `/etc/wsl.conf` | Bootstrap сообщает uid 1000 и passworded sudo; это не повторено в evidence root 001-A | `id -un`, uid, группы и разрешённый sudo-путь совпадают с bootstrap | Любое расхождение требует gap handling | Re-probe; `/etc/wsl.conf` не менять в рамках A |
| Source placement | Linux source root, путь `/home/sipbot/src/sip-bot` | Рабочий каталог агента — `C:\devel\sip-bot`; Linux source root и filesystem type проверены, но в проекте пока нет source content/коммитов | `pwd -P`, mount/filesystem и `df` показывают Linux filesystem; repository/revision проверяются, когда source content появится | До появления source content revision/checkout неприменимы | A-002; проверить source root без копирования dirty Windows content |
| GPU driver path | WSL Ubuntu NVIDIA visibility | Host `nvidia-smi` видел RTX 5060 Ti, 16311 MiB; Ubuntu visibility не проверена | Ubuntu `nvidia-smi` возвращает GPU name, driver, memory и exit code | WSL passthrough/CUDA userspace может отличаться от host | A-003; зафиксировать driver API отдельно от toolkit |
| CUDA toolkit/userspace | `nvcc`, CUDA shared libraries и loader inventory | Не проверено | Состояние `present/absent/unknown` каждой проверяемой части зафиксировано; отсутствие не скрыто | Нужные для выбранных компонентов layers выясняются execution probe | A-003; не выбирать CPU fallback и не ставить driver/toolkit молча |
| Disk | Host `C:` и Linux source filesystem | Host evidence сообщает `107210481664` свободных bytes; Linux source volume не измерен | Total/free bytes, mount и timestamp доступны; свободно не менее `20 ГБ` на каждом relevant filesystem | Фактический объём Linux filesystem не измерен | A-003; применить заданный порог `20 ГБ` |
| Base system dependencies | Ubuntu package database и package repositories | Состав пакетов и источники не зафиксированы | Execution-derived manifest содержит package/version/arch/source/installed state и воспроизводимую проверку | Manifest ещё не получен | A-004; component-specific/native deps передаются 001-B/001-C* |
| Reproducible evidence | `artifacts/feasibility/environment.md` | Bootstrap partial evidence существует | Собственный root 001-A содержит manifest, command log, raw outputs, status и redaction record | Нельзя дописать bootstrap как будто это closeout | A-005; bootstrap только read-only reference |
| Worktree governance | `git status --short`, protected docs | Есть unrelated changes и текущий draft создаётся отдельно | Фактический write-set не пересекает protected baseline | Registry/backlog sync выполняется интегратором после drafting | Capture status; не смешивать evidence и tracked docs |

### Write-set текущей drafting-сессии

В этой сессии допустим ровно один repository write: создание
`docs/plans/plan-001-A-environment-baseline.md` через `apply_patch`. Никакие команды runtime, установки пакетов,
правки evidence, registry, backlog, roadmap или иных файлов не выполняются.

### Write-set будущего execution stage

После owner review execution stage может писать только:

- `artifacts/feasibility/001-A-environment-baseline/**` — inventory, command manifest, raw stdout/stderr, hashes,
  gap register и closeout;
- в Ubuntu-24.04 — только owner-approved `/etc/wsl.conf`, если отдельный repair slice будет явно разрешён и его
  diff попадёт в evidence;
- в Ubuntu-24.04 — Linux source root под `/home/sipbot/src/sip-bot`; будущий checkout не создаётся автоматически и не
  получает dirty Windows content;
- Ubuntu package database и установленные пакеты только по утверждённому A-004 manifest, с сохранёнными командами и
  версиями.

Запрещено писать или изменять `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md`,
`docs/plans/plan-001-deadline-feasibility.md`, requirements/architecture/technical specification, ADR-файлы,
`artifacts/feasibility/environment.md`, project source, `.idea/`, `.codex/`, `.gitignore/` и `tools/` в рамках
execution этого child plan. Запрещены удаление/перемещение пользовательских файлов, сохранение credentials,
model downloads, audio artifacts, Docker-only replacement, `/mnt/c` canonical placement и любые native imports.

## Audit владельца поведения и парадигмы реализации

`Not applicable`. План не добавляет public algorithm, runtime service, SIP/FSM/channel behavior, data-plane helper,
adapter или API. Поэтому нет нового объекта, который должен владеть состоянием, lifecycle, отменой или
component-specific semantics. Environment capability и evidence принадлежат владельцу проекта/оператору среды;
они не становятся владельцем поведения Dialogue Manager, SIP adapter или любого AI-компонента.

Если при execution появится необходимость в helper, startup path, adapter, IPC или коде, он выходит за этот audit и
срабатывает unexpected gap protocol до продолжения.

## Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Какую среду считать авторитетной? | Ubuntu 24.04 LTS x86_64 в WSL2; Docker только для явно назначенного peer/test-stand lane | Все environment probes выполняются из Ubuntu, а Docker-only результат не закрывает 001-A | `resolved` (наследовано из Map-001/APG) |
| Считать ли bootstrap `environment.md` закрытием 001-A? | Нет; это partial bootstrap evidence, используемое read-only | Нужен отдельный root и полный inventory | `resolved` |
| Какой Linux source path использовать? | `/home/sipbot/src/sip-bot`; это рабочее решение для execution, а не отдельный вопрос согласования | A-002 проверяет доступность и filesystem facts; `/mnt/c` не используется как silent fallback | `resolved by plan` |
| Какой минимум свободного места необходим? | `20 ГБ` свободного места на Windows и `20 ГБ` на Linux filesystem | A-003 проверяет фактические bytes; меньший запас блокирует environment closeout | `resolved by owner` |
| Что считается CUDA baseline? | Проверить фактическую видимость RTX 5060 Ti из Ubuntu и необходимые driver/toolkit/library layers; состав слоёв выясняется probe | `nvidia-smi` не маскирует отсутствие нужного слоя; CPU-only не вводится молча | `resolved as execution task` |
| Какой базовый package manifest разрешён? | Execution сам определяет минимальный воспроизводимый набор системных пакетов и фиксирует его в evidence; component-native deps остаются другим планам | Отсутствующий/нерепродуцируемый пакет фиксируется как runtime blocker, а не как вопрос предварительного согласования | `resolved as execution task` |
| Можно ли чинить user/WSL/driver автоматически? | Нет; repair, Windows driver change и repository change требуют owner discussion и отдельной записи | Красный probe останавливает зависимый slice | `resolved` (политика) |
| Можно ли использовать CPU-only или Docker-only результат? | Нет как silent fallback; такой вариант требует owner decision и отдельного plan/ADR при изменении boundary | 001-A остаётся `blocked` при отсутствии требуемого Ubuntu/GPU baseline | `resolved` (политика) |
| Что открывает следующий child plan? | Только собственный 001-A closeout с полным evidence и owner acceptance | После этого можно открыть 001-B; native imports остаются запрещены | `resolved` |

## Process invariant audit

| Инвариант APG | Аудит 001-A | Статус |
|---|---|---|
| Срез узкий и имеет наблюдаемый результат | Scope ограничен environment evidence; результат — воспроизводимый inventory, а не runtime smoke | `pass by design` |
| Релевантные и нерелевантные проверки различены | WSL/user/source/GPU/disk/package probes релевантны; CPython/no-GIL/native/component tests явно переданы 001-B/001-C* | `pass by design` |
| Авторитетный environment baseline выбран | Ubuntu/WSL2 является authority; Docker не используется для закрытия среды | `pass by design` |
| Dirty worktree не смешивается | Status snapshot сохранён; write-set ограничен evidence root и разрешёнными внешними paths | `pass with evidence` |
| Один документ остаётся владельцем факта | Plan владеет execution contract, а actual environment values принадлежат generated evidence; требования и архитектура не копируются как новые требования | `pass by design` |
| Registry/backlog checks выполняются после соответствующих изменений | Registry и backlog после изменения execution state проверены отдельными governance-командами; roadmap не изменялся | `pass with evidence` |
| Fallback и simplification явны | Реестр ниже фиксирует отсутствие введённого fallback; CPU-only, Docker-only и `/mnt/c` запрещены без owner decision | `pass by design` |
| Production-ready свойства не объявляются | Plan закрывает foundation baseline, не production environment или capacity guarantee | `pass by design` |
| Deferred evidence не маскируется `skip`/`xfail` | Тесты не создаются; deferred evidence conformance явно `not applicable` | `pass by design` |
| Команды воспроизводимы | Command manifest, tool versions, exit codes, stdout/stderr и redaction record сохранены в evidence root | `pass with evidence` |
| Closeout отражает pre-existing и out-of-scope | Template требует dirty worktree, незакрытые blockers и переданные 001-B/001-C* boundaries | `pass by design` |

## Architecture invariant audit

| Архитектурный инвариант | Воздействие 001-A | Контроль |
|---|---|---|
| Dispatcher владеет control plane и Dialogue FSM | Не затрагивается | Не создавать runtime code или control message |
| SIP/media callbacks не ждут AI и обрабатывают BYE | Не затрагивается | SIP/media operation запрещён в scope |
| Audio/text payload идут по data plane, не через Dispatcher | Не затрагивается | Не создавать channels, adapters или payload bridge |
| Closed channel делает stale producer безвредным | Не затрагивается | Channel lifecycle не проверяется в 001-A |
| Только final ASR может менять FSM и разрешать TTS | Не затрагивается | ASR/LLM/TTS imports и operation запрещены |
| Speculative result не выполняет irreversible action | Не затрагивается | Не создавать speculative/runtime path |
| TTS playback отменяем и поколения не смешиваются | Не затрагивается | TTS/audio test передан 001-C4 |
| LLM выдаёт ограниченное structured decision без SIP access | Не затрагивается | Model/inference не запускаются; ADR-001/002 сохраняются |
| MVP PCMU, без реальных внешних сервисов и аудиозаписи | Сохраняется как protected baseline | Не подключать SIP/PBX/cloud и не писать audio |
| Config хранится в `config/constants.py` | Не создаётся и не изменяется в 001-A | Не вводить hidden environment defaults вместо config contract |
| Free-threaded CPython и native isolation | Только dependency hand-off; проверки принадлежат 001-B/001-C* | Не устанавливать CPython и не импортировать native components |
| У каждого канала есть owner/close/cancel | Не затрагивается | Не создавать channel behavior |

## Узкие implementation slices

Каждый slice выполняется только после owner review этого child plan. Команды в этом разделе и в evidence contract
ниже являются будущей спецификацией запуска; в текущей drafting-сессии они не исполняются.

### A-001 — Bootstrap provenance и dirty-worktree snapshot

Граница: повторно проверить WSL/Ubuntu release, WSL2, `sipbot`, uid/groups, sudo semantics, systemd indication и
зафиксировать host/Linux worktree status. Использовать `environment.md` как input, не переписывая его.

Допустимый write-set: только `artifacts/feasibility/001-A-environment-baseline/bootstrap/` и raw command outputs.
Repair `/etc/wsl.conf`, credential handling и source synchronization в этот slice не входят.

Acceptance:

- отдельные probes с exit code подтверждают Ubuntu 24.04.x, x86_64 и WSL2;
- `id -un`/uid/groups показывают `sipbot`, а sudo probe имеет явный результат без сохранения пароля;
- исходный `git status --short` и дату фиксации можно сопоставить с write-set;
- bootstrap evidence помечено как reference, а не как closure.

Stop conditions: distro/user mismatch, необходимость скрытого repair, потеря raw exit code или обнаружение overlap с
чужим write-set. Следующий slice — A-002 и A-003 после закрытия нужных blocker IDs.

### A-002 — Linux filesystem и source placement

Граница: по пути `/home/sipbot/src/sip-bot` проверить `pwd -P`, mount/filesystem type и `df` из Linux. Если source
content уже существует, дополнительно проверить repository root, revision и статус checkout. В текущем проекте source
content и коммиты отсутствуют, поэтому пустой Linux source root является достаточным prerequisite для `001-A`; dirty
Windows changes не копируются автоматически.

Допустимый write-set: Linux checkout directory `/home/sipbot/src/sip-bot` без изменения tracked content и
`artifacts/feasibility/001-A-environment-baseline/source-placement/`. `/mnt/c` можно зафиксировать как текущий host
path, но нельзя принять за canonical source placement.

Acceptance: canonical path находится в Linux filesystem под `/home/sipbot/src/sip-bot`; path, filesystem и free bytes
записаны; source root доступен как `sipbot`. Если source content отсутствует, это явно записано как `not applicable yet`;
если source content существует, также фиксируются repository root, revision и worktree state.

Stop conditions: canonical path недоступен, будущий source доступен только через `/mnt/c`, создание mirror требует
silent merge dirty changes, или source path пересекает protected files. Следующий slice — A-003/A-004 при наличии source
root evidence.

### A-003 — GPU/CUDA visibility и disk inventory

Граница: из Ubuntu, а не только из Windows, проверить WSL-visible NVIDIA driver/GPU, CUDA toolkit/shared-library
visibility и capacity relevant filesystems. Не запускать model inference и не импортировать Python/CUDA bindings.

Допустимый write-set: `artifacts/feasibility/001-A-environment-baseline/gpu-disk/` и только raw inventory. Изменение
Windows/NVIDIA driver или установка WSL driver/toolkit не входит без отдельного owner decision.

Acceptance:

- Ubuntu `nvidia-smi` имеет exit code 0 и сообщает фактическое имя GPU, driver version и memory total/free;
- driver API, `nvcc` availability и relevant loader/library fields сохранены раздельно как `pass`, `absent` или
  `unknown`;
- host C: и Linux source filesystem имеют total/free bytes, mount и timestamp;
- заданный порог `20 ГБ` применён и результат не подменён CPU-only или Docker-only evidence.

Stop conditions: Ubuntu GPU probe fails, значения host и Ubuntu необъяснимо расходятся, либо свободное место ниже `20 ГБ`,
или нужная toolkit component отсутствует и требуется fallback. Следующий slice — A-004 только после явного
решения по соответствующему blocker.

### A-004 — Base OS/tooling dependency inventory

Граница: inventory и подготовка минимального общего OS/tooling manifest. Кандидатный список
выше не является разрешением на установку. Component-specific native libraries, Python packages, CPython build/install
steps и model dependencies принадлежат 001-B/001-C*.

Допустимый write-set: `artifacts/feasibility/001-A-environment-baseline/dependencies/` и Ubuntu package state только
по execution-derived manifest. Сначала фиксируются apt sources, architecture, installed versions и simulation result;
необъяснимое расхождение останавливает slice.

Acceptance: для каждого разрешённого package name зафиксированы installed/available version, architecture, source,
команда и exit code; manifest можно повторно проверить в той же Ubuntu distro; отсутствующий пакет классифицирован,
а не скрыт `|| true`.

Stop conditions: package source недоступен, manifest требует CPython/native component import, установка выходит за
agreed scope или result нельзя воспроизвести. Следующий slice — A-005.

### A-005 — Reproducible inventory synthesis и child closeout

Граница: собрать отдельный `inventory.md`, машинно читаемый `inventory.json`, command manifest, raw output index,
redaction record и closeout. Сверить все blocker IDs и оформить hand-off к 001-B.

Допустимый write-set: `artifacts/feasibility/001-A-environment-baseline/{inventory.md,inventory.json,commands.md,closeout.md,redaction.md}`
и связанные raw outputs. Parent Map, registry, backlog и roadmap не обновляются этим slice.

Acceptance: каждый required field имеет source command, timestamp, exit code и status; bootstrap clearly labelled;
dirty worktree и protected baseline отражены; unresolved red result не превращён в `pass`; зафиксированы source path,
порог `20 ГБ`, CUDA semantics и dependency manifest.

Stop conditions: отсутствует raw evidence, незакрыт обязательный blocker, owner review не получен или hand-off требует
CPython/native work. Успешный результат открывает только `001-B`; `001-C`/`001-C*` ждут его собственных gates.

## Blocker register

Статусы ниже относятся к proposed plan до execution. Bootstrap evidence может быть входом в доказательство, но не
переводит child blocker в `resolved` без нового command/evidence record.

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-001-A-001` | A-001 | WSL не доступен, distro не `Ubuntu-24.04`/не WSL2, release/arch не подтверждены отдельным probe | Весь 001-A и 001-B | project owner | `bootstrap/wsl-status.*`, `os-release.*`, `uname.*` | `resolved` |
| `B-001-A-002` | A-001 | Default user не `sipbot`, uid/groups расходятся или sudo semantics не воспроизводимы | A-002 и все dependent plans | project owner | `environment.md` bootstrap + `bootstrap/user-sudo.*` | `resolved` |
| `B-001-A-003` | A-002 | `/home/sipbot/src/sip-bot` недоступен, будущий source попадает под `/mnt/c` или source недоступен `sipbot` | Source baseline и 001-B | project owner | `source-placement/inventory.*`, `findmnt/df/git` outputs | `resolved; not triggered` |
| `B-001-A-004` | A-003 | Ubuntu `nvidia-smi` не видит RTX 5060 Ti/driver или GPU data имеет необъяснимое расхождение с host | GPU-dependent 001-C3 и environment closeout | project owner | `gpu-disk/nvidia-smi.*`, host/Ubuntu comparison | `resolved` |
| `B-001-A-005` | A-003 | Нужный для согласованного candidate path CUDA layer отсутствует или фактическая GPU visibility не подтверждена | GPU-dependent candidate checks | project owner | `gpu-disk/cuda-visibility.*`, probe result | `open on trigger` |
| `B-001-A-006` | A-003 | Не измерены relevant filesystems или свободное место меньше `20 ГБ` на Windows/Linux | Source placement, model/runtime provisioning и closeout | project owner | `gpu-disk/disk.*`, threshold record | `open on trigger` |
| `B-001-A-007` | A-004 | Нужный базовый пакет недоступен, apt source/version/arch не воспроизводимы или пакет выходит за scope | 001-A closeout и 001-B hand-off | project owner | `dependencies/manifest.*`, apt simulation/inventory | `open on trigger` |
| `B-001-A-008` | A-001/A-002 | Planned evidence/write-set пересекается с существующими `.idea/.codex`, docs, artifacts, tools или dirty source | Безопасное выполнение всех slices | project owner | initial/final `git status --short`, path comparison | `resolved; no overlap` |
| `B-001-A-009` | A-005 | Не сохранены команда, version, architecture, exit code, stdout/stderr, timestamp или redaction record | Доверие к environment result | project owner | `inventory.json`, raw-output index, hashes | `resolved` |
| `B-001-A-010` | A-005 | Execution пытается закрыть environment без обязательного inventory/evidence или вводит silent fallback | 001-A closeout и открытие 001-B | project owner | review record + closeout | `resolved; not triggered` |

`B-6.2-002` из Map-001 покрывается child IDs `B-001-A-003`–`B-001-A-007`. Ни один из них нельзя закрыть строкой
из map-level register или одним host-only probe.

## Test plan и evidence

### Статус проверки

В этом plan создаются не тесты приложения, а environment probes и reproducible inventory. Unit, contract,
state-machine, SIP/RTP, BYE, barge-in, stale-result, multi-turn, no-GIL/import, VRAM/latency и component operation
tests не входят в 001-A и должны быть созданы/запущены в соответствующих child plans. Отсутствие этих тестов не
является pass для 001-A.

### Evidence contract

Будущий execution сохраняет минимум:

```text
artifacts/feasibility/001-A-environment-baseline/
  bootstrap/
  source-placement/
  gpu-disk/
  dependencies/
  raw/<probe-id>.stdout
  raw/<probe-id>.stderr
  inventory.md
  inventory.json
  commands.md
  redaction.md
  closeout.md
```

Для каждого probe фиксируются: `evidence_id`, UTC/local timestamp с timezone, exact command, working directory,
user, distro, tool version, exit code, stdout path, stderr path, expected result, actual result, status и причина
failure/partial. Raw output redacts credentials, tokens, passwords, private keys, model secrets и не содержит audio.
Hash/index raw files, если используется, также сохраняется.

### Обязательные probe-классы

| Evidence ID | Что доказывается | Команда/источник выполнения | Acceptance |
|---|---|---|---|
| `E-001-A-WSL-001` | WSL status и distro inventory | `wsl.exe --status`; `wsl.exe --list --verbose` | WSL2 и `Ubuntu-24.04` явно видны, exit codes сохранены |
| `E-001-A-OS-001` | Ubuntu release, architecture, kernel/user | `cat /etc/os-release`; `uname -a`; `uname -m`; `id` | Ubuntu 24.04.x, x86_64 и expected user evidence |
| `E-001-A-USER-001` | Default user/sudo policy | `id -un`; `id -u`; `id -G`; explicit passworded sudo probe without persisting secret | `sipbot`, expected uid/groups, sudo result and non-interactive behavior documented |
| `E-001-A-SRC-001` | Linux source placement | `pwd -P`; `findmnt -T /home/sipbot/src/sip-bot`; `df -B1 /home/sipbot/src/sip-bot`; `git rev-parse --show-toplevel`; `git status --short` | Canonical path is Linux filesystem, accessible to `sipbot`, status/revision captured |
| `E-001-A-GPU-001` | GPU passthrough from Ubuntu | `nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader` | Exit 0 and actual RTX 5060 Ti/driver/memory recorded |
| `E-001-A-CUDA-001` | CUDA visibility layers | `command -v nvcc`; `nvcc --version` when present; loader/library inventory such as `ldconfig -p` filtered for CUDA names | Driver API, toolkit and libraries are separately `present/absent/unknown`; no hidden fallback |
| `E-001-A-DISK-001` | Host and Linux capacity | host `Get-PSDrive C`; Ubuntu `df -B1 /home/sipbot/src/sip-bot` | Free/total bytes, mount/filesystem and `20 ГБ` threshold recorded |
| `E-001-A-PKG-001` | Base dependency reproducibility | `dpkg-query`, `apt-cache policy`, apt source inventory and execution dry-run/install record | Package/version/arch/source/exit code reproducible; no component-native imports |
| `E-001-A-WT-001` | Dirty worktree protection | host and Linux `git status --short`, path/write-set comparison | Pre-existing files are classified and untouched |
| `E-001-A-INV-001` | Machine-readable inventory | generated `inventory.json` + command/raw-output index | All required fields and statuses link to evidence |

Каждая команда выполняется отдельным probe с сохранением exit code; нельзя превращать отрицательный результат в
успешный через `|| true`, молча пропущенный command или host-only substitute. В текущем draft ни один probe не
запущен.

### Acceptance boundary и hand-off

`001-A` может получить environment foundation closeout только если WSL/user/source/GPU/disk/dependency/inventory
fields имеют evidence, а blocker register не содержит обязательного `open`. Отсутствие source content и git revision в
пустом проекте не является blocker: это фиксируется как `not applicable yet` и становится обязательным при появлении
первого source content.
`environment.md` может быть процитирован как bootstrap input, но не заменяет собственные `E-001-A-*` records.

После этого hand-off к `001-B` содержит environment path, package manifest, GPU/CUDA facts, disk facts и known gaps.
Он не содержит CPython binary, no-GIL claims или native component decisions.

## Deferred evidence conformance

Статус: `not applicable`.

В 001-A не создаются тесты, которые ожидаемо остаются красными до corrective-задачи; создаются только environment
probes и inventory evidence. Поэтому для этого plan нет deferred `evidence_id`, связанного с `TASK-NNN`, и не вводятся
локальные `skip`/`xfail`, selectors, collection hooks или promotion claims. CPython/no-GIL и component checks — это
границы следующих child plans, а не deferred test этого плана. Если во время execution появится красный тестовый
артефакт, его нельзя скрывать: execution останавливается и применяется unexpected gap protocol.

## Legacy/fallback/simplification register

| Элемент | Классификация | Решение и ограничение | Где закрывается | Статус |
|---|---|---|---|---|
| `artifacts/feasibility/environment.md` | Bootstrap evidence | Сохраняется read-only как provenance; не объявляет 001-A закрытым и не переписывается этим plan | A-005 inventory/closeout | `retained, not closure` |
| `C:\devel\sip-bot` / `/mnt/c` | Текущий host placement | Допустим как исходный dirty worktree и источник сравнения; не принимается canonical Linux source path | A-002 owner decision | `not adopted as fallback` |
| Docker Desktop | Existing infrastructure evidence | Может быть зафиксирован для context/peer lane; не заменяет Ubuntu GPU/runtime baseline | Map-001/test-stand plans | `not a fallback` |
| CPU-only при отсутствии Ubuntu CUDA | Предлагаемый fallback | Не вводится; требует owner discussion и отдельного plan/ADR при изменении baseline | Owner decision before closeout | `none introduced` |
| Automatic WSL/user repair | Compatibility shortcut | Не вводится; repair допускается только отдельным owner-approved slice с diff/evidence | Unexpected gap protocol | `none introduced` |
| Component-specific native/Python dependencies | Deferred boundary | Не устанавливаются и не импортируются в 001-A; принадлежат 001-B/001-C* | Dependent child plans | `out of scope, explicit` |
| Hidden package substitution or `|| true` probe | Silent simplification | Запрещено; отсутствие пакета/команды остаётся evidence failure/owner decision | A-004/A-005 | `none introduced` |

В этом plan нет owner-approved fallback или intentional simplification, меняющих acceptance. Любой fallback требует
отдельного обсуждения владельца; deadline не является таким разрешением.

## Unexpected gap protocol

Если source-map или probe показывает неучтённое architectural/environment решение, зависимый slice немедленно
останавливается. В evidence root создаётся запись с уникальным gap ID и следующими полями:

```text
Обнаруженный gap:
Gap ID:
Затронутые документы и компоненты:
Почему текущий plan нельзя продолжать:
Фактическая команда, exit code и raw evidence:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Владелец решения:
Нужен ли новый ADR/roadmap/plan-file:
Условие возобновления:
```

Примеры, которые нельзя обходить молча:

- Ubuntu не видит GPU: не переходить автоматически на CPU-only или Docker-only;
- source checkout возможен только под `/mnt/c`: не объявлять Windows mount canonical;
- user provisioning не совпадает с `sipbot`: не менять `/etc/wsl.conf` без owner decision;
- package manifest требует native component или нефиксируемый repository: не подменять пакет и не переносить его в
  main process;
- disk threshold не выдержан: не удалять данные и не менять source placement без owner approval;
- для closeout нужен CPython/native import: остановить 001-A и передать работу 001-B/001-C*.

До review запрещены новый adapter/facade/IPC, скрытый startup path, fallback, compatibility bridge, изменение
protected baseline или ослабление acceptance.

## Execution report и closeout template

Этот шаблон заполняется только после отдельного owner review и фактического execution. Сам факт создания plan-file не
является execution report и не меняет его статус `proposed`.

```text
Plan: 001-A — Environment baseline Ubuntu 24.04/WSL2
Уровень: child plan
Родительская карта: Map-001
Статус plan до исполнения: proposed
Статус исполнения: complete | blocked
Дата/время начала и завершения:
Owner review record:

Фактически выполненные slices:
- A-001:
- A-002:
- A-003:
- A-004:
- A-005:

Фактически изменённые файлы и внешние paths:
- repository evidence root:
- WSL config (если owner-approved):
- Linux source checkout (path/revision; tracked content unchanged):
- package state (manifest and versions):

Команды, версии, архитектура и exit codes:
Evidence root:
Bootstrap reference:
GPU/CUDA result:
Disk result and applied thresholds:
System dependency result:
Dirty-worktree snapshot and pre-existing changes:
Redaction/hash audit:

Blocker register:
- resolved IDs:
- open IDs:
- unexpected gap IDs:

Не выполнено и почему:
Out-of-scope findings handed to 001-B/001-C*:
Deferred evidence conformance: not applicable (tests were not created by this plan)
Fallback/simplification decisions: none unless separately owner-approved

Document registry audit: not run in drafting; record future governance result here
Task backlog audit: no backlog change authorized by this plan; record separate governance result if applicable
Roadmap/Map-001 changes: none authorized by this plan

Новый baseline:
Условие открытия 001-B:
Следующий узкий шаг: 001-B после полного closeout `001-A`
Итоговый статус child plan: complete | blocked
```

Для текущего execution фактический результат closeout зафиксирован в
`artifacts/feasibility/001-A-environment-baseline/closeout.md`; runtime и component imports не запускались.
