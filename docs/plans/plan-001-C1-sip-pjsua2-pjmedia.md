# Plan: C1 — проверка SIP/PJSUA2/PJMEDIA

Уровень: `child plan`  
Статус исполнения: `complete`  
Candidate decision: `pass`  
Родительская карта: [`Map-001: Scope freeze и feasibility к демонстратору 25 сентября`](plan-001-deadline-feasibility.md)  
Родительская roadmap: [`roadmap.md`](../roadmap.md)  
Дата подготовки: 2026-08-26  
Owner review: `2026-08-27` — child plan принят к исполнению в рамках текущего распоряжения продолжать работу. Объём
execution ограничен PJSUA2/PJMEDIA candidate и заранее перечисленными acceptance boundaries; это принятие не означает
предварительного успеха candidate и не разрешает fallback, новый test stand или изменение архитектуры.

Этот документ является self-contained планом и execution record одного feasibility-среза. Owner review разрешил
исполнять его узкие slices; после появления отдельного стенда `001-S` все четыре acceptance boundaries пройдены.
Это закрывает только SIP/media candidate decision C1 и не закрывает `Map-001`.

## Цель и проверяемый результат

Цель — первым проверить кандидат SIP/media-стека **PJSUA2 + PJMEDIA** на latest stable free-threaded CPython >= 3.14
(`3.14t`) в Ubuntu 24.04 LTS x86_64 под WSL2 по четырём узким acceptance boundaries:

1. импорт Python-обёртки и критичных native-зависимостей без непроизвольного включения GIL;
2. минимальный SIP lifecycle одного вызова;
3. фактический медиапуть PCMU, 8 kHz, mono через PJMEDIA;
4. обработка входящего `BYE` во время контролируемой длительной операции без ожидания этой операции.

Ожидаемый результат после отдельного owner review и execution stage — один из следующих явно доказанных исходов:

- `pass` — PJSUA2/PJMEDIA пригодны для основного процесса и все четыре acceptance boundaries пройдены;
- `fail` — хотя бы одна обязательная проверка провалена или не имеет достаточного evidence; execution C1 останавливается;
- `isolation_gap` — кандидат нельзя принять в основном процессе, а возможная process isolation требует отдельного
  решения владельца и отдельного плана. Этот статус не является автоматическим fallback и не закрывает C1.

При любом провале не запускаются автоматически Sofia-SIP, Baresip или иной fallback. Сначала фиксируется concrete
blocker и проводится owner discussion. В этом child plan не реализуются полноценный SIP adapter, тестовый SIP/RTP
стенд, интеграция с PBX, ASR/LLM/TTS или пользовательский demo-flow.

## Candidate build invariant: required generated-SWIG patches

Для принятого C1 baseline PJSUA2/PJMEDIA `2.17` нельзя использовать upstream-сгенерированный Python wrapper без патчей.
Оба патча являются частью воспроизводимой сборки кандидата и должны применяться к generated `pjsua2_wrap.cpp` до компиляции
и установки binding:

1. [`pjsua2-free-threading.patch`](../../artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading.patch)
   добавляет под `#ifdef Py_GIL_DISABLED` вызов `PyUnstable_Module_SetGIL(m, Py_MOD_GIL_NOT_USED)` для single-phase
   extension module;
2. [`pjsua2-free-threading-buffer.patch`](../../artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading-buffer.patch)
   убирает `SWIG_PYTHON_THREAD_BEGIN_ALLOW/END_ALLOW` вокруг helper-ов `assign_from_bytes` и `copy_to_bytearray`,
   использующих Python buffer API.

Применение выполняется к внешнему build tree PJSIP после генерации wrapper и до `make`:

```text
cd /home/sipbot/src/pjsip-build/pjproject-2.17/pjsip-apps/src/swig/python
patch -p0 < /mnt/c/devel/sip-bot/artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading.patch
patch -p0 < /mnt/c/devel/sip-bot/artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading-buffer.patch
```

После сборки обязательны import/no-GIL и operation checks из C1-S1–C1-S4. Непатченный import сохранён только как
negative evidence: он включает GIL, а непатченный media buffer path аварийно завершается. Если generated wrapper или
его layout изменится, патчи нельзя переписывать молча: сначала обновляется этот раздел, patch evidence и candidate hash.

## Применимые документы и извлечённые правила

### Документы-источники

- [`architectural-planning-gate.md`](../architectural-planning-gate.md) — обязательная структура child plan, source-map,
  write-set, audits, blocker register, evidence и closeout.
- [`plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md) — родительская карта, зависимости, первый
  кандидат PJSUA2/PJMEDIA и owner-gated политика fallback.
- [`requirements.md`](../requirements.md) — границы MVP, один русский SIP-разговор, PCMU, локальность и запрет записи
  аудио.
- [`architecture.md`](../architecture.md) — ownership SIP/media, control plane/data plane, каналы и правило
  немедленной обработки `BYE`.
- [`technical-specification.md`](../technical-specification.md) — latest stable free-threaded CPython >= 3.14, PCMU 8 kHz mono, сигнальные события
  и технические критерии проверки.
- [`tooling-notes.md`](../tooling-notes.md) — методика no-GIL/import/operation evidence и авторитетные локальные
  проверки документации.
- [`documentation-process.md`](../documentation-process.md) — владелец фактов и запрет молчаливого дублирования.

### Применимые ADR

Непосредственно применим [`ADR-003: Приоритет free-threaded CPython и проверка совместимости зависимостей`](../decisions/ADR-003-free-threaded-python.md).
Он задаёт free-threaded baseline, проверки `Py_GIL_DISABLED` и `sys._is_gil_enabled()`, проверку состояния после
импортов и операции, а также правило, что native-компонент с автоматическим включением GIL нельзя молча оставить в
основном процессе.

`ADR-001` не применяется: C1 не меняет разделение LLM и Dialogue Manager и не создаёт structured LLM decision.
`ADR-002` не применяется: C1 не выбирает LLM, не проверяет VRAM inference и не меняет AI pipeline.

### Rule extraction table

| Источник | Извлечённое правило | Влияние на C1 | Проверка/evidence | Stop condition |
|---|---|---|---|---|
| `architectural-planning-gate.md` | Child plan самодостаточен; execution начинается только после owner review; у каждого slice есть acceptance и blocker register | Сначала готовится план и review, затем — отдельные узкие проверки | Этот файл содержит требуемые разделы; будущий closeout содержит фактический diff и evidence | Попытка исполнять C1 при `proposed` или без закрытых зависимостей |
| `plan-001-deadline-feasibility.md` | PJSUA2/PJMEDIA проверяется первым; fallback не запускается автоматически | Не исследовать другой SIP-кандидат в рамках C1 | `C1-DEC-001`, итоговый status и owner decision | Любой `fail`/`isolation_gap` → остановка и owner discussion |
| `requirements.md` | MVP локальный, один разговор, PCMU, без записи аудио и без реальных внешних сервисов | Probe не использует внешний PBX, не сохраняет аудио и не расширяется до multi-call | Lifecycle/media evidence и перечень созданных файлов | Нужны PBX, несколько вызовов или аудиофайлы |
| `architecture.md` | SIP/media владеет сигнализацией и медиатаймингом; payload идёт по data plane; `BYE` не ждёт длительную операцию | Проверяется независимость SIP callback/control path от долгой работы и прямой PCMU media path | События, timestamps, codec negotiation и channel ownership в JSON | `BYE` задержан callback-ом/Dispatcher или media идёт через Dispatcher |
| `technical-specification.md` | Основной runtime — latest stable free-threaded CPython >= 3.14; PCMU — 8 kHz mono; SIP events/commands явные | Import gate и media acceptance выполняются на фактически выбранном runtime | `runtime.json`, `import.json`, `lifecycle.json`, `pcmu.json`, `bye.json` | GIL включён, codec не PCMU/8 kHz mono или lifecycle не доказан |
| `ADR-003` | После каждого критичного импорта и операции `sys._is_gil_enabled()` должен оставаться `False`; warning об auto-enable — ошибка | Проверяются обычные и lazy imports, инициализация, lifecycle и media operation | Structured stdout/stderr, exit code и состояния GIL по стадиям | Любое `True`, warning или отсутствие подтверждения после операции |
| `tooling-notes.md` | Имя `cp314t` недостаточно; нужны runtime identity, import, operation и JSON evidence | Evidence не ограничивается версией интерпретатора | Manifest модулей, версии, команды, stdout/stderr, exit codes | Есть только filename/tag без фактического поведения |
| `documentation-process.md` | Факт имеет одного владельца; архитектурное изменение требует отдельного ADR/обновления owner-документа | C1 фиксирует candidate evidence, но не переписывает architecture/spec/ADR молча | Closeout и owner-doc sync record | Обнаружен новый архитектурный контракт без review |
| Этот child plan | Разрешён только PJSUA2/PJMEDIA feasibility; полноценный adapter/test stand запрещены | Будущий probe — одноразовый evidence driver, не production code и не regression suite | Source-map, write-set и execution report | Scope расширен за пределы четырёх acceptance boundaries |

## Граница задачи

```text
Цель:
  Получить evidence по import/no-GIL, минимальному SIP lifecycle, PCMU media path и BYE responsiveness
  для PJSUA2/PJMEDIA на выбранном stable free-threaded CPython.

Входит:
  - проверка runtime identity и GIL до/после критичных импортов, lazy imports и минимальных операций;
  - минимальный одноразовый SIP probe для одного вызова при наличии заранее доступного peer/loopback;
  - проверка сигнализации start/answer/media/close и идемпотентного shutdown;
  - проверка фактической PCMU negotiation/transport и преобразования PCMU ↔ внутренний PCM S16LE, 8 kHz mono;
  - проверка входящего BYE во время контролируемой длительной операции;
  - structured evidence под отдельным root и candidate decision.

Не входит:
  - автоматический fallback на Sofia-SIP, Baresip или другой стек;
  - реализация полноценного SIP adapter, Dispatcher, Dialogue FSM, production channels или IPC-контракта;
  - создание постоянного SIP/RTP test stand, PBX, fake operator или нового peer;
  - ASR, VAD, LLM, retrieval, TTS, barge-in пользовательского сценария и end-to-end demo;
  - multi-call, production packaging, HA, внешние сервисы и реальная операторская инфраструктура;
  - запись, сохранение или анализ аудио как файла;
  - изменение config/constants.py, architecture.md, technical-specification.md, ADR, roadmap, backlog или registry.

Protected baseline:
  - latest stable free-threaded CPython >= 3.14, Ubuntu 24.04 LTS x86_64 в WSL2;
  - основной процесс сохраняет отключённый GIL;
  - PCMU (G.711 μ-law), 8 kHz, mono;
  - control plane отделён от data plane; Dispatcher не является транзитом аудио;
  - SIP/media callback не ждёт ASR/LLM/TTS/отчёт или искусственно долгую работу;
  - закрытый channel не переиспользуется, закрытие идемпотентно, stale payload не доставляется;
  - один локальный вызов, без аудиозаписи и без молчаливого fallback.

Состояние рабочего дерева перед execution:
  - все существующие изменения считаются пользовательскими и сохраняются;
  - `001-A` и `001-B` закрыты, `001-C` принят как child map;
  - локальный SIP/RTP peer не создан и не входит в write-set C1;
  - перед execution зафиксирован target runtime и отдельный evidence root;
  - probe остаётся одноразовым feasibility driver и не является production source.

Зависимости и внешние сервисы:
  - закрытый `001-A` для Ubuntu/WSL и базовых системных предпосылок (транзитивная зависимость);
  - закрытый `001-B` для воспроизводимого stable free-threaded CPython и исходного no-GIL evidence;
  - согласованный `001-C` с manifest кандидата, порядком и критерием остановки;
  - доступный stable release/source PJSUA2/PJMEDIA; версия и способ сборки/поставки фиксируются execution evidence;
  - принятый отдельный план [`001-S`](plan-001-S-voip-test-stand.md) и созданный им локальный SIP/RTP peer с PCMU;
    C1 сам стенд не создаёт;
  - доступ к evidence root `artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/` после открытия execution stage.
  - Реальный внешний PBX/SIP-сервис зависимостью C1 не является и не должен появиться как скрытый prerequisite.
```

## Source-map, write-set и запрещённые изменения

### Карта источников и будущих объектов

| Область | Файл или компонент | Текущее состояние | Целевое состояние | Gap | Действие в C1 |
|---|---|---|---|---|---|
| Runtime | Latest stable free-threaded CPython >= 3.14 в Ubuntu/WSL | `001-B` закрыт: CPython 3.14.7t, `Py_GIL_DISABLED=1`, stdlib/concurrency probe pass | Import и operations проходят без GIL | Совместимость конкретного SIP binding ещё не проверена | Использовать `001-B` runtime как read-only prerequisite; не собирать и не менять runtime в C1 |
| SIP binding | PJSUA2 Python binding и его native dependencies | Версия, source/wheel и import manifest ещё не зафиксированы | Критичные imports и lazy imports доказаны на target runtime | Provenance появляется в execution evidence | Выбрать stable release и зафиксировать manifest в probe |
| PJMEDIA | PJMEDIA native media path, `AudioMediaPort` или эквивалент конкретной версии | Candidate выбран Map-001, operation path не проверен | PCMU 8 kHz mono фактически negotiated и проходит через media port | Точный binding/API path open | Проверить через одноразовый probe; отдельный Python `pjmedia` import не предполагать без manifest |
| SIP lifecycle | PJSUA2 endpoint/account/call callbacks | Production adapter отсутствует | Один минимальный вызов проходит start/answer/media/close | Нужен локальный peer/loopback | Использовать только одноразовый probe; не создавать adapter или test stand |
| BYE control path | SIP callback и shutdown path | Поведение при длительной операции не подтверждено | Входящий `BYE` наблюдается/подтверждается до завершения долгой работы | Threshold и доступный signal timing open | Выполнить только после owner decision по сценарию; при задержке остановиться |
| Evidence | `artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/` | Root отсутствует | JSON/текст с версиями, командами, стадиями, stdout/stderr, exit codes и status | Нужен execution stage | Создать только в согласованном execution; не хранить audio |
| Probe | Будущий `tools/feasibility/pjsua2_pjmedia_probe.py` либо эквивалент | Файл отсутствует | Одноразовый driver для узких acceptance checks | Путь и API manifest зависят от stable release | Разрешён только в отдельном execution stage; это не test stand и не adapter |
| Production SIP adapter | Будущий runtime-компонент | Не существует | Не изменяется C1 | Архитектурная реализация ещё впереди | Не создавать, не stub-ить и не объявлять готовым |

### Write-set

Write-set execution после owner review ограничен этим child plan, его одноразовым probe и собственным evidence root:

```text
C:\devel\sip-bot\docs\plans\plan-001-C1-sip-pjsua2-pjmedia.md
artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/
tools/feasibility/pjsua2_pjmedia_probe.py
```

В probe допустимы только orchestration, import/runtime checks, наблюдение PJSUA2/PJMEDIA lifecycle и запись
структурированного evidence. Probe не получает право менять Dialogue FSM, конфигурацию проекта, внешний SIP routing
или ownership production channels.

### Явно запрещённые изменения

- любой файл вне указанного child plan, approved probe и собственного evidence root;
- `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md`, `docs/requirements.md`,
  `docs/architecture.md`, `docs/technical-specification.md` и все ADR;
- существующие `.idea/`, `.codex/`, `.local/`, `artifacts/`, `tools/` и иные пользовательские изменения;
- `config/constants.py`, `src/`, production adapter, Dispatcher, FSM, channel implementation и IPC schema;
- постоянный `tests/` runner, SIP/RTP test stand, fake PBX, fake operator или новый SIP peer;
- сборка/замена CPython runtime, запуск полного приложения и создание SIP/RTP test stand;
- автоматический запуск другого SIP-кандидата после красного результата;
- ослабление assertion, `skip`/`xfail`, no-op media stub, startup-only path, legacy bridge или скрытый compatibility path;
- сохранение аудио, отправка пользовательских данных во внешний сервис и подключение реального PBX.

## Audit владельца поведения и парадигмы реализации

Производственное поведение C1 не добавляет и не изменяет: это feasibility-проверка кандидата до создания SIP adapter.
Поэтому отдельный public algorithm owner для текущего документа — `not applicable`.

Граница владения для будущего approved probe фиксируется заранее:

- **SIP lifecycle owner** — будущий `SIP adapter`: он владеет endpoint/call lifecycle, protocol callbacks и переводом
  низкоуровневых событий в ограниченный control-plane контракт.
- **Media owner** — будущий SIP/media слой с `PJMEDIA AudioMediaPort`: он владеет codec negotiation, media timing,
  PCMU ↔ PCM преобразованием и bounded data-plane delivery.
- **Dispatcher** — владелец control plane и Dialogue FSM; probe не заменяет его и не меняет его состояние.
- **Probe driver** — не production owner. Свободные функции driver допустимы только как stateless orchestration:
  они вызывают scoped dependency, собирают version/GIL/timestamp evidence и возвращают результат. Они не меняют SIP
  state, FSM, channel generation, transfer outcome или payload ownership.

Если во время проверки для BYE требуется новый facade, callback contract, generation protocol, IPC или другой публичный
алгоритм, это не считается helper-задачей: срабатывает [unexpected gap protocol](#unexpected-gap-protocol), execution
останавливается, а owner определяет новый plan/ADR.

Отмена и observability для будущего probe должны быть scoped: каждый вызов имеет собственный call/evidence context,
явный shutdown, timestamps для BYE/media/lifecycle и bounded timeout. Probe не должен удерживать Dispatcher или
имитировать production ownership через глобальное состояние.

## Owner-review решения

| ID | Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|---|
| `C1-DEC-001` | Какой SIP-кандидат проверять первым? | PJSUA2 + PJMEDIA, как установлено Map-001 | Другие VoIP-стеки не запускаются в C1 | `resolved (inherited)` |
| `C1-DEC-002` | Какой baseline runtime? | Latest stable free-threaded CPython >= 3.14, Ubuntu 24.04 LTS x86_64, WSL2 | GIL-enabled CPython не является успешным baseline; фактическая версия фиксируется probe | `resolved (inherited)` |
| `C1-DEC-003` | Что делать при провале? | Остановить C1 и провести owner discussion; fallback автоматически не проверять | `fail`/`isolation_gap` не запускает Sofia/Baresip и не меняет architecture | `resolved (inherited)` |
| `C1-DEC-004` | Допустима ли process isolation в этом child plan? | C1 может зафиксировать isolation gap, но не реализует и не утверждает isolation без отдельного решения | `pass_with_isolation` нельзя заявить только по import failure; нужен отдельный plan/owner decision | `resolved as gate policy` |
| `C1-DEC-005` | Какой PJSUA2/PJMEDIA source, stable version, build и import manifest использовать? | Execution выбирает последний доступный стабильный вариант и фиксирует manifest/provenance в evidence | Evidence содержит фактические ABI/SOABI и критичные imports | `resolved as execution task` |
| `C1-DEC-006` | Какой SIP/RTP peer даёт минимальный call и PCMU loopback? | Использовать peer, созданный и описанный в отдельной VoIP test-stand map; C1 не расширяет её scope | До готовности test-stand проверяются import/lifecycle slices; media slices ждут dependency | `resolved as dependency on test-stand map` |
| `C1-DEC-007` | Как определяется «BYE responsiveness»? | Execution строит peer scenario и timestamps; 200–500 ms используется как comfort orientation, отдельный owner upper bound не требуется | Проверяется `BYE` во время долгой операции и отсутствие ожидания downstream; результат измеряется и докладывается | `resolved as execution task` |
| `C1-DEC-008` | Можно ли создать одноразовый probe? | Да, как часть execution write-set после review child plan; probe не является test stand, adapter или regression suite | Write-set ограничен feasibility driver и evidence root | `resolved by plan scope` |
| `C1-DEC-009` | Нужно ли менять owner-документы по факту candidate result? | Да, если результат меняет архитектурный baseline; отдельным согласованным документным изменением | C1 не редактирует owner-docs молча и не меняет registry/backlog/roadmap | `resolved as process rule` |

Execution stage начинается после review этого child plan и закрытия `001-B`. Candidate manifest, peer details и
timestamps формируются задачей в execution; отдельного предварительного owner-question для них нет.

## Process invariant audit

| Инвариант | Аудит C1 | Статус на момент drafting |
|---|---|---|
| Срез узкий и имеет наблюдаемый результат | Четыре независимых, но относящихся к одному SIP candidate acceptance boundaries разделены на S1–S4; итог — candidate decision/evidence | `pass for plan; execution pending` |
| Карта и child plan не смешаны | Родитель остаётся Map-001; этот файл не закрывает карту и не разрешает следующий child plan | `pass` |
| Релевантные и нерелевантные проверки различены | В scope только SIP/runtime/media/BYE; ASR/LLM/TTS, full demo и PBX явно out-of-scope | `pass` |
| Environment baseline авторитетен | `001-B` подтвердил CPython 3.14.7t/Ubuntu WSL2 и disabled GIL; Windows host Python не доказывает no-GIL совместимость приложения | `pass; component evidence pending` |
| Пользовательские требования не дублируются как новый источник | В плане приведены только операционные выводы и ссылки на owner-документы | `pass` |
| Архитектурные факты не меняются молча | Candidate result сначала фиксируется в C1 evidence; изменение architecture/spec/ADR проходит отдельный review | `pass` |
| Registry/backlog policy соблюдается | Registry/backlog/roadmap синхронизируются по фактическому owner review и closeout, без скрытого изменения требований | `in progress` |
| Fallback/compatibility/simplification явно разрешены | Register ниже содержит `none`; красный результат не превращается в зелёный | `pass` |
| Production-ready не объявляется | Формулируется только feasibility decision, не MVP/prod readiness | `pass` |
| Deferred test не скрывается `skip`/`xfail` | Регулярные тесты и deferred tests этим drafting plan не создаются; conformance явно `not applicable` | `not applicable` |
| Команды и evidence воспроизводимы | Команды/формат/стадии описаны в Test plan; actual exit codes появятся только в execution report | `pending execution` |
| Dirty worktree не смешивается | Существующие изменения перечислены ниже; target-only write-set сохраняется | `pass for drafting` |

## Architecture invariant audit

| Архитектурный инвариант | Как применяется к C1 | Статус |
|---|---|---|
| Dispatcher владеет control plane и Dialogue FSM | Probe только наблюдает callbacks/commands; FSM и Dispatcher не создаются и не меняются | `preserved; verify in probe boundary` |
| SIP/media callbacks не ждут ASR/LLM/TTS или отчёт | S4 моделирует длительную работу на отдельном worker path и проверяет входящий `BYE`; callback, который ждёт её завершения, — fail | `required; verified by bounded busy fixture and BYE evidence` |
| Audio/text payload не проходит через Dispatcher | S3 связывает candidate media port с direct data-plane fixture/consumer; Dispatcher в probe не транзитирует фреймы | `required; preserved and verified at probe boundary` |
| Закрытие отбрасывает stale producer и channel не переиспользуется | S2/S4 фиксируют close, shutdown и отсутствие доставки после close; новый production generation C1 не реализует | `required where observable; otherwise gap` |
| Только authoritative final ASR меняет FSM | ASR не входит в C1; правило не тестируется и не изменяется | `not applicable` |
| Speculative pipeline не выполняет irreversible SIP action | Speculative pipeline не запускается; probe не принимает LLM decisions | `not applicable; preserved` |
| TTS playback отменяется при barge-in | TTS и barge-in не входят в C1 | `not applicable` |
| LLM имеет ограниченный structured contract и не получает SIP access | LLM не импортируется и не вызывается | `not applicable; preserved` |
| SIP/media формат MVP — PCMU | S3 требует PCMU, 8 kHz, mono; другой codec не является упрощением | `required; verified by 001-S/pcmu.json` |
| Конфигурация MVP в `config/constants.py` | Config не создаётся/не меняется; probe получает explicit test parameters только из approved manifest/command | `preserved; no config change` |
| Free-threaded CPython и native no-GIL | S1 проверяет runtime, imports, lazy imports, initialization и operation; generated-SWIG patches обязательны | `required; verified by patched candidate evidence` |
| Нет внешнего сервиса, PBX-логики и записи аудио | Только локальный peer/loopback; аудио остаётся in-memory и не сохраняется | `preserved` |
| Каждый channel имеет owner, close, cancel и repeat-close test | S2/S4 наблюдают lifecycle/shutdown; отсутствие owner/идемпотентного close — blocker | `required; pending evidence` |

## Узкие implementation slices

Execution stage разрешён owner review этого child plan и закрытым runtime prerequisite. Порядок slices ниже используется
как execution record; фактические результаты записываются в evidence root и closeout.

### C1-S0 — prerequisite и manifest gate

**Цель и границы:** подтвердить, что можно проверять именно согласованный PJSUA2/PJMEDIA candidate в правильной среде.

**Затрагиваемые объекты:** evidence от `001-B`/`001-C`, execution candidate manifest, будущий evidence root.

**Допустимый write-set:** evidence root и manifest copy, а также одноразовый probe этого child plan.

**Последовательность:**

1. Проверить наличие `001-B` evidence с `Py_GIL_DISABLED == 1`, начальным `sys._is_gil_enabled() == False` и
   воспроизводимым Ubuntu/WSL runtime.
2. Проверить, что `001-C` разрешил порядок PJSUA2/PJMEDIA и что version/source/build/import manifest заполнен.
3. Проверить наличие локального peer из отдельной VoIP test-stand map и BYE scenario; не создавать отсутствующий stand.
4. Зафиксировать `git status --short` перед любой будущей кодовой правкой.

**Acceptance:** `C1-AC-000` — runtime/map входы доступны, фактические версии и команды зафиксированы в execution
manifest; отсутствие peer явно вынесено в `C1-B-004` и блокирует только peer-dependent slices.

**Stop conditions:** нет `001-B`/`001-C` evidence, неясен provenance или требуется установка/сборка, которую нельзя
выполнить в разрешённом контуре. Отсутствие peer не останавливает S1, но останавливает S2–S4.

**Релевантные проверки:** read-only prerequisite inspection, version/provenance capture и запись blocker status.

**Следующий slice:** при pass — `C1-S1`; при stop — owner review, без подготовки fallback.

### C1-S1 — import и no-GIL behavior

**Цель и границы:** доказать runtime identity и поведение PJSUA2/PJMEDIA imports/initialization на выбранной stable free-threaded-сборке CPython >=3.14.

**Затрагиваемые объекты:** target CPython process, `pjsua2` binding, PJMEDIA/native modules из manifest, одноразовый
probe и `import.json`.

**Допустимый write-set:** только approved probe и structured evidence root; не менять пакет, runtime, config или
production source.

**Последовательность проверки:**

1. В чистом target process проверить Python version/implementation/architecture, `sysconfig.get_config_var("Py_GIL_DISABLED")`
   и начальное `sys._is_gil_enabled()`.
2. Импортировать ровно явный manifest: `pjsua2` и прямые критичные native dependencies; не делать безымянный
   `pkgutil.walk_packages` и не добавлять тяжёлые модули «на всякий случай».
3. После каждого import проверить `sys._is_gil_enabled() == False` и сохранить stdout/stderr, warnings и exit code.
4. Выполнить предусмотренные manifest-ом lazy imports и минимальную инициализацию endpoint/media object; повторить
   проверку GIL после каждого шага.
5. Не считать имя wheel, `cp314t` tag или успешный `import` достаточным evidence без фактического состояния GIL.

**Acceptance:** `C1-AC-001` — все обязательные imports/lazy imports и минимальная инициализация завершаются в target
runtime, `Py_GIL_DISABLED == 1`, GIL остаётся disabled, warning об auto-enable отсутствует, provenance зафиксирован.

**Stop conditions:** import error, ABI mismatch, warning/auto-enable GIL, `True` после любого шага, неясный module
manifest или необходимость молча заменить candidate.

**Релевантные проверки:** no-GIL import gate и native compatibility evidence. ASR/LLM/TTS import не выполняется.

**Следующий slice:** при pass — `C1-S2`; при fail — `C1-S5` только для оформления fail/evidence, затем owner discussion.

### C1-S2 — минимальный SIP lifecycle

**Цель и границы:** проверить один минимальный SIP call без создания полноценного SIP adapter или test stand.

**Затрагиваемые объекты:** PJSUA2 endpoint/account/call callbacks, заранее доступный local peer, `lifecycle.json`.

**Допустимый write-set:** одноразовый probe, in-memory event log и JSON evidence; никаких production callbacks, persistent
   fixtures или внешних routing changes.

**Последовательность проверки:**

1. Поднять endpoint и транспорт в probe в соответствии с execution manifest.
2. Провести один заранее согласованный локальный сценарий: `call_started` → answer/`call_answered` →
   `media_started` → controlled close/remote hangup → `media_stopped`/`remote_hangup` → shutdown.
3. Зафиксировать callback order, command result, thread/context, timestamps и ошибки; не передавать audio payload
   через Dispatcher.
4. Повторить закрытие/cleanup, если API позволяет, и проверить идемпотентность без повторного использования старого
   channel/call generation.

**Acceptance:** `C1-AC-002` — один вызов проходит минимальный lifecycle, callbacks не блокируют control path,
   media start/stop наблюдаемы, shutdown завершается и повторное close не ломает состояние.

**Stop conditions:** peer unavailable, требуется новый test stand, сигнализация не проходит, callback блокируется,
   media lifecycle не наблюдается, close не идемпотентен или нужен production adapter для продолжения.

**Релевантные проверки:** только один локальный SIP call и lifecycle. Transfer, multi-call, PBX и полный dialogue flow
   нерелевантны и не запускаются.

**Следующий slice:** при pass — `C1-S3`; при fail — `C1-S5` для оформления fail, затем owner discussion.

### C1-S3 — PCMU media path

**Цель и границы:** доказать фактический PCMU path через PJMEDIA для одного вызова, не подменяя его no-op fixture.

**Затрагиваемые объекты:** negotiated SDP/media settings, `AudioMediaPort` или точный equivalent, bounded in-memory
data-plane consumer/producer, `pcmu.json`.

**Допустимый write-set:** только одноразовый in-memory probe и JSON metrics; audio files, persistent recordings и
   reusable media test framework запрещены.

**Последовательность проверки:**

1. В manifest/command явно задать требование PCMU, 8 kHz, mono и зафиксировать фактическую negotiated codec/payload.
2. Подать короткий детерминированный in-memory PCM S16LE fixture через PJMEDIA media port во время реального local
   call; fixture не сохранять на диск.
3. Проверить, что на SIP/RTP path используется PCMU, а на внутренней границе получается PCM S16LE, 8 kHz, mono.
4. Проверить обратный путь media egress: PCM возвращается в PCMU без неоговорённого codec fallback.
5. Зафиксировать frames, sample rate, channels, payload type, media start/stop, overrun/underrun и close behavior.

**Acceptance:** `C1-AC-003` — реальный candidate media path согласует PCMU и пропускает данные в обе стороны при
   8 kHz mono; данные не идут через Dispatcher, audio file не создаётся, codec mismatch не скрывается.

**Stop conditions:** negotiated codec не PCMU, частота/каналы отличаются, operation only works with a no-op/null media
   path, нет доказательства RTP/PJMEDIA crossing, обнаружен hidden transcoding/fallback или запись аудио необходима.

**Релевантные проверки:** PCMU media operation и data-plane ownership. ASR preprocessing и end-to-end latency не
   проверяются в C1.

**Следующий slice:** при pass — `C1-S4`; при fail — `C1-S5` для оформления fail, затем owner discussion.

### C1-S4 — BYE responsiveness during long operation

**Цель и границы:** проверить, что входящий `BYE` обрабатывается protocol/control path во время контролируемой
   длительной операции и не ждёт её завершения.

**Затрагиваемые объекты:** active local call, PJSUA2 signaling callback, controlled non-SIP long operation, `bye.json`.

**Допустимый write-set:** одноразовый timing probe и JSON evidence; не добавлять Dispatcher, global queue, IPC,
   adapter facade или fake downstream component.

**Последовательность проверки:**

1. На активном вызове запустить явно обозначенную длительную operation на отдельном non-SIP worker path с известными
   `start/end` timestamps. Operation должна быть synthetic и ограниченной; она не должна занимать SIP callback.
2. С заранее согласованного local peer отправить входящий `BYE` во время окна длительной operation.
3. Зафиксировать `long_op_started`, `bye_sent/received`, protocol acknowledgement или callback, `media_closed` и
   `long_op_finished`, насколько это доступно API.
4. Проверить, что `BYE` event/ack и начало cleanup происходят до завершения долгой operation; callback не ожидает
   downstream completion и не блокирует повторное закрытие.
5. Зафиксировать measured latency и сопоставить её с ориентиром комфорта `200–500 ms`; отсутствие отдельного
    отдельный заранее заданный upper bound не является самостоятельным блокером.

**Acceptance:** `C1-AC-004` — `BYE` наблюдаем, protocol-level response/cleanup начинается до конца долгой operation;
    timestamps сохранены и сопоставлены с ориентиром `200–500 ms`; нет ожидания Dispatcher/AI/report, stale media не
    доставляется после close.

**Stop conditions:** `BYE` обрабатывается только после long operation, callback ждёт downstream, нет измеримого
   acknowledgement/timestamp, cleanup повторно использует закрытый channel, либо для сценария требуется новый
   test stand/IPC contract.

**Релевантные проверки:** только BYE/control responsiveness и close semantics. Реальные ASR/LLM/TTS и barge-in не
   являются частью C1.

**Следующий slice:** при pass — `C1-S5`; при fail или gap — немедленно `C1-S5` для фиксации результата и owner
   discussion; fallback не запускать.

### C1-S5 — evidence, candidate decision и closeout

**Цель и границы:** собрать фактические результаты S1–S4 и классифицировать только PJSUA2/PJMEDIA, не принимая новое
   архитектурное решение молча.

**Допустимый write-set:** evidence root и execution report в child plan; owner-doc changes только отдельным согласованным
   изменением, если результат меняет source-of-truth.

**Acceptance:**

- `C1-AC-005` — каждый mandatory acceptance имеет status, команду, stdout/stderr, exit code, runtime/candidate
  provenance и evidence path;
- итоговый status однозначно `pass`, `fail` или `isolation_gap`;
- blocker register обновлён concrete IDs;
- явно записаны pre-existing failures, out-of-scope findings, отсутствие fallback и следующий plan/gate.

**Stop conditions:** неполное evidence, status выведен по версии без operation, красный результат замаскирован,
   открытый owner decision выдан за resolved или есть несинхронизированный architectural gap.

**Следующий шаг:** только `pass` с закрытыми зависимостями передаёт SIP candidate decision в `001-D`; `fail` и
   `isolation_gap` сначала требуют owner discussion и не порождают автоматический fallback plan.

## Blocker register

Этот register относится к C1 и должен обновляться после каждого фактического slice. До execution `open` означает
конкретное условие, которое ещё не проверено, а не доказанный дефект.

| ID | Срез | Concrete trigger | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `C1-B-001` | S0–S4 | Нет закрытого `001-B` evidence с `Py_GIL_DISABLED == 1` и GIL disabled | Весь execution C1 | Owner Map-001 / runtime child plan | `001-B` runtime JSON и command record | `resolved 2026-08-27` |
| `C1-B-002` | S0–S4 | `001-C` или candidate manifest не фиксирует точные PJSUA2/PJMEDIA source/version/build/imports | Весь execution C1 | SIP candidate owner | `candidate-manifest.json`, provenance record | `resolved 2026-08-27` |
| `C1-B-003` | S0–S4 | PJSUA2/PJMEDIA binding не импортируется, ABI не совпадает или native dependency не определена | S1 и все зависимые slices | SIP candidate owner после фактического evidence | `patched-import-lifecycle.json`, `native-dependencies.txt`, exit code | `resolved for patched candidate 2026-08-27` |
| `C1-B-004` | S2–S4 | Нет заранее доступного/approved local SIP/RTP peer с PCMU | Lifecycle, media и BYE acceptance | Owner Map-001 / `001-S` stand owner | `001-S` peer availability record; не создавать stand в C1 | `resolved by 001-S on 2026-08-27` |
| `C1-B-005` | S4 | Не согласованы long-operation scenario, BYE timestamps или upper bound | Только S4 и итоговая candidate decision | Owner SIP/media behavior | `C1-DEC-007`, `001-S/bye.json` | `resolved by executable scenario on 2026-08-27` |
| `C1-B-006` | S1–S4 | После import, lazy import, initialization или operation `sys._is_gil_enabled()` становится `True` либо появляется auto-enable warning | Основной-process acceptance; возможный isolation discussion | Owner Map-001 | Stage-by-stage GIL evidence | `resolved for patched candidate on 2026-08-27` |
| `C1-B-007` | S2 | Нет наблюдаемого call lifecycle, callback blocks или close не идемпотентен | Lifecycle и все media/BYE slices | SIP adapter behavior owner | `001-S/lifecycle.json`, callback/timing log | `not triggered; lifecycle pass` |
| `C1-B-008` | S3 | Negotiated codec не PCMU/8 kHz mono или media path не пересекает PJMEDIA/RTP | PCMU acceptance и candidate decision | SIP/media owner | `001-S/pcmu.json`, SDP/media metrics | `not triggered; PCMU/RTP pass` |
| `C1-B-009` | S4 | `BYE`/ack/cleanup ждёт завершения long operation или нет измеримого timing evidence | BYE acceptance и candidate decision | SIP/media owner | `001-S/bye.json`, timestamps, exit code | `not triggered; remote BYE pass` |
| `C1-B-010` | S0–S5 | Для продолжения предлагается fallback, no-op stub, новый test stand/adapter или ослабление assertion без review | Зависимый slice и candidate decision | Owner Map-001 | Owner discussion record / unexpected gap record | `open by policy` |
| `none` | — | На момент подготовки нет resolved runtime evidence; отсутствие факта не трактуется как отсутствие блокеров | — | — | Этот register | `not applicable; register non-empty` |

Необъяснимый красный результат или отсутствие обязательного evidence останавливает зависимый slice. `C1-B-006`–
`C1-B-009` не могут быть закрыты сменой assertion, повторным импортом в том же процессе или запуском fallback.

## Test plan и evidence

### Границы проверки

Релевантны только четыре обязательных evidence lane: no-GIL/import, minimal lifecycle, PCMU media и BYE responsiveness.
Нерелевантны для C1: ASR partial/final, VAD/endpointing, LLM structured output, TTS, barge-in, retrieval, multi-turn
context, transfer на оператора, полный MVP call, production latency 200–500 ms и test stand implementation.

Регулярный проектный test runner и постоянный test stand этим plan-file не создаются. Одноразовый probe — это
воспроизводимый evidence driver для candidate decision, а не замена production tests и не повод заявить готовность MVP.

### Планируемые команды и environment

Команды выполняются после owner review и закрытия соответствующего prerequisite. Все команды должны исполняться
внутри Ubuntu 24.04 LTS x86_64 с выбранным target CPython >=3.14, а не host Python Windows.

1. Runtime preflight:

   ```text
   /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys,sysconfig; print(sys.version); print(sysconfig.get_config_var('Py_GIL_DISABLED')); print(sys._is_gil_enabled())"
   ```

2. Candidate import/operation probe:

   ```text
   /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/pjsua2_pjmedia_probe.py --output <root>/import.json --initialize
   # lifecycle/PCMU/BYE commands are resumed only after the approved local peer exists
   ```

3. Документный closeout после фактического изменения Markdown:

   ```text
   python tools/check_document_registry.py
   ```

   При изменении backlog дополнительно применяется `python tools/check_task_backlog.py`; C1 не меняет backlog молча.
   Результаты applicable checker-ов должны быть записаны в closeout; их отсутствие не превращается в pass.

Probe обязан зафиксировать фактическую команду, рабочий каталог, runtime identity, version/source/build, manifest,
стадию, stdout, stderr, exit code, warnings, timestamps, status и stop condition. Секреты, пароли, внешние SIP
credentials и аудиофайлы в evidence не сохраняются.

### Evidence root и минимальный формат

```text
artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/
├── candidate-manifest.json
├── native-dependencies.txt
├── unpatched-import-lifecycle.json
├── patched-import-lifecycle.json
├── lifecycle.json       # создаётся после появления peer
├── pcmu.json            # создаётся после появления peer
├── bye.json             # создаётся после появления peer
├── evidence-index.md
└── closeout.md
```

Каждый JSON должен содержать как минимум:

```json
{
  "evidence_id": "C1-E-...",
  "plan": "001-C1",
  "candidate": "PJSUA2/PJMEDIA",
  "runtime": "<selected stable free-threaded CPython >=3.14> / Ubuntu 24.04 LTS x86_64",
  "stage": "import|lifecycle|pcmu|bye",
  "command": "<exact command>",
  "status": "pass|fail|blocked|isolation_gap",
  "exit_code": 0,
  "gil": {"py_gil_disabled": 1, "before": false, "after_import": false, "after_operation": false},
  "stdout": "<captured or redacted>",
  "stderr": "<captured or redacted>",
  "stop_condition": null,
  "owner_decision": null
}
```

`lifecycle.json` дополнительно содержит callback/event sequence, call/media identifiers, command results, close/re-close
outcome и timestamps. `pcmu.json` содержит negotiated payload type, codec, sample rate, channels, frame counters,
media-port path и факт отсутствия audio file. `bye.json` содержит long-operation window, BYE/ack/callback/cleanup
timestamps, measured bound и outcome.

### Acceptance matrix

| ID | Доказательство | Pass condition | При отсутствии/провале |
|---|---|---|---|
| `C1-AC-001` | `runtime.json`, `import.json` | Target runtime, import manifest, lazy imports и init; GIL остаётся disabled, warning отсутствует | `fail`/`isolation_gap`, C1 stop |
| `C1-AC-002` | `lifecycle.json` | Один call проходит start/answer/media/close, callbacks не блокируют, close идемпотентен | C1 stop, не создавать adapter/stand |
| `C1-AC-003` | `pcmu.json` | Реальный PCMU 8 kHz mono path в обе стороны, direct data plane, без записи audio | C1 stop, не включать codec fallback |
| `C1-AC-004` | `bye.json` | BYE/ack/cleanup происходит в измеренном и зафиксированном временном окне во время long operation; результат сопоставлен с ориентиром 200–500 мс | C1 stop, gap передаётся на review |
| `C1-AC-005` | `summary.md` и blocker register | Все mandatory statuses и blockers согласованы, decision однозначен | Неполное evidence не считается pass |

### Deferred evidence conformance

Для этого child plan постоянный test runner не создаётся, а отдельный deferred test, ожидаемо красный до corrective
задачи, не вводится. Одноразовый probe относится к evidence execution. Поэтому deferred evidence conformance:
**`not applicable`**.

Будущий одноразовый probe не должен оформляться как `skip`/`xfail`. Если execution stage обнаружит, что требуется
постоянный тест, ожидаемо красный до отдельной задачи, execution сначала останавливается и этот plan обновляется
owner-approved `evidence_id`, `TASK-NNN`/roadmap scope, owner закрытия, командой deferred-прогона, сохранением
stdout/stderr/exit code и promotion criteria. До такой записи deferred test не создаётся.

## Legacy/fallback/simplification register

| Что введено | Почему необходимо для MVP | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| `none` | C1 не вводит legacy, fallback или упрощение | Красный candidate result остаётся красным; PJSUA2 проверяется как единственный SIP candidate | Owner discussion и отдельный plan только после failure | `none` |

Следующие вещи являются запретами, а не скрытыми упрощениями:

- process isolation не объявляется результатом без отдельного owner decision;
- Sofia-SIP/Baresip не проверяются автоматически после PJSUA2/PJMEDIA failure;
- null/no-op media path, prerecorded audio, stubbed BYE и ослабленные timing/assertions не заменяют реальный evidence;
- временный probe не превращается в production adapter или permanent test stand;
- отсутствующий peer не обходится fake success;
- обычный CPython с GIL не выдаётся за основной baseline.

Если owner после failure одобрит isolation, fallback candidate или дополнительное MVP-упрощение, это будет новый
записанный вариант с owner, причиной, scope, corrective path и принимающим plan/ADR. До этого execution C1 остановлен.

## Unexpected gap protocol

Если source-map или execution показывает неучтённый архитектурный gap, зависимый slice немедленно останавливается.
Нельзя продолжать через новый adapter, facade, IPC, startup-only path, fallback, изменённый channel contract или
ослабленный acceptance.

Запись gap должна иметь конкретный идентификатор и следующий формат:

```text
Gap ID: C1-GAP-...
Обнаруженный gap:
Затронутые документы и компоненты:
Почему текущий plan нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Нужен ли новый ADR/roadmap/plan-file:
Владелец решения:
Evidence/команда/exit code:
Статус: open | resolved | rejected
```

После записи gap требуется owner discussion. Если меняется архитектурный источник факта, сначала обновляется
соответствующий owner-документ или создаётся ADR отдельным согласованным изменением; этот child plan не поглощает
решение молча. До разрешения gap сохраняются все pre-existing changes, а fallback не запускается.

## Execution report и closeout

Дата выполнения: `2026-08-27`  
Статус исполнения: `complete`  
Candidate decision: `pass`  
Owner review перед execution: `2026-08-27`

### Фактически изменённые/созданные файлы

- `tools/feasibility/pjsua2_pjmedia_probe.py` — one-shot PJSUA2/PJMEDIA probe, включая narrow no-GIL buffer-path patch
  support и bounded background-work fixture для BYE-сценария.
- `tools/feasibility/voip_test_stand_probe.py` — оркестратор локального Baresip peer/fake-operator стенда.
- `artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/` — candidate/build/import evidence.
- `artifacts/feasibility/001-S-voip-test-stand/` — внешний peer, PCMU, BYE и transfer evidence.
- Этот plan и связанные owner-документы синхронизированы после получения evidence.

### Protected baseline и process audit

- Runtime: Ubuntu 24.04.4 LTS / WSL2 / CPython 3.14.7t, `Py_GIL_DISABLED=1`.
- GIL: `False` до импорта, после импорта, после инициализации и после SIP/media operation; warning отсутствуют.
- PCMU: negotiated `PCMU/8000/1`; Baresip подтверждает decoder/encoder 8 kHz mono.
- SIP/RTP peer: получен из отдельного принятого plan `001-S`; C1 стенд не создавал.
- External PBX/audio recording: не использовались/не создавались.
- BYE fixture: 10-секундная bounded background operation была активна в момент remote disconnect; PJSUA2 обработал
  `DISCONNECTED` до локального hangup.
- Fallback и архитектурное упрощение: не применялись.

### Команды и evidence

| Slice | Result | Evidence |
|---|---|---|
| S0 prerequisite/manifest | `pass` | `candidate-manifest.json`, `commands.md` |
| S1 import/no-GIL/initialization | `pass with two narrow candidate patches` | `patched-import-lifecycle.json`, `patches/pjsua2-free-threading*.patch` |
| S2 minimal SIP lifecycle | `pass` | `001-S-voip-test-stand/lifecycle.json` |
| S3 PCMU 8 kHz mono media | `pass` | `001-S-voip-test-stand/pcmu.json` |
| S4 BYE during busy operation | `pass` | `001-S-voip-test-stand/bye.json` |
| S5 candidate decision/closeout | `pass` | this section and `evidence-index.md` |

Applicable checkers are run again after this documentation sync; their exact output is recorded in the closeout
artifact and project task/backlog documents.

### Acceptance

- `C1-AC-001`: `pass` — source/version/build/import provenance is complete.
- `C1-AC-002`: `pass` — free-threaded import and operation remain GIL-disabled.
- `C1-AC-003`: `pass` — SIP lifecycle is observable and resources close.
- `C1-AC-004`: `pass` — PCMU/RTP path is bidirectional and reaches the PJSUA2 media port.
- `C1-AC-005`: `pass` — BYE is observed during active bounded work before local close, with timestamps and exit code.

### Decision and limits

PJSUA2/PJMEDIA `2.17` is accepted as the primary SIP/media candidate for the MVP main process, subject to the two
recorded generated-SWIG compatibility patches. The `Py_MOD_GIL_NOT_USED` declaration and the buffer wrapper change are
candidate compatibility measures, not a blanket proof of native thread safety under arbitrary production load.

The `001-S` transfer scenario proves only that the local stand can exercise transfer; it does not implement or accept
the production bot transfer adapter. PJSUA2 SIP/media C1 also does not cover ASR/LLM/TTS, VAD, barge-in, full
Dispatcher/FSM behavior or production latency.

`C1-B-010` remains an open-by-policy guard: any fallback, new isolation boundary, contract change or assertion change
requires a separate owner discussion. No such change is needed for this pass.

### Next gate

Передать candidate decision SIP/media в `001-D` после его owner review; параллельно продолжить следующий разрешённый
component feasibility slice `001-C2` (ASR), не смешивая его evidence с C1.

План C1 закрыт статусом `complete` в пределах своего candidate-feasibility scope. Candidate decision остаётся `pass`;
это не является заявлением о `MVP complete`, `prod-ready complete` или полном SIP-боте.
