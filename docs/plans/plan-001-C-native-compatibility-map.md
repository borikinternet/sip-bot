# Plan-001-C: карта native compatibility для SIP, ASR, LLM и TTS

Уровень: `map` (дочерняя карта)  
Статус: `complete`  
Родительская карта: [Map-001: Scope freeze и feasibility к демонстратору](plan-001-deadline-feasibility.md)

Owner review: `2026-08-27` — child map принят к execution planning в рамках
общего распоряжения продолжать работу без новых уточняющих вопросов. Это
открывает подготовку component child plans, но не объявляет ни один native
компонент совместимым и не запускает fallback.

Этот документ фиксирует карту и контракт будущих проверок, но не является execution benchmark. Создание этого файла не
считает ни один компонент совместимым, не выбирает baseline по результатам и не разрешает запуск runtime.

## 1. Цель и результат

Цель — разложить проверку native compatibility на четыре независимых компонента:

1. `C1 SIP` — SIP/PJSUA2/PJMEDIA и media callback boundary;
2. `C2 ASR` — выбранный локальный ASR и partial/final operation;
3. `C3 LLM` — выбранный локальный inference runtime и structured response;
4. `C4 TTS` — выбранный локальный TTS и выдача русского аудио.

Проверка каждого компонента должна использовать один и тот же порядок:

```text
import → operation → GIL state → cancellation/lifecycle → evidence
```

Результат карты — согласованная matrix `C1`–`C4`, четыре disjoint child execution plan-файла с собственными
evidence roots и одно правило выбора: на компонент допускается ровно один `primary candidate`; fallback не запускается
автоматически и требует отдельного owner decision. Runtime gate закрыт, а C1–C4 имеют собственные owner-reviewed
closeout и candidate decision.

Допустимый статус component decision: `pass`, `pass_with_isolation` или `fail`. Статус исполнения этой карты —
`complete; component execution complete; handoff to 001-D`. Результаты C1–C4 не дублируются здесь целиком, а
передаются в `001-D` по ссылкам на child closeout.

## 2. Применимые документы и извлечение правил

| Источник | Правило | Влияние на эту карту | Проверка | Stop condition |
|---|---|---|---|---|
| [Map-001](plan-001-deadline-feasibility.md) | `001-C` — карта карт; `C1`–`C4` имеют отдельные acceptance boundaries и child plans | Не объединять native imports, operations и GPU-heavy smoke в один прогон; порядок фиксируется ниже | Matrix, зависимости и child-plan status | Попытка закрыть все компоненты одним benchmark или начать child execution без owner review |
| [Architectural Planning Gate](../architectural-planning-gate.md) | Child plan обязан иметь scope, source-map, owner review, audits, slices, blocker register, evidence и closeout | Все обязательные разделы присутствуют в этом файле; execution передаётся только самодостаточным child plans | Этот документ и closeout каждого `C1`–`C4` | Неразрешённый вариант маскируется временной реализацией |
| [requirements.md](../requirements.md) | MVP — один русский локальный SIP-разговор; внешние API, реальный PBX и запись аудио не входят | Native compatibility проверяется только в локальном demo boundary и не расширяет пользовательский scope | Scope/evidence review | Нужны облачный сервис, реальный PBX или аудиозапись |
| [architecture.md](../architecture.md) | Dispatcher владеет control plane; audio/text payload идут по data plane; lifecycle каналов закрывается владельцем | Проверяем границы адаптера, callback responsiveness, отмену и stale-result policy, а не сквозную интеграцию | Architecture invariant audit и component evidence | Кандидат требует payload через Dispatcher или блокирует SIP callback ожиданием AI |
| [technical-specification.md](../technical-specification.md) | Main process — latest stable free-threaded CPython >= 3.14, PCMU 8 kHz mono; critical native imports проверяются в чистом процессе и после lazy imports | Все child plans используют один фактически выбранный runtime baseline и фиксируют формат/процессную границу | Runtime identity, import/operation/lifecycle evidence | Нет воспроизводимого free-threaded runtime или нарушен PCMU/main-process baseline |
| [tooling-notes.md](../tooling-notes.md) | Нужны явный manifest, import gate, real component smoke, cancellation/lifecycle и структурированное JSON-evidence; filename tag недостаточен | Не использовать широкий неявный import graph; сохранять stdout/stderr, exit code и GIL state по стадиям | Evidence schema каждого child plan | Есть только имя `cp314t`, import-only результат или отсутствие operation evidence |
| [ADR-001](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM возвращает структурированное действие; Dialogue Manager владеет FSM и SIP-командами | `C3` не получает SIP-доступ и не меняет состояние разговора; его operation заканчивается structured result | JSON/action contract и architecture audit | LLM или inference adapter вызывает SIP напрямую |
| [ADR-002](../decisions/ADR-002-llm-model-selection.md) | Qwen3.5-9B — текущий основной кандидат; проверяются structured output, VRAM, latency и cancellation | Для `C3` проверяется этот primary, а фактические backend/quantization/version фиксируются execution evidence; альтернативы не становятся fallback без owner decision | C3 child plan и candidate evidence | Кандидат не помещается в protected GPU boundary или требует неразрешённый speculative path |
| [ADR-003](../decisions/ADR-003-free-threaded-python.md) | Проверять `Py_GIL_DISABLED`, `sys._is_gil_enabled()` до/после imports и operation; автоматическое включение GIL — failure; isolation явна | Один контракт применяется к каждому C-контру; несовместимый native-компонент не импортируется в main process | Runtime/GIL checkpoints и process-boundary evidence | GIL включился в main process или isolation предлагается без owner review |
| [documentation-process.md](../documentation-process.md) | Факт имеет один документ-владелец; после Markdown нужен registry audit, а backlog изменяется отдельно | Эта карта не дублирует требования и не меняет registry/backlog/roadmap в текущем drafting scope | Closeout template и отдельный owner action | Фактическое runtime-решение пытаются записать только в эту карту |

## 3. Граница задачи

```text
Цель:
  Согласовать карту native compatibility C1 SIP → C2 ASR → C3 LLM → C4 TTS,
  общий contract проверки, disjoint write-set и owner-gated fallback policy.

Входит:
  - планирование четырёх независимых compatibility child plans;
  - единый import → operation → GIL state → cancellation/lifecycle → evidence contract;
  - порядок и зависимости между C1–C4;
  - первичный кандидат на каждый контур как обязательное поле owner review;
  - статусы pass / pass_with_isolation / fail для будущих child checks;
  - component-level blocker register и unexpected gap protocol.

Не входит:
  - запуск CPython, SIP, ASR, LLM, TTS, GPU или любого native operation;
  - установка пакетов, сборка wheels, изменение окружения или создание IPC;
  - выбор baseline по фактическим latency/VRAM/quality результатам;
  - реализация SIP adapter, ASR/LLM/TTS adapter, Dispatcher, FSM или data-plane channels;
  - end-to-end demo, PBX integration, реальный оператор, облачные сервисы и запись аудио;
  - создание тестов, deferred markers, `skip`/`xfail` или runtime tools;
  - изменение `document-registry.md`, `task-backlog.md`, `roadmap.md` или других файлов.

Protected baseline:
  - последняя доступная стабильная free-threaded-сборка CPython не ниже 3.14 в Ubuntu 24.04 LTS x86_64/WSL2;
  - main process остаётся GIL-disabled; несовместимый native runtime может быть только в явном отдельном процессе;
  - PCMU, 8 kHz, mono; один локальный разговор; отсутствие записи аудио;
  - SIP/media callbacks не ждут ASR/LLM/TTS, а payload не проходит через Dispatcher;
  - один primary candidate на компонент; fallback только после owner discussion;
  - все pre-existing изменения рабочего дерева сохраняются и не смешиваются с этим plan.

Предположения о dirty worktree:
  - На чтении `git status --short` показал pre-existing A/AM/?? изменения в `.idea/`, `.codex/`, `artifacts/`,
    `docs/` и `tools/`; они принадлежат текущей рабочей сессии/пользователю и не редактируются этим plan.
  - Отсутствие исходного runtime-кода не трактуется как проход compatibility gate.
  - Текущий write-set — только этот файл, создаваемый через `apply_patch`.

Зависимости и внешние сервисы:
  - Разрешение execution зависит от закрытых `001-A` и `001-B`, прежде всего от воспроизводимой stable free-threaded-сборки CPython >=3.14.
  - Требуется один и тот же Ubuntu/WSL2 runtime для C1–C4; GPU-heavy C2–C4 выполняются последовательно.
  - Peer-dependent C1 S2–S4 зависят от отдельного принятого плана [`001-S`](plan-001-S-voip-test-stand.md);
    этот child map и C1 не создают VoIP-стенд.
  - Любая native dependency, отсутствующая в manifest, является gap до owner decision; пакеты в рамках этого plan не ставятся.
  - Внешний PBX, облачные ASR/LLM/TTS и реальный оператор запрещены; допустим только локальный test boundary,
    если он будет отдельно согласован в соответствующем child plan.
```

## 4. Source-map и write-set

### 4.1. Карта областей

| Область / будущий владелец | Текущее состояние | Целевое состояние child map | Gap | Действие |
|---|---|---|---|---|
| `C1 SIP` / SIP adapter и media boundary | PJSUA2/PJMEDIA 2.17: S0–S4 pass; import/operation pass после двух explicit free-threading patches и отдельного `001-S` peer | Передать SIP/media candidate decision в `001-D` с указанными patch и test limits | Arbitrary native thread-safety under production load не доказана | Использовать C1 decision в `001-D`; новые isolation/fallback только через owner review |
| `C2 ASR` / ASR adapter | `faster-whisper==1.2.1`; patched CTranslate2 binding; tested main-process path | Передать candidate decision, patch и cancellation limitation в `001-D` | Полная потокобезопасность и hard native cancellation не доказаны | Использовать C2 closeout/evidence в `001-D` |
| `C3 LLM` / inference adapter | Qwen3.5-9B Q4_K_M через Ollama 0.33.1; отдельный native process, HTTP IPC на `127.0.0.1` | Передать `pass_with_isolation`, VRAM/timing и cancellation limitation в `001-D` | Hard native cancellation ack не доказан | Использовать C3 closeout/evidence в `001-D` |
| `C4 TTS` / TTS adapter | XTTS-v2 v2.0.3; patched main-process path; WAV и PCMU boundary проверены | Передать candidate decision, patches и cancellation limitation в `001-D` | Полный SIP playback/barge-in integration не доказан | Использовать C4 closeout/evidence в `001-D` |
| Runtime / `001-B` | `001-A` и `001-B` закрыты; CPython 3.14.7t/no-GIL evidence создано | Единый latest stable free-threaded CPython >= 3.14 main-process baseline | Native compatibility остальных компонентов не запускалась | Использовать `001-B` runtime в C1–C4 |
| Evidence / `artifacts/feasibility/` | `001-A`, `001-B`, `001-S` и C1–C4 evidence созданы в disjoint roots | Сводка component decisions выполняется в `001-D` | Полная integrated evidence ещё отсутствует | Передать только ссылки и фактические ограничения, не копировать raw evidence |

### 4.2. Допустимый write-set

Фактический write-set текущего действия:

```text
docs/plans/plan-001-C-native-compatibility-map.md
```

Зарезервированный, но не активированный write-set будущих execution child plans:

| Срез | Допустимые будущие файлы | Запрет на общий state |
|---|---|---|
| `C1` | `docs/plans/plan-001-C1-sip-pjsua2-pjmedia.md`; `artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/**` | Не менять plan-001, C2–C4 plans, shared tools, source code или `candidate-matrix.md` |
| `C2` | `docs/plans/plan-001-C2-asr-primary.md`; `artifacts/feasibility/native-compatibility/C2/**` | Не менять C1/C3/C4 roots, model/runtime config или shared tools |
| `C3` | `docs/plans/plan-001-C3-llm-primary.md`; `artifacts/feasibility/native-compatibility/C3/**` | Не менять C1/C2/C4 roots, SIP/FSM code или shared GPU configuration |
| `C4` | `docs/plans/plan-001-C4-tts-primary.md`; `artifacts/feasibility/native-compatibility/C4/**` | Не менять C1/C2/C3 roots, playback code или shared tools |
| `001-D` handoff | Только его own plan и согласованный сводный evidence/baseline register | Не писать из C1–C4 в общий сводный файл и не менять protected documents молча |

`C1`–`C4` не получают права создавать production code, `config/constants.py`, runtime probe tools, тесты или IPC
adapter. Если это потребуется для воспроизводимой проверки, срабатывает unexpected gap protocol и создаётся отдельный
owner-approved slice.

### 4.3. Явно запрещённые изменения

- Любые изменения, кроме указанного plan-файла, в текущем drafting step.
- Изменения `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md`, parent Map-001 и ADR.
- Изменения `.idea/`, `.codex/`, `artifacts/feasibility/environment.md`, существующих tools и существующего кода.
- Установка пакетов, сборка native wheels, запуск runtime, импорт кандидатов и создание GPU/SIP/AI evidence.
- Автоматический переход на Sofia-SIP, Baresip, другой ASR/TTS/LLM или другой Python runtime.
- Молчаливое добавление fallback, compatibility bridge, startup-only path, shared global queue или нового IPC.

## 5. Единый contract проверки

Каждый будущий `C1`–`C4` child plan обязан повторить contract ниже и добавить только component-specific operation и
lifecycle assertions. Никакой один этап не заменяет другой.

### 5.1. Общие стадии

| Стадия | Обязательное наблюдение | Минимальный критерий |
|---|---|---|
| `import` | В чистом процессе: версия/архитектура, `SOABI`, `Py_GIL_DISABLED`, manifest direct и critical transitive imports, warnings/errors, состояние GIL до и после каждого обычного и lazy import | Manifest воспроизводим; ошибки и automatic-GIL warning не скрыты |
| `operation` | Одна реальная операция выбранного primary, достаточная для проверки не только import, без сквозного benchmark | Объект создан, operation observable, shutdown path достижим |
| `GIL state` | `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`; `sys._is_gil_enabled()` проверен до import, после каждого import/lazy import и после operation | В main process GIL остаётся `False`; включение GIL — `fail` для main process |
| `cancellation/lifecycle` | Отмена или закрытие во время operation, повторное закрытие, отсутствие stale result после close, освобождение component resources | Отмена/close bounded и идемпотентны; callback/worker не зависает и не выдаёт stale output |
| `evidence` | JSON с plan/component/candidate/runtime/stages/status/process boundary; stdout, stderr, exit code, команды, версии и причины failure | Evidence открывает решение `pass`, `pass_with_isolation` или `fail` без устного контекста |

Состояние GIL до imports является обязательным baseline checkpoint, хотя итоговый contract сохраняет указанный порядок:
import → operation → GIL state → cancellation/lifecycle → evidence. Lazy import и operation повторно фиксируются в
GIL stage; import-only success не считается compatibility.

### 5.2. Component-specific operation и lifecycle boundary

| Контур | Operation, которую должен определить child plan | Cancellation/lifecycle boundary | Запрещённый вывод |
|---|---|---|---|
| `C1 SIP` | Инициализация SIP/media объекта, минимальный локальный callback/media path и проверка ответа/завершения в пределах согласованного local test boundary | BYE обрабатывается без ожидания AI; закрытие SIP/media и повторное close не зависают; PCMU path остаётся внутри media layer | Import PJSUA2 не доказывает callback safety; SIP callback не должен ждать ASR/LLM/TTS |
| `C2 ASR` | Короткий русский PCMU/PCM fixture, observable partial/final result и штатное завершение | Отмена текущего распознавания, close канала и stale partial после close; только final результат может быть authoritative | Partial result не меняет FSM и не разрешает TTS |
| `C3 LLM` | Один локальный запрос по естественным наукам с минимальным structured result `{action, text?}` в рамках выбранного runtime | Отмена генерации до completion; отсутствие позднего результата после close/cancel; освобождение model/runtime resources | LLM не выбирает SIP target и не вызывает SIP/FSM; speculative result не становится final action |
| `C4 TTS` | Короткая русская фраза, первый PCM audio chunk и проверка согласованного формата | Остановка synthesis/playback при barge-in/close, повторное close, отсутствие смешивания старого и нового ответа | Первый audio chunk без cancel/lifecycle evidence не считается pass |

### 5.3. Candidate policy

| Контур | Primary candidate на момент drafting | Что считается fallback | Статус |
|---|---|---|---|
| `C1` | `CAND-C1-P1`: PJSUA2/PJMEDIA 2.17, проверен первым по Map-001 | Sofia-SIP/aiortp, Baresip или иной основной стек не запускаются автоматически; Baresip остаётся отдельным test-stand candidate | `pass: S0–S4 with recorded patches; main-process feasibility accepted within test limits` |
| `C2` | `CAND-C2-P1`: `faster-whisper==1.2.1` с patched CTranslate2 binding | Следующий ASR-кандидат только по отдельному owner decision после `fail` primary | `pass; tested patched main-process path` |
| `C3` | `CAND-C3-P1`: Qwen3.5-9B Q4_K_M через Ollama 0.33.1 | Qwen3.5-4B, Qwen3-8B или другой кандидат не запускаются без owner decision | `pass_with_isolation; owner-approved HTTP process boundary` |
| `C4` | `CAND-C4-P1`: XTTS-v2 v2.0.3 с recorded no-GIL patches | Следующий TTS-кандидат только по отдельному owner decision после `fail` primary | `pass; tested patched main-process path` |

Правило promotion fallback:

1. primary получает evidence со статусом `fail`, а не просто «кажется неудобным»;
2. owner письменно выбирает конкретный fallback, scope и process boundary;
3. зависимый child plan и, если меняется архитектурная граница, ADR обновляются до запуска fallback;
4. fallback получает собственный candidate ID и evidence root;
5. fallback failure не превращается в pass заменой assertion или ослаблением contract.

## 6. Owner-review decisions

| ID | Вопрос | Решение/предложение | Последствие | Статус |
|---|---|---|---|---|
| `OR-CMAP-001` | Можно ли считать этот файл execution benchmark? | Нет; это child map и contract, execution выделяется в `C1`–`C4` | Никаких запусков и baseline claims в текущем plan | `resolved by scope` |
| `OR-CMAP-002` | В каком порядке идут контуры? | Независимые drafting/read-only задачи допускают параллелизм; зависимые и GPU-heavy execution lanes идут по gate | Main executor сохраняет общий audit и disjoint evidence roots | `resolved by Map-001 policy` |
| `OR-CMAP-003` | Какой SIP primary проверять первым? | PJSUA2/PJMEDIA; stable version/build выбираются и фиксируются в C1 execution | Sofia-SIP/aiortp и Baresip остаются fallback только после failure и owner decision | `resolved by Map-001; result task-owned` |
| `OR-CMAP-004` | Как выбрать ASR primary? | C2 выбирает один доступный stable/local кандидат по заданным критериям и фиксирует выбор в evidence | Предварительного owner blocker нет; второй кандидат не проверяется после failure без owner decision | `resolved as execution task` |
| `OR-CMAP-005` | Какой LLM primary? | Qwen3.5-9B 4-bit — текущий primary по ADR-002; C3 выбирает stable backend и фиксирует детали в evidence | Qwen3.5-4B/Qwen3-8B не запускаются как fallback без отдельного решения | `resolved by ADR-002; execution details task-owned` |
| `OR-CMAP-006` | Как выбрать TTS primary? | C4 выбирает один доступный stable/local кандидат по заданным критериям и фиксирует выбор в evidence | Предварительного owner blocker нет; второй кандидат не проверяется после failure без owner decision | `resolved as execution task` |
| `OR-CMAP-007` | Что делать при automatic GIL enable? | Main-process compatibility считать `fail`; isolation не выбирать автоматически | Нужны owner decision, process boundary и отдельный IPC plan, если isolation допустима | `resolved policy; execution open` |
| `OR-CMAP-008` | Можно ли менять protected docs ради регистрации карты? | Нет в этой задаче: registry/backlog/roadmap не меняются | Registry/backlog synchronization остаётся отдельным owner action | `resolved by user scope` |

## 7. Audit владельца поведения и парадигмы реализации

Для текущей карты: **`not applicable`**. Файл не добавляет public algorithm, не меняет SIP state, FSM, channel
generation, payload ownership или runtime behavior; свободные функции и helper-ы не создаются.

Владельцы поведения для будущих child plans предварительно зафиксированы, чтобы compatibility probe не стал новым
владельцем продуктовой логики:

| Контур | Владелец поведения | Scoped dependencies и lifecycle |
|---|---|---|
| `C1` | SIP adapter/media capability | SIP endpoint, PCMU media boundary, callback cancellation и close принадлежат адаптеру; Dispatcher получает только control events |
| `C2` | ASR adapter и его recognition session | Audio input, partial/final result, cancellation token и session close; finality передаётся Dispatcher как событие |
| `C3` | LLM inference adapter; Dialogue Manager владеет действием и FSM | Model/runtime handle, request cancellation и structured result; SIP target и irreversible actions остаются у Dialogue Manager |
| `C4` | TTS adapter/playback capability | Approved text input, PCM output, playback cancellation и close; playback channel не передаёт payload через Dispatcher |

Probe/helper, если он понадобится, должен быть typed side-facade конкретного child plan и не может менять состояние
продуктового компонента. Появление нового adapter/facade или IPC-владельца требует unexpected gap protocol.

## 8. Process invariant audit

| Инвариант | Состояние draft | Как закрывается |
|---|---|---|
| Карта не смешивает независимые benchmarks | Соблюдён: C1–C4 разделены | Каждый child plan имеет свой acceptance и evidence root |
| Execution gates имеют зависимости | Подготовка независимых child plans допускает параллелизм; upstream-зависимые и GPU-heavy execution lanes идут по gate | Не запускать child до его review и закрытых зависимостей |
| Dirty worktree не смешан | Соблюдён: pre-existing изменения protected | Проверить фактический diff перед любым будущим execution |
| Runtime baseline авторитетен | `001-B` подтвердил CPython 3.14.7t/Ubuntu WSL2 и disabled GIL; C1–C4 проверены на этом baseline или с явной isolation boundary | Использовать component closeouts; не смешивать runtime и component claims |
| Relevant и irrelevant checks разделены | Component contract релевантен; e2e/MOS/full benchmark отложены в другие планы | Child acceptance не расширять скрыто |
| Requirements не дублируются без owner link | В таблицах используются краткие ссылки на owner-documents | Новые факты о требованиях писать в owner-document отдельным решением |
| Registry/backlog policy соблюдается | Registry/backlog синхронизируются после C1–C4 closeout отдельным owner-document action | Повторить governance audit после этой синхронизации |
| Fallback и simplification видимы | Есть отдельный register; silent fallback запрещён | Любой новый вариант проходит owner review и получает ID |
| Deferred test не маскируется | Component probes выполнены в child plans; integrated tests остаются deferred | См. раздел 10; `skip`/`xfail` отсутствуют |
| Closeout должен содержать фактический diff и failures | Карта содержит только map-level acceptance; C1–C4 факты принадлежат child closeout | Заполнять component results только в их child plans и handoff `001-D` |

## 9. Architecture invariant audit

- `Dispatcher` остаётся владельцем control plane и Dialogue FSM; C1–C4 не получают права менять FSM напрямую.
- SIP/media callback не ожидает ASR, LLM, TTS или evidence; BYE относится к отдельному C1 lifecycle path и должен быть
  обработан немедленно.
- PCM/audio и крупные text payload не проходят через Dispatcher; Dispatcher видит только control/result events.
- Закрытие канала отбрасывает stale producer output, закрытый канал не переиспользуется; C2/C3/C4 должны это доказать
  в своих lifecycle assertions.
- Только authoritative final ASR result может породить финальное LLM action и разрешить TTS; partial ASR и
  provisional LLM output не меняют FSM и не выполняют transfer/hangup.
- TTS playback отменяется при barge-in, новый ответ не смешивается со старым; C4 обязан иметь отдельный cancel path.
- LLM выдаёт ограниченный structured result и не получает произвольный SIP-доступ; operator target берётся из
  конфигурации Dialogue Manager.
- PCMU, один разговор, локальный boundary и отсутствие записи аудио не меняются этой картой.
- Free-threaded CPython — main-process baseline; automatic GIL enable является fail, а isolation — только явным
  owner-approved решением.
- В этот plan не добавляются реальные внешние сервисы, PBX-логика, production observability или новый IPC protocol.

## 10. Узкие implementation slices (только планирование границ)

Эти slices описывают будущие execution boundaries; ни один из них не выполняется созданием этого файла.

| Slice | Цель и порядок | Допустимый write-set | Acceptance для открытия/закрытия | Stop condition / следующий шаг |
|---|---|---|---|---|
| `C-MAP-0` Contract freeze | Утвердить общий contract, status vocabulary, candidate IDs и evidence schema | Только этот map до owner review | Все четыре контура используют один порядок и имеют явного owner | Неясен stage/status/process boundary → остановка и `OR-CMAP` review |
| `C-MAP-1` / `C1` | Создать и согласовать SIP child plan; проверить первым после `001-B` | Только C1 plan и `.../C1/**` | Primary PJSUA2/PJMEDIA, operation, BYE/PCMU lifecycle и evidence fields определены | Import/operation/GIL/cancel gap → C1 fail/owner discussion; не запускать C2 |
| `C-MAP-2` / `C2` | После закрытия C1 создать и согласовать ASR child plan | Только C2 plan и `.../C2/**` | Один выбранный в execution stable/local ASR; partial/final/cancel/lifecycle contract проверен | Нет primary или final/cancel evidence boundary → C2 blocked; fallback не запускать |
| `C-MAP-3` / `C3` | После закрытия C2 создать и согласовать LLM child plan | Только C3 plan и `.../C3/**` | Qwen3.5-9B как текущий primary; backend/runtime/quantization зафиксированы execution evidence; structured result, VRAM observation и cancel defined | GIL/VRAM/structured/cancel gap → C3 blocked; не менять SIP/FSM |
| `C-MAP-4` / `C4` | После закрытия C3 создать и согласовать TTS child plan | Только C4 plan и `.../C4/**` | Один выбранный в execution stable/local TTS; Russian PCM first chunk and cancel defined | Нет audio/cancel/close evidence → C4 blocked; fallback не запускать |
| `C-MAP-5` handoff | Свести только результаты C1–C4 для `001-D` | Сводка принадлежит `001-D`, не C1–C4 | У каждого контура ровно один status, process boundary и evidence link | Любой `fail`, missing evidence или open owner decision → не открывать `001-D` closeout |

Переход между slices не является автоматическим: owner review каждого child plan нужен до его execution, а результат
`pass_with_isolation` требует отдельного подтверждения process boundary. `C-MAP-5` не выбирает новый кандидат и не
исправляет красный результат.

## 11. Blocker register

| ID | Срез | Проверяемый триггер | Что блокируется | Владелец решения | Evidence/решение | Статус на 2026-08-27 |
|---|---|---|---|---|---|---|
| `B-CMAP-001` | Вся карта | `001-B` не дал воспроизводимой stable free-threaded-сборки CPython >=3.14 и disabled-GIL evidence | Execution C1–C4 | project owner | `001-B` runtime evidence | `resolved 2026-08-27` |
| `B-CMAP-002` | Вся карта | Child map не прошёл отдельный owner review | Создание/запуск C1–C4 execution stage | project owner | Owner response по этому файлу | `resolved 2026-08-27` |
| `B-CMAP-003` | C1 | PJSUA2/PJMEDIA primary не подтверждён как допустимый candidate или требует неучтённый native build | C1 и все зависимые C2–C4 | project owner | C1 owner decision или gap record | `resolved 2026-08-27; C1 pass with recorded patches` |
| `B-CMAP-004` | C2 | C2 execution не выбрал и не зафиксировал ASR candidate | C2 execution и matrix closeout | executor | C2 execution manifest/evidence | `resolved 2026-08-27` |
| `B-CMAP-005` | C3 | Qwen3.5-9B 4-bit или выбранный execution backend нарушает 16 GB protected GPU boundary | C3 execution и `001-D` | executor/project owner по факту gap | C3 VRAM evidence и decision record | `resolved 2026-08-27; no OOM` |
| `B-CMAP-006` | C4 | C4 execution не выбрал и не зафиксировал TTS candidate | C4 execution и matrix closeout | executor | C4 execution manifest/evidence | `resolved 2026-08-27` |
| `B-CMAP-007` | C1–C4 | Любой import, lazy import или operation включает GIL в main process | Main-process decision этого компонента | project owner | GIL checkpoints и isolation decision | `resolved 2026-08-27 for tested paths` |
| `B-CMAP-008` | C1–C4 | Cancellation/close не bounded, не идемпотентны или выдаётся stale result | Component pass и следующий slice | component owner + project owner | Lifecycle evidence | `resolved 2026-08-27 with explicit native-cancel limitations` |
| `B-CMAP-009` | C1–C4 | Evidence не содержит command, version, stdout/stderr, exit code или failure reason | `pass`/`pass_with_isolation` и handoff | child-plan owner | Structured evidence root | `resolved 2026-08-27` |
| `B-CMAP-010` | C1–C4 | Fallback запускается до primary `fail` и owner decision | Текущий и зависимый child plan | project owner | Candidate decision record | `resolved 2026-08-27; no fallback run` |
| `B-CMAP-011` | C1–C4 | Два контура запускаются одновременно и конкурируют за runtime/GPU или общий write-set | Достоверность component evidence | main executor | Process/write-set audit | `not triggered; GPU-heavy probes serialized` |
| `B-CMAP-012` | C1–C4 | Для проверки требуется новый adapter, facade, IPC, shared tool или protected-doc edit | Зависимый slice до архитектурного review | project owner | Unexpected gap record; новый ADR/plan при необходимости | `resolved; existing HTTP IPC explicitly accepted for C3` |

Необъяснимый красный результат не переводится в `pass`; блокируется только зависимый slice, пока owner не выберет
разрешённый путь и не появится соответствующее evidence.

## 12. Test/evidence plan

В этом child map тесты и probes не создаются. Ниже — обязательный контракт для будущих child plans, а не утверждение,
что какая-либо проверка уже выполнена.

### 12.1. Логические lanes

- `Import lane`: чистый процесс, explicit manifest прямых и critical транзитивных native dependencies, runtime identity,
  GIL checkpoints, import warnings и lazy imports.
- `Operation lane`: ровно одна минимальная component operation из таблицы раздела 5.2; не e2e benchmark и не full model
  quality run.
- `GIL lane`: checkpoint после operation и всех lazy imports; automatic enable — failure для main process.
- `Cancellation/lifecycle lane`: cancel/close/re-close, bounded completion, stale-result suppression и resource release.
- `Evidence lane`: структурированный result, stdout/stderr, exit code, command, versions, candidate ID, process boundary,
  failure reason и owner decision reference.

### 12.2. Раздельные evidence roots

Будущие child plans резервируют:

```text
artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/
artifacts/feasibility/001-C2/
artifacts/feasibility/001-C3-llm-primary/
artifacts/feasibility/001-C4-tts-primary/
```

Каждый root принадлежит только своему child plan. Минимальная JSON-запись должна содержать:

```json
{
  "plan_id": "001-C1",
  "component": "SIP",
  "candidate_id": "CAND-C1-P1",
  "runtime": {"python": "<selected stable free-threaded CPython >=3.14>", "gil_disabled": true},
  "stages": ["import", "operation", "gil_state", "cancellation_lifecycle"],
  "status": "pass|pass_with_isolation|fail",
  "process_boundary": "main|isolated|undecided",
  "command": "<recorded by child plan>",
  "exit_code": 0,
  "failure_reason": null
}
```

Значения `status`, `exit_code`, GIL state, versions и commands не заполняются этим drafting step. `candidate-matrix.md`
и `baseline-register.md` принадлежат последующему handoff/closeout, а не C1–C4 общему write-set.

### 12.3. Нерелевантные для этой карты проверки

Полный SIP/RTP demo, multi-turn FSM, RAG quality, MOS-CQ, end-to-end turn latency, production readiness и operator
transfer не являются acceptance этого child map. Они остаются в соответствующих media/dialogue/test-stand plans.

## 13. Deferred evidence conformance

Статус для этого plan: **`not applicable`**.

Причина: этот файл не создаёт тестов, probes, deferred checks, markers или ожидаемо красных assertions; component
evidence принадлежит отдельным `C1`–`C4` child execution plans. Здесь нет `skip`/`xfail`; отсутствие evidence по
конкретному child означает `not executed`, не `pass`.

Если будущий child plan создаст обязательную проверку, которую нельзя выполнить в его scope, он обязан завести свой
стабильный `evidence_id`, owner, команду явного запуска, stdout/stderr/exit code и promotion condition. Такой deferred
case не добавляется молча в этот map.

## 14. Legacy / fallback / simplification register

| ID | Элемент | Политика | Где закрывается | Владелец | Статус |
|---|---|---|---|---|---|
| `LG-CMAP-001` | Legacy helper/compatibility bridge | Не вводить; tests-only helper не сохранять ради удобства | Unexpected gap + отдельный approved plan, если реально нужен | project owner | `none approved` |
| `FB-CMAP-001` | Native dependency включает GIL | Допустима только явная process isolation; main-process pass не подменяется | Component child plan, IPC plan и/или ADR после owner discussion | project owner | `approved policy; owner-gated` |
| `FB-CMAP-002` | Следующий SIP/ASR/LLM/TTS кандидат | Не запускать автоматически; сначала primary `fail`, затем concrete owner decision и новый candidate ID | Тот же child plan после review или отдельный plan/ADR | project owner | `not authorized` |
| `SIM-CMAP-001` | Не выполнять full benchmark/e2e в карте | Это boundary child map; operation остаётся минимальным и наблюдаемым | C1–C4 и последующие integration plans | project owner | `approved scope` |
| `SIM-CMAP-002` | Не включать speculative LLM path | Унаследованная deadline boundary; partial/provisional output не authoritative | Dialogue/LLM implementation plan после отдельного решения | project owner | `approved scope` |
| `SIM-CMAP-003` | Не менять registry/backlog/roadmap в текущем drafting step | Это явное ограничение запроса, не способ скрыть результат execution | Отдельный owner/documentation action | project owner | `protected; not executed` |

Ни одно из перечисленного не разрешает снизить assertion, заменить fail на pass или импортировать несовместимый
native-модуль в main process.

## 15. Unexpected gap protocol

При обнаружении gap зависимый slice немедленно останавливается. Заполняется запись:

```text
Gap ID:
Обнаруженный gap:
Затронутые документы и компоненты:
Фактический trigger/evidence:
Почему текущий plan нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Нужен ли новый ADR/roadmap/child plan:
Owner decision и дата:
```

Обязательные триггеры остановки:

- native import требует отсутствующий пакет, source build или системную библиотеку, не описанную в `001-B`;
- operation включает GIL, выполняет блокирующий callback или нарушает data/control-plane boundary;
- cancellation/lifecycle нельзя доказать без нового IPC, shared adapter, facade или изменения owner;
- выбранный primary отсутствует, заменился версией молча или требует parallel fallback;
- evidence не может сохранить command, version, stdout/stderr и exit code;
- изменение затрагивает protected baseline, registry/backlog/roadmap или чужой child write-set.

До review запрещены скрытый fallback, startup-only path, ослабление acceptance, подмена Python runtime, расширение
scope и продолжение зависимого slice.

## 16. Execution report и closeout template

Карта принята 2026-08-27 и находится в состоянии `complete; component execution complete; handoff to 001-D`. Этот closeout
фиксирует map-level review, runtime handoff и ссылки на C1–C4 decisions; raw execution evidence в этот файл не переносится.

```text
Plan: 001-C native compatibility map
Уровень: child map
Execution status: complete; component execution complete; handoff to 001-D
Owner review: 2026-08-27, accepted; runtime handoff: `../../artifacts/feasibility/001-B/closeout.md`

Фактические даты и исполненные slices:
  - C-MAP-0: 2026-08-27, contract freeze reviewed
  - C1: 2026-08-27, S0–S4 pass with explicit free-threading patches and separate `001-S` peer; see child closeout
  - C2: 2026-08-27, pass; faster-whisper patched main-process path, see child closeout
  - C3: 2026-08-27, pass_with_isolation; Qwen3.5-9B via local Ollama HTTP IPC, see child closeout
  - C4: 2026-08-27, pass; XTTS-v2 patched main-process path, see child closeout

Runtime:
  - OS/WSL: Ubuntu 24.04.4 LTS x86_64 / WSL2
  - CPython/SOABI/Py_GIL_DISABLED: 3.14.7t / cpython-314t-x86_64-linux-gnu / 1
  - GIL checkpoints: `001-B` stdlib import and concurrency evidence, all disabled

Candidate decisions:
  - C1 primary/status/process boundary/evidence: PJSUA2/PJMEDIA primary; pass with recorded patches, main-process feasibility accepted within test limits; see `../../artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/closeout.md`
  - C2 primary/status/process boundary/evidence: faster-whisper 1.2.1; pass, patched main-process path; see `../../artifacts/feasibility/001-C2/closeout.md`
  - C3 primary/status/process boundary/evidence: Qwen3.5-9B Q4_K_M; pass_with_isolation, Ollama HTTP IPC; see `../../artifacts/feasibility/001-C3-llm-primary/closeout.md`
  - C4 primary/status/process boundary/evidence: XTTS-v2 v2.0.3; pass, patched main-process path; see `../../artifacts/feasibility/001-C4-tts-primary/closeout.md`

Commands, versions, exit codes и evidence roots:
  - C1: PJSIP/PJSUA2/PJMEDIA 2.17, SWIG 4.2.0, CPython 3.14.7t; S0–S4 evidence in `../../artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/` and `../../artifacts/feasibility/001-S-voip-test-stand/`
  - C2–C4: commands, versions and evidence are recorded in their child-plan roots; this map carries only the handoff summary
  - Runtime handoff: `../../artifacts/feasibility/001-B/commands.md`

Отрицательные результаты и причины отказа: unpatched SWIG import/unsafe buffer path failed as expected and was retained as negative evidence; patched candidate passed
Открытые blocker IDs и owner decisions: component execution blockers закрыты или не triggered; residual limitations
(patched native bindings, process isolation и отсутствие hard native cancellation ack) передаются в `001-D`.
Fallback/isolation decisions и их corrective paths: fallback не запускался; C3 принят как `pass_with_isolation` по
owner decision, C2/C4 приняты в patched main-process путях.
Pre-existing failures:
  - Existing dirty worktree recorded before child execution; no component files were mixed
Out-of-scope findings: ASR, LLM, TTS and application implementation remain deferred; arbitrary production native
thread-safety/load and final SIP adapter implementation are not claimed by C1
Registry audit result: `python tools/check_document_registry.py` — PASS after this synchronization
Backlog/roadmap/document-registry changes: registry/backlog/roadmap were synchronized after `001-A`/`001-B`; no
component result was written here

Непосредственный handoff в `001-D` выполнен; затем `001-D` и `001-E` также закрыты собственными evidence/closeout.
Текущий handoff карты — в Map-002; новые implementation child plans не считаются частью этого feasibility map.
Остаточные риски к 2026-09-24:
Фактический closeout owner/status:
```

Карта получила статус `complete`: каждый применимый `C1`–`C4` имеет завершённое execution, evidence и closeout;
candidate decisions (`pass`/`pass_with_isolation`) сохранены отдельно от статуса карты.
