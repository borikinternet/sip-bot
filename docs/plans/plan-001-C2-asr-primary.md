# Plan 001-C2: проверка primary ASR-кандидата

Уровень: child plan  
Статус исполнения: `complete`  
Candidate decision: `pass`  
Родительская Map: [Map-001](plan-001-deadline-feasibility.md)  
Идентификатор child plan: 001-C2

План исполнен в узком candidate-specific scope. Фактические команды и результаты находятся в [C2 closeout](../../artifacts/feasibility/001-C2/closeout.md).
Результат — `pass` для проверенного patched main-process пути; это не закрывает Map-001 и не объявляет полную
production/integration готовность ASR-контура.

## 1. Цель и результат

Цель — подготовить воспроизводимую проверку ровно одного primary ASR-кандидата на baseline latest stable
free-threaded CPython >= 3.14 с фиксацией следующих границ:

1. чистый import критичных зависимостей и проверка отсутствия непреднамеренного включения GIL;
2. одна короткая русскоязычная операция на входе PCMU/PCM с наблюдаемым результатом;
3. partial/final поведение, включая исправление промежуточной гипотезы без накопления устаревшего хвоста;
4. cancellation boundary: отмена активной операции, закрытие соответствующего канала, отсутствие принятия stale
   результата и повторное закрытие без ошибки;
5. evidence, достаточное для решения pass, pass_with_isolation или fail по правилам Map-001.

Результат child plan — отдельный evidence root и owner-reviewed решение по выбранному кандидату, его режиму исполнения
и ограничениям. Frozen primary — `faster-whisper==1.2.1` с patched CTranslate2 binding; fallback не запускался.

Точное имя, версия и runtime primary ASR в текущих документах не зафиксированы. Это не предварительный вопрос владельца:
первый execution slice выбирает один доступный стабильный локальный кандидат по ранее заданным критериям и фиксирует
его в candidate-freeze evidence в `artifacts/feasibility/001-C2/`. До выполнения этого slice candidate-specific детали
не утверждаются заранее.

## 2. Применимые документы и извлечённые правила

| Источник | Извлечённое правило | Влияние на этот child plan | Проверка/evidence | Stop condition |
|---|---|---|---|---|
| [architectural-planning-gate.md](../architectural-planning-gate.md) | Child plan обязан иметь self-contained scope, source-map, write-set, owner review, audits, slices, blockers, test/evidence plan и closeout | План содержит все обязательные границы; status остаётся proposed до review | Структурный review этого файла и отдельный closeout | Отсутствует обязательный раздел или execution начат до owner review |
| [plan-001-deadline-feasibility.md](plan-001-deadline-feasibility.md) | 001-C2 зависит от 001-B и 001-C; проверяется один ASR-кандидат; primary/fallback не выбираются молча | Candidate selection выполняется внутри C2; fallback после failure требует owner decision | C2-OR-001, C2-B-*, artifacts/feasibility/001-C2/ | Нет runtime gate или candidate selection/evidence |
| [requirements.md](../requirements.md) | ASR локальный, русский, по возможности потоковый; MVP использует один разговор и PCMU 8 kHz mono; аудио разговора не записывается | Проверяется короткая русская операция локально; нет внешнего API, PBX или записи live-разговора | Metadata входа, partial/final evidence, отсутствие аудиозаписи в write-set | Нужны внешний сервис, live recording или другой обязательный codec |
| [architecture.md](../architecture.md) | ASR получает PCM напрямую по data plane; Dispatcher владеет control plane; final ASR authoritative, partial не меняет FSM; закрытый канал отбрасывает stale payload | Probe не гоняет аудио через Dispatcher и не реализует Dialogue FSM; cancellation проверяет границу канала | Event trace, channel-close/cancel evidence, отсутствие SIP-команд | Кандидат требует синхронного ожидания Dispatcher или partial приводит к FSM/TTS |
| [technical-specification.md](../technical-specification.md) | Baseline — latest stable free-threaded CPython >= 3.14/Ubuntu 24.04 LTS x86_64; PCMU 8 kHz mono; internal PCM и критичные import/no-GIL checks обязательны | Runtime/input metadata и import stages обязательны в evidence | Runtime manifest, format manifest, stdout/stderr и exit code | Нет target runtime, формат скрыт default-ом или import возвращает GIL |
| [ADR-003](../decisions/ADR-003-free-threaded-python.md) | Проверять Py_GIL_DISABLED и sys._is_gil_enabled() до/после import, lazy import и операции; несовместимый native-компонент не допускается в main process без решения | Import-only результат недостаточен; операция и shutdown проверяются отдельно; isolation не включается автоматически | import-no-gil.json, operation record, owner decision | GIL включился, есть предупреждение или не доказана граница процесса |
| [ADR-001](../decisions/ADR-001-llm-and-dialogue-manager.md) | ASR/LLM заменяемы независимо; критичные переходы и SIP остаются у Dialogue Manager | ASR evidence не содержит SIP-команд, transfer/hangup или произвольного изменения FSM | Architecture audit и event trace | ASR adapter получает прямой SIP-доступ или authoritative action из partial |
| [ADR-002](../decisions/ADR-002-llm-model-selection.md) | Документ относится к shortlist и проверке LLM | К ASR-кандидату, его import и audio operation неприменим; LLM/VRAM/structured output в этот child plan не входят | Явная запись not applicable; LLM не запускается | Попытка расширить этот plan до LLM smoke |
| [tooling-notes.md](../tooling-notes.md) | Имя cp314t не является доказательством; нужен явный manifest import-ов, operation smoke и JSON со стадиями, командами, output и failure reason | Используется явный список критичных модулей и стадий, а не общий обход пакетов | Structured evidence root | Есть только filename tag или import-only claim |
| [documentation-process.md](../documentation-process.md) | Факт имеет одного владельца; изменения owner-документов синхронизируются после фактического результата | Этот plan не переписывает требования/архитектуру/ADR; фактический candidate decision обновляется только owner-ом после evidence | Closeout с перечнем фактически синхронизированных документов | Обнаружен конфликт документов или изменён не тот owner |

## 3. Граница задачи

~~~text
Цель:
  После review этого child plan выбрать и проверить один primary ASR-кандидат:
  import/no-GIL, короткая русская PCMU/PCM operation, partial/final, cancellation и evidence.

Входит:
  - выбор и фиксация candidate, фактической версии/revision, пакета, runtime, лицензии и режима процесса;
  - проверка выбранного stable free-threaded CPython до import, после каждого критичного import/lazy import и после ASR operation;
  - одна bounded audio operation на согласованном коротком русском fixture;
  - наблюдение partial, revision/stability, final и cancellation/close boundary;
  - сохранение команд, версий, stdout/stderr, exit code, метаданных входа, timestamps и решения;
  - решение main process или отдельный process isolation после фактического результата по правилам ADR-003.

Не входит:
  - выбор или автоматическая проверка fallback ASR;
  - сравнение нескольких ASR-кандидатов или benchmark-suite;
  - реализация полного ASR adapter, VAD, Turn Detector, Transcript Assembler, Dispatcher, Dialogue FSM,
    SIP/media adapter, LLM, RAG или TTS;
  - сквозной SIP/RTP loopback, BYE integration и fake operator;
  - speculative LLM/retrieval, semantic endpointing, multi-session и production hardening;
  - обучение/fine-tuning ASR, запись live-аудио разговора или подключение внешнего API;
  - установка пакетов, запуск runtime и создание evidence в текущей drafting-сессии.

Protected baseline:
  - основной runtime: latest stable free-threaded CPython >= 3.14 на Ubuntu 24.04 LTS x86_64 в WSL2;
  - PCMU (G.711 μ-law), 8 kHz, mono на SIP/media boundary;
  - рабочий внутренний формат: PCM S16LE, mono, 8 kHz; конкретная conversion boundary разрабатывается в C2 execution;
  - data plane для audio/payload и control plane для cancel/lifecycle остаются раздельными;
  - только final ASR result может быть authoritative для Dialogue/FSM/TTS;
  - несовместимый native-компонент не включает GIL в main process; isolation не выбирается автоматически;
  - fallback, compatibility bridge и снижение assertion не выбираются автоматически.

Предположения о рабочем дереве:
  - дерево dirty до начала drafting; существующие изменения в .idea/, .codex/, .gitignore, artifacts/, docs/ и tools/
    считаются pre-existing и не принадлежат этому plan;
  - перед будущим execution stage executor повторно сохраняет git status --short и не перезаписывает existing
    evidence под artifacts/feasibility/;
  - в текущем turn намеренно создаётся только этот Markdown-файл; runtime не запускается и пакеты не устанавливаются.

Зависимости и внешние сервисы:
  - закрытые evidence 001-A и 001-B, прежде всего воспроизводимый stable free-threaded CPython;
  - закрытый 001-C с порядком проверки; candidate selection выполняется первым execution slice C2;
  - target WSL2/Ubuntu environment и доступный для выбранного кандидата CPU/GPU режим;
  - короткий offline русский test fixture, выбранный execution-задачей с известными format/sample-rate/duration/hash;
    fixture не является записью live SIP-разговора;
  - package/native dependencies кандидата и их license/version metadata;
  - локальный evidence root; внешние сервисы, реальные PBX и облачный ASR запрещены.
~~~

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение/состояние | Целевое поведение для 001-C2 | Gap | Действие |
|---|---|---|---|---|---|
| Candidate identity | ASR adapter и C2-OR-001 | Frozen primary: `ASR-PRIMARY-001-faster-whisper`, `faster-whisper==1.2.1` | Candidate/revision/runtime/license/hash зафиксированы в evidence | Mirror fixture alias и patched binding остаются ограничениями | Читать `candidate-freeze.md` и closeout |
| Runtime/import | CPython `3.14.7t`; `tools/asr_primary_probe.py` | Critical imports и patched CTranslate2 import/operation прошли без возврата GIL | `Py_GIL_DISABLED=1`, GIL disabled на проверенных стадиях, warnings отсутствуют | Полная произвольная thread-safety не доказана | Читать import evidence и C2 closeout |
| Audio ingress | SIP/media boundary и internal PCM data-plane contract | PCMU/PCM fixture и conversion path зафиксированы для tested operation | Одна bounded operation показывает согласованный вход и формат | Полный SIP media path не является C2 acceptance | Читать operation evidence; не расширять scope |
| Partial/final | ASR capability и Transcript Assembler boundary | Partial/final и stable-prefix observation получены; authoritative final без накопления хвоста | Partial не меняет FSM, final может передаваться дальше | Полный Transcript Assembler ещё не реализован | Передать observation в `001-D` |
| Cancellation/lifecycle | ASR operation, channel owner, cancellation token/close boundary | Generator close/канал и stale-output policy прошли tested path | Close идемпотентен на проверенной границе | Hard native cancellation не доказана | Передать limitation в `001-D` |
| Evidence | `artifacts/feasibility/001-C2/` | Manifest, logs, JSON records, patches и closeout созданы | Evidence доступен для owner-reviewed decision | Это feasibility evidence, не regression suite | Читать evidence root и closeout |
| Test code | tests/ | Тестового каталога/нового test-файла для этого drafting нет | Для текущего plan test code не создаётся; future probe/evidence не маскируется как regression pass | Deferred runner/promotion tooling отсутствует | deferred evidence conformance = not applicable; при создании теста plan сначала обновляется |
| Owner documents | requirements.md, architecture.md, technical-specification.md, decisions/, roadmap.md, task-backlog.md, document-registry.md | Protected baseline; component result теперь синхронизируется отдельным owner-document action | Краткие status/next-step записи согласованы без переноса raw evidence | Нормативные детали остаются в собственных owner-документах | Не дублировать raw evidence в registry/map |

### 4.1. Разрешённый write-set

Фактический write-set текущего drafting turn — только:

~~~text
docs/plans/plan-001-C2-asr-primary.md
~~~

Для будущего execution stage, после owner review и повторной фиксации dirty-worktree, разрешённый write-set child
plan предлагается ограничить следующими путями:

~~~text
artifacts/feasibility/001-C2/
tools/asr_primary_probe.py                 # только если нужен воспроизводимый committed probe
~~~

Внутри evidence root допустимы только records этого среза: candidate-freeze, import/no-GIL, operation,
partial/final, cancellation, command/version manifest, stdout/stderr и closeout. Модельные веса, секреты и live
audio не являются write-set. Если committed probe не нужен, tools/asr_primary_probe.py не создаётся.

### 4.1.1. Candidate-specific no-GIL invariant

Для frozen primary `faster-whisper==1.2.1` используется CTranslate2 binding с обязательным узким patch
`artifacts/feasibility/001-C2/ctranslate2-free-threading.patch`. Patch меняет только декларацию pybind11-модуля,
чтобы binding объявлял `py::mod_gil_not_used()`; exact source revision, команда сборки, wheel hash и факт
переиспользования native library записываются в `artifacts/feasibility/001-C2/patch-build.md`.

Непатченный `_ext` уже наблюдался автоматически включающим GIL и не является допустимым runtime для этого
child plan. Любая смена исходной revision, native library, patch или способа установки требует повторного
import/no-GIL и operation evidence; silent fallback на unpatched wheel запрещён. Это candidate-specific
инварианта, а не общее разрешение считать произвольные native-модули no-GIL совместимыми.

### 4.2. Запрещённые изменения

В текущем turn и в execution stage этого child plan запрещены:

- изменение document-registry, task-backlog, roadmap, requirements, architecture, technical-specification или ADR
  под видом временной синхронизации;
- выбор, импорт или smoke-проверка fallback без owner discussion;
- изменение config/constants.py, SIP/media contract, Dispatcher/FSM, VAD/Turn Detector, LLM/RAG/TTS;
- добавление скрытого default, compatibility bridge, startup-only path, mock, weakened assertion, skip или xfail,
  который превращает красный результат в зелёный;
- передача аудиофреймов через Dispatcher, выдача SIP-команд из ASR или разрешение TTS по partial;
- запись или хранение live-аудио разговора, подключение облачного/внешнего ASR или реального PBX;
- параллельная проверка второго ASR-кандидата, сравнение shortlist или изменение baseline runtime;
- перезапись existing файлов/evidence за пределами указанного child evidence root.

Если фактическая проверка требует любого из запрещённых изменений, срабатывает unexpected gap protocol, а зависимый
slice останавливается.

## 5. Audit владельца поведения и парадигмы реализации

Audit применим к будущему ASR operation contract, хотя этот drafting turn не добавляет публичного кода.

- Владелец распознавания — capability Streaming ASR/будущий ASR adapter, а не Dispatcher, SIP callback или
  свободный helper. Именно adapter владеет состоянием активной ASR-сессии, буфером входных PCM-фреймов, partial/final
  events и lifecycle native/inference runtime.
- Transcript Assembler владеет reconciliation partial-гипотез и стабильного префикса; этот child plan проверяет
  observable candidate behavior, но не переносит assembler semantics в ASR probe и не реализует assembler.
- Dialogue Manager/Dispatcher владеет control-plane переходами и решением, может ли final result продолжить FSM и
  разрешить TTS. ASR не владеет SIP, transfer, hangup, TTS authorization или состоянием разговора.
- Cancellation приходит в ASR adapter как scoped lifecycle command/token от владельца канала; adapter отменяет
  собственную операцию и закрывает/дренирует свой data-plane boundary. Late result должен быть отброшен закрытым
  каналом, а не обработан свободной функцией.
- Свободные функции допустимы только для pure форматирования/сериализации fixture и evidence. Они не могут менять
  состояние канала, FSM, поколения или маршрута и не обходят component boundary.
- До появления кода конкретные имена классов и методов не утверждаются. Если candidate API требует отдельной facade,
  IPC или иного владельца, это architectural gap, а не повод добавить helper в этот plan.

## 6. Owner-review решения

| ID | Вопрос | Предложение для review | Последствие для реализации | Статус |
|---|---|---|---|---|
| C2-OR-001 | Как выбрать primary ASR? | C2 выбирает первый доступный стабильный локальный кандидат по заданным критериям, затем фиксирует его name/version/revision/hash/license/runtime в candidate-freeze evidence | В рамках этого plan проверяется только выбранный кандидат; fallback после failure требует owner decision | resolved as execution task |
| C2-OR-002 | Где определить входной контракт выбранного кандидата? | Начальная граница задана документами: PCMU 8 kHz mono и внутренний PCM S16LE mono 8 kHz; место decode/resample и candidate-specific параметры разрабатываются в C2-S2 и фиксируются в evidence | Один fixture и одна воспроизводимая conversion path; hidden defaults запрещены | resolved as execution task |
| C2-OR-003 | Что считать достаточным partial/final и cancellation result? | C2-S3 реализует и проверяет минимальные наблюдаемые partial/final, исправление хвоста, cancel active operation, отсутствие stale result и idempotent close; quality/latency observations записываются, а не запрашиваются заранее у владельца | Недостаточный результат остаётся `fail`/`blocked`, не маскируется изменением порога | resolved as execution task |
| C2-OR-004 | Main process или process isolation? | Сначала пройти no-GIL import/operation. Main process возможен только при GIL disabled; pass_with_isolation возможен лишь после отдельного owner decision с явным IPC boundary | Красный no-GIL не запускает fallback и не получает статус pass автоматически | resolved for tested patched main-process path; evidence в C2 closeout |
| C2-OR-005 | Разрешён ли fallback ASR при провале primary? | Нет автоматической проверки и нет молчаливого fallback. При fail владелец отдельно обсуждает replacement/isolation и создаёт corrective plan/ADR при изменении boundary | Этот child закрывается fail/blocked до решения; второй кандидат не входит в этот execution | resolved: owner-gated |
| C2-OR-006 | Какой fixture использовать для русской операции? | Execution выбирает короткий offline fixture с известными hash/форматом; live SIP recording не используется | Неподтверждённый fixture блокирует operation; синтетическая подмена не объявляется equivalent без evidence | resolved as execution task |

### 6.1. Правило открытия execution stage

До execution требуется review самого child plan и закрытые upstream dependencies. Candidate selection, входной
формат, fixture и критерии наблюдения являются рабочими задачами C2 и фиксируются по мере исполнения. C2-OR-004
остаётся policy: окончательное решение main process или `pass_with_isolation` появляется только по фактическому
evidence; fallback по-прежнему не выбирается автоматически.

## 7. Process invariant audit

| Инвариант | Аудит для этого child plan | Статус/условие |
|---|---|---|
| Срез узкий и имеет наблюдаемый результат | Только один ASR-кандидат и четыре observable boundary; LLM/SIP/full demo вынесены | pass для proposed scope |
| Scope и owner docs не дублируются | Требования и пороги кратко ссылаются на owner-документы; candidate выбирается execution-задачей | pass |
| Зависимости и gates соблюдены | 001-B и 001-C — prerequisites; candidate selection является первым execution slice | resolved for planning |
| Dirty worktree не смешивается | Existing changes защищены; текущий intentional write-set — один файл; future evidence имеет отдельный root | pass для drafting; повторить перед execution |
| Авторитетная среда выбрана | Runtime evidence — Ubuntu/WSL2 stable free-threaded CPython >= 3.14; Docker не назначается для AI operation | resolved baseline; evidence pending |
| Команды воспроизводимы | Команда фиксируется в candidate/version manifest после выбора кандидата; в drafting запусков нет | pending execution |
| Registry/backlog audit | Этот turn не меняет registry/backlog/roadmap по явному ограничению пользователя; check_document_registry.py и runtime не запускаются | deferred owner sync; не evidence execution |
| Fallback/compatibility/упрощение явно контролируются | Fallback отсутствует; isolation owner-gated; ослабленные assertions/skip/xfail запрещены | pass |
| Production-ready claims отсутствуют | План заявляет только feasibility evidence и не закрывает MVP/production | pass |
| Deferred evidence не маскируется | Новых тестов этот plan не создаёт; пропуски не будут оформлены как pass | not applicable для deferred-test conformance |
| Findings получают IDs и owner | Blocker register содержит C2-B-*; conditional fallback gap имеет отдельный ID | pass для plan; closeout pending |
| Документы синхронизируются по владельцу | Child не редактирует owner docs; фактические изменения перечисляются в closeout | pass с owner-gated sync |

## 8. Architecture invariant audit

| Применимый инвариант | Как сохраняется в 001-C2 | Проверка/stop condition |
|---|---|---|
| Dispatcher владеет control plane и Dialogue FSM | Probe не меняет FSM и не принимает SIP-решения; ASR только публикует наблюдаемые events | Stop, если candidate API требует прямой SIP/FSM access |
| Audio/text payload идут по data plane, не через Dispatcher | PCM/PCMU fixture подаётся в ASR data-plane boundary; cancel/close идут как lifecycle control | Event/channel trace; stop при глобальной очереди для audio payload |
| Только authoritative final ASR меняет FSM и разрешает TTS | Partial и speculative observation не вызывают FSM/TTS; final маркируется как authoritative только на downstream boundary | Stop, если partial считается финальным действием |
| Stale producer и закрытие канала безопасны | После cancel/close поздний candidate result не принимается; close проверяется повторно | Failure, если late result попадает в consumer или close не идемпотентен |
| PCMU — MVP media format | Fixture начинается с PCMU 8 kHz mono или имеет явный PCMU→PCM decode; внутренний ASR input фиксируется в metadata | Stop при скрытом другом codec/resample или отсутствии format record |
| Free-threaded CPython — main baseline | Проверяются Py_GIL_DISABLED, sys._is_gil_enabled() по import/lazy/operation; GIL-enabled main process не принимается | fail при auto-enable GIL; isolation только по C2-OR-004 |
| Lifecycle имеет owner, cancel, close и повторное закрытие | ASR adapter владеет operation; cancel/close и no-stale behavior входят в C2-S3 | Stop при отсутствии cancellation boundary |
| BYE не блокируется AI operation | BYE integration не реализуется в C2; этот child требует только cancelable ASR operation и оставляет BYE для 001-C1/integration | Не объявлять BYE доказанным; gap передавать в соответствующий plan |
| Нет внешних сервисов и аудиозаписи | Только локальный кандидат и offline fixture, выбранный в execution; live audio не пишется | Stop при внешнем API или recording path |

## 9. Узкие implementation slices

### C2-S0 — candidate freeze и открытие execution

**Цель и границы:** выбрать candidate, разработать рабочие input/fixture details и подтвердить prerequisites 001-B/001-C.
Runtime и пакеты в drafting stage не запускаются.

**Допустимый write-set:** только candidate-freeze record в будущем artifacts/feasibility/001-C2/ после review child plan;
текущий turn меняет только этот plan-file.

**Acceptance:** выбранный candidate, package/revision/hash, license, runtime, process hypothesis, input format/conversion,
fixture metadata и command template записаны. Для исходной drafting stage статус был `proposed`; фактический closeout
этого плана имеет статус `pass`.

**Stop conditions:** candidate selection не выполнен; 001-B не закрыт; fixture не выбран; для проверки нужен внешний сервис,
live recording или скрытый fallback.

**Следующий slice:** после выполнения C2-S0 и закрытия его фактических blockers — C2-S1.

### C2-S1 — clean import и no-GIL gate

**Цель и границы:** импортировать только выбранный в C2-S0 ASR package и его явные критичные транзитивные
зависимости в чистом stable free-threaded CPython process.

**Порядок:** зафиксировать runtime identity; проверить Py_GIL_DISABLED и GIL до imports; выполнить direct/lazy imports
по manifest; после каждого stage проверить GIL и warnings; сохранить версии, wheel/source build, stdout/stderr и exit
code. Import-only pass не закрывает operation.

**Acceptance:** Py_GIL_DISABLED == 1; GIL отключён до/после каждого critical/lazy import; нет автоматического GIL
warning; candidate import завершается воспроизводимо; manifest и команды сохранены.

**Stop conditions:** любой auto-enable GIL, warning, import crash без объяснения, неизвестная native dependency или
неподтверждённый runtime. Не пробовать fallback автоматически.

**Релевантные проверки:** no-GIL/import probe; это не regression test и не доказательство потокобезопасности.

**Следующий slice:** при pass — C2-S2; при красном результате — blocker C2-B-004 и owner review.

### C2-S2 — короткая русская PCM/PCMU operation

**Цель и границы:** на одном offline fixture, выбранном в execution, проверить минимальную реальную ASR operation, не реализуя
полный audio pipeline.

**Порядок:** записать hash/format/sample-rate/channels/duration; проверить PCMU boundary и явный decode в internal PCM
если это предусмотрено контрактом; передать bounded PCM operation выбранному ASR; собрать first useful partial, final,
latency и resource observations; завершить operation штатно.

**Acceptance:** operation не падает и не зависает; формат пути и conversion явно доказаны; выдаётся непустой
русскоязычный результат; timestamps и exit code сохранены; shutdown завершён. Качество и latency отражаются
наблюдениями, а не предварительным owner threshold.

**Stop conditions:** нет выбранного fixture; candidate принимает только иной формат без разработанной conversion boundary;
результат не наблюдаем; операция требует внешнего API/записи; import/no-GIL evidence красный.

**Релевантные проверки:** bounded PCM/PCMU smoke и operation evidence. Сквозной SIP/RTP тест здесь не выполняется.

**Следующий slice:** при pass — C2-S3; при fail — C2-B-003/C2-B-005 и owner discussion.

### C2-S3 — partial/final, revision и cancellation

**Цель и границы:** проверить streaming boundary кандидата и его отмену в рамках одной ASR session.

**Порядок:** подать несколько bounded chunks; зафиксировать partial A, исправленный partial B и final C; проверить,
что исправленный хвост не накапливается; инициировать cancel до natural final или в активной операции; закрыть
соответствующий канал; проверить late result drop и повторное close.

**Acceptance:** partial наблюдаем, revision не дублирует старый хвост, final единственный и authoritative только на
предусмотренной downstream boundary; cancel имеет причину/время/status; после cancel/close stale result не принимается;
close идемпотентен; события и stdout/stderr сохранены.

**Stop conditions:** нет partial/final distinction; final приходит после отмены и принимается; cancel только sleep/mock
без candidate operation; закрытие блокирует или переиспользует старый channel; race не классифицирован.

**Релевантные проверки:** partial/final contract, cancellation/close smoke, stale-result evidence. BYE, TTS barge-in и
FSM transition остаются за другими slices.

**Следующий slice:** при pass — C2-S4; при fail — соответствующий blocker и owner review, без fallback.

### C2-S4 — evidence decision и closeout

**Цель и границы:** собрать self-contained evidence и оформить одно из решений Map-001.

**Допустимый write-set:** только artifacts/feasibility/001-C2/ и при необходимости committed probe из source-map.

**Acceptance:** evidence содержит candidate/runtime/process/input/event/cancel metadata, команды, версии, stdout/stderr,
exit codes и результаты всех slices; итог имеет один из статусов pass, pass_with_isolation, fail; owner указал
main-process/isolation decision и ограничения; unresolved blockers перечислены.

**Stop conditions:** нет команды или exit code; evidence нельзя воспроизвести; pass_with_isolation заявлен без owner
decision и IPC boundary; fallback назван baseline без отдельного review; parent Map закрывается по одному только плану.

**Документальная синхронизация:** child не редактирует registry/backlog/roadmap в этом turn; фактическая потребность
изменить owner document перечисляется в closeout и выполняется отдельным owner-approved шагом.

## 10. Отдельный blocker register

| ID | Срез | Проверяемый триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| C2-B-001 | C2-S0 | Execution не выбрал и не зафиксировал один ASR-PRIMARY-ID с фактической package/version/revision provenance | Все candidate-specific slices | executor | C2-OR-001, candidate-freeze record | open on trigger |
| C2-B-002 | C2-S0/C2-S1 | 001-B не доказал stable free-threaded CPython >= 3.14 и disabled GIL | Import и operation | project owner | runtime-probe.json из 001-B | open |
| C2-B-003 | C2-S2 | Нет выбранного короткого русского fixture или неизвестны format/sample-rate/hash | PCM/PCMU operation | executor | C2-OR-006, input metadata | open on trigger |
| C2-B-004 | C2-S1 | Import/lazy import/operation включает GIL или выдаёт auto-enable warning | Main-process acceptance и baseline claim | project owner | import-no-gil.json, ADR-003 checks | open; fallback не запускается |
| C2-B-005 | C2-S2/C2-S3 | Operation не даёт требуемый observable partial/final или observations не позволяют оценить результат | Candidate decision | executor | C2-OR-003, operation/event trace | open |
| C2-B-006 | C2-S3 | Cancel/close не прерывает active operation, принимает late result или не идемпотентен | Cancellation acceptance | project owner | cancellation record и repeated-close trace | open |
| C2-B-007 | C2-S1–C2-S4 | Для красного primary результата предлагают fallback без owner discussion | Fallback decision; primary evidence остаётся fail | project owner | owner response, новый plan/ADR при необходимости | conditional open |
| C2-B-008 | C2-S1–C2-S4 | Candidate требует новый IPC/adapter/format boundary, отсутствующий в docs | Зависимый slice и архитектурный claim | project owner/architecture owner | unexpected gap record | conditional open |
| C2-B-009 | C2-S4 | Evidence не содержит команду, версии, stdout/stderr или exit code | Reproducibility и closeout | child executor | evidence manifest audit | open |

Неизвестный красный результат не классифицируется как none: он остаётся открытым blocker до owner review. В этом
предложении есть открытые blockers, поэтому строка none не применяется.

## 11. Test plan и evidence

### 11.1. Что должно быть доказано

| Boundary | Минимальный evidence | Не доказывается этим child plan |
|---|---|---|
| Runtime/import | Python version/arch, Py_GIL_DISABLED, GIL before/after every import/lazy stage/operation, warnings, dependency manifest | Production compatibility всех пакетов или потокобезопасность всей системы |
| PCM/PCMU operation | Fixture hash/format/rate/channels/duration, conversion path, one real operation, partial/final output, timestamps, resource observation, exit code | Полный SIP/RTP loopback, network latency, MOS |
| Partial/final | Ordered events, revision/stable-prefix trace, one final, no accumulation of corrected tail | Полноценный Transcript Assembler implementation и FSM transition |
| Cancellation | Cancel trigger/time/reason, operation status, channel close, late-result disposition, repeated-close result | BYE integration, TTS barge-in и multi-component cancellation |
| Decision | pass/pass_with_isolation/fail, owner decision, main/isolation boundary, known limitations | Automatic fallback selection или Map-001 closeout |

### 11.2. Предлагаемый evidence root

~~~text
artifacts/feasibility/001-C2/
├── candidate-freeze.md
├── runtime-manifest.json
├── import-no-gil.json
├── operation.json
├── partial-final.json
├── cancellation.json
├── commands-and-versions.txt
├── stdout/
├── stderr/
└── closeout.md
~~~

Имена являются предложенным контрактом будущего evidence root, а не созданными сейчас файлами. Каждый record должен
содержать evidence_id, дату/время, команду, runtime, candidate identity, фактический exit code и status. Для failure
обязательны причина и следующий owner decision. Fixture хранится только если это разрешено owner review и не нарушает
политику отсутствия live audio recording.

### 11.3. Команды и environment

В drafting stage команды не запускаются. После C2-S0 executor должен зафиксировать фактический путь к target
interpreter и команду вида:

~~~text
<CPYTHON_3_14_7T> tools/asr_primary_probe.py \
  --candidate-id <ASR-PRIMARY-ID> \
  --evidence-root artifacts/feasibility/001-C2
~~~

Если committed probe не создаётся, одноразовая команда и её полный inline/script source сохраняются в
commands-and-versions.txt; host Python не считается no-GIL evidence. Не допускается подставлять имя пакета или
runtime до выполнения candidate-selection slice.

### 11.4. Deferred evidence conformance

Для этого plan: not applicable.

Причина: текущая задача создаёт только plan-file и не создаёт test file, regression selector, skip/xfail или тест,
который ожидаемо остаётся красным до corrective-задачи. Будущая ASR probe/evidence — feasibility operation, а не
deferred regression test. Если execution stage решит создать такой тест, сначала нужно обновить этот plan stable
evidence_id, owner, default/deferred command, stdout/stderr/exit-code policy и promotion criteria; до этого тест не
создаётся и не запускается.

## 12. Legacy/fallback/simplification register

| Что введено | Почему допустимо/необходимо | Как ограничено | Где закрывается | Владелец | Статус |
|---|---|---|---|---|---|
| Fallback ASR | Ничего не вводится в этот child plan | Второй кандидат не проверяется автоматически; после fail нужен owner discussion и отдельный plan/ADR при изменении boundary | Owner review после primary evidence | project owner | none; owner-gated if triggered |
| Process isolation | Это предусмотренный ADR-003 способ сохранить no-GIL main process, а не автоматический fallback | Только explicit IPC/process boundary и owner decision; обычный GIL-enabled process не считается main-process pass | C2-OR-004, отдельный isolation plan при необходимости | project owner | policy only; not selected |
| Один короткий fixture и один candidate | Узкая feasibility boundary Map-001, не заявление качества всего ASR | Не расширяется в benchmark; fixture и threshold фиксируются заранее | C2-S0/C2-S2 closeout | project owner | scope boundary |
| Legacy helper/compatibility bridge/ослабленный assertion | Для проверки не требуется | Не сохраняются и не добавляются | Unexpected gap protocol | child executor | none |
| Тестовый skip/xfail | Тесты в этом drafting plan не создаются | Deferred conformance явно not applicable | Этот plan | child executor | none |

Молчаливый fallback, скрытый default и подмена красного результата не разрешены. Если primary не проходит, этот child
не превращает результат в pass; он фиксирует fail и останавливается на owner decision.

## 13. Протокол неожиданного gap

При обнаружении gap зависимый slice немедленно останавливается. Заполняется запись, а не добавляется временный adapter,
fallback или startup path:

~~~text
gap_id: C2-GAP-...
Обнаруженный gap:
Затронутые документы и компоненты:
Почему текущий plan нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Владелец решения:
Нужен ли новый ADR/roadmap/plan-file:
Требуемое evidence:
~~~

Для этого child типовые triggers: candidate требует незафиксированный sample rate/decoder, native import включает GIL,
cancel API не отделён от process shutdown, partial result способен менять FSM, fixture имеет неясную лицензию/приватность,
или owner предлагает второй candidate/fallback. До review запрещено маскировать такой gap mock-ом, снижением assertion,
skip/xfail или неоговорённой process isolation.

## 14. Execution report и closeout template

Ниже сохранён reusable template для повторного execution. Фактический результат текущего execution находится в
[C2 closeout](../../artifacts/feasibility/001-C2/closeout.md); статус исполнения плана — `complete`, candidate decision — `pass`.

~~~text
Plan: 001-C2
Уровень: child plan
Родитель: Map-001
Статус исполнения: complete
Candidate decision: pass | pass_with_isolation | fail
Owner review date/decision:
ASR-PRIMARY-ID:
Package/version/revision/hash/license:
Inference runtime:
Main process или isolation:
Runtime и target environment:
Fixture metadata/hash:

Фактически изменённые файлы:
  - ожидаемый child write-set:
  - pre-existing files, не принадлежащие child:

Выполненные slices:
  - C2-S0:
  - C2-S1:
  - C2-S2:
  - C2-S3:
  - C2-S4:

Команды, версии и фактические exit codes:
Evidence root:
Результат no-GIL import:
Результат PCM/PCMU operation:
Результат partial/final:
Результат cancellation/close:
Итоговый статус child plan: complete | blocked

Закрытые blockers:
Открытые blockers и owner:
Unexpected gaps:
Pre-existing failures:
Out-of-scope findings:
Fallback/legacy/simplification decision:
Изменённые owner-документы (если owner отдельно разрешил):
Registry audit:
Task-backlog audit:
Следующий узкий plan/gate:
~~~

Closeout не может устанавливать MVP complete или prod-ready; он закрывает только evidence boundary 001-C2. При
fail, открытом blocker или owner-gated isolation следующий шаг указывается явно, а Map-001 остаётся незакрытой.
