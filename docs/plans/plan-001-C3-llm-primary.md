# Plan-001-C3: Проверка primary LLM Qwen3.5-9B в 4-bit

Уровень: `child plan`  
Статус исполнения: `complete`  
Candidate decision: `pass_with_isolation`  
Родительская карта: [`Map-001`](plan-001-deadline-feasibility.md)  
Родительская roadmap: [`roadmap.md`](../roadmap.md)  
Идентификатор среза: `001-C3`  

План исполнен. GPU-evidence и итоговая классификация находятся в [C3 closeout](../../artifacts/feasibility/001-C3-llm-primary/closeout.md).
Итоговая граница — `pass_with_isolation`: native inference runtime работает в отдельном локальном процессе, а основной
no-GIL-процесс обращается к нему через существующий HTTP IPC на `127.0.0.1`.

## 1. Цель и результат

Проверить единственного primary-кандидата ADR-002 — **Qwen3.5-9B в 4-битной квантизации** — на целевой локальной
конфигурации, не меняя архитектурный baseline. Фактические backend/version details выбираются и фиксируются в execution.

Проверка должна дать один из явно различимых результатов:

- `pass` — импорт и минимальная операция проходят в основном latest stable free-threaded CPython >= 3.14 процессе без включения GIL, модель
  загружается в 4-bit, один русский вопрос по естественным наукам даёт допустимое структурированное решение,
  измерены VRAM и время до первого полезного токена/ответа, отмена генерации подтверждена;
- `pass_with_isolation` — результат получен только через заранее согласованную process isolation boundary, при этом
  native inference runtime не импортируется в основной no-GIL-процесс; решение об isolation и её IPC-контракте должно
  быть owner-approved и не появляется молча в этом срезе;
- `fail` — обязательная проверка не пройдена, либо данных недостаточно для baseline decision;
- `blocked` — проверку нельзя безопасно начать или закрыть из-за открытого owner decision/dependency blocker.

Минимальный результат closeout — evidence root с зафиксированными model id и revision, runtime/backend и вариантом
квантизации, import/no-GIL probe, structured decision, VRAM, `first useful token`/`first useful response`, задержкой
от получения финальной пользовательской фразы до первого полезного вывода и до первого валидного ответа, cancellation
и явным решением `main process` или `isolation gap`. Ни один из этих результатов сам по себе не означает готовность
полного SIP-бота или production-ready свойства.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan самодостаточен: scope, source-map, owner review, invariants, slices, blockers, evidence и closeout обязательны | Этот файл содержит полный APG-контракт и не подменяет Map-001 | Структурный review файла и отдельный closeout | Отсутствует обязательный раздел или смешаны map/child-plan claims |
| [`plan-001-deadline-feasibility.md`](plan-001-deadline-feasibility.md) | `001-C3` зависит от `001-B` и `001-C`; один AI-кандидат проверяется минимальным наблюдаемым сценарием; fallback не запускается автоматически | Не вести общий benchmark и не переходить к другой модели при первом сбое | Проверить upstream gates и child evidence root | Нет CPython/no-GIL baseline или candidate evidence |
| [`requirements.md`](../requirements.md) | LLM локальная, русский диалог, короткий ответ; внешний API и аудиозапись не входят в MVP | Один локальный русский natural-science fixture; без SIP, внешних API и записи аудио | Prompt/output audit и dependency inventory | Запуск требует внешнего inference API или сохраняет аудио |
| [`architecture.md`](../architecture.md) | Dispatcher владеет control plane; LLM выдаёт structured input; payload не проходит через Dispatcher; финальное действие нельзя получить из speculative результата | В этом срезе нет SIP/FSM side effect, TTS и speculative pipeline | Architecture invariant audit и отсутствие запрещённых write-set | Модель получает SIP-доступ или provisional output разрешает действие |
| [`technical-specification.md`](../technical-specification.md) | Baseline — Ubuntu 24.04 LTS x86_64/latest stable free-threaded CPython >= 3.14, GPU до 16 ГБ, локальный LLM, JSON action contract | Все измерения привязаны к этому runtime и фиксируют memory/latency state | Runtime probe, schema validation и VRAM evidence | Использован другой основной runtime либо нарушен JSON-контракт |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM не управляет SIP; возвращает ограниченное действие и текст, Dialogue Manager валидирует решение | Ожидается `action=answer` и непустой русский `text`; SIP target не моделируется | JSON/schema и boundary audit | Свободный текст или произвольная команда принимается как действие |
| [`ADR-002`](../decisions/ADR-002-llm-model-selection.md) | Qwen3.5-9B 4-bit — основной кандидат; thinking по умолчанию не используется; финальный ASR, а не speculative text, является authoritative | Проверяется только Qwen3.5-9B 4-bit в non-thinking/instruct режиме; backend details фиксируются execution, альтернативы не запускаются этим планом | Candidate identity, prompt mode и one-question evidence | Модель/квантизация изменены без зафиксированного execution finding или speculative path выдан за baseline |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | После каждого критичного import/lazy operation `sys._is_gil_enabled()` остаётся `False`; incompatible native component — только explicit process isolation | Проверяется import, lazy load и минимальный inference operation, а не только имя wheel/runtime | `Py_GIL_DISABLED`, GIL state, warnings и operation evidence | GIL включился в main process без согласованной isolation |

## 3. Граница задачи

```text
Цель:
  Закрыть узкую LLM feasibility-проверку primary Qwen3.5-9B в 4-bit.

Входит:
  - выбор и проверка доступного стабильного inference backend в чистом latest stable free-threaded CPython;
  - import/no-GIL probe до import, после критичных import, после lazy model load и после операции;
  - загрузка Qwen3.5-9B в 4-bit на RTX 5060 Ti с фактическим измерением VRAM;
  - один фиксированный русский вопрос по естественным наукам;
  - проверка ограниченного structured decision: action=answer и непустой русский text;
  - измерение времени от приёма authoritative final user turn до первого непустого output chunk/token и до первого
    валидного response; дополнительно сохраняется время от фактического старта model request;
  - отдельная отмена активной генерации и проверка отсутствия stale result;
  - сохранение command/version/exit-code/stdout/stderr и closeout evidence.

Не входит:
  - Qwen3.5-4B, Qwen3-8B, Vikhr, Qwen3.6/Qwen3.8, Gemma и любые другие модели;
  - speculative LLM/retrieval, provisional ASR, prompt/KV-cache optimization;
  - ASR, TTS, SIP/RTP, Dispatcher, Dialogue FSM, transfer/hangup, barge-in playback и полный end-to-end звонок;
  - совместный VRAM benchmark ASR+LLM+TTS и утверждение полного GPU baseline;
  - реализация нового inference adapter, нового IPC protocol, нового runtime или изменение config/constants.py;
  - product-code changes вне evidence root; подготовка execution dependencies и загрузка model artifact относятся к
    execution evidence, а не к реализации продукта этим child plan;
  - изменение requirements, architecture, technical specification, ADR, roadmap, task-backlog или document-registry.

Protected baseline:
  Latest stable free-threaded CPython >= 3.14 в Ubuntu 24.04 LTS x86_64/WSL2 остаётся основным runtime.
  Компонент, включающий GIL в основном процессе, не принимается как main-process baseline.
  LLM не получает SIP-доступ; structured decision не исполняется этим срезом.
  Один локальный разговор, PCMU, отсутствие внешних inference API и отсутствие записи аудио не ослабляются.
  Deadline не разрешает молчаливый fallback, снижение assertion или изменение acceptance.

Предположения о dirty worktree:
  На drafting-входе git status --short был не пуст: присутствовали pre-existing изменения/untracked в .idea/,
  .codex/, artifacts/, docs/ и tools/. Эти изменения принадлежат рабочему дереву и защищены. Перед execution
  повторно сохранить git status --short; не выполнять clean/reset/checkout и не смешивать unrelated diff.
   В execution фактический write-set ограничен evidence root C3. Синхронизация owner-документов после owner decision
   выполняется отдельным документным изменением и не является скрытым результатом GPU probe.

Зависимости и внешние сервисы:
  - закрытый upstream baseline `001-A`/`001-B` и карта кандидатов `001-C`;
  - Ubuntu/WSL2, RTX 5060 Ti и доступные 16 ГБ VRAM;
  - локальный model artifact Qwen3.5-9B с фактически выбранным revision и проверенной лицензией;
  - доступный локальный inference backend; его версия, quantization implementation и cancellation API выясняются execution;
  - внешние inference API, реальный PBX и оператор запрещены; получение недостающих пакетов/весов допустимо только как
    явно зафиксированная часть execution и не может скрываться внутри smoke-команды.
```

Фиксированный вопрос для всех запусков этого плана:

> `Почему небо днём кажется голубым?`

Повторное использование этого же вопроса в cancellation-сценарии не создаёт второй предметный тест. Срез проверяет
контракт и эксплуатационные свойства кандидата, а не полноценную оценку научной корректности, RAG или качества
русского диалога на наборе вопросов.

## 4. Source-map, write-set и запрещённые изменения

| Область | Файл или компонент | Текущее состояние | Целевое состояние | Gap | Действие и допустимый write-set |
|---|---|---|---|---|---|
| Plan contract | `docs/plans/plan-001-C3-llm-primary.md` | Child plan исполнен | Self-contained child plan со статусом исполнения `complete`; candidate decision `pass_with_isolation` | Boundary и evidence должны оставаться синхронизированными | Изменять plan только при повторном execution/review |
| Python/no-GIL | Latest stable free-threaded CPython >= 3.14, основной процесс | Baseline задан ADR-003, фактический C3 probe отсутствует | GIL disabled до/после critical imports, lazy load и операции | Backend может автоматически включить GIL | В execution только read/execute probe и evidence; исходный runtime не менять |
| LLM artifact | Локальный Qwen3.5-9B, 4-bit | Primary рекомендован ADR-002, revision и backend не закреплены | Execution фиксирует model id, revision, quantization и load parameters | Нет воспроизводимого artifact или лицензии | Получить/проверить локальный artifact в рамках execution; не менять model cache молча |
| Inference boundary | Локальный Ollama native server | Ollama 0.33.1 и HTTP IPC over `127.0.0.1` зафиксированы в C3 evidence | Import/main-process boundary, inference и cancel имеют наблюдаемый boundary | Жёсткая native cancellation не подтверждается отдельным ack | Использовать существующий HTTP IPC; не создавать новый IPC в рамках C3 |
| One-question fixture | Evidence root `artifacts/feasibility/001-C3-llm-primary/` | Evidence отсутствует | Сохранены prompt, schema и exact question | Нет command/output provenance | В execution разрешено создать `question.txt`, `prompt.json` и result evidence только в этом root |
| Import evidence | Тот же evidence root | Нет probe | `import-probe.json`, stdout/stderr, exit code и GIL state по стадиям | Нет фактического import/operation result | В execution разрешено писать только перечисленные evidence-файлы |
| Inference/VRAM/cancel evidence | Тот же evidence root | Нет measurements | `inference.json`, `vram.json`, `cancellation.json`, `measurements.md`, `closeout.md` | Нет pass/fail decision | В execution разрешены эти evidence-файлы; тестовый код и product code не входят в write-set |
| SIP/data plane | Dispatcher, Dialogue FSM, SIP/RTP, TTS/ASR | Не затрагиваются C3 | Границы сохранены без изменений | Полный integration результат отсутствует | Не менять и не создавать файлы/каналы этих компонентов |

### 4.1. Write-set

Фактический write-set этой сессии: только `docs/plans/plan-001-C3-llm-primary.md`.

У будущего execution stage, после review child plan и закрытия upstream gates, допустим только следующий evidence write-set:

```text
artifacts/feasibility/001-C3-llm-primary/
  question.txt
  prompt.json
  import-probe.json
  inference.json
  vram.json
  cancellation.json
  measurements.md
  stdout.log
  stderr.log
  closeout.md
```

Создание нового probe script, test fixture вне этого root, inference adapter, IPC facade или конфигурационного ключа
требует unexpected gap protocol и отдельного owner-approved plan.

### 4.2. Запрещённые изменения

- любые файлы, кроме указанного plan-file в текущей сессии;
- `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md` и исходные документы/ADR;
- `config/constants.py`, `src/`, `tests/`, `tools/` и существующие artifacts вне C3 evidence root;
- model cache, системный Python, Docker/WSL configuration и GPU driver;
- выбор другой модели, квантизации или backend под видом исправления;
- hidden fallback, startup-only path, lowered assertion, `skip`/`xfail` или «успешный» результат без evidence.

## 5. Audit владельца поведения и парадигмы реализации

В текущей drafting-сессии audit изменения публичного алгоритма имеет статус `not applicable`: runtime, public API,
FSM, SIP state, channel generation и product code не изменяются.

Для будущего execution stage зафиксирован владелец поведения:

| Поведение | Владелец | Данные, invariants и lifecycle | Парадигма и зависимости |
|---|---|---|---|
| Загрузка модели, inference, потоковый output и cancellation | локальный `LLM inference adapter/service` выбранного backend | model revision, quantization, GPU context, request lifecycle, cancellation token/handle, bounded output и timestamps | Метод/объект capability-владельца; scoped model/runtime dependencies и observability передаются при создании request |
| Проверка `action`/`text` и решение о допустимости действия | `Dialogue Manager` по ADR-001 | FSM state и final user turn; LLM не имеет SIP target и не меняет FSM напрямую | Typed structured contract; validation остаётся у Dialogue Manager и не переносится в свободный helper |
| Evidence/telemetry | probe runner/evidence writer для этого feasibility slice | request id, stage timestamps, GIL state, VRAM, exit code, cancellation outcome | Техническая side-facade без ownership SIP/FSM; не изменяет runtime state |

Свободная функция для stateful inference здесь не допускается: она скрыла бы model lifecycle, cancellation и GPU
ownership. Pure formatter/validator может быть отдельной функцией только при последующем code plan, если он не меняет
state, channel, generation, route или transfer outcome и не обходит Dialogue Manager.

## 6. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Какой кандидат является primary? | Только Qwen3.5-9B | Не запускать Qwen3.5-4B и другие модели этим plan-file | `resolved` по запросу и ADR-002 |
| Какой вариант весов? | Только 4-bit; фактический quantization format и revision фиксируются execution evidence | Нельзя подменить 4-bit другой квантизацией ради зелёного результата | `resolved`; details are task-owned |
| Какой язык и fixture? | Один вопрос `Почему небо днём кажется голубым?` | Оценка ограничена контрактом одного русского natural-science запроса | `resolved` |
| Какой режим генерации? | Non-thinking/instruct; скрытое reasoning не попадает в response и history | Не измерять speculative path и не принимать reasoning text за ответ | `resolved` по ADR-002 |
| Какой structured decision? | Для этого fixture ожидается JSON с `action=answer` и непустым русским `text`; допустимые action ограничены ADR-001 | `transfer` target, SIP command и FSM transition не создаются моделью в этом срезе | `resolved` |
| Что считать first useful token? | Первый непустой неслужебный output chunk/token; отдельно измеряется первый полностью валидный structured response | Для non-streaming backend фиксируется `first_token=not_available`, а `first_response` всё равно обязателен; это finding, а не скрытый pass | `resolved` |
| От какой точки считать задержку после финальной фразы? | От отдельной метки `final_phrase_received_at`, которую probe ставит непосредственно перед передачей в LLM уже собранной authoritative final user turn; вычисляются `final_phrase_to_first_useful_output_ms` и `final_phrase_to_first_valid_response_ms` | C3 не включает в эту метрику ASR, VAD, SIP/RTP и сетевой путь; для сопоставления сохраняются также `request_started_at` и интервалы от него. Если backend не stream-ит, `final_phrase_to_first_useful_output_ms=not_available`, но задержка до валидного ответа обязательна | `resolved` |
| Какой inference backend и команда? | Выбран Ollama 0.33.1 с bundled native `llama.cpp` CUDA runner; точные команды и версии сохранены в evidence | Не использовать внешний API; HTTP на `127.0.0.1` — локальный IPC, а не облачный сервис | `resolved by execution` |
| Что делать при GIL re-enable? | Не принимать native inference в main process; использовать явно принятую process-isolation boundary с HTTP IPC | Main process остаётся no-GIL; `pass_with_isolation` зафиксирован owner-ом | `resolved by owner decision` |
| Как трактовать VRAM? | Измерить LLM-only load/inference на 16 ГБ; не выдавать результат за совместный ASR+LLM+TTS baseline | Concurrent GPU benchmark передаётся в `001-D`/следующий plan | `resolved` для scope |
| Что делать при провале Qwen3.5-9B? | Зафиксировать `fail`/isolation gap и открыть owner discussion | Qwen3.5-4B и другие кандидаты — только owner-gated fallback/next plan | `resolved` policy; конкретное решение `open on failure` |
| Разрешён ли speculative path? | Нет, не deadline-critical и не часть acceptance C3 | Не запускать его и не считать его доказательством | `resolved` по Map-001 и запросу |

Execution stage завершён после review child plan, закрытия upstream dependencies и preflight. Backend details,
quantization revision, candidate evidence и owner classification синхронизированы с closeout. Повторный запуск должен
создавать новый evidence revision, а не переписывать смысл уже принятого результата.

## 7. Process invariant audit

| Инвариант | Проверка этого plan-file | Статус |
|---|---|---|
| Срез узкий и имеет один наблюдаемый acceptance boundary | Один primary, один вопрос, structured output, VRAM, timing и cancel; SIP/ASR/TTS вынесены | `pass for planning` |
| Планирование не считается исполнением | GPU/runtime execution вынесен в отдельную стадию и отражён в C3 evidence; создание plan-file само по себе его не подменяет | `pass` |
| Релевантные и нерелевантные проверки различены | C3 проверяет LLM candidate boundary; full dialog, RAG, SIP and concurrent GPU явно out-of-scope | `pass` |
| Авторитетная среда задана | Ubuntu/WSL2 + CPython `3.14.7t`; Ollama native runner вынесен в отдельный процесс | `pass for executed path` |
| Dirty worktree не маскируется | Pre-existing status сохранён в execution closeout | `pass for executed path` |
| Registry/backlog не изменяются молча | В drafting-файле не меняются registry, backlog и roadmap; их owner-process audit не выполняется в этой сессии | `not run by instruction` |
| Fallback и упрощения явны | Только owner-gated next plan; no silent fallback, no lowered assertion | `pass` |
| Production-ready свойства не объявляются | Evidence candidate не закрывает MVP/demo readiness | `pass` |
| Команды и результаты воспроизводимы | Backend/model/version/hash, timing, VRAM, cancel и controller evidence сохранены в C3 root | `pass for executed path` |
| Closeout содержит pre-existing и out-of-scope findings | Поля предусмотрены в template | `pass for planning` |

Документный sync после execution не подменяет evidence и не меняет его фактический результат. Registry/backlog audit
выполнен после синхронизации; его результат не изменяет candidate decision.

## 8. Architecture invariant audit

| Архитектурный инвариант | Применение в C3 | Статус/доказательство |
|---|---|---|
| Dispatcher владеет control plane и Dialogue FSM | Structured result только проверяется как контракт; Dispatcher/FSM не вызываются | `preserved; no runtime claim` |
| SIP/media callback не ждёт LLM; BYE обрабатывается немедленно | SIP/media отсутствуют в scope | `not applicable; no SIP changes` |
| Audio/text payload не идёт через Dispatcher | Нет аудиоканала и нет production text channel; prompt/result остаются probe payload | `preserved; no channel code` |
| Закрытие канала отбрасывает stale producer | Channel lifecycle не реализуется и не изменяется | `not applicable` |
| Только authoritative final ASR меняет FSM и разрешает TTS | Вопрос — фиксированный fixture, не ASR; FSM/TTS не запускаются | `preserved; no FSM/TTS action` |
| Speculative pipeline не делает необратимые действия | Speculative pipeline полностью исключён | `preserved; no speculative evidence` |
| TTS playback отменяется при barge-in | TTS и barge-in не входят в C3; проверяется только LLM request cancellation | `not applicable; no TTS claim` |
| LLM выдаёт ограниченное structured decision без SIP-доступа | Проверка `action`, `text`, отсутствия SIP target и скрытого reasoning | `mandatory; E-C3-QUESTION-001` |
| PCMU — основной SIP/media формат | Media отсутствует; формат не переопределяется | `preserved; no media change` |
| Конфигурация MVP в `config/constants.py`, скрытые defaults запрещены | Конфигурация не меняется; backend parameters должны быть записаны в evidence | `preserved; no config write` |
| Free-threaded CPython и native compatibility | Проверяются `Py_GIL_DISABLED`, `sys._is_gil_enabled()` и lazy operation | `mandatory; E-C3-IMPORT-001` |
| Нет внешних сервисов, PBX logic или audio recording | Запуск только локального model artifact; SIP/PBX/audio отсутствуют | `preserved; no external service` |
| У каждого канала есть owner/close/cancel/re-close test | C3 не создаёт channels; LLM request cancellation имеет отдельный lifecycle evidence | `LLM request only; channel test deferred to other plan` |

Любое обнаружение, что для проверки нужен новый Dispatcher path, production IPC, SIP adapter или изменение FSM,
немедленно переводит работу в unexpected gap protocol.

## 9. Узкие implementation slices

Срезы ниже описывают decomposition execution stage. Фактические результаты завершённых срезов зафиксированы в C3
closeout и связанных evidence-файлах.

### S0 — Execution gate и воспроизводимый preflight

  - **Цель и границы:** подтвердить закрытие `001-A`/`001-B`/`001-C`, доступность локального artifact, выбранного в S0
  backend, target GPU и чисто зафиксированный dirty baseline.
- **Компоненты/файлы:** только runtime и локальные model/backend dependencies; evidence root C3.
- **Write-set:** `question.txt`, `prompt.json` и preflight fields в `closeout.md`; product code не меняется.
  - **Последовательность:** повторить `git status --short`; проверить runtime identity, GPU, model id/revision,
  quantization/backend versions; выбрать доступный backend и зафиксировать фактические commands.
  - **Acceptance:** upstream gates закрыты, evidence root идентифицирован, command templates заменены реальными
  командами, dirty baseline сохранён; нет package install или внешнего inference API.
  - **Stop conditions:** не закрыт upstream runtime gate; модель/artifact недоступны; candidate/backend не удаётся
  воспроизводимо зафиксировать.
- **Релевантные проверки:** read-only inventory и command provenance.
- **Синхронизация:** не менять документы-владельцы в этом slice; фактический новый baseline отражается только в closeout
  и затем передаётся owner-у для отдельной синхронизации.
- **Следующий slice:** S1 только после закрытия S0.

### S1 — Import/no-GIL и минимальная operation probe

- **Цель и границы:** доказать, что candidate backend не включает GIL в main process на import, lazy load и минимальной
  операции; не выполнять полноценный диалог.
- **Компоненты/файлы:** выбранный stable free-threaded CPython, локальный LLM backend, `import-probe.json`, stdout/stderr.
- **Write-set:** только evidence root C3.
- **Последовательность:** fresh process; проверить `Py_GIL_DISABLED == 1` и `not sys._is_gil_enabled()` до imports;
  импортировать прямые/critical dependencies; загрузить model lazily; выполнить минимальную operation; после каждой
  стадии проверить GIL и warnings.
- **Acceptance:** exit code 0; runtime identity совпадает; GIL остаётся disabled на всех стадиях; версии и команда
  сохранены; native operation действительно вызвана, а не только импортирована.
- **Stop conditions:** GIL re-enable, missing dependency, warning, crash, unbounded load или необходимость скрытого
  compatibility bridge. При GIL re-enable статус main-process — `fail` до owner decision.
- **Релевантные проверки:** import, lazy import и minimal operation; SIP/ASR/TTS проверки нерелевантны и не запускаются.
  - **Синхронизация:** при main-process failure не менять ADR-003 молча; для C3 применена заранее зафиксированная owner-approved process boundary.
  - **Следующий slice:** S2 разрешён после owner-approved isolation gap и завершённого S1 evidence.

### S2 — Один русский вопрос и structured decision

- **Цель и границы:** получить по фиксированному вопросу один ограниченный JSON-результат от Qwen3.5-9B 4-bit в
  non-thinking/instruct режиме.
- **Компоненты/файлы:** local LLM backend, fixed prompt, `inference.json`, output logs.
- **Write-set:** только evidence root C3; SIP/FSM/Dialogue Manager code не меняется.
- **Последовательность:** загрузить выбранный artifact; зафиксировать `final_phrase_received_at` непосредственно перед
  передачей в backend уже собранного authoritative final user turn; отправить один prompt с вопросом и минимальным
  schema contract; зафиксировать first non-empty output chunk/token; собрать response; валидировать JSON и допустимые
  поля.
- **Измерения:** сохранить monotonic timestamps для `final_phrase_received_at`, `request_started_at`, первого полезного
  output chunk/token и первого полностью валидного structured response. Рассчитать задержку от финальной фразы до каждого
  из двух результатов, а также request-to-result intervals. В C3 финальная фраза подаётся синтетическим fixture-handoff:
  ASR/VAD и транспортные задержки в этот срез не входят.
- **Acceptance:** model id/revision/4-bit подтверждены; response — валидный JSON, `action=answer`, непустой русский
  `text`, без Markdown/служебного reasoning/SIP target; сохранены timestamps финальной фразы, первого полезного вывода и
  первого валидного ответа, рассчитаны `final_phrase_to_first_useful_output_ms` и
  `final_phrase_to_first_valid_response_ms`, сохранены output и exit code. Семантическая оценка ответа фиксируется как
  ручная owner review, а не как скрытый benchmark.
- **Stop conditions:** invalid JSON, другой action без зафиксированного изменения fixture, пустой/нерусский text, leaked
  reasoning, SIP instruction, timeout или отсутствие response. Нестриминговый backend не даёт `first_token` pass:
  он фиксируется как `not_available` и требует отдельной owner оценки соответствия ADR-002.
- **Релевантные проверки:** schema/contract, response timing и output safety; RAG quality и multi-turn не входят.
- **Синхронизация:** не менять ADR-001/002 по результату без owner decision.
- **Следующий slice:** S3 при наличии валидного response.

### S3 — VRAM и first useful timing

- **Цель и границы:** измерить memory footprint и время LLM-only на целевой 16 ГБ карте; не заявлять concurrent
  ASR+LLM+TTS fit.
- **Компоненты/файлы:** GPU telemetry, approved backend, `vram.json`, `measurements.md`.
- **Write-set:** только evidence root C3.
- **Последовательность:** зафиксировать total/free VRAM; измерить load peak; повторить S2 с тем же вопросом; записать
  allocated/reserved/peak на load, timestamps финальной фразы, старта request, first token/chunk, first valid response и
  cleanup; сохранить driver/runtime/model versions и command.
- **Acceptance:** отсутствие OOM; peak/available/headroom и measurement method сохранены; все доступные timings
  привязаны к monotonic timestamps; `final_phrase_to_first_valid_response_ms` существует для успешного запуска,
  `final_phrase_to_first_useful_output_ms` либо существует, либо явно равен `not_available` для non-streaming backend.
  200–500 ms остаётся общей инженерной целью, а не скрытым LLM-only SLA.
- **Stop conditions:** OOM, неотличимые/неполные telemetry, отсутствие valid response или требование другой модели/
  quantization для fit. В этом случае не переключаться на Qwen3.5-4B.
- **Релевантные проверки:** target GPU memory и candidate timing; ASR/TTS contention вынесен в `001-D`.
- **Синхронизация:** результат `fit` не изменяет техническое ТЗ до owner review.
- **Следующий slice:** S4 при достаточных S2/S3 evidence.

### S4 — Cancellation boundary

- **Цель и границы:** подтвердить отмену активной генерации того же candidate/request без stale final decision.
- **Компоненты/файлы:** approved backend cancellation API, `cancellation.json`, logs.
- **Write-set:** только evidence root C3.
- **Последовательность:** начать отдельный request с тем же вопросом и контролируемым окном генерации; убедиться, что
  generation active; послать cancel; зафиксировать ack/stop time, tokens after cancel, worker/process state и memory
  cleanup; проверить, что response не публикуется после cancel.
- **Acceptance:** cancel послан в активную генерацию; backend завершил request в документированном bounded timeout;
  после `cancel_sent` нет принятого structured decision/stale output; ресурс запроса освобождён или изоляция явно
  отражена; exit code и logs сохранены.
  - **Stop conditions:** cancel не поддерживается, зависает, оставляет stale output, ломает следующий clean request или
  требует нового неутверждённого process bridge. Это `fail`/isolation gap, а не повод заменить модель.
- **Релевантные проверки:** LLM request cancellation; barge-in/TTS playback cancellation не утверждаются.
- **Синхронизация:** cancellation limitation передаётся owner-у; новый IPC/adapter — отдельный plan.
  - **Следующий slice:** S5 после закрытия cancellation blocker либо явного owner decision о classification; в текущем
    execution owner classification выполнена.

### S5 — Evidence closeout и candidate decision

- **Цель и границы:** собрать результаты S0–S4 в один воспроизводимый candidate decision.
- **Write-set:** только `closeout.md`, `measurements.md` и evidence index в C3 root.
- **Acceptance:** каждый evidence ID имеет command, version, exit code, stdout/stderr, фактический результат и owner
  classification; статус выбран из `pass`, `pass_with_isolation`, `fail`, `blocked`; negative/pre-existing/out-of-scope
  findings перечислены; следующий шаг указан.
- **Stop conditions:** отсутствуют обязательные evidence, решение выведено по умолчанию, либо closeout маскирует failure
  fallback-моделью.
- **Синхронизация:** document-registry/backlog/roadmap не изменяются этим plan-file; если фактический результат требует
  изменения owner-документа, сначала owner review и отдельный документный diff.
  - **Следующий slice:** при `pass` или `pass_with_isolation` — `001-D`; при `fail` — owner discussion и только затем
    fallback/next plan.

## 10. Blocker register

Статусы ниже отражают завершённое execution C3. `resolved` означает, что blocker закрыт для зафиксированного пути;
это не расширяет scope до совместного ASR+LLM+TTS benchmark или production readiness.

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-C3-S0-001` | S0 | `001-B` не закрыл stable free-threaded CPython >= 3.14/no-GIL baseline | S0–S5 | project owner | runtime and C3 import evidence | `resolved` |
| `B-C3-S0-002` | S0 | Не удалось выбрать доступный stable backend или зафиксировать candidate provenance | S0–S5 | executor | candidate manifest + closeout | `resolved` |
| `B-C3-S0-003` | S0 | Нет доступного локального Qwen3.5-9B 4-bit artifact/revision или target GPU inventory | S1–S5 | executor | artifact/license/version record and GPU inventory | `resolved` |
| `B-C3-S0-004` | S0 | Dirty worktree не зафиксирован перед execution или write-set не изолирован | S0–S5 | main executor | execution closeout | `resolved` |
| `B-C3-S1-001` | S1 | Critical import/lazy operation включает GIL или выдаёт unsupported warning | Main-process baseline; S2–S5 | project owner | `E-C3-IMPORT-001` | `resolved for controller; native runtime isolated` |
| `B-C3-S1-002` | S1 | Backend требует новый IPC/adapter, которого нет в approved boundary | S1–S5 | project owner | owner decision + closeout | `resolved: existing HTTP IPC approved` |
| `B-C3-S2-001` | S2 | Ответ не является валидным JSON `action=answer` с русским non-empty `text` | Candidate decision; S3–S5 | project owner | `E-C3-QUESTION-001` | `resolved` |
| `B-C3-S2-002` | S2 | Backend не даёт first useful token/response, не позволяет измерить задержку от финальной фразы либо leaking reasoning/SIP target | Timing/contract acceptance | project owner | inference evidence | `resolved for tested path` |
| `B-C3-S3-001` | S3 | OOM, неполная telemetry или нет воспроизводимого 4-bit VRAM result | Candidate baseline promotion | project owner | `E-C3-VRAM-001` | `resolved` |
| `B-C3-S4-001` | S4 | Cancel не останавливает active request, оставляет stale output или не освобождает resource | Candidate decision/closeout | project owner | `E-C3-CANCEL-001` | `resolved for client boundary; hard native ack unavailable` |
| `B-C3-S5-001` | S5 | Нет exact command, version, exit code, stdout/stderr или evidence provenance | Closeout and next gate | main executor | evidence completeness audit | `resolved` |
| `B-C3-S5-002` | S5 | Failure превращён в silent Qwen3.5-4B/other-model fallback | Closeout integrity | project owner | fallback register + owner review | `resolved: no fallback run` |

Необъяснимый красный результат блокирует зависимый slice. Внешний pre-existing дефект, не затрагивающий C3, не
считается blocker-ом, но должен попасть в closeout как `pre-existing` или `out-of-scope` с конкретным описанием.

## 11. Test plan и evidence

В этом child plan не создаётся production code или постоянный regression test. Предусмотрен будущий минимальный
feasibility probe с одним вопросом и отдельными evidence-файлами.

| Evidence ID | Что доказать | Будущая команда/сценарий | Минимальные поля | Acceptance |
|---|---|---|---|---|
| `E-C3-IMPORT-001` | Runtime и import/lazy operation не включают GIL | `<CP314T> -c "<approved import/no-GIL probe>"` в fresh process; exact command фиксируется в S0 | Python version/arch, `Py_GIL_DISABLED`, GIL state до/после каждого import/lazy operation, warnings, exit code | `Py_GIL_DISABLED=1`, GIL disabled на всех стадиях, operation выполнена |
| `E-C3-QUESTION-001` | Один русский вопрос даёт ограниченное structured decision | `<selected-llm-command> --model Qwen3.5-9B --revision <selected> --quantization 4bit --prompt-file <C3>/prompt.json`; backend-specific flags фиксируются в S0/S1 | prompt hash, model/revision, action, text, raw output hash, schema result, exit code | JSON, `action=answer`, non-empty Russian text, no SIP target/reasoning |
| `E-C3-TOKEN-001` | Измерены задержки от финальной фразы до first useful output и first valid response | Тот же successful S2 request с monotonic timestamps и synthetic final-phrase handoff; для non-streaming явно записать `not_available` | `final_phrase_received_at`, `request_started_at`, first non-empty chunk/token, first valid response, derived intervals, units, stream mode | `final_phrase_to_first_valid_response_ms` есть; useful-output interval есть либо явно `not_available`; token gap и request gap не скрыты |
| `E-C3-VRAM-001` | Qwen3.5-9B 4-bit помещается в LLM-only target run | `nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv` + backend telemetry; exact command and sampling method in S3 | total/free/allocated/reserved/peak VRAM, OOM state, driver/CUDA/backend/model versions | Нет OOM и есть полная memory evidence; concurrent AI fit не заявляется |
| `E-C3-CANCEL-001` | Активная генерация отменяется без stale result | S4: same fixed question, active generation, approved cancel API/driver, bounded wait | cancel sent/ack/stopped timestamps, tokens after cancel, published-result flag, cleanup, exit code | No accepted result after cancel; no hang; cleanup or explicit isolation result |
| `E-C3-CLOSEOUT-001` | Candidate decision воспроизводим и честно классифицирован | S5 evidence completeness audit; no fallback run | status, commands, versions, files, blockers, pre-existing/out-of-scope, owner decision, next plan | `pass`/`pass_with_isolation`/`fail`/`blocked` supported by all required evidence |

Общий latency budget 200–500 ms используется только как проектный ориентир из требований и ТЗ. Этот plan измеряет
составляющие LLM candidate, но не подменяет end-to-end metric суммой локальных значений и не объявляет LLM-only run
достаточным для SIP demo.

### 11.1. Контракт deferred evidence

`not applicable` для текущего файла и drafting-сессии: тестовый код, deferred regression test, `skip` и `xfail` не
создаются. Предусмотренные выше evidence — будущая feasibility-проверка, а не уже созданный тест.

Если execution stage обнаружит corrective gap, который предполагает постоянный красный тест, его нельзя добавить молча:
сначала нужен стабильный `evidence_id`, owner, принимающий документ, explicit deferred command, stdout/stderr/exit code
и promotion criteria по APG §5.8A. До этого deferred test не создаётся и не считается пройденным.

## 12. Legacy/fallback/simplification register

| Категория | Что зафиксировано | Почему допустимо/необходимо | Ограничение и corrective path | Владелец | Статус |
|---|---|---|---|---|---|
| Legacy path | Legacy LLM adapter/compatibility bridge не вводится | В C3 нет product-code implementation | Если backend требует bridge, unexpected gap и отдельный plan/ADR | project owner | `none introduced` |
| Fallback model | Qwen3.5-4B и другие кандидаты не запускаются | Сохраняется честная проверка ADR-002 primary | Только owner discussion после `fail`/isolation gap; отдельный next plan | project owner | `owner-gated` |
| Speculative path | Provisional ASR/LLM/retrieval не запускается | Не deadline-critical и не часть C3 acceptance | Возможен только в отдельном owner-approved plan; provisional result не может менять FSM/TTS | project owner | `out-of-scope` |
| Scope simplification | Один вопрос, LLM-only VRAM, без SIP/ASR/TTS/RAG quality suite | Это минимальный child acceptance из Map-001, не подмена красной проверки | Полный integration/concurrent GPU evidence принимает `001-D` или следующий plan | project owner | `approved scope boundary` |
| Non-streaming behavior | Если backend не выдаёт token/chunk, измеряется только first response и gap фиксируется | Нельзя выдать отсутствие streaming за streaming pass | Зафиксировать finding и передать в следующий plan/ADR только если меняется baseline; модель не заменять молча | project owner | `finding-gated` |
| Isolation | Main-process GIL re-enable не обходится скрытым запуском | Сохраняется ADR-003 | Только explicit process boundary/IPC decision; иначе `fail` | project owner | `owner-gated` |

Ни одна строка этого register не разрешает менять модель, снижать assertions или продолжать после stop condition без
owner discussion.

## 13. Unexpected gap protocol

При обнаружении gap работа по зависимому месту немедленно останавливается. В частности, gap возникает при необходимости
нового inference adapter, IPC, process boundary, config key, runtime patch, модели, квантизации или изменения
structured contract.

Заполняемый record:

```text
Gap ID: GAP-C3-<NNN>
Обнаруженный gap:
Затронутые документы и компоненты:
Почему текущий plan нельзя продолжать:
Возможные варианты:
Рекомендуемый вариант:
Что блокируется (slice и blocker ID):
Меняет ли gap protected baseline:
Нужен ли новый ADR/roadmap/plan-file:
Owner решения и дата review:
Evidence, command и exit code:
```

До owner review были запрещены hidden fallback, startup-only path, ослабление acceptance, замена Qwen3.5-9B,
молчаливое включение GIL в main process и выдача isolation/compatibility за уже принятое решение. Для текущего
closeout process isolation явно принята владельцем и отражена как `pass_with_isolation`.

## 14. Execution report и closeout template

Ниже сохранён reusable template для повторного execution. Текущий результат уже заполнен в отдельном
[C3 closeout](../../artifacts/feasibility/001-C3-llm-primary/closeout.md), статус исполнения plan — `complete`, candidate decision — `pass_with_isolation`.

```text
Plan: 001-C3
Уровень: child plan
Родитель: Map-001
Дата/время owner approval:
Дата/время execution:
Статус исполнения child plan: complete | blocked
Candidate decision: pass | pass_with_isolation | fail

Dirty-worktree baseline:
Фактически изменённые файлы:
  - ожидается только artifacts/feasibility/001-C3-llm-primary/*
  - product code/config/docs/registry/backlog/roadmap: не изменялись / перечислить gap

Runtime:
  OS/WSL:
  Python version/build:
  Py_GIL_DISABLED:
  GIL state by stage:
Backend/model:
  backend/version:
  model id/revision:
  quantization/parameters:
  GPU/driver/CUDA:

Evidence:
  E-C3-IMPORT-001:
  E-C3-QUESTION-001:
  E-C3-TOKEN-001:
  E-C3-VRAM-001:
  E-C3-CANCEL-001:
  E-C3-CLOSEOUT-001:

Acceptance:
  structured action/text:
  final phrase received at:
  request started at:
  first useful token/chunk:
  first valid response:
  final_phrase_to_first_useful_output_ms:
  final_phrase_to_first_valid_response_ms:
  request_to_first_useful_output_ms:
  request_to_first_valid_response_ms:
  VRAM peak/headroom/OOM:
  cancellation ack/stop/stale-result:

Commands and results:
  exact commands:
  versions:
  exit codes:
  stdout/stderr paths:

Blockers:
  resolved IDs:
  open IDs:
  owner decisions:

Findings:
  pre-existing:
  out-of-scope:
  deferred evidence: not applicable unless a new APG-compliant record is added

Fallback/legacy/simplification decision:
  Qwen3.5-4B/other models run: no, unless separate owner-approved next plan is named

Document/process audit:
  document registry result:
  task backlog result:
  roadmap/ADR synchronization required:

Next step:
  pass -> 001-D only after owner review;
  fail/isolation gap -> owner discussion and named next/fallback plan;
  blocked -> list decision required.
```

План не закрывает `Map-001`, не выбирает fallback и не разрешает следующий компонентный срез до собственного owner
review и evidence closeout.
