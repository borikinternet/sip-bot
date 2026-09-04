# Plan-001-C4: Проверка одного primary TTS-кандидата

Уровень: `child plan`  
Статус исполнения: `complete`  
Candidate decision: `pass`  
Родительская карта: [Map-001 — `plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md)  
Зависимости: `001-B` и `001-C` из Map-001  
Execution stage: завершён для проверенного candidate-specific main-process пути; production integration не входит в closeout

План прошёл owner review и был исполнен в узком candidate-specific scope. Фактические команды, патчи, runtime-
ограничения и результаты находятся в [`closeout.md`](../../artifacts/feasibility/001-C4-tts-primary/closeout.md) и
связанных evidence-файлах. План закрыт статусом `complete` в пределах candidate-specific scope; closeout не является
заявлением о production readiness или полном SIP/RTP-контуре.

## 1. Цель и проверяемый результат

Подготовить узкую feasibility-проверку ровно одного primary TTS-кандидата, выбранного execution-задачей
проекта. Проверка должна установить факты о следующем минимальном контуре:

1. кандидат импортируется в чистом latest stable free-threaded CPython >= 3.14 без непроизвольного включения GIL;
2. кандидат принимает короткий русский ответ и выдаёт первый непустой PCM-фрагмент;
3. PCM-фрагмент имеет наблюдаемый формат и проходит через границу, совместимую с PCMU 8 kHz mono;
4. текущая генерация/выдача может быть отменена после начала потока, а stale PCM не попадает в закрытый playback-канал.

Результат исполнения — evidence root с точным именем, версией, источником, лицензией и voice/model asset, командами,
stdout/stderr, exit code, состоянием GIL по стадиям, метаданными первого PCM-фрагмента, результатом PCMU boundary,
результатом cancellation и прослушиваемым WAV-образцом полного короткого TTS-ответа. WAV-образец создаётся из того же
успешного синтетического TTS operation, не является записью разговора и сохраняется по пути
`artifacts/feasibility/001-C4-tts-primary/tts-sample.wav`. Допустимые итоговые статусы Map-001: `pass`,
`pass_with_isolation` или `fail`.

`pass_with_isolation` не выбирается этим планом автоматически: он возможен только после отдельного owner decision и
явной фиксации process/IPC boundary. При отсутствии такого решения результат несовместимого кандидата остаётся
`fail` или `blocked`, а не превращается в fallback.

Точное имя primary TTS в текущих документах не зафиксировано. Его выбор, stable version и voice/model asset являются
первой execution-задачей C4 и фиксируются в candidate manifest; предварительный owner-вопрос не требуется.

## 2. Применимые документы и извлечённые правила

| Источник | Извлечённое правило | Влияние на этот план | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan самодостаточен и имеет scope, source-map/write-set, owner review, audits, slices, blockers, evidence и closeout | Все обязательные разделы находятся в этом файле; создание плана не открывает execution stage | Проверка структуры плана перед owner review | Отсутствует обязательный раздел или смешаны planning и execution |
| [`plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md) | `001-C4` проверяет один TTS-кандидат; policy кандидатов — один основной кандидат, следующий только после провала и owner decision | C4 выбирает один stable/local candidate и не запускает fallback автоматически; соблюдает зависимости `001-B`/`001-C` | Execution manifest + отдельный evidence root `001-C4` | Candidate selection не выполнен или появился неразрешённый fallback |
| [`requirements.md`](../requirements.md) | TTS локальный; русский диалог; TTS начинает работу после первой пригодной фразы; при перебивании текущая речь прекращается | Проверка ограничена локальным коротким ответом, первым PCM и cancellation; полный SIP-сценарий не подменяется | Operation, first-fragment и cancellation evidence | Внешний API, отсутствие первого PCM или невозможность прекратить выдачу |
| [`architecture.md`](../architecture.md) | TTS получает одобренный текст по data plane и пишет PCM в playback buffer; Dispatcher владеет control plane, но не переносит payload | Probe не вызывает TTS из RTP callback и не прокладывает PCM через Dispatcher; закрытие playback-канала отбрасывает stale producer | Boundary/cancellation probe и architecture audit | Требуется аудио через Dispatcher, прямое SIP-управление или переиспользование закрытого канала |
| [`technical-specification.md`](../technical-specification.md) | Baseline — latest stable free-threaded CPython >= 3.14 в Ubuntu 24.04 WSL2; SIP media — PCMU, 8 kHz, mono; внутренний PCM — рабочий формат | Проверить import/no-GIL, PCM metadata и совместимость `PCM S16LE mono 8 kHz → PCMU 8 kHz mono`; не сохранять аудиозапись разговора, но сохранить отдельный синтетический TTS sample для ручного прослушивания | Stage evidence с командами, версиями и exit code | GIL включён, формат не наблюдаем, boundary не доказан или cancellation зависает |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | После каждого критичного импорта и операции `sys._is_gil_enabled()` остаётся `False`; несовместимый native-компонент не импортируется в main process | Проверка делается в чистом процессе с `Py_GIL_DISABLED`, обычными/lazy imports и operation smoke | `import.json` и stderr/stdout | Автоматическое включение GIL или только import tag без operation evidence |
| [`ADR-001-llm-and-dialogue-manager.md`](../decisions/ADR-001-llm-and-dialogue-manager.md) | Dialogue Manager владеет состоянием, отменой и таймаутами; TTS остаётся заменяемым адаптером; LLM не получает прямой SIP-доступ | TTS probe не меняет FSM/SIP и не объявляет адаптером владельца звонка; отмена проверяется как scoped operation/channel boundary | Owner audit и cancellation evidence | Probe начинает менять FSM, SIP outcome или скрывает отмену внутри свободного helper-а |
| [`ADR-002-llm-model-selection.md`](../decisions/ADR-002-llm-model-selection.md) | ADR относится к ещё не утверждённому LLM; shared GPU и latency являются только контекстом | Не использовать ADR-002 для выдумывания TTS-кандидата или его выбора; учитывать только совместную ресурсную конкуренцию, если она фактически наблюдается | Candidate manifest и closeout | TTS-кандидат выводится из LLM-shortlist без owner decision |
| [`licensing-policy.md`](../licensing-policy.md) | Для модели, программной зависимости и голоса фиксируются источник, версия и лицензия; веса не коммитятся автоматически | До operation нужны provenance и license evidence; voice assets не копируются в репозиторий или evidence root без отдельного решения | Manifest и license record | Нет права на локальное исследование/демонстрационный сценарий или требуется неразрешённая публикация asset |
| [`documentation-process.md`](../documentation-process.md) | Каждый факт имеет owner-документ; решения не дублируются молча | План ссылается на owner-документы; результат, меняющий ADR или технический контракт, передаётся на отдельную синхронизацию | Closeout и owner review | Результат требует молчаливого изменения требований, архитектуры или ADR |
| [`tooling-notes.md`](../tooling-notes.md) | Имя `cp314t` не является evidence; нужны import/operation checks и структурированный stdout/stderr/exit code | Команда и формат будущего probe фиксируются заранее; host Python не доказывает совместимость основного runtime | Evidence manifest | Есть только название wheel/runtime или только успешный import |

## 3. Граница задачи

```text
Цель:
  Подготовить проверку одного execution-selected primary TTS-кандидата на import/no-GIL,
  короткий русский ответ, первый PCM-фрагмент, PCMU-compatible boundary и cancellation.

Входит:
  - выбор и фиксация имени, фактической версии/commit, runtime, источника и лицензии кандидата;
  - чистый import/no-GIL probe в latest stable free-threaded CPython после прямых и lazy imports;
  - одна короткая русская фраза, например «Вода кипит при ста градусах Цельсия.»;
  - первый непустой PCM-фрагмент и его metadata;
  - разработка и проверка границы PCM S16LE mono 8 kHz к PCMU 8 kHz mono в рамках C4/media plan;
  - cancellation после начала выдачи и отбрасывание stale output закрытого playback-канала;
  - сохранение только структурированного feasibility evidence, без записи аудио разговора.

Не входит:
  - сравнение нескольких кандидатов и автоматический fallback;
  - сравнение кандидатов, автоматический fallback, silent simplification или выбор isolation;
  - полный SIP/RTP call, регистрация, BYE, transfer, Dispatcher/FSM и test-stand integration;
  - оценка качества голоса, многоходового диалога, RAG, ASR, LLM или end-to-end latency;
  - production playback, запись/хранение аудио, публикация весов/голоса или создание полноценного адаптера;
  - установка пакетов, загрузка весов и изменение конфигурации в рамках текущего drafting;
  - изменение требований, architecture, technical specification, ADR, roadmap, backlog или registry.

Protected baseline:
  - основной runtime: latest stable free-threaded CPython >= 3.14, Ubuntu 24.04 LTS x86_64 в WSL2;
  - GIL остаётся отключённым в main process после import и operation;
  - несовместимый native-компонент не импортируется в main process;
  - PCMU/G.711 μ-law, 8 kHz, mono; целевая внутренняя граница — PCM S16LE, mono, 8 kHz;
  - payload идёт по data plane, control plane и отмена принадлежат Dispatcher/Dialogue lifecycle;
  - только одобренный финальный текст является входом authoritative TTS path;
  - внешние API, реальный PBX и аудиозапись не вводятся.

Предположения о рабочем дереве:
  - рабочее дерево уже содержит pre-existing added/untracked документы, tools, .idea, .codex и artifacts;
  - этот child plan не присваивает себе эти изменения, не очищает их и не меняет unrelated files;
  - до будущего execution повторно фиксируется `git status --short`, а baseline не смешивается с evidence этого среза;
  - текущая операция создаёт только этот Markdown-файл.

Зависимости и внешние сервисы:
  - закрытые prerequisites `001-B` и `001-C` (native compatibility matrix);
  - локально доступные model/voice assets и зависимости, найденные в C4-S0; их отсутствие — blocker, а не повод выбрать fallback;
  - Ubuntu/WSL2 — авторитетная среда runtime; Docker допустим только для явно назначенного peer/test-stand lane;
  - внешние SIP, cloud TTS и внешние API не используются;
  - текущий drafting не требует и не разрешает установки пакетов или запусков runtime.
```

## 4. Source-map, write-set и запрещённые изменения

### 4.1. Source-map

| Область | Источник/будущий компонент | Текущее состояние | Целевое состояние | Gap | Действие в execution stage |
|---|---|---|---|---|---|
| Идентичность кандидата | C4-S0 и будущий `candidate-manifest` | Точное имя primary TTS в docs отсутствует | Есть имя, stable version/commit, источник, license и voice/model provenance | `B-C4-001` | Выбрать и зафиксировать manifest до candidate imports |
| Runtime/import | Latest stable free-threaded CPython >= 3.14, `tools/feasibility/tts_primary_probe.py` и candidate-specific patched native modules | Для проверенного пути применены `torchaudio-free-threading.patch`, `tokenizers-free-threading.patch` и `monotonic-alignment-search-free-threading.patch`; optional Triton отключён, torchcodec не требуется | Прямые, lazy imports и operation проходят без GIL re-enable | `B-C4-002` и `B-C4-007` | Проверить clean-process import/operation evidence и повторить только с теми же патчами |
| TTS operation | TTS capability будущего adapter/probe | Компонент и public API не выбраны | Один короткий русский ответ выдаёт первый PCM-фрагмент | API зависит от `B-C4-001` | Не создавать production adapter; использовать только узкий probe |
| PCM boundary | Media egress boundary из `architecture.md`/`technical-specification.md` | Код media boundary ещё не создан | Наблюдаемый PCM совместим с `PCM S16LE mono 8 kHz → PCMU 8 kHz mono` | `B-C4-004` | Проверить существующий/отдельно одобренный boundary; новый converter не вводить молча |
| Cancellation | TTS playback channel и Dispatcher cancellation contract | Полного channel implementation нет | После cancel выдача прекращается, закрытый channel не принимает stale PCM | `B-C4-005` | Проверить candidate stop и channel-close semantics в локальном probe |
| Evidence | `artifacts/feasibility/001-C4-tts-primary/` | Evidence для C4 отсутствует | Структурированные manifest/import/operation/boundary/cancel/closeout записи | Нет после открытия execution | Создавать только в согласованном evidence root |
| Документы-владельцы | `ADR-002`, `architecture.md`, `technical-specification.md`, `task-backlog.md`, `document-registry.md`, `roadmap.md` | Источники содержат открытый выбор TTS и текущие planning records | Синхронизация только если фактический результат меняет принадлежащий им факт | Не разрешено текущим write-set | Передать изменения на отдельный owner-approved docs sync |

### 4.2. Write-set

Текущий drafting write-set:

- создать только [`docs/plans/plan-001-C4-tts-primary.md`](plan-001-C4-tts-primary.md);
- не создавать evidence, probe, fixtures, тесты, конфигурацию или model assets.

Предварительный write-set будущей execution stage, который потребуется отдельно открыть owner review:

- `tools/feasibility/tts_primary_probe.py` — только candidate-specific probe, без production ownership и SIP side effects;
- `artifacts/feasibility/001-C4-tts-primary/manifest.json`;
- `artifacts/feasibility/001-C4-tts-primary/import.json`;
- `artifacts/feasibility/001-C4-tts-primary/operation.json`;
- `artifacts/feasibility/001-C4-tts-primary/tts-sample.wav` — полный короткий синтетический TTS-ответ для ручного
  прослушивания;
- `artifacts/feasibility/001-C4-tts-primary/pcmu-boundary.json`;
- `artifacts/feasibility/001-C4-tts-primary/cancellation.json`;
- `artifacts/feasibility/001-C4-tts-primary/torchaudio-free-threading.patch`;
- `artifacts/feasibility/001-C4-tts-primary/tokenizers-free-threading.patch`;
- `artifacts/feasibility/001-C4-tts-primary/monotonic-alignment-search-free-threading.patch`;
- `artifacts/feasibility/001-C4-tts-primary/patch-build.md`;
- `artifacts/feasibility/001-C4-tts-primary/closeout.md`.

Исходный raw PCM buffer не сохраняется отдельным `.pcm`-дампом. Разрешённый `tts-sample.wav` — это не запись разговора,
а прослушиваемый результат того же короткого синтетического operation; его metadata, sample format, sample rate,
channels, duration и digest фиксируются в `operation.json`. Voice/model weights в evidence root не копируются.

### 4.2.1. Candidate-specific no-GIL invariant

Для проверенного main-process пути обязательны именно зафиксированные исходные патчи и собранные с ними native
модули. Использование непатченных wheel-файлов не является тем же самым runtime и не может быть объявлено успешным
повторением C4:

- `torchaudio-free-threading.patch` добавляет `pybind11::mod_gil_not_used()` в `_torchaudio`;
- `tokenizers-free-threading.patch` добавляет `#[pymodule(gil_used = false)]`;
- `monotonic-alignment-search-free-threading.patch` заменяет module slot на `Py_MOD_GIL_NOT_USED`;
- точные исходники, команды сборки, хэши патчей и хэши бинарников фиксируются в `patch-build.md`;
- optional Triton отключён на проверенном пути, а `torchcodec` не импортируется и не является скрытым fallback;
- после candidate import, lazy initialization и operation `sys._is_gil_enabled()` должен оставаться `False`.

Эти патчи являются частью candidate-specific feasibility setup, а не молчаливым изменением production-зависимостей.

### 4.3. Запрещённые изменения

В текущем drafting и в execution stage этого child plan запрещены:

- любые файлы, кроме указанного текущего plan-file и отдельно разрешённых будущих probe/evidence paths;
- `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md` и другие owner-документы без отдельного docs sync;
- production `src/`, `config/constants.py`, `tests/`, package manifests, lockfiles, Docker/compose и системное окружение;
- импорт или вызов неуказанного кандидата, второго TTS, fallback, скрытого compatibility bridge или startup-only path;
- автоматический переход к process isolation, новый IPC-протокол, новый converter или новый media adapter;
- внешний API, реальный PBX, сеть за пределами локальной среды и запись разговора;
- ослабление assertion, подмена `fail` на `pass`, безымянный `skip`/`xfail` или удаление blocker из-за deadline.

## 5. Audit владельца поведения и парадигмы реализации

В текущем drafting новый runtime-алгоритм или публичный production API не создаётся. Поэтому для самого создания плана
audit имеет статус `not applicable`; при этом границы будущего поведения зафиксированы, чтобы probe не стал скрытым
владельцем runtime-семантики:

| Поведение | Владелец | Scoped dependencies и lifecycle | Что probe не имеет права делать |
|---|---|---|---|
| Текст → PCM streaming и candidate-specific stop | будущий `TTS adapter/capability` | Одобренный candidate runtime, text input, cancellation handle и output channel конкретной проверки | Менять FSM, SIP state или выбирать другой candidate |
| Отмена, закрытие playback и жизненный цикл канала | `Main Dispatcher / Dialogue FSM` в сквозной системе | Поколение/канал разговора, cancel command и idempotent close; payload не проходит через Dispatcher | Прятать отмену в helper-е и считать закрытие локального буфера полным FSM-событием |
| PCM → PCMU media conversion | `Media egress`/media boundary | Формат PCM, 8 kHz mono, bounded frame и codec boundary | Добавлять новый codec/runtime или выдавать candidate output за RTP proof |
| Candidate probe | Временная диагностическая side-facade, не production owner | Только manifest, clean process, in-memory buffer и evidence sink | Становиться новым adapter, IPC protocol, compatibility path или источником SIP-команд |

Свободные функции допускаются здесь только как локальные pure helpers для разбора metadata/evidence; они не меняют
состояние SIP, FSM, channel, generation или transfer outcome. Если будущая реализация probe выходит за эту границу,
работа останавливается по unexpected gap protocol.

## 6. Owner-review решения

Execution stage открывается после review child plan и закрытия upstream dependencies. Рабочие решения ниже принимаются
внутри execution и фиксируются в evidence; они не являются предварительным опросником владельца.

| ID | Вопрос | Решение сейчас | Последствие для реализации | Статус |
|---|---|---|---|---|
| `C4-OR-001` | Как выбрать primary TTS? | C4-S0 выбирает один доступный stable/local кандидат и фиксирует name/version/source в manifest | Только выбранный кандидат допускается к S1–S4; fallback после failure требует owner decision | `resolved as execution task` |
| `C4-OR-002` | Какой voice/model asset и license использовать? | C4-S0 находит локально доступный asset с разрешённым demo-use и фиксирует provenance/license | Asset не копируется и не публикуется молча; отсутствие разрешённого asset — blocker | `resolved as execution task` |
| `C4-OR-003` | В каком runtime lane кандидат проверяется? | Latest stable free-threaded CPython >= 3.14; для проверенного main-process пути обязательны три candidate-specific no-GIL patch-а, описанные в `patch-build.md` | GIL fail не запускает fallback; isolation не выбирается автоматически | `resolved by tested patched path` |
| `C4-OR-004` | Где разработать PCM→PCMU media boundary? | В C4-S3 и отдельной VoIP test-stand map; конкретная реализация определяется задачей | Если boundary не удаётся доказать, фиксируется gap; converter не добавляется молча | `resolved as execution task` |
| `C4-OR-005` | Какой cancellation result достаточен для primary smoke? | Observable cancel, завершение выдачи и отсутствие stale PCM; фактические timestamps записываются | Зависание/пост-cancel output — failure; отдельный numerical threshold не нужен | `resolved as execution task` |
| `C4-OR-006` | Разрешено ли после failure проверить второй кандидат? | Только после отдельного owner discussion и нового/обновлённого plan; автоматически — нет | Текущий C4 завершается `fail`/`blocked`, не fallback | `resolved policy; fallback owner-gated` |
| `C4-OR-007` | Нужно ли обновить ADR/technical docs после результата? | Только если результат меняет принадлежащий документ факт; не в текущем write-set | Отдельный docs sync и registry audit, без изменения этого плана задним числом | `resolved process boundary` |

## 7. Process invariant audit

| Инвариант | Проверка в этом плане | Статус до execution |
|---|---|---|
| Срез узкий и имеет наблюдаемый результат | Четыре связанные acceptance boundaries одного TTS-кандидата; SIP/LLM/ASR не включены | `pass` |
| Planning и execution не смешаны | Явно указано, что создание файла не является исполнением; commands только templates | `pass` |
| Релевантные и нерелевантные проверки разделены | Import/no-GIL, first PCM, PCMU boundary и cancellation — relevant; full call/BYE/transfer — out-of-scope | `pass` |
| Авторитетная среда выбрана | Ubuntu/WSL2 + latest stable free-threaded CPython >= 3.14; Docker только для назначенного peer lane | `pass` |
| Требования не дублируются без owner-ссылки | Таблица содержит краткое правило и ссылку на owner-документ | `pass` |
| Документы-владельцы не изменяются молча | Все возможные updates вынесены в отдельный docs sync; текущий write-set ограничен plan-file | `pass` |
| Registry/backlog audit выполняется после соответствующего изменения | В текущей операции `document-registry`, `task-backlog` и `roadmap` не меняются; audit не объявляется пройденным | `not run by scope` |
| Fallback/compatibility/simplification явно разрешены и имеют место закрытия | Fallback запрещён автоматически; isolation и новый converter имеют owner-gated места закрытия | `pass` |
| Production-ready свойства не объявляются | Результат — feasibility evidence, не MVP/prod readiness | `pass` |
| Deferred evidence не скрывается skip/xfail | Тесты сейчас не создаются; отдельная conformance ниже имеет `not applicable` | `pass` |
| Команды воспроизводимы и фиксируют версии/stdout/stderr/exit code | Командные шаблоны дополнены фактическими командами и records в `commands.md` | `resolved by commands/evidence` |
| Closeout фиксирует pre-existing и out-of-scope findings | Фактические ограничения и out-of-scope findings зафиксированы в `closeout.md` | `resolved by closeout` |

## 8. Architecture invariant audit

| Инвариант | Применение к C4 | Статус |
|---|---|---|
| Dispatcher владеет control plane и Dialogue FSM | Probe не меняет FSM; cancellation в production остаётся Dispatcher-owned | `preserved; not executed` |
| SIP/media callbacks не ждут TTS и немедленно обрабатывают BYE | Full SIP/BYE не входит в C4; probe не создаёт callback path и не делает blocking SIP call | `preserved; evidence deferred to C1/media plan` |
| Аудио и текстовый payload идут по data plane | PCM проверяется в локальном output channel, не через Dispatcher | `preserved; boundary evidence pass` |
| Закрытый канал отбрасывает stale producer и не переиспользуется | Cancellation slice требует close и post-close stale-output assertion | `pass with candidate cancel limitation` |
| Только authoritative final ASR result разрешает TTS | В C4 входной текст — заранее одобренная короткая тестовая фраза; speculative ASR path отсутствует | `preserved; not full-pipeline evidence` |
| Speculative pipeline не запускает TTS | Speculative path не создаётся и не проверяется в C4 | `not applicable to probe` |
| TTS playback отменяется при barge-in, новый ответ не смешивается | Проверяется локальный cancel/close boundary; реальный barge-in — отдельный integration slice | `partial; local evidence pass` |
| LLM не получает произвольный SIP-доступ | LLM не запускается; probe не имеет SIP commands | `preserved` |
| SIP/media MVP — PCMU | Target boundary фиксирован как PCMU 8 kHz mono | `pass for local boundary; RTP not tested` |
| Конфигурация не подменяется скрытыми defaults | Candidate/runtime/format не угадываются; manifest и explicit args обязательны | `preserved` |
| Free-threaded CPython и native isolation | Import/no-GIL проверка обязательна; isolation не выбирается автоматически | `pass for patched main-process path; no isolation introduced` |
| Нет реальных внешних сервисов и записи аудио | Probe локальный; raw PCM не сохраняется; SIP/PBX не подключаются | `preserved` |
| Lifecycle имеет владельца, отмену и повторное закрытие | Cancellation slice проверяет idempotent close в узком output channel | `pass with explicit native-cancel limitation` |

## 9. Узкие implementation slices

Срезы ниже задают approved execution boundary. Фактические результаты исполненных срезов и их ограничения
зафиксированы в [`closeout.md`](../../artifacts/feasibility/001-C4-tts-primary/closeout.md); новые production-изменения
этим closeout не вводятся.

### C4-S0 — Candidate selection и manifest

**Цель и границы:** выбрать ровно одного доступного stable/local primary TTS-кандидата и зафиксировать его фактическую
версию/commit, источник, license,
voice/model asset, runtime lane и разрешённый способ вызова. Это administrative gate, не runtime smoke.

**Write-set:** `manifest.json` и `asset-manifest.json` в C4 evidence root.

**Acceptance:** manifest однозначен; отсутствуют второй кандидат и fallback
команда; prerequisites `001-B`/`001-C` имеют evidence или явно открытые blocker IDs.

**Stop conditions:** execution не определил имя/версию; источник или license не подтверждены; кандидат требует cloud API,
неразрешённую voice asset или непредусмотренный native runtime.

**Релевантная проверка:** execution selection и проверка manifest; runtime candidate operation на этом slice не запускается.

**Синхронизация:** результат может стать входом в `ADR-002` только отдельным owner-approved docs sync; этот slice не
меняет ADR, roadmap, backlog или registry.

**Следующий slice:** только при acceptance — `C4-S1`.

### C4-S1 — Import и no-GIL после lazy import

**Цель и границы:** проверить candidate direct imports, критичные транзитивные/lazy imports и минимальную инициализацию
в чистом latest stable free-threaded CPython >= 3.14. Не проверять качество синтеза и не строить production adapter.

**Write-set:** `tools/feasibility/tts_primary_probe.py`, `import.json` и связанные command stdout/stderr records;
другие source/test/config paths запрещены.

**Последовательность:**

1. Запустить clean process целевым latest stable free-threaded CPython и записать `Py_GIL_DISABLED` и архитектуру.
2. Проверить `sys._is_gil_enabled()` до candidate imports.
3. Импортировать только manifest-listed direct/critical modules и после каждого шага записать GIL state.
4. Выполнить предусмотренный lazy import/initialization path и снова проверить GIL.
5. Записать stderr, включая предупреждения об автоматическом включении GIL, stdout и exit code.

**Acceptance:** `Py_GIL_DISABLED == 1`; GIL отключён до/после каждого импорта и инициализации; candidate import не
имеет непредусмотренных side effects; manifest, runtime version, module list, stdout/stderr и exit code сохранены.

**Stop conditions:** отсутствует `001-B` runtime evidence; import включает GIL; native module не импортируется в baseline;
обнаружен скрытый network/API call; отсутствует reproducible command.

**Релевантная проверка:** no-GIL/import evidence. Полный operation smoke переносится в `C4-S2`.

**Синхронизация:** при GIL failure не менять ADR-003 молча; записать blocker и передать owner decision.

**Следующий slice:** только при acceptance — `C4-S2`.

### C4-S2 — Короткий русский ответ и первый PCM-фрагмент

**Цель и границы:** после успешного S1 выполнить одну короткую локальную операцию синтеза с фиксированным русским
входом, получить первый непустой PCM-фрагмент и зафиксировать его metadata. Полный playback/RTP и субъективная оценка
голоса не входят.

**Write-set:** `operation.json`, `tts-sample.wav` и in-memory buffer probe; отдельный raw PCM dump не создаётся.

**Последовательность:**

1. Подать заранее заданную короткую русскую фразу без Markdown/служебных инструкций.
2. Зафиксировать время начала operation и время первого непустого PCM-fragment.
3. Записать sample format, sample rate, channels, byte count, frame/sample count, duration и digest фрагмента.
4. Собрать полный результат этой короткой операции и сохранить его как `tts-sample.wav` в формате WAV с PCM payload,
   пригодным для ручного прослушивания. Это диагностический synthetic sample, а не запись разговора.
5. Зафиксировать для файла metadata WAV/PCM, duration, byte/sample count и digest в `operation.json`; исходный raw PCM
   dump отдельно не сохранять.

**Acceptance:** operation завершается с наблюдаемым результатом; первый fragment непустой и является PCM; metadata
полны и согласованы между собой; `tts-sample.wav` существует, непуст и соответствует полному результату именно этой
операции; ответ не требует внешнего сервиса; результат не выдан за end-to-end SIP evidence.

**Stop conditions:** нет русского output; нет первого непустого фрагмента; формат не определён; candidate operation
зависает; результат получен только через незафиксированный fallback или внешний API.

**Релевантная проверка:** first-fragment operation evidence и TTS-local latency. End-to-end latency не проверяется.

**Синхронизация:** если фактический формат противоречит technical/architecture contract, остановиться и открыть gap вместо
изменения документов или добавления converter-а.

**Следующий slice:** только при acceptance — `C4-S3` и `C4-S4` в указанном порядке.

### C4-S3 — PCMU-compatible conversion boundary

**Цель и границы:** проверить только media-format boundary `PCM S16LE mono 8 kHz → PCMU 8 kHz mono` для fragment из S2.
Не строить SIP/RTP transport, не менять media architecture и не вводить новый codec dependency.

**Write-set:** `pcmu-boundary.json` и локальный boundary invocation; SIP/RTP test stand этим срезом не подменяется.

**Последовательность:**

1. Проверить, что входной fragment имеет целевой PCM metadata либо записать фактическое отклонение.
2. Передать его через media boundary, разработанную в C4/test-stand execution.
3. Зафиксировать output codec, sample rate, channels, byte/frame count, exit code и диагностические сообщения.
4. Если boundary поддерживает decode/round-trip check, проверить число samples и отсутствие явного corruption; точное
   waveform equality не требовать от lossy PCMU.

**Acceptance:** есть воспроизводимое доказательство non-empty PCMU 8 kHz mono output из PCM fragment либо явное
доказательство, что кандидат требует отдельного conversion step. Второй вариант не является `pass`: он создаёт
`blocked`/`fail` и gap для следующей engineering-задачи.

**Stop conditions:** отсутствует разработанная boundary; требуется новый пакет/codec adapter; sample rate/channel mapping
неоднозначны; conversion делает скрытый resampling или clipping без metadata; результат выдан за RTP loopback.

**Релевантная проверка:** PCMU-compatible format evidence. SIP/RTP, packet timing и network loopback — out-of-scope.

**Синхронизация:** новый converter, dependency или format exception требуют отдельного owner review и, при необходимости,
ADR/child plan; текущий C4 их не вводит.

**Следующий slice:** при acceptance — `C4-S4`; при boundary gap — closeout только с `blocked`/`fail` и owner action.

### C4-S4 — Cancellation и stale PCM suppression

**Цель и границы:** после появления первого фрагмента запросить cancellation до естественного окончания выдачи,
закрыть узкий output channel и проверить отсутствие stale PCM после close. Реальный barge-in, RTP и FSM не создаются.

**Write-set:** `cancellation.json` и in-memory channel/probe state.

**Последовательность:**

1. Начать streaming operation и дождаться первого непустого fragment.
2. Отправить explicit cancel через candidate-supported mechanism.
3. Зафиксировать cancel request, stop/return event, elapsed time, stdout/stderr и exit code.
4. Идемпотентно закрыть output channel и проверить, что post-close writes не доставляются consumer.
5. Убедиться, что новый output не смешан с отменённым fragment и что повторное закрытие не ломает probe.

**Acceptance:** cancellation observable; candidate operation прекращает выдачу или возвращает documented cancellation
result; channel close идемпотентен; stale PCM после close не доставляется; сохранённый `tts-sample.wav` относится к
завершённому до cancellation успешному sample и не пополняется stale PCM после закрытия канала.

**Stop conditions:** candidate не поддерживает cancel; cancel блокирует probe без конечного результата; после close приходит
доставленный stale output; для исправления требуется скрытый worker, новый IPC или fallback.

**Релевантная проверка:** local cancellation/channel evidence. Полная barge-in интеграция — отдельный future slice.

**Синхронизация:** отсутствие cancellation не маскировать новым кандидатом; передать owner decision и сохранить `fail`/
`blocked`.

**Следующий slice:** при acceptance — C4 closeout и передача результата в `001-D`; иначе — owner review.

## 10. Отдельный blocker register

Статус ниже относится к моменту создания child plan. Красный или необъяснённый результат блокирует только зависимый
slice, пока владелец не примет решение. Ни один blocker не закрывается выбором fallback внутри этого плана.

| ID | Срез | Проверяемый триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-C4-001` | `C4-S0` | Execution не выбрал и не зафиксировал один stable/local primary TTS candidate | Вся candidate-specific execution | executor | `C4-OR-001`, execution `manifest.json` | `open on trigger` |
| `B-C4-002` | `C4-S1` | Map prerequisite `001-B` не дал воспроизводимый stable free-threaded CPython >= 3.14 | Import/no-GIL и все dependent operation slices | project owner | Parent runtime evidence `runtime-probe.json` | `open` |
| `B-C4-003` | `C4-S1`/closeout | После candidate GIL failure не принято решение main process vs отдельная isolation | Candidate baseline decision и переход в `001-D` | project owner | ADR-003 review + отдельный plan/IPC decision | `open; owner-gated` |
| `B-C4-004` | `C4-S3` | Не удалось разработать PCM→PCMU media boundary или нужен новый converter/dependency | PCMU compatibility acceptance | executor | `pcmu-boundary.json` или unexpected-gap record | `open on trigger` |
| `B-C4-005` | `C4-S4` | Candidate не возвращает конечный cancel result или observation contract не реализуем | Cancellation acceptance и candidate decision | executor | `C4-OR-005`, `cancellation.json` | `open on trigger` |
| `B-C4-006` | `C4-S2`/`C4-S3` | Candidate output не PCM S16LE mono 8 kHz и boundary gap не закрыт | First PCM → PCMU boundary | project owner | `operation.json`, `pcmu-boundary.json` | `open on trigger` |
| `B-C4-007` | `C4-S1`/`C4-S2` | Map environment/runtime/native prerequisites или target local asset unavailable | Reproducible import/operation evidence | project owner | `001-A`/`001-B`/`001-C` evidence and manifest | `open on trigger` |
| `B-C4-008` | любой | Probe требует внешний API, скрытый compatibility path, audio recording или package install для обхода gap | Весь C4 и следующий candidate gate | project owner | stdout/stderr + unexpected-gap record | `open on trigger` |

Если после owner review конкретный slice действительно не имеет blocker, его register не удаляется: добавляется явная
строка `none` с evidence и датой решения.

Таблица выше сохраняет initial blocker state плана. Для исполненного C4 актуальные resolution находятся в
[`closeout.md`](../../artifacts/feasibility/001-C4-tts-primary/closeout.md): `B-C4-003`, `B-C4-004`, `B-C4-006` и
`B-C4-007` закрыты для проверенного пути; `B-C4-005` закрыт с явно зафиксированным ограничением отсутствия native
cancel token; `B-C4-008` не сработал. Автоматический fallback не запускался.

## 11. Test plan и evidence

### 11.1. Релевантные проверки

| Evidence ID | Проверка | Ожидаемый факт | Где сохраняется |
|---|---|---|---|
| `E-C4-IMPORT-001` | Clean import/no-GIL | `Py_GIL_DISABLED == 1`; `sys._is_gil_enabled() == False` до/после direct, lazy import и init; нет GIL warning | `import.json` |
| `E-C4-PCM-001` | Короткий русский operation | Один локальный ответ даёт первый непустой PCM fragment; metadata полна | `operation.json` |
| `E-C4-PCMU-001` | PCM→PCMU boundary | Наблюдаемая совместимость с PCMU 8 kHz mono или explicit gap; без RTP claim | `pcmu-boundary.json` |
| `E-C4-CANCEL-001` | Cancel после первого fragment | Candidate stop/return observable; output channel close идемпотентен; stale PCM не доставляется | `cancellation.json` |
| `E-C4-LATENCY-001` | Локальная first-fragment timing | Зафиксировано время operation start → first PCM; это не end-to-end SLA | `operation.json` |
| `E-C4-AUDIO-001` | Прослушиваемый TTS sample | Полный короткий synthetic TTS-ответ сохранён в `tts-sample.wav`; формат и digest совпадают с `operation.json`; это не запись разговора | `tts-sample.wav`, `operation.json` |

### 11.2. Командные шаблоны и фактические execution records

Ниже сохранён шаблон запуска для повторения candidate-specific проверки. Фактические команды, runtime и records
исполненного C4 находятся в [`commands.md`](../../artifacts/feasibility/001-C4-tts-primary/commands.md) и
`patch-build.md`; `<SELECTED_FREE_THREADED_CPYTHON>` и `<EXECUTION_MANIFEST>` не являются фактическими значениями.

```text
<SELECTED_FREE_THREADED_CPYTHON> tools/feasibility/tts_primary_probe.py \
  --manifest <EXECUTION_MANIFEST> --stage import \
  > artifacts/feasibility/001-C4-tts-primary/import.stdout.txt \
  2> artifacts/feasibility/001-C4-tts-primary/import.stderr.txt

<SELECTED_FREE_THREADED_CPYTHON> tools/feasibility/tts_primary_probe.py \
  --manifest <EXECUTION_MANIFEST> --stage operation

<SELECTED_FREE_THREADED_CPYTHON> tools/feasibility/tts_primary_probe.py \
  --manifest <EXECUTION_MANIFEST> --stage pcmu-boundary

<SELECTED_FREE_THREADED_CPYTHON> tools/feasibility/tts_primary_probe.py \
  --manifest <EXECUTION_MANIFEST> --stage cancellation
```

Для каждого повторного запуска сохраняются exact command, runtime identity, candidate manifest, stdout, stderr, exit
code, дата, host/WSL context и stage status. Если команда требует непатченный runtime, второй candidate или новый
неодобренный compatibility path, она останавливается и становится blocker.

### 11.3. Не относящиеся к C4 проверки

Unit/state-machine, полный SIP/RTP, BYE во время TTS, barge-in от реального RTP, transfer, ASR/LLM context, VRAM
смешанной модели и full end-to-end latency не являются acceptance этого child plan. Они остаются в родительской карте,
`001-C1`, `001-D` или последующих media/integration plans и не должны быть отмечены этим evidence как выполненные.

### 11.4. Deferred evidence conformance

Для этого child plan: `not applicable`.

В рамках текущей задачи тесты и regression selectors не создаются; нет ожидаемо красного теста, который нужно было бы
скрывать через `skip`/`xfail`. Будущий candidate probe является одноразовым feasibility evidence, а не deferred test
gate. Открытые blockers выше — это owner-gated решения, а не deferred evidence.

Если отдельная будущая задача создаст тест, который должен оставаться красным до corrective work, до его создания нужно
отдельно зафиксировать стабильный `evidence_id`, связанный с `TASK-NNN` или roadmap scope, owner, принимающий документ,
команду deferred-прогона, stdout/stderr/exit code и условие promotion. Локальные безымянные `skip`/`xfail` запрещены.

## 12. Legacy/fallback/simplification register

| ID | Категория | Что разрешено/введено | Ограничение и причина | Где закрывается | Статус |
|---|---|---|---|---|---|
| `C4-LEGACY-001` | Legacy path | Ничего | Production legacy helper или tests-only helper не создаётся ради probe | Не применимо | `none` |
| `C4-FB-001` | Fallback | Второй TTS-кандидат не запускается автоматически | После primary failure нужен owner discussion и отдельный plan/decision | Owner review / новый child plan | `owner-gated; not introduced` |
| `C4-FB-002` | Compatibility/isolation | Process isolation не выбирается автоматически при GIL failure | Нужны owner decision, явный IPC contract и отдельный acceptance | `001-D` или новый plan/ADR | `policy only; not introduced` |
| `C4-SIM-001` | Simplification | Проверка только одного короткого русского ответа без полного call | Это граница component feasibility, не claim полного MVP-flow | `001-D`/media plan для integration | `approved scope boundary` |
| `C4-SIM-002` | Simplification | Отдельный raw PCM dump не сохраняется; сохраняется один прослушиваемый WAV sample и metadata/digest | Соблюдается запрет на запись разговора; synthetic TTS result доступен для ручной проверки | `operation.json`, `tts-sample.wav` | `approved scope boundary` |
| `C4-SIM-003` | Compatibility path | Новый converter или скрытый resampling не добавляется | Format gap должен быть виден и передан владельцу | Unexpected gap protocol | `not introduced` |

Ни одна строка этого реестра не превращает красный результат в зелёный. Особенно `C4-FB-001` и `C4-FB-002` не являются
командами для автоматического продолжения.

## 13. Протокол неожиданного gap

При обнаружении неучтённого архитектурного, runtime, media-format, license или lifecycle gap зависимый slice немедленно
останавливается. Executor заполняет запись по форме:

```text
Gap ID:
Обнаруженный gap:
Затронутые документы и компоненты:
Фактическая команда, версия, stdout/stderr и exit code:
Почему текущий plan нельзя продолжать:
Какой protected baseline или invariant затронут:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется:
Владелец решения:
Нужен ли новый ADR/roadmap/plan-file:
Какой evidence должен закрыть gap:
Условие возобновления:
```

Типовые triggers для C4: точное имя кандидата отсутствует; native import включает GIL; output не имеет однозначного
PCM metadata; отсутствует разработанная PCM→PCMU boundary; cancellation требует нового IPC/adapter; candidate делает
внешний вызов; предлагается второй кандидат; нужно сохранять raw audio; package install требуется для обхода failure.

До owner review запрещено вводить adapter, facade, fallback, compatibility bridge, новый IPC, скрытый startup-only
path, undocumented resampling или изменение acceptance. Gap не закрывается сроком, переименованием failure или
ослаблением assertion.

## 14. Execution report и closeout template

Ниже сохранён шаблон для будущего повторного исполнения. Текущий фактический результат уже заполнен в
[`closeout.md`](../../artifacts/feasibility/001-C4-tts-primary/closeout.md), который является авторитетным closeout
для этого плана; статус исполнения плана — `complete`, candidate decision — `pass`.

```text
Plan: 001-C4
Уровень: child plan
Родитель: Map-001
Owner review дата/решение:
Execution start/end:
Статус исполнения child plan: complete | blocked
Candidate decision: pass | pass_with_isolation | fail
Подтверждённый primary TTS name/version/commit:
Источник, license и voice/model provenance:
Runtime/version/WSL host:
Изменённые файлы:
  - план:
  - разрешённый probe:
  - evidence root:
Запрещённые/неизменённые файлы подтверждены:

Срез C4-S0 manifest:
  Решение и evidence:
Срез C4-S1 import/no-GIL:
  Py_GIL_DISABLED:
  GIL до/после imports/init/operation:
  stderr warning:
  Команда и exit code:
Срез C4-S2 first PCM:
  Русский input:
  first fragment timestamp/bytes/duration:
  PCM format/sample rate/channels:
  Прослушиваемый TTS sample:
    path: artifacts/feasibility/001-C4-tts-primary/tts-sample.wav
    format/sample rate/channels/duration/bytes/digest:
  Отдельный raw PCM dump сохранён: нет:
Срез C4-S3 PCMU boundary:
  PCM input:
  PCMU output metadata:
  Boundary command/exit code:
  Gap:
Срез C4-S4 cancellation:
  cancel request/stop event/elapsed time:
  channel close idempotency:
  stale output after close:
  Команда и exit code:

Открытые blockers и owner decisions:
Pre-existing failures:
Out-of-scope findings:
Deferred evidence: not applicable | список с evidence_id:
Изменённые owner-документы: none | отдельный docs sync:
Результат registry audit: не выполнялся в drafting | команда/результат execution:
Результат backlog audit: не выполнялся; backlog не изменён | команда/результат execution:
Новый baseline для 001-D:
Следующий узкий шаг:
```

Closeout не может объявить C4 закрытым, если exact primary candidate не указан, импорт/no-GIL evidence отсутствует,
первый PCM или PCMU boundary не доказаны, cancellation не проверена, либо open blocker скрыт. Если candidate fail-ит
и owner не разрешил isolation/замену, closeout фиксируется как `fail` или `blocked` с concrete owner action.
