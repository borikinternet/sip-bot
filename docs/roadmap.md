# Дорожная суперкарта MVP голосового SIP-бота

Уровень: `supermap`  
Статус: `in_progress`

Документ уровня supermap описывает порядок доведения проекта от текущих архитектурных набросков до воспроизводимой
демонстрации MVP. Он не заменяет map- и child plan-файлы отдельных направлений. Каждая карта и каждый узкий срез,
требующий существенной кодовой работы, перед исполнением должны получить применимый APG с source-map, критериями
приёмки и stop conditions.

## 1. Назначение и ожидаемый результат

Цель — получить локально работающий демонстрационный SIP-бот на русском языке, обслуживающий один параллельный разговор:

- принимает обычный SIP-звонок с PCMU;
- непрерывно принимает пользовательский звук;
- потоково распознаёт речь;
- понимает вопрос с учётом контекста и настраиваемой локальной базы знаний;
- формирует короткий ответ;
- озвучивает ответ через TTS и SIP;
- поддерживает перебивание;
- сообщает о невозможности ответа и переводит пользователя на локально эмулируемого оператора;
- сохраняет текстовый контекст и создаёт итоговый отчёт.

MVP не является production-ready решением и не включает внутреннюю реализацию PBX, запись разговоров, реальные внешние сервисы, многосессионную нагрузку и production-хранилище секретов.

## 2. Границы текущей карты

### Входит

- локальный inference ASR, LLM и TTS;
- free-threaded CPython как приоритетная среда либо изоляция несовместимого runtime в отдельном процессе;
- один SIP-вызов и один локально эмулируемый оператор;
- PCMU, RTP/RTCP, SIP-сигнализация и перевод звонка;
- control/data plane и центральный Dispatcher;
- VAD, Turn Detector/endpointing и Transcript Assembler;
- speculative и authoritative LLM-пути;
- RAG по тестовой базе знаний;
- контекст разговора, итоговый текстовый отчёт и измерение задержек;
- тестовый стенд, автоматизированные проверки и демонстрационный сценарий.

### Не входит

- обучение собственных моделей;
- production PBX и его внутренняя логика;
- запись аудио разговоров;
- реальные внешние сервисы и реальная операторская инфраструктура;
- более одного параллельного разговора;
- HA, кластеризация, production secret management и полноценный security hardening;
- production SLO и эксплуатационный runbook.

### Protected baseline

- Пользовательские решения в `docs/requirements.md`, `docs/technical-specification.md`, `docs/architecture.md` и принятых ADR не изменяются молча.
- SIP-адаптер не получает от LLM произвольные SIP-команды.
- Сетевой и медиатракт не должен зависеть от завершения LLM.
- Аудио не проходит через Dispatcher.

### Dirty-worktree note

До появления кода рабочее дерево считается содержащим только пользовательские документы. При начале реализации нужно сохранить unrelated changes, зафиксировать `git status --short` и не смешивать изменения разных срезов.

## 3. Правила планирования и источники процесса

При составлении и исполнении этой дорожной карты применяются [`architectural-planning-gate.md`](architectural-planning-gate.md)
и относящиеся к срезу правила [`development-guidelines.md`](development-guidelines.md). При подготовке локального gate
были просмотрены process-документы `cpbx-camel-integration`; они остаются только источником адаптации и не являются
зависимостями проекта.

| Источник | Применённое правило | Как проверяется в этой карте | Stop condition |
|---|---|---|---|
| [`docs/architectural-planning-gate.md`](architectural-planning-gate.md) | План содержит scope, source-map, owner review, process/architecture audit, test gates и closeout evidence | Обязательные разделы этой карты и отчёт о закрытии | Нельзя переходить к реализации при неразрешённом architectural gap или owner-review вопросе |
| [`docs/development-guidelines.md`](development-guidelines.md) | Применимые правила узких slices, воспроизводимых проверок, deferred evidence и контролируемой синхронизации | Срезы, evidence и критерии перехода ниже | Не расширять текущий срез молча и не скрывать незакрытый gap без owner/evidence |
| `docs/architecture.md` | Dispatcher владеет control plane, payload идёт по data plane | Архитектурный audit в разделе 9 | Нельзя передавать аудиофреймы через Dispatcher или давать LLM прямой SIP-доступ |
| `docs/technical-specification.md` | Конфигурация MVP хранится в файле констант, проверяются PCMU, latency и no-GIL | Acceptance gates срезов 1–5 | Нельзя подменять фактическую конфигурацию скрытыми defaults |

Английские термины оставлены только там, где это название компонента, протокола, runtime, идентификатора или технического механизма. Постановка, критерии, ограничения и closeout сформулированы на русском языке.

## 4. Owner-review решения, действующие до начала реализации

| Вопрос | Текущее решение | Последствие |
|---|---|---|
| Кто владеет состоянием звонка и диалога? | Main Dispatcher / Dialogue FSM | Все state transitions и SIP semantic commands проходят через него |
| Где передаётся payload? | Напрямую по data plane | Dispatcher управляет каналами, но не переносит аудио и текстовые фреймы |
| Как отменяются устаревшие результаты? | Закрытием соответствующего канала; поколения необязательны | Запись в закрытый канал отбрасывается, старые каналы не переиспользуются |
| Как обрабатывается промежуточный ASR? | Через Transcript Assembler и speculative pipeline | Только финальный текст может менять FSM и разрешать TTS |
| Как определяется конец хода? | Soft endpoint около 250–300 ms, hard endpoint около 500 ms тишины; после Map-008 выбран hard `520 ms` | Значения конфигурационные, 520 ms проверено на controlled TTS corpus и live path |
| Какая среда Python приоритетна? | Free-threaded CPython | Native-модули проверяются на непроизвольное включение GIL; несовместимый runtime изолируется |
| Какая LLM является выбранной? | Для текущего Map-002 execution baseline принят Qwen3.5-9B Q4_K_M через локальный Ollama/HTTP IPC; ADR-002 остаётся `proposed` как документ сравнительного выбора | Сквозной demo-path использует этот baseline; замена модели требует отдельного решения |

Неразрешённые owner-review вопросы блокируют соответствующий implementation slice, но не препятствуют проведению независимых feasibility-тестов.

## 5. Source map текущего проекта

| Область | Источник | Текущее состояние | Целевое состояние | Действие |
|---|---|---|---|---|
| Требования MVP | `docs/requirements.md` | Требования зафиксированы | Используются как acceptance boundary | Не дублировать в кодовых plan-файлах |
| Сквозная архитектура | `docs/architecture.md` | Зафиксирован первый вариант | Синхронизировать после каждого изменения ownership/contract | Обновлять как owner-документ архитектуры |
| Технические ограничения | `docs/technical-specification.md` | Зафиксированы конфигурация, latency, persistence и interface-правила | Синхронизировать с фактическими runtime и config constants | Обновлять по мере реализации |
| Выбор LLM | `docs/decisions/ADR-002-llm-model-selection.md` | `proposed`, shortlist обновлён | Benchmark и финальный выбор | Не считать модель выбранной до gate 1 |
| No-GIL | `docs/decisions/ADR-003-free-threaded-python.md` | `accepted` | Проверить зависимости и fallback через процесс | Обновлять при выборе inference/runtime |
| Документационный процесс | `docs/documentation-process.md` | Зафиксирован владелец информации | Поддерживать ссылки и отсутствие дублей | Проверять после каждого среза |
| Реестр документов | `docs/document-registry.md` | Все Markdown-документы распределены по визуальным таблицам | Проверять полноту и уникальность после каждого изменения docs | Запускать `python tools/check_document_registry.py` |
| Backlog задач | `docs/task-backlog.md` | Зафиксированы первые deferred/out-of-scope задачи | Синхронизировать с roadmap и closeout | Запускать `python tools/check_task_backlog.py` |
| Tooling notes | `docs/tooling-notes.md` | Зафиксированы адаптируемые no-GIL-паттерны и локальные команды | Обновлять при появлении новых tools | Не копировать чужие runtime-specific правила |
| Код | `src/`, `tests/`, `config/` | Пока отсутствует | Появляется по узким implementation slices | Source-map уточняется перед каждым срезом |
| Тестовый стенд | [`plans/plan-001-S-voip-test-stand.md`](plans/plan-001-S-voip-test-stand.md) и локальная test infrastructure | Plan принят и выполнен 2026-08-27; Baresip peer/fake operator evidence записаны | Воспроизводимый SIP/RTP/модельный стенд с PCMU, BYE и fake operator | Использовать approved `001-S` peer; повторять только при изменении SIP candidate |

## 6. Конкретные правила работы

- Roadmap не исполняется монолитно: перед кодом создаётся узкий plan-file для текущего среза.
- После каждого среза обновляются только документы-владельцы изменившихся фактов или решений.
- Если обнаружен архитектурный gap, работа останавливается до owner decision; обходной fallback не вводится молча.
- Тесты разделяются на релевантные текущему срезу и нерелевантные; нерелевантное падение не расширяет scope автоматически.
- Deferred-тесты не создаются через локальные безымянные `skip`/`xfail`; при необходимости применяется отдельная evidence-политика.
- Для child plan статус закрытия бинарен: только `complete` или `blocked`; `partial complete` и `foundation complete`
  не закрывают план. Промежуточные статусы допустимы на уровне supermap/map и не разблокируют child plans.

## 7. Этапы MVP и оценка трудозатрат

Оценка рассчитана на работу одного разработчика при постоянной проверке решений владельцем проекта. В неё входит время на интеграционные проблемы, повторные прогоны и синхронизацию документов, но не входит длительное обучение моделей.

| Этап | Результат | Оценка активной работы | Gate перехода |
|---|---|---:|---|
| 1. Проверка применимости кандидатов | Замеры ASR, LLM, TTS, no-GIL и базового SIP/media runtime на целевой машине | 5–7 дней | Есть воспроизводимые результаты, выбран рабочий baseline или зафиксирован изолированный runtime |
| 2. Уточнение архитектуры компонентами | Контракты, потоки данных, ownership, отмена, ошибки и конкретные реализации | 4–5 дней | Закрыты архитектурные gaps текущего среза, обновлены architecture/technical specification/ADR |
| 3. Создание тестового стенда | Локальный SIP/RTP стенд, эмуляция оператора, fixtures базы знаний и модельные smoke-тесты | 5–6 дней | Один сценарий звонка проходит воспроизводимо без полного бота |
| 4. Реализация основной логики | Карта 4 и её child plans: от media до диалога, перебивания, перевода и отчёта | 18–22 дня | Сквозной MVP-сценарий работает на стенде |
| 5. Тестирование и исправления | Интеграционные, latency, barge-in, контекстные и failure-path проверки | 8–10 дней | Acceptance gates выполнены либо каждый остаточный gap имеет явное решение |
| 6. Подготовка доклада | Описание архитектуры, ограничений, демонстрационного сценария и результатов | 3–4 дня | Доклад и reproducible demo instructions готовы |
| 7. Демонстрация | Финальный прогон и показ возможностей | 1–2 дня | Сценарий демонстрации пройден на чистом запуске |

Итого ориентир — 45–60 активных рабочих дней, или примерно 9–12 календарных недель с учётом обсуждений, ожидания загрузки моделей и повторных проверок. Оценка относится к PJSUA2/PJMEDIA как базовому VoIP-варианту. Переход на Sofia-SIP с отдельным RTP-слоем добавляет ориентировочно 1–2 недели, а вариант с Baresip и собственным audio bridge — 2–4 недели.

Оценка не является обязательством по сроку: feasibility-gate первого этапа может изменить состав компонентов и, следовательно, длительность следующих этапов.

## 8. Вертикальные срезы 1–3: от feasibility до стенда

### Срез 1. Проверка применимости выбранных кандидатов

Задача среза — не выбрать компоненты по описанию, а получить минимальные измеримые доказательства на целевой машине.

Проверить:

- free-threaded CPython: версию, запуск с отключённым GIL, импорт каждого native-зависимого компонента и факт отсутствия непреднамеренного возврата GIL;
- ASR: PCMU → нужный PCM-формат, потоковые partial/final результаты, устойчивость к русской речи, отмену и время появления полезного partial;
- LLM: Qwen3.5-9B как основной новый кандидат, Qwen3.5-4B как быстрый baseline, Qwen3-8B и Vikhr-Llama3.1-8B-Instruct как контрольные варианты; отдельно оценить 27B-кандидатов только как stretch-ветку, не принимая их заранее для 16 GB VRAM;
- LLM: structured output, контекст, обязательный RAG-путь, speculative/authoritative вызовы, отмену устаревшего вызова и расход VRAM с KV-cache;
- TTS: потоковую генерацию, выдачу первого полезного аудиофрагмента, русский язык, отмену при barge-in и совместимость формата с media path;
- базовый SIP/media runtime: регистрацию или прямой вызов в локальном стенде, PCMU, RTP callbacks, независимую
  обработку протокольных событий во время долгой операции, answer/hangup/transfer и корректное завершение media;
- сквозной latency budget: отдельно измерить времена ASR, endpointing, speculative/authoritative LLM, TTS и media, не подменяя их одним средним значением.

Артефакты среза:

- таблица `candidate → runtime → VRAM → latency → streaming → cancellation → GIL → license`;
- короткие воспроизводимые benchmark-команды и сохранённые текстовые результаты;
- обновлённые ADR по фактическому выбору или явно оставленному `proposed` решению;
- список несовместимых кандидатов и причина исключения.

Gate среза: для каждого обязательного контура существует рабочий baseline или документированное решение об изоляции в отдельном процессе. Не требуется, чтобы все кандидаты одновременно помещались в VRAM: проверка выполняется по очереди.

### Срез 2. Уточнение архитектуры конкретными компонентами

На основании среза 1 закрепить конкретные реализации и границы модулей:

- SIP/media adapter и его callback-модель;
- Dispatcher и Dialogue FSM;
- VAD, Turn Detector и Transcript Assembler;
- ASR adapter, speculative context/intent path, authoritative LLM path, Skill & Prompt Manager и RAG adapter;
- версионируемые skills/templates, generation profiles и typed `LlmRequest` как отдельная boundary между context/FSM и LLM Facade;
- RAG boundary: подготовленный локальный корпус, chunking/index, retrieval, source IDs, relevance threshold и передача
  найденных фрагментов в prompt;
- TTS adapter, playback channel и механизм отмены;
- transfer adapter для локально эмулируемого оператора;
- persistence контекста и итогового отчёта;
- конфигурационные константы и зависимости, включая явные лимиты очередей и таймауты.

Для каждого data-plane канала определить владельца, формат, жизненный цикл, backpressure, отмену, поведение при закрытии и правило отбрасывания stale payload. Для каждого control-plane события определить источник, потребителя, допустимые состояния FSM и реакцию на событие, пришедшее во время другого действия.

Отдельно описать обязательные прерывания и протокольные события во время ASR/LLM/TTS: BYE, CANCEL, re-INVITE/UPDATE
(hold/resume), OPTIONS, RTP/media failure, отказ модели, переполнение аудиобуфера, возврат речи пользователя во время
TTS и запрос перевода. Документировать, какие операции выполняются немедленно самим адаптером, а какие только
публикуют событие наверх.

Gate среза: обновлены `docs/architecture.md` и `docs/technical-specification.md`, а каждое принятое спорное решение имеет ADR либо ссылку на уже существующий ADR. Не допускается реализация «временной» связи, нарушающей разделение control/data plane.

### Срез 3. Создание тестового стенда

Стенд должен позволять запускать один разговор полностью локально и заменять тяжёлые модели deterministic adapters, не меняя контракты компонентов.

Минимальный состав:

- SIP caller/peer для установления вызова и генерации протокольных событий/запросов (BYE, DTMF, re-INVITE/UPDATE и
  применимые ошибки) или команды перевода;
- RTP loopback с PCMU и контролируемыми паузами, потерями и остановкой потока;
- локальный fake operator, принимающий transfer и подтверждающий переключение;
- fixture базы знаний по естественным наукам и фиксированный набор русских вопросов;
- deterministic ASR/LLM/TTS adapters для быстрых unit и state-machine тестов;
- режим с реальными выбранными моделями для smoke и latency-прогонов;
- сбор событий, временных меток, причин отмены, состояния каналов и итогового отчёта.

Сначала стенд должен доказать отдельно: SIP answer/hangup, передачу PCMU, независимую реакцию на протокольное событие
во время занятой обработки (BYE — обязательный пример), открытие/закрытие data-plane каналов и transfer. Только после
этого к нему подключаются реальные ASR/LLM/TTS.

Gate среза: чистый запуск стенда воспроизводимо устанавливает вызов, получает ответ и закрывает его; отдельные
сценарии показывают, что обязательная протокольная реакция не ждёт модель (BYE — минимальный пример), и подтверждают
transfer на fake operator. Все команды запуска и зависимости записаны в проекте.

## 9. Карта 4 и последующие этапы: логика, проверка и демонстрация

### Карта 4. Реализация основной логики

Бывший «срез 4» объявлен map-level направлением: он объединяет независимые runtime, SIP/media, speech, dialogue,
context, Skill & Prompt Manager, LLM Facade, TTS/playback и integration boundaries. Его APG и декомпозиция находятся в отдельном документе
[`plans/plan-002-mvp-media-and-speech-integration.md`](plans/plan-002-mvp-media-and-speech-integration.md).

Первой обязательной под картой карты 4 является [`plans/plan-002-I-boundary-interaction-map.md`](plans/plan-002-I-boundary-interaction-map.md):
она фиксирует topology взаимодействий, циклы и правила итерационного уточнения типов до сборки компонентов.
После owner decision по разделению Dispatcher/CallSession/FSM создан её successor plan
[`plans/plan-002-I.0-call-session-orchestration-and-state.md`](plans/plan-002-I.0-call-session-orchestration-and-state.md),
который закрыл deterministic call-session composition boundary. Live wiring
существующих typed input methods вынесен в successor plan
[`plans/plan-002-I.1-live-call-asyncio-wiring.md`](plans/plan-002-I.1-live-call-asyncio-wiring.md),
owner review которого принят `2026-09-03`; его execution идёт до
возобновления J4. Plan закрыт `2026-09-04` после full live gate r20 и
J4/J5 synchronization.

Supermap фиксирует только результат и переходные ограничения карты 4. Подробные scope, source-map, child plan graph,
параллелизм, map-gates, blocker register, test/evidence и closeout принадлежат документу карты 4 и не дублируются здесь.

Карта 4 должна привести к запускаемому application baseline, который проходит полный happy path
«SIP → PCMU → ASR → endpointing → retrieval/context → Skill & Prompt Manager → LLM → TTS → PCMU» и обязательные interaction scenarios. Реализация ведётся
короткими child plans; каждый из них получает отдельный owner review и собственный APG до execution stage.

Map gate карты 4: согласованы её scope и child plan graph, каждый executable пункт имеет self-contained plan-file, а
сквозной baseline и остаточные gaps переданы в closeout. Закрытие карты 4 не закрывает supermap: следующий этап —
отдельная карта тестирования и исправлений.

### Карта 5 (`Map-005`). Системное тестирование и готовность демонстратора

План карты создан в [`plans/plan-005-system-testing-and-demo-readiness.md`](plans/plan-005-system-testing-and-demo-readiness.md).
Owner review карты и групповой owner review дочерних планов `005-A`–`005-D` приняты `2026-09-04`; `005-A`–`005-D`
исполнены. Пользовательское прослушивание r7 выявило mid-stream потерю большей части TTS output, которую не отражает
один только `egress_underruns=0`. Поэтому Map-005 была возвращена в `in_progress` по APG и дополнена child plan
[`005-E`](plans/plan-005-E-tts-playback-integrity-corrective.md): dynamic bounded accumulation, frame pacing,
lifecycle/overflow tests и новый target live gate r10. r7, `report.md`, Baresip raw/stereo recording и requirement
matrix сохранены как историческое evidence; полнота TTS принята по r10. Отдельное согласование `005-E` не являлось
дополнительным gate, поскольку подход явно принят владельцем. `005-E` и map-level acceptance закрыты 2026-09-04;
финальный r10 подтвердил полный слышимый TTS output, отсутствие overflow и `egress_underruns=0`.

Составить матрицу проверок по требованиям и failure paths:

- SIP: answer, normal hangup, протокольные события (`BYE`, `CANCEL`, `re-INVITE`/hold/resume, `OPTIONS`) в каждой
  долгой фазе, RTP/media error, повторное закрытие ресурсов;
- audio: PCMU, пропуски/очереди, VAD false positive/negative, речь после soft endpoint, hard endpoint, barge-in;
- ASR/текст: исправление partial, финализация, пустой ход, русский текст, длинный ход и stale result;
- LLM/RAG: контекст предыдущих ходов, retrieval с source IDs, отсутствие знания, structured decision, отмена speculative и authoritative вызова;
- TTS: первый фрагмент, остановка playback, новый ответ после перебивания, ошибка генерации;
- FSM: недопустимые события, гонка terminal protocol event/transfer, единственность terminal state и отсутствие
  SIP-действия из произвольного текста модели;
- lifecycle/report: сохранение текстового контекста во время звонка, итог после normal hangup и transfer, отсутствие
  аудиофайлов, создаваемых ботом; live/rehearsal-запись Baresip test peer сохраняется в evidence; отдельный обязательный
  `state.json` не требуется;
- runtime: VRAM, CPU, no-GIL/import checks, повторный чистый запуск и отсутствие неявных внешних сервисов.

Latency gate измеряет время от фактического окончания речи пользователя до первого полезного TTS-аудио, а также отдельно показывает вклад endpointing, ASR, LLM, TTS и media. Бюджет RTP принимается равным 30 ms; остальные значения не маскируются усреднением. Порог 200–500 ms используется как ориентир комфорта, при этом вклад hard endpoint около 500 ms должен быть явно отражён в результате, а не исключён из измерения.

Gate этапа 5: обязательные сценарии проходят на чистом запуске; каждый обнаруженный дефект имеет исправление, обоснованное ограничение MVP или зарегистрированное deferred-решение с owner и условием возврата. Безымянные подавления тестов не принимаются.

### Карта 6 (`Map-006`). Подготовка доклада и демонстрационного пакета

Карта оформлена и исполнена по [`plan-006-report-and-demo-preparation.md`](plans/plan-006-report-and-demo-preparation.md),
затем была переоткрыта для corrective child `006-D` по явному запросу владельца и закрыта после target r6.
`006-A`–`006-C` подготовили source index, воспроизводимый runbook, русскоязычный черновик доклада и publication
checklist; map-level package был обновлён по принятому r10 evidence, после чего добавлена задача сократить лишние
паузы в Baresip input fixture с сохранением всех сценарных проверок. Выбор project license и фактическая публикация
остаются отдельным будущим действием и не входят в технический closeout Map-006. Corrective child `006-D` закрыт target
r6: compact fixture, 7/7 checks, Baresip stereo recording и audio audit прошли; исторические r1–r5 сохранены.

### Срез 6. Подготовка доклада

Доклад строится по фактически полученным результатам, а не по обещаниям архитектуры:

- задача и границы MVP;
- схема control plane/data plane и причина разделения;
- роли Dispatcher, Dialogue FSM, VAD, Turn Detector, Transcript Assembler, ASR, Skill & Prompt Manager, LLM/RAG и TTS;
- выбранные модели, runtime, лицензии и ограничения RTX 5060 Ti/16 GB;
- сценарии перебивания, отказа знания и перевода оператору;
- latency/VRAM/качество распознавания на зафиксированном наборе тестов;
- что не является production-ready и какие gaps намеренно оставлены вне MVP;
- инструкции воспроизводимого запуска и демонстрации.

Gate этапа 6: любой существенный тезис доклада имеет ссылку на код, тестовое evidence или документ; неподтверждённые свойства обозначены как план или ограничение.

### Срез 7. Демонстрация

Подготовить чистый сценарий запуска с заранее загруженными моделями и локальной базой знаний. Минимальный demo-flow:

1. входящий SIP-вызов и приветствие;
2. вопрос по естественным наукам с уточняющим follow-up;
3. перебивание ответа новым вопросом;
4. вопрос вне базы знаний и предложение перевода;
5. явное согласие и перевод на fake operator;
6. проверка итогового отчёта, полной Baresip-записи разговора в артефактах и отсутствия аудиозаписи со стороны runtime бота.

Перед показом выполнить прогон с чистого состояния, сохранить версии моделей/runtime и зафиксировать фактические результаты. Если реальное время ответа не укладывается в ориентир, демонстрация не скрывает это: показываются измерение и причина задержки.

### Карта 7 (`Map-007`). Переход live-речевого контура на WebRTC VAD

После закрытия Map-006 для подготовки мастер-классов выделена отдельная карта
[`plans/plan-007-webrtc-vad-migration.md`](plans/plan-007-webrtc-vad-migration.md). В текущем коде WebRTC VAD уже
выбран как кандидат и имеет адаптер, но application/live gates использовали детерминированный `_AmplitudeVad`.
Map-007 закрыта 2026-09-13: patched `webrtcvad-wheels 2.0.14` прошёл target/combined no-GIL gate, `VAD_MODE=2`
подключён к существующему `PcmFrame → VadDecision → TurnDetector` пути, а clean-start Baresip/PCMU I1 и полный J4
live gate прошли с WebRTC VAD. Исторические deterministic fixtures сохранены и не считаются live VAD evidence. Карта
не меняла endpointing, ASR, LLM, TTS, SIP, control/data plane или closed evidence Map-005/Map-006; наблюдение о
вариативном числе ASR-финализаций передано в дальнейшую настройку качества.

### Карта 8 (`Map-008`). Калибровка VAD и TurnDetector для телефонных условий

После Map-007 подготовлена и исполнена отдельная карта
[`plans/plan-008-vad-turn-calibration.md`](plans/plan-008-vad-turn-calibration.md). Она не переоткрывает выбор WebRTC
VAD и не меняет production topology: сначала на неизменяемом множестве TTS-фраз одного голоса и известной timing
разметке сравниваются modes `0..3`, затем отдельно настраивается существующий `TurnDetector`, затем выполняется
application/live validation. ASR не участвует в первичной VAD-разметке; его результат допускается только как downstream
diagnostic. Карта закрыта со статусом `complete`: child plans `008-A`–`008-C` исполнены последовательно, выбран
`VAD_MODE=2`, а `ENDPOINT_HARD_MS=520` прошёл standalone и live validation. Подробное evidence сохранено в
[`Map-008 closeout`](../artifacts/implementation/008-vad-turn-calibration/closeout.md). Controlled TTS baseline не
заменяет будущую human/noise generalization.

## 10. Контрольные аудиты и evidence

Перед объявлением MVP завершённым выполнить четыре независимые проверки.

### Архитектурный audit

- Dispatcher остаётся единственным владельцем control-plane transition и semantic SIP commands.
- SIP/media callbacks не ждут LLM, TTS или записи отчёта; обязательная протокольная реакция выполняется немедленно,
  а BYE является только одним из примеров.
- Аудио и крупные текстовые payload идут по data plane напрямую между владельцами каналов.
- Закрытие канала делает stale результат безвредным; закрытый канал не переиспользуется для нового поколения.
- Только authoritative final ASR result может менять FSM и разрешать TTS.
- Speculative result не может напрямую выполнить transfer, hangup или начать необратимое действие.
- TTS playback отменяется при barge-in, а новая фраза не смешивается со старым поколением ответа.
- LLM выдаёт ограниченный structured decision, а не произвольный SIP вызов.
- No-GIL требование либо доказано тестом для runtime, либо несовместимый компонент вынесен в отдельный процесс с явным контрактом.

### Process/documentation audit

- актуальны source-map и владельцы информации;
- нет дублирующих нормативных описаний в roadmap, requirements, architecture и technical specification;
- каждый изменённый контракт отражён в документе-владельце;
- каждый ADR имеет статус, контекст, решение и последствия;
- в репозитории есть инструкции запуска, тестирования и демонстрации;
- внешние документы `cpbx-camel-integration` использованы как ориентир процесса, но не считаются частью deliverable и не изменяются.

### Test/evidence audit

Сохранить минимальный пакет свидетельств:

- commit или snapshot исходного состояния;
- команды и версии runtime/dependencies/models;
- результаты feasibility benchmark;
- логи обязательных SIP-протокольных событий, barge-in, context, no-answer и transfer сценариев; BYE сохраняется как
  обязательный конкретный smoke-кейс.
- latency/VRAM summary с разбивкой по компонентам;
- итоговую таблицу требований `requirement → test/evidence → status`;
- список известных ограничений и deferred-решений.

### Closeout audit

Supermap/MVP можно обозначить как `MVP complete`, только если happy path и обязательные interruption/failure paths
проходят на чистом запуске, а evidence доступно другому разработчику. Если работает только часть сквозного сценария,
статус supermap/map остаётся `partial complete` или `in_progress`; child plan при этом обязан иметь только `complete` или
`blocked`. `prod-ready complete` в рамках этой карты недостижим по определению scope.

## 11. Явно отложенные production-задачи

Следующие задачи не должны случайно расширять MVP, но должны быть видны в итоговом отчёте:

- несколько одновременных разговоров и планирование общей GPU/CPU нагрузки;
- отказоустойчивость, рестарт отдельных компонентов и восстановление после падения процесса;
- production observability, метрики, tracing и alerting;
- безопасное хранилище секретов, управление доступом и полноценный security review;
- настоящая операторская инфраструктура и production transfer policy;
- подбор моделей под широкий спектр голосов, шумов, диалектов и доменов;
- production-quality evaluation датасет, MOS-исследование и нагрузочные тесты;
- запись разговоров, retention, персональные данные и юридические процедуры вокруг аудио;
- high availability, контейнеризация и эксплуатационный runbook;
- расширенное semantic endpointing для длинных пауз и сложных незавершённых фраз.

Отложенная задача считается учтённой только при наличии владельца будущего решения или явно принятого ограничения. Она не маскируется как выполненная возможность MVP.

## 12. Следующий рабочий шаг

Срез 1 признан картой feasibility, а не узким execution slice. Текущая supermap и созданная декомпозиция находятся в
[`plans/plan-001-deadline-feasibility.md`](plans/plan-001-deadline-feasibility.md). `001-A` и `001-B` отдельно приняты
и закрыты evidence 27 августа; отдельный [`001-S`](plans/plan-001-S-voip-test-stand.md) дал pass для lifecycle, PCMU,
remote BYE и fake-operator transfer. `001-C1`–`001-C4` также закрыты component evidence: C1/C2/C4 приняты в
проверенных main-process путях с необходимыми patch-ограничениями, C3 — как `pass_with_isolation` через локальный
Ollama/HTTP IPC. `001-D` закрыт статусом `complete` с synthesis result `pass`, а `001-E` закрыт статусом `complete`:
финальные
baseline/gate/blocker/evidence документы созданы в `artifacts/feasibility/001-D/` и
`artifacts/feasibility/001-E/`. Owner review карты 4 и `Map-002-I` принят 2 сентября; child plans карты 4 созданы.
`Map-001` закрыта статусом `complete`; `002-A`–`002-H` отдельно согласованы,
исполнены и закрыты статусом `complete`. `002-B` передал SIP/media contracts,
`002-C`–`002-E` прошли main I1–I2 propagation, а `002-F`/`002-G` закрыли real embedding/RAG и latency evidence;
`002-H` закрыл XTTS/GPU, PCMU/RTP playback и barge-in. J1–J3 приняты главным executor; owner decision по существующим
Dispatcher/DialogueFSM и отдельному CallSession реализован в `002-I.0`, который закрыт статусом `complete` только в
пределах deterministic composition scope с deterministic и real component evidence. `state.json` не является входным
требованием и удалён из обязательного scope. Актуальная ревизия `Map-002-I` — 21. J4 isolated clean-start lanes,
базовый live SIP/RTP full-flow и единый full live scenario gate закрыты: r20 доказал follow-up, RAG/source IDs,
barge-in, unknown-answer/transfer, report и PCMU SIP/RTP. Карта 4, Map-005, Map-006 и Map-007 закрыты в пределах
своих scope; Map-008 исполнена, а следующий шаг — использовать её параметры и evidence в материалах мастер-класса и
следующим интеграционным шагом была [`Map-009`](plans/plan-009-optional-sip-registration.md) для optional SIP
registration на локальном FreeSWITCH. Map-009 закрыта 13 сентября: target r15 подтвердил registered full-AI path, runtime-scoped
readiness, PCMU/RTP и Baresip stereo recording; workshop runbook готов, production PBX/TLS/multi-call остаются
за пределами текущей карты.

### Карта 10 (`Map-010`). Непрерывный PCMU/RTP и comfort noise в idle

При прослушивании registered full-AI artifact `cold-20260913-r15` обнаружен дефект evidence/media policy: при
отсутствии RTP-пакетов в idle Baresip `dec` сжимается до времени фактически полученных ответов, а старый stereo helper
ориентируется на независимые границы raw-файлов. Это делает запись непригодной для доказательства одновременного разговора и потенциально
позволяет PBX трактовать молчание как разрыв media.

Map-010 не меняет закрытые планы 005/009 и не реализует RFC 3389/CN. Её цель — regular negotiated PCMU frames на
каждом media tick, низкоуровневый configurable comfort-noise PCM в idle и честный audit общей temporal шкалы.
Карта декомпозирована на [`010-A`](plans/plan-010-A-idle-pcmu-comfort-noise.md), [`010-B`](plans/plan-010-B-stereo-recording-timeline.md)
и [`010-C`](plans/plan-010-C-live-continuity-gate.md). Все child plans завершены 2026-09-14: target r4 подтвердил
event-window RTP continuity (`ptime=20 ms`, expected/egress/peer `6281/6281/6281`, loss/underrun/errors/drops `0`),
а Baresip recording audit и stereo derivative прошли. После corrective revision stereo строится по answered-call
window и timestamps старта `enc`/`dec`; raw duration gap больше не используется как общая шкала. Статус Map-010: `complete`.
RFC 3389/CN остаётся deferred.

## 13. Ускоренный профиль к докладу 25 сентября 2026 года

### 13.1. Новый критерий успеха

К 20 сентября должен существовать воспроизводимо запускаемый рабочий демонстратор, который можно показать 25 сентября.
Первоначальная оценка `45–60` рабочих дней относится к расширенному MVP и больше не является планом текущего календарного
среза. На дату начала исполнения, 26 августа, доступно 23 будних дня включая день доклада и 22 будних дня до rehearsal; последние два дня
перед докладом резервируются под прогон и только критические исправления.

Демонстратор не объявляется production-ready и не обязан закрыть весь первоначальный scope, если обязательный demo-flow
работает и ограничения явно показаны в докладе.

### 13.2. Обязательный demo-flow

1. Локальный SIP-вызов устанавливается, бот отвечает и принимает PCMU.
2. Пользователь задаёт русский вопрос по естественным наукам; ASR выдаёт partial/final текст.
3. Retrieval находит фрагменты в локальном curated knowledge set, Skill & Prompt Manager собирает versioned `LlmRequest`
   с source IDs, LLM формирует ответ по переданному контексту и TTS возвращает речь.
4. В ответ бота пользователь вмешивается новой репликой; playback отменяется, новая реплика обрабатывается.
5. Второй вопрос использует контекст предыдущего хода.
6. Для вопроса вне базы знаний бот сообщает ограничение, предлагает оператора, а по подтверждению выполняет локальный
   transfer на fake operator.
7. После завершения создаётся текстовый отчёт; runtime бота аудиозапись не создаёт, а test peer Baresip сохраняет полную
   запись разговора в evidence.

### 13.3. Разрешённые упрощения

Ниже перечислены согласованные owner-ом границы демонстрационного scope, а не автоматическое разрешение упрощать
обязательный demo-flow. Каждое упрощение имеет запись в реестре карты и corrective path либо явное решение сделать его
target invariant. Process/native fallback остаётся owner-gated и не включается автоматически.

- speculative LLM/retrieval path не входит в критический demo-path; partial ASR сохраняется, authoritative LLM вызывается
  по финальному ходу;
- semantic turn detector не реализуется; применяется VAD и фиксированный endpointing с конфигурационными порогами;
- `completion_hint` LLM не используется для управления FSM;
- база знаний — небольшой заранее подготовленный русский срез по естественным наукам, без полноценного Wikipedia crawler;
- размер корпуса и индекс можно ограничить MVP-объёмом, но retrieval нельзя молча заменить ответом только из pretraining:
  в докладе должен быть показан source-aware ответ и отдельный unknown-answer сценарий;
- context — последние ходы и компактное детерминированное резюме, без отдельной модели summarization;
- допускается один процесс Dispatcher/FSM и отдельные локальные процессы inference для ASR/LLM/TTS, если native-зависимость
  не проходит no-GIL gate;
- latency 200–500 ms остаётся измеряемой целью и предметом доклада, но не блокирует демонстратор при наличии корректной
  разбивки задержки и естественного поведения;
- Docker используется для тестовых peer-компонентов и стенда; обязательная production-like контейнеризация бота не входит;
- оператор эмулируется локальным SIP peer или минимальным fake operator, без полноценного контакт-центра.

### 13.4. Жёсткие границы календаря

| Дата | Gate | Результат | Что блокирует продолжение |
|---|---|---|---|
| 26 августа | Environment bootstrap и классификация feasibility | Ubuntu/WSL2 bootstrap evidence, признание среза 1 картой | Не определена карта дочерних планов |
| 27 августа | Map/child-plan owner review, runtime и SIP gate | `001-A`/`001-B` приняты и закрыты; `001-C1` pass после отдельного `001-S`; Baresip peer, PCMU, BYE и fake transfer имеют evidence | Новая native incompatibility или несинхронизированный blocker register |
| 28–31 августа | AI native compatibility gate | По одному owner-approved кандидату на ASR/LLM/TTS; no-GIL/isolation evidence и закрытие component blockers | Нет runtime/model evidence или требуется owner decision |
| 1–4 сентября | ASR/LLM/TTS native compatibility gate | По одному кандидату на AI-контур; no-GIL/isolation decision и evidence | Нет runtime/model evidence или требуется owner decision |
| 5–10 сентября | Speech pipeline gate | VAD, partial/final ASR, endpointing, text channels | Нет одного финального пользовательского хода |
| 11–15 сентября | Answer path gate | LLM, retrieval/curated KB, context, TTS и первый полный source-aware ответ | Нет сквозного ответа на фиксированный вопрос или не доказана передача локального контекста |
| 16–18 сентября | Interaction gate | barge-in, unknown-answer, offer/transfer, report | Не работает любой обязательный demo-flow |
| 19–20 сентября | Integration/evidence gate | Чистый запуск, latency/VRAM evidence, исправление P0/P1; рабочий демонстратор к 20 сентября | Не проходит полный сценарий с чистого состояния |
| 21 сентября | Code/demo freeze | Заморожен демонстрационный baseline и доклад | Любая новая функция без owner approval |
| 22–24 сентября | Rehearsal и резерв | Два полных прогона; только критические исправления | Нет воспроизводимого прогона или неясен recovery plan |
| 25 сентября | Доклад | Демонстрация и честное описание ограничений | — |

### 13.5. Правило остановки расширений

После 31 августа новые компоненты, дополнительные режимы диалога, улучшения качества и production-функции не добавляются,
если они не закрывают конкретный обязательный demo-flow. При конфликте качества и срока выбирается рабочий ограниченный
сценарий с явным сообщением пользователю, а не незавершённая универсальная функция.

Текущий map-level plan-file карты 4: [`plans/plan-002-mvp-media-and-speech-integration.md`](plans/plan-002-mvp-media-and-speech-integration.md).
Его child plan может перейти к execution stage только после прохождения owner review supermap/map и собственного APG.

## 14. Дополнительный конференционный track: FreeSWITCH call-center workshop

Для отдельного мастер-класса создана [`Map-011`](plans/plan-011-freeswitch-small-company-callcenter-workshop.md). Это
не расширение MVP SIP-бота и не переоткрытие закрытых Map-001–Map-010: задача — на новом Debian WSL установить
FreeSWITCH из pinned package source `@ru_freeswitch`, показать direct call двух MicroSIP-клиентов, затем очередь
`mod_callcenter` с одним MicroSIP agent и получить повторяемый сценарий для участника без контекста переписки.

Map-011 разложена последовательно на `011-A` Debian/packages/startup, `011-B` два MicroSIP endpoints и прямой вызов,
`011-C` очередь/agent и `011-D` clean repeat/runbook и завершена 2026-09-21. Owner-provided mirror использован для
Debian 12 Bookworm; FreeSWITCH 1.11.3 поднимается штатным systemd unit после WSL restart; две MicroSIP registrations,
direct PCMU bridge и `mod_callcenter` queue bridge подтверждены. Владелец подтвердил акустическую последовательность,
а независимый субагент без контекста после corrective review принял self-contained workshop runbook. Docker,
существующая Ubuntu, исходники FreeSWITCH и application baseline не изменялись.

## 15. Дополнительный конференционный track: смена RAG-корпуса и мастер-класс

Для практического мастер-класса по настройке ассистента на документы небольшой компании выполнена
[`Map-012`](plans/plan-012-rag-corpus-onboarding-workshop.md). Она устраняет разрыв между рабочим source-aware
RAG-прототипом и пользовательским workflow: corpus validation/normalization, deterministic chunking, offline index
build, атомарная публикация, runtime load/readiness без полного re-embedding, evaluation set и clean live SIP proof.

Карта не меняет веса Qwen, SIP/media/ASR/TTS/FSM baseline и не вводит внешнюю vector DB без нового owner decision.
Map-012 закрыта 2026-09-21: `012-I`, `012-A`–`012-F` complete. Опубликованы strict `rag-corpus-v1`, deterministic
`markdown-semantic-v1`, атомарный `rag-index-v1`, active corpus компании «СервисПлюс» и science rollback artifact.
Immutable evaluation прошёл `12/12`; clean build воспроизвёл тот же SHA-256; runtime probe подтвердил ноль corpus
embedding requests. Финальный registered `live-r5` подтвердил positive/follow-up, смену темы, корректный
unknown-answer/offer-transfer, transfer, source-aware report, непрерывный RTP и stereo recording. Self-contained
runbook прошёл независимый context-free review после corrective pass; science corpus остаётся regression fixture.

## 16. Corrective Map-013: greeting и короткий prompt package

22 сентября закрыта [`Map-013`](plans/plan-013-call-greeting-and-short-prompt.md), не расширяющая обязательный demo-flow,
а исправляющая два обнаруженных rehearsal-дефекта: отсутствие первой реплики бота и дублирование prompt text в
authoritative runners. `013-A` централизовала skill/template/profile в `config/constants.py` и добавила точную
инструкцию `Отвечай коротко.`; `013-B` добавила отменяемое `Алло.` через существующие FSM/TTS boundaries без LLM/RAG.

Финальный registered RAG gate `registered-rag-live-20260922-r3` прошёл greeting, follow-up, barge-in,
unknown-answer/transfer, report и RTP continuity в одном звонке. Real AI gate показал first usable output `176.215 ms`
и final structured decision `884.254 ms`; это измеренный текущий результат, а не гарантированный SLA `0.6 s`.

## 17. Corrective Plan-014: адаптивный VAD и turn-scoped ASR boundary

После реального звонка 22 сентября создан и принят к исполнению
[`Plan-014`](plans/plan-014-adaptive-vad-energy-gate.md). WebRTC VAD mode 2 на реальном тракте принимал слабый фон и
акустический возврат за речь; Python binding не предоставлял наружу внутренние noise/speech estimates. В существующий
`VadProcessor` без нового канала добавлен per-call energy gate с RMS dBFS, устойчивым noise-floor estimate,
rate-limited adaptation, speech-level analytics и hysteresis. Problem-call replay уменьшил raw positives `447 → 94`
и оставил один authoritative turn; controlled Map-008 corpus сохранил три ожидаемых хода.

Первый повторный live run `20260922-145749` отделил следующий дефект: семь реальных коротких реплик успели создать
несколько endpoints при отстающем ASR, а `turn_id` отсутствовал в ASR chunk/hypothesis boundary. Единственный pending
endpoint был перезаписан, и call-loop завершился ошибкой transcript scope. Corrective slice протянул authoritative
`TurnDetector.turn_id` через accumulator/ASR/assembler, исключил sub-`min_speech_ms` bursts из ASR prefix и добавил
регрессии для трёх back-to-back turns. Authoritative registered repeat `registered-repeat-20260922-r8` прошёл пять
ходов, follow-up/barge-in/unknown-answer/transfer/report при нулевых dropped/stale/runtime errors и GIL off. Plan-014
закрыт `complete`.

## 18. Corrective Map-015: semantic turn и составные пользовательские действия

Последний повторный live-звонок подтвердил исправленное разделение последовательных ASR-ходов, но выявил semantic-path
дефект: реплика вида `Нет, не надо. Почему небо днём голубое?` содержит отказ от pending transfer и самостоятельный
вопрос. Текущий FSM классифицирует весь `FinalUserTurn` как одно подтверждение, теряет residual content и не запускает
для него retrieval. Одновременно active RAG возвращает false-insufficient для разговорной формулировки, хотя правильный
source является top-1 и его score выше объявленного configured threshold.

Для исправления подготовлена [`Map-015`](plans/plan-015-semantic-turn-understanding.md): `015-I` фиксирует фактическую
interaction revision; `015-A` вводит typed `DialogueExpectation`/`DialogueAct`/`SemanticTurn` и deterministic parser;
`015-B` материализует ordered acts в FSM/pipeline без нового delivery owner; `015-C` исправляет sufficiency только по
expanded immutable evaluation; `015-D` выполняет target/live gate. LLM semantic-parser не входит в обязательный scope и
может появиться только отдельной evidence-driven картой. Group owner review принят 2026-09-22. Для positive confirmation
с residual content утверждено поведение «сначала ответить на вопрос, затем повторно спросить подтверждение перевода»;
немедленный transfer запрещён.

22 сентября Map-015 закрыта `complete`: `015-I` и `015-A`–`015-D` выполнены, immutable RAG evaluation прошла `12/12`,
host gate — `284 passed, 2 skipped` на CPython 3.14.7t с GIL off. Registered aggregate `015-D/live-v7` прошёл три
сценария compound negative/positive/unknown, barge-in, повторное подтверждение, единственный offer и transfer. В ходе
live corrective pass уточнён parser invariant: pending confirmation задаёт смысл коротких ответов, но не подавляет
самодостаточную явную просьбу перевода.

## 19. Corrective Map-016: speech evidence и устойчивый barge-in

Следующий реальный звонок 22 сентября выявил остаточный дефект speech boundary: WebRTC VAD/energy gate создавал turns из
слабого акустического возврата, а `FasterWhisperC2Backend` выбрасывал `no_speech_prob` и другие segment diagnostics,
оставляя приложению только hallucinated text. Во время playback такой ложный start дополнительно превращался в
`BARGE_IN` до проверки ASR.

Для исправления принята [`Map-016`](plans/plan-016-speech-evidence-and-barge-in-corrective.md). `016-I` фиксирует
producer-first revision `speech-evidence-I1`; `016-A` добавляет typed ASR evidence и безопасное отбрасывание rejected
turn; `016-B` применяет per-call near-end reference и отдельный строгий barge-in threshold; `016-C` повторяет исходную
запись, controlled corpus, target/no-GIL и registered FreeSWITCH gate. AEC/media-reference edge не вводится и станет
отдельным owner-review gap только при доказанной недостаточности двухуровневой защиты.

22 сентября Map-016 закрыта `complete`. Problem-call replay сократил authoritative turns `12 → 4`; три точных
акустических/no-speech интервала отклонены по model evidence. Host regression прошла `291 passed, 6 skipped`, target
3.14.7t — `294 passed, 3 skipped` с GIL off. Registered FreeSWITCH gate `016-C/registered-live-r3` прошёл четыре
ожидаемых хода, source-aware ответы, настоящий barge-in, transfer, отчёт, стереозапись и непрерывный RTP при нулевых
runtime errors/drops/underruns. AEC/media-reference edge не потребовался.

## 20. Corrective Plan-017: задержка hard endpoint

Последующий анализ той же записи отделил ошибку временного сопоставления от реального поведения: WebRTC VAD снимает
speech-флаг на следующем 20-ms кадре, а 520 ms добавляет fixed policy существующего `TurnDetector`. По явному решению
владельца endpointing должен занимать не более 300–400 ms; прежний 520-ms baseline, выбранный ради искусственной
480-ms паузы Map-008, больше не является operational target.

Исполняется [`Plan-017`](plans/plan-017-endpoint-latency-corrective.md): hard endpoint 360 ms, обязательная regression
на caller channel реального registered call, прозрачная sensitivity-проверка старой TTS-паузы, target no-GIL и новый
registered live gate. Filler phrases, SIP transfer completion, дефект greeting TTS и замена synthetic fixture записаны
отдельными задачами `TASK-022`–`TASK-025` и не входят в speech-timing corrective.

23 сентября Plan-017 закрыт `complete`: target replay сохранил четыре реальные реплики, historical 480-ms split
зафиксирован явно, target regression прошла `301 passed`, registered live gate — полный сценарий без runtime errors.
Фактические hard endpoints `[380, 362, 361, 383] ms`, maximum `383 <= 400`; сервис после gate прогрет и снова
зарегистрирован как `1002` в очереди `7100`.

## 21. Corrective Plan-018: задержка первого аудио XTTS

Разложение задержки после Plan-017 показало, что около `0.4 s` после финального решения LLM занимало ожидание первой
порции waveform XTTS при исходном `stream_chunk_size=20`. Это не media `ptime`: параметр определяет, сколько
авторегрессионных акустических токенов XTTS накапливает перед очередным декодированием waveform.

23 сентября выполнен [`Plan-018`](plans/plan-018-tts-first-audio-latency-tuning.md). В live path добавлены typed
diagnostic timestamps без нового delivery channel; на одном прогретом XTTS runtime проверены `20/10/5` по пяти
русским фразам и двум проходам. Median first-normalized-PCM составила соответственно `398.059`, `204.681` и
`107.277 ms`; все варианты имели full RTF `< 1`, нулевые producer underruns и нулевой clipping. Baseline изменён на
`TTS_STREAM_CHUNK_SIZE=5`.

Registered FreeSWITCH gate прошёл полный сценарий и дал `LLM final → first playback frame` `173.499–223.834 ms` на
четырёх ответах. RTP continuity `6151/6151`, `egress_underruns=0`, output overflow и runtime errors отсутствуют;
target CPython 3.14.7t regression прошла полностью. План закрыт `complete`, сервис снова прогрет и зарегистрирован.

## 22. Конференционный Map-019: параллельный мастер-класс на двух WSL-дистрибутивах

Для 60-минутного мастер-класса подготовлена новая, **не исполненная** [`Map-019`](plans/plan-019-dual-wsl-freeswitch-live-masterclass.md) с self-contained child plans `019-A`–`019-D`. Ведущий вручную собирает стенд в одном чистом Debian 12 WSL2, агент без истории чата работает во втором на той же Windows-машине. У обоих одинаковые входные материалы и критерии: пакетный FreeSWITCH, прямой вызов двух MicroSIP, очередь операторов и подготовленная очередь бота. Исторические результаты Map-011 не засчитываются как результаты новых дорожек.

WSL2-дистрибутивы могут делить сетевое пространство и конфликтовать по слушающим портам. Поэтому карта допускает параллельную подготовку, но назначает исключительные окна запуска FreeSWITCH и живых SIP/RTP-проверок; время ожидания окна в сравнении учитывается отдельно. Формат ожидает owner review перед исполнением. Ни два новых WSL-стенда, ни их acceptance пока не заявлены как готовые.

## 23. Конференционный Map-020: browser SIP over WSS/DTLS-SRTP

В рабочем дереве подготовлена отдельная [`Map-020`](plans/plan-020-freeswitch-webrtc.md) для транспорта browser SIP:
локальный WSS baseline, browser REGISTER/ICE/DTLS-SRTP и отдельный rollout на целевой FreeSWITCH. Карта не меняет
очередь `mod_callcenter`, SIP-бота или его односессионное ограничение. На 23 сентября 2026 года Map-020 имеет статус
`in_progress`: локальная репетиция и серверная часть разделены, а серверный rollout зависит от доступности host,
сертификата и решения LAN/public.

Map-021 использует только подтверждённый browser/SIP contract Map-020; незавершённый transport gate не считается
evidence web-demo.

## 24. Конференционный Map-021: web-интерфейс, session-scoped RAG и звонок

Для быстрого закрытого demo подготовлена [`Map-021`](plans/plan-021-web-rag-conference-demo.md) с ADR-006 и
self-contained child plans `021-I`, `021-A`–`021-E`. Карта добавляет отдельный `demo-web/`: загрузка `.md`/`.txt`/текстового `.pdf`
до `640 KiB`, metadata и embeddings, `rag_ready`-обновление страницы, heartbeat/session registry, QR/логотипы и
browser call на существующую очередь FreeSWITCH `mod_callcenter`.

Вызовы остаются последовательными: один bot runtime получает caller ID из PJSUA2, выбирает подготовленный корпус и
загружает его между `180 Ringing` и `200 OK`; после terminal event корпус освобождается. Backend не создаёт вторую
очередь и не передаёт PCM через WebSocket. Локальный execution pass Map-021 выполнен: web sidecar, session-scoped
RAG, live Ollama/`embeddinggemma` preparation, mirrored WSL с прямой публикацией WSS/SIP/RTP на `192.168.1.74`,
локальный `mod_callcenter` prerequisite и typed caller-ID/readiness contracts подтверждены. Карта остаётся
`in_progress`: для внешнего телефона требуется elevated Hyper-V firewall rule и зарегистрированный browser →
`mod_callcenter` → one-bot trace с caller-ID/RAG correlation; локальный QR/IP позже заменяется финальным conference URL.
