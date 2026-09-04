# Map-002 (карта 4): реализация основной логики MVP

Уровень: `map`  
Статус: `in_progress` — owner review принят `2026-09-02`; базовый live SIP-to-AI path принят, J4 остановлен на обязательной scenario matrix  
Родительская supermap: [`roadmap.md`](../roadmap.md)

Дата подготовки: `2026-09-02`  
Календарная граница: сквозной рабочий демонстратор должен быть готов к `2026-09-20`.

Этот документ планирует карту 4 дорожной supermap. Он не является исполняемым child plan и не разрешает реализацию всех
перечисленных работ. Сначала согласуется структура карты, затем каждый child plan получает собственный APG и отдельный
owner review. До сборки компонентов сначала должна пройти отдельная под карта взаимодействий и boundary-контрактов
[`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md).

## 1. Цель и проверяемый результат

Собрать из подтверждённых feasibility-компонентов первый воспроизводимо запускаемый прикладной контур бота:

`SIP/RTP → PCMU → ASR/VAD/endpointing → Dispatcher/Dialogue FSM → context/KB/retrieval → Skill & Prompt Manager → LLM Facade → TTS/playback → PCMU`

Карта должна привести к рабочему демонстрационному сценарию на один параллельный разговор, включая barge-in,
продолжение контекста, обязательное получение релевантных фрагментов из локальной базы знаний (RAG) с передачей
source-aware `KnowledgeContext` в prompt, отсутствие ответа с предложением transfer, перевод на локального fake operator
и текстовый отчёт. Ответ, подготовленный только из встроенных знаний модели без подтверждённого локального контекста,
не считается успешным результатом карты. Проверки должны показывать, что обязательные протокольные реакции не ждут ASR, LLM, TTS или отчётность. BYE является
обязательным минимальным примером, но не ограничивает перечень проверяемых реакций: учитываются применимые `CANCEL`,
`OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume и RTP/media failure.

## 2. Граница карты

### Входит

- создание прикладного runtime и конфигурации MVP;
- построение topology взаимодействий, явных циклов и итерационного propagation contract-типов;
- интеграция принятого PJSUA2/PJMEDIA baseline с approved `001-S` peer/fake operator;
- Dispatcher, Dialogue FSM и control-plane контракты;
- прямые data-plane каналы для аудио и крупных текстовых payload;
- VAD, Transcript Assembler, soft/hard endpointing и partial/final ASR;
- authoritative LLM-путь через существующий Ollama HTTP IPC, context/KB и обязательный локальный RAG;
- Skill & Prompt Manager: выбор разрешённого skill/profile и сборка версионируемого `LlmRequest`;
- TTS, прямой playback, cancellation и barge-in;
- структурированные решения для ответа, уточнения, неизвестного ответа, transfer и завершения разговора;
- context snapshot и итоговый текстовый отчёт;
- минимальные contract/smoke/evidence-проверки каждого child plan и один сквозной integration slice.

### Не входит

- обучение, fine-tuning или замена утверждённых моделей без отдельного решения;
- новый SIP/RTP stack, реальный PBX или реальная операторская инфраструктура;
- запись аудио разговоров;
- более одного параллельного разговора;
- полноценный semantic turn detector и speculative LLM path в критическом demo-path;
- полноценный regression/load/MOS campaign и production hardening — это область последующих этапов supermap;
- скрытые fallback, compatibility bridge или намеренное ослабление acceptance.

### Protected baseline

- основной процесс — CPython `3.14.7t`/no-GIL;
- точные патчи C1/C2/C4 сохраняются и передаются в реализацию как обязательные ограничения;
- C3 работает отдельным локальным процессом Ollama через существующий HTTP IPC;
- Dispatcher владеет control plane и переходами Dialogue FSM, но не проксирует аудио и большие текстовые payload;
- SIP/media adapter самостоятельно выполняет обязательные протокольные реакции и не ждёт тяжёлую модель;
- только authoritative final ASR result может менять FSM и разрешать TTS;
- Skill & Prompt Manager не принимает SIP-решений: он получает разрешённый FSM-профиль, контекст и final user turn,
  формирует `LlmRequest` и не меняет смысл пользовательского текста;
- answer path обязан предъявлять source-aware `KnowledgeContext`; ответ только из встроенных знаний модели не считается
  выполнением RAG-требования;
- LLM выдаёт ограниченное structured decision и не получает произвольный SIP-доступ;
- PCMU/G.711 mu-law, 8 kHz, mono; один параллельный разговор;
- конфигурация MVP хранится в `config/constants.py`;
- локальный стенд `001-S` используется как единственный approved peer для этой карты.

## 3. Извлечённые правила APG и документов-владельцев

| Источник | Правило | Влияние на карту 4 | Проверка | Stop condition |
|---|---|---|---|---|
| [`roadmap.md`](../roadmap.md) | После 31 августа новые расширения не добавляются, если они не нужны обязательному demo-flow | Child plans обязаны сохранять deadline-critical scope | Scope review и map gate | В карту попала функция вне demo-flow без owner decision |
| [`requirements.md`](../requirements.md) | Один русский SIP-разговор, контекст, barge-in, transfer и отчёт | Эти возможности остаются acceptance boundary | Demo matrix и integration evidence | Child plan ломает обязательный пользовательский сценарий |
| [`architecture.md`](../architecture.md) | Control plane отделён от data plane; Dispatcher не переносит payload | Все каналы и ownership проектируются отдельно | Architecture invariant audit | Аудио/крупный текст передаются через Dispatcher или LLM получает SIP API |
| [`technical-specification.md`](../technical-specification.md) | PCMU, 30 ms RTP budget, config constants, persistence и no-GIL constraints | Контракты и evidence фиксируют эти значения явно | Contract/config/runtime checks | Скрытые defaults или другой media format подменяют baseline |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM предлагает решение, FSM исполняет | Все необратимые действия проходят через Dispatcher/FSM | Structured decision tests | LLM напрямую инициирует SIP action |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Free-threaded CPython — приоритет; несовместимые native-модули изолируются процессом | Используются принятые C1/C2/C4 patch/isolation decisions | Import/operation checks | GIL непреднамеренно включается или isolation вводится молча |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Map не разрешает исполнение child plans; каждый child plan самодостаточен | Для каждого child plan нужны scope, source-map, write-set, audits, blockers, tests и closeout | Map/child-plan audit | Child plan запускается без owner review |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Для сборки компонентов обязательны interaction topology и propagation контрактов | Сначала создаётся `Map-002-I`, затем после каждого component output обновляется contract revision и downstream tests | Boundary/contract audit | Компоненты интегрируются на неявных или устаревших типах |
| [`documentation-process.md`](../documentation-process.md) | У каждого факта один документ-владелец | Map хранит только планирование и ссылки, а не копирует требования/решения | Document registry и source-map review | Нормативная информация дублируется с другим владельцем |

## 4. Owner review

| Вопрос | Предлагаемое решение | Последствие | Статус |
|---|---|---|---|
| Является ли карта 4 map-level документом? | Да; она декомпозирует реализацию основной логики на self-contained child plans | Исполнение начинается только после согласования карты и каждого child plan | `resolved: owner review accepted 2026-09-02` |
| Нужна ли предварительная карта взаимодействий? | Да; `Map-002-I` сначала фиксирует topology, циклы и правила итерационного уточнения контрактов | `Map-002-I` согласована; component integration всё равно запрещена без актуальной contract revision | `resolved: Map-002-I accepted 2026-09-02` |
| Какой baseline использовать? | PJSUA2/PJMEDIA, approved `001-S`, PCMU, подтверждённые C1/C2/C3/C4 boundaries | Новый VoIP stack и новый IPC не выбираются в рамках карты | `resolved` |
| Где проходит payload? | Напрямую между владельцами data-plane каналов | Dispatcher передаёт только control events/commands | `resolved` |
| Как обрабатываются протокольные события во время тяжёлой операции? | SIP/media adapter отвечает немедленно, затем публикует нормализованное событие наверх, если оно меняет FSM | Поведение проверяется для всех применимых событий, BYE — минимальный smoke-кейс | `resolved` |
| Какой путь LLM критичен для демонстрации? | Authoritative final-turn path через Ollama HTTP IPC | Speculative path не блокирует карту и не меняет FSM | `resolved` |
| Нужен ли отдельный Skill & Prompt Manager? | Да; он выбирает разрешённый skill/profile и собирает версионируемый `LlmRequest` между context/FSM и `LLM Facade` | Prompt policy, latency и качество проверяются отдельно от transport/inference boundary | `resolved` |
| Обязателен ли RAG для демонстрационного answer path? | Да; локальный корпус, retrieval и source-aware context должны быть реально использованы в сценарии доклада | Model-only ответ не закрывает applicability claim; unknown-answer должен проверяться отдельно | `resolved` |
| Согласован ли child plan graph? | Да; состав `002-A`–`002-H` и `002-J`, зависимости и допустимый параллелизм приняты | Следующий gate — создание и отдельное owner review каждого child plan | `resolved: owner review accepted 2026-09-02` |
| Какая календарная граница карты 4? | Рабочий демонстратор должен быть готов к `2026-09-20`; 22–24 сентября — репетиции и резерв перед докладом | Integration/evidence gate должен завершиться не позднее 20 сентября | `resolved: owner review accepted 2026-09-02` |
| Можно ли безопасно распараллеливать работу? | Да для drafting, read-only analysis и disjoint write-set; зависимые integration gates и GPU-heavy прогоны последовательны | Каждый child plan явно указывает зависимости и write-set | `resolved; child-owned details` |
| Нужен ли successor plan для call-session composition gap? | Да; оформить как `002-I.0`, не `002-K`; переиспользовать существующие Dispatcher и DialogueFSM и добавить отдельный CallSession, сохранив один Dispatcher и один active call | J4 ждёт I.0 owner review и propagation | `resolved: owner decision 2026-09-03` |
| Когда карта считается закрытой? | После closeout всех обязательных child plans и прохождения map-level integration gate | Создание или частичное исполнение child plans не закрывает карту | `resolved` |

Owner review карты и её состава завершён. Создание child plans разрешено, но execution stage каждого из них начинается
только после собственного APG и отдельного owner review.

## 5. Почему это карта, а не узкий срез

Исходный «срез 4» объединяет несколько независимых execution boundaries: runtime/bootstrap, SIP/media, речевой вход,
Dispatcher/FSM, context, Skill & Prompt Manager, LLM Facade, TTS/playback, transfer/reporting и их сквозную интеграцию. Помимо списка узлов необходимо
описать весь граф их взаимодействий, типы на рёбрах и обратные события. У каждого направления свои владельцы поведения,
write-set, lifecycle каналов, тесты отмены, failure paths и критерии closeout.

Один исполняемый plan на весь этот объём скрывал бы архитектурные решения и не позволял бы отдельно остановить работу
при проблеме конкретного канала. Поэтому срез 4 повышается до карты 4, а реализация выполняется через под карту
взаимодействий и дочерние планы.

## 6. Под карта взаимодействий и дочерние планы

### 6.1. Обязательная под карта взаимодействий

[`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) является отдельным map-level
документом внутри карты 4. Сначала она фиксирует topology узлов, направленные и обратные рёбра, control/data plane,
циклы и candidate-типы. Затем она поддерживает итерационный propagation process: после каждого фактически проверенного
компонента его выходы инвентаризируются, сопоставляются с потребителями, а входные типы и contract tests передаются
следующей boundary.

Ни один child plan карты 4 не может считать boundary готовой только по названию компонента. Для каждого подключаемого
ребра должна существовать актуальная ревизия contract registry с producer, consumer, owner, lifecycle, cancellation,
backpressure, stale-result policy и failure semantics. Циклические связи (`SIP adapter ⇄ Dispatcher`, barge-in,
dialogue turn, transfer и channel lifecycle) регистрируются явно с termination и re-entrancy rules.

### 6.2. Карта дочерних планов

Имена ниже являются зарезервированными child plan-файлами. До owner review карты они не считаются созданными или
согласованными. Каждый файл должен содержать собственный APG, source-map/write-set, owner behavior audit, blocker
register, test/evidence plan, fallback/deferred register и closeout.

| ID | Child plan | Узкая цель | Зависит от | Допустимый параллелизм | Минимальный результат | Статус |
|---|---|---|---|---|---|---|
| `002-A` | `plan-002-A-application-runtime-skeleton.md` | Пакет приложения, `config/constants.py`, lifecycle, logging и базовые control events | `Map-002-I` I0, `001-A`, `001-B`, `001-D`, `001-E` | Первый execution baseline; drafting можно вести параллельно | Приложение запускается на `3.14.7t`, конфигурация читается из констант, lifecycle наблюдаем | `complete 2026-09-02` |
| `002-B` | `plan-002-B-sip-media-adapter.md` | PJSUA2/PJMEDIA adapter, SIP lifecycle, PCMU/RTP и protocol-event handling | `002-A`, актуальная ревизия `Map-002-I`, `001-C1`, `001-S` | После согласования A; contract tests можно готовить заранее | Вызов устанавливается/завершается, PCMU проходит, adapter не ждёт модель | `complete 2026-09-03; B3/B4 corrective pass and Map-I revision 4 recorded` |
| `002-C` | `plan-002-C-audio-boundary-buffering.md` | Media format/framer, PCM fan-out, bounded audio channels и ASR input accumulator/chunker с timer/flush | `002-B`, актуальная ревизия `Map-002-I` | Contract fixtures можно готовить параллельно с B; real-media execution — после B | `ptime`-кадры преобразуются в bounded ASR chunks без блокировки VAD и со штатным flush | `complete 2026-09-03; main audit и C→D propagation accepted in Map-I revision 5; downstream F propagation revision 6` |
| `002-D` | `plan-002-D-speech-ingress.md` | VAD, Turn Detector, Transcript Assembler и ASR partial/final | `002-C`, актуальная ревизия `Map-002-I`, `001-C2` | Deterministic ASR/VAD tests можно готовить параллельно с B/C; authoritative integration — после C propagation | Наблюдаем один authoritative final user turn без stale payload | `complete 2026-09-03; C→D corrective pass and D→E/F handoff accepted in revision 5; current downstream propagation revision 6` |
| `002-E` | `plan-002-E-dispatcher-dialogue-fsm.md` | Dispatcher, Dialogue FSM, control contracts, cancellation и protocol/application event routing | `002-A`, актуальная ревизия `Map-002-I`, `001-D`, `ADR-001` | FSM с deterministic adapters можно разрабатывать параллельно с B–D; integration handoff — после contract review | Допустимые состояния и transitions проверяются, LLM не получает SIP API | `complete 2026-09-03; E→F/G/H/J handoff accepted in revision 5; current downstream propagation revision 6` |
| `002-F` | `plan-002-F-skill-prompt-context.md` | Skill & Prompt Manager, context snapshot, curated KB, локальный RAG/index, prompt templates, generation profiles и `LlmRequest` | `002-D`, `002-E`, актуальная ревизия `Map-002-I`, `001-C3` | Corpus fixtures, index builder, prompt schema и deterministic retrieval tests можно готовить заранее; GPU embedding probe — последовательно | Финальный ход получает source-aware `KnowledgeContext`, а затем превращается в версионируемый валидный `LlmRequest` без скрытой подмены пользовательского текста | `complete 2026-09-03; deterministic, target no-GIL и real embedding/RAG evidence accepted` |
| `002-G` | `plan-002-G-llm-facade.md` | Внутренний typed `LLM Facade`, Ollama HTTP IPC, stream decoding, cancellation и structured answer decision | `002-F`, актуальная ревизия `Map-002-I`, `001-C3` | Facade/HTTP contract и deterministic response tests можно готовить параллельно с F; actual inference — main-only sequential | Фасад принимает только typed `LlmRequest`, возвращает typed stream/status/decision и не раскрывает Ollama API consumers | `complete 2026-09-03; deterministic, corrective config, real Ollama chat/embed и latency evidence accepted` |
| `002-H` | `plan-002-H-tts-output-playback-barge-in.md` | XTTS adapter, потоковые chunks, TTS output buffer/framer/pacer, playback, cancellation и barge-in | `002-B`, `002-E`, `002-G`, актуальная ревизия `Map-002-I`, `001-C4` | TTS contract tests можно готовить после фиксации channel contract; actual execution — после E/G propagation | Произвольные TTS chunks превращаются в paced media frames, playback останавливается при новой речи | `complete 2026-09-03; deterministic, XTTS/GPU, PCMU/RTP и barge-in evidence accepted` |
| `002-J` | `plan-002-J-transfer-report-integration.md` | Transfer на fake operator, context/report closeout и один сквозной demo-flow | `002-B`, `002-C`, `002-D`, `002-E`, `002-F`, `002-G`, `002-H`, актуальная ревизия `Map-002-I`, `001-S`, `002-I.0`, `002-I.1` | J1–J5 исполнены после upstream closeouts; full live evidence выполнено главным executor | Happy path, barge-in, unknown-answer/transfer и отчёт проходят на чистом запуске | `complete 2026-09-04; j4-full-live-20260904-r20, 6/6 checks` |
| `002-I.0` | `plan-002-I.0-call-session-orchestration-and-state.md` | Deterministic CallSession composition вокруг существующих Dispatcher/DialogueFSM и active-session slot | `002-A`–`002-H`, `Map-002-I`, J4 preflight | Owner review принят 2026-09-03; execution завершено в согласованном write-set | Deterministic one-call composition, typed lifecycle и обязательная финализация `report.md` переданы в successor I.1/J4; live SIP wiring не входит | `complete 2026-09-03` |
| `002-I.1` | `plan-002-I.1-live-call-asyncio-wiring.md` | Live wiring существующих typed input methods через основной asyncio loop | `002-A`–`002-H`, `002-I.0`, актуальная ревизия `Map-002-I`, `001-S` | Owner review принят; I1-1–I1-8 выполнены; live/GPU evidence выполнил main | Один live SIP/RTP вызов проходит SIP→speech/AI→paced playback, включая interruptions и report | `complete 2026-09-04; base r4 и corrective full matrix r20` |

Параллелизм ограничен write-set и контрактами: подготовка тестов, fixtures и документации может идти одновременно, но
один канал не считается интегрированным до его собственного lifecycle/cancellation evidence. GPU-heavy inference
прогоны не делегируются дочерним планам без отдельного решения основного исполнителя.

Текущая волна исполнения не нарушает propagation rule `Map-002-I`: C, D и E могли одновременно выполнять только
изолированные implementation slices и deterministic/unit/contract fixtures на текущей ревизии входных типов. Они не
передают соседям новые authoritative-типы, не собирают сквозной путь и не закрывают downstream boundary. После каждого
результата главный исполнитель проводит I1–I2: фиксирует фактические выходы, обновляет Map-002-I, выпускает новую
ревизию входного контракта и только затем разрешает зависимую интеграцию или corrective pass. F deterministic scope
принят main executor, Map-I обновлена до revision 6, и G теперь разрешён к изолированному execution по propagated
typed seam; реальный embedding/GPU probe остаётся последовательным main-only gate.
embedding/GPU и зависимая сборка выполняются последовательно.

## 7. Map-level gates и порядок переходов

| Gate | Условие открытия | Условие закрытия | Что запрещено до закрытия | Статус |
|---|---|---|---|---|
| `M4-G0` owner review карты | Создан этот map-file и обновлены ссылки supermap/registry | Owner подтвердил scope, boundary map, child plan graph, календарные границы и protected baseline | Создание execution-разрешений для child plans | `closed: owner review accepted 2026-09-02` |
| `M4-I-G0` topology/contract-map gate | `M4-G0` закрыт и создан `Map-002-I` | Owner подтвердил nodes, edges, cycles, candidate types и iterative propagation rules | Интеграция компонентов на неявных boundary | `closed: owner review accepted 2026-09-02` |
| `M4-G1` child-plan readiness | `M4-I-G0` закрыт | Для каждого исполнительного child plan `002-A`–`002-H`, `002-I.0`, `002-I.1` и `002-J` создан APG-файл с собственной acceptance, blockers, evidence root, write-set и ссылкой на актуальную contract revision | Исполнение child plan без отдельного review | `closed for created plans: A–H, I.0, I.1 и J owner review accepted; Map-I revision 21` |
| `M4-G2` runtime/control foundation | `002-A` согласован и исполнен; runtime/control contract propagated в Map-002-I | Runtime, config constants, lifecycle и базовые control events имеют evidence | Подключение тяжёлых моделей к незафиксированному lifecycle | `closed: 002-A complete 2026-09-02` |
| `M4-G3` media/speech/answer lanes | `002-B`–`002-G` прошли применимые child gates и contract propagation checkpoints | SIP/media, final user turn, RAG retrieval, prompt composition, structured LLM answer и context path работают по отдельности | Сквозной happy path до закрытия зависимых каналов | `closed for component lanes; 002-B–002-G complete, Map-I revision 21, real RAG/chat evidence accepted 2026-09-03` |
| `M4-G4` playback/interaction | `002-H` согласован и зависит только от закрытых контрактов | TTS playback, cancellation и barge-in имеют evidence | Объявление barge-in рабочим по unit-тесту без RTP smoke | `closed: 002-H complete; XTTS/GPU/RTP/barge-in evidence accepted 2026-09-03` |
| `M4-G5` карта 4 closeout | `002-I.0`, `002-I.1` и `002-J` согласованы и все обязательные child plans закрыты | Сквозной demo-flow и map-level evidence доступны; остатки переданы в map 5/backlog | Переход к расширенному тестированию после closeout | `pass: I.1/J4/J5 завершены; r20 6/6, B-002-J-004 и B-002-MAP-006 resolved` |

Закрытие карты 4 не означает завершение проекта или supermap. Карта 5 принимает её integration baseline для отдельного
регрессионного, latency и failure-path тестирования.

## 8. Source-map и write-set карты

На момент подготовки application source tree ещё не создан. Ниже зафиксированы разрешённые будущие области; фактические
пути и символы должны быть уточнены в каждом child plan до его execution stage.

| Область | Файл/компонент | Текущее состояние | Целевое состояние | Владелец изменений |
|---|---|---|---|---|
| Interaction topology/contracts | [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) и `artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/` | `Map-002-I` создана и согласована; implementation evidence root ещё не создан | Версионируемая topology, cycle register и propagation evidence | `Map-002-I` |
| Runtime/bootstrap | `src/`, `config/constants.py` | Исходного кода приложения нет | Запускаемый Python-пакет и конфигурация MVP | `002-A` |
| SIP/media | PJSUA2/PJMEDIA adapter и `001-S` peer | Feasibility/stand evidence pass | Application callback/media lifecycle | `002-B` |
| Speech ingress | ASR adapter, VAD, Transcript Assembler, endpointing | ASR baseline pass; application path отсутствует | Partial/final text data-plane channels и final-turn contract | `002-C` |
| Control plane | Dispatcher/Dialogue FSM и typed events | Архитектурный owner определён, runtime нет | Допустимые transitions, cancellation и semantic SIP commands | `002-E` |
| Skill/prompt/context | Skill & Prompt Manager, context files, curated KB, RAG index и prompt registry | Deterministic и real embedding/RAG evidence приняты | Source-aware `KnowledgeContext`, retrieval evidence, версионируемый `LlmRequest`, prompt/profile evidence и context continuation | `002-F` |
| LLM facade | C3 Ollama HTTP client, chat/stream и typed embedding operation | Real local HTTP boundary и structured chat evidence приняты; C3 isolation limitation сохранена | Typed stream/status/decision/embedding result без раскрытия Ollama API consumers | `002-G` |
| TTS/playback | XTTS-v2 adapter и playback channel | TTS baseline pass | Direct PCM/PCMU playback и barge-in cancellation | `002-H` |
| Call-session composition | Dispatcher, CallSession, DialogueFSM, runtime/channel lifecycle and context/report lifecycle | I.0 deterministic composition accepted; live SIP-to-AI input-method wiring remains outside materialized boundary | One-call typed composition and context/report lifecycle | `002-I.0`; live wiring выполняется в `002-I.1` |
| Transfer/report/integration | Fake operator, context snapshot, report и test harness | J1–J3, isolated J4 lanes и full live SIP→AI→SIP path pass; обязательная scenario matrix закрыта r20 | Transfer outcome и reproducible end-to-end evidence | `002-J`, `j4-full-live-20260904-r20`, complete |
| Evidence | `artifacts/implementation/002-mvp-media-and-speech-integration/` | Child roots `002-A`–`002-H`/`002-I.0` и `002-I.1` содержат base live evidence | Дополнить scenario matrix/J4 evidence, затем map closeout | Все child plans по своим root |

Разрешённый write-set карты: будущие `src/`, `config/`, `tests/`, application evidence root и зарезервированные child
plan-файлы. Запрещено молча менять `requirements.md`, `architecture.md`, `technical-specification.md`, принятые ADR,
исполненные планы `001-*` и их feasibility evidence. При изменении факта документы-владельцы обновляются отдельным
синхронизированным изменением.

## 9. Audit владельца поведения и парадигмы реализации

На map-level этот audit не закрывает конкретную реализацию: карта не добавляет public API и не меняет runtime behavior.
Для child plans заранее зафиксированы предполагаемые владельцы:

- SIP/media adapter владеет protocol-level reactions, media lifecycle и закрытием media resources;
- Dispatcher/Dialogue FSM владеет control-plane transitions и semantic SIP commands;
- каждый data-plane channel владеет своим lifecycle, cancellation и правилом закрытия;
- Transcript Assembler владеет сборкой partial/final текста, но не решением о SIP action;
- Skill & Prompt Manager владеет выбором skill/profile, сборкой `LlmRequest`, prompt versioning и diagnostics, но не
  переходами FSM или SIP action;
- Context/KB и retrieval boundary владеет corpus, chunking, index, query, source metadata, relevance threshold и
  unknown-context result; он не выдаёт model-only ответ за подтверждённый RAG.
- LLM Facade владеет только transport/inference request/response, stream cancellation и typed result mapping;
- playback channel владеет воспроизведением и отменой при barge-in;
- report builder владеет текстовым итогом и не создаёт аудиозаписи.

Каждый child plan обязан доказать этот ownership audit и не выносить component-specific semantics в свободный helper без
отдельного обоснования.

## 10. Process invariant audit

- Карта отделена от исполняемых child plans и не выдаёт создание файла за выполнение.
- До component integration существует отдельная interaction topology/cycle map с candidate contract registry.
- У каждого child plan будет собственный scope, source-map, write-set, acceptance, stop conditions, blocker register,
  test/evidence plan и closeout.
- После каждого component output обновляется contract revision и downstream contract tests; устаревшая ревизия не используется
  для сборки следующей boundary.
- Независимые drafting/test-preparation работы могут выполняться параллельно только при disjoint write-set.
- GPU-heavy inference и зависимые integration gates выполняются последовательно основным исполнителем.
- В roadmap, requirements, architecture и technical specification не копируются новые нормативные формулировки без
  необходимости; map хранит ссылки и планирование.
- После изменения Markdown запускаются `python tools/check_document_registry.py` и соответствующие проверки backlog.
- Deferred evidence не маскируется безымянными `skip`/`xfail`; каждая отложенная обязательная проверка получает owner,
  evidence и условие promotion.
- Молчаливое намеренное упрощение запрещено; согласованные cuts supermap остаются scope boundary.

## 11. Architecture invariant audit

- Dispatcher — единственный владелец control-plane transitions и semantic SIP commands.
- Каждое взаимодействие имеет явные plane, producer, consumer, owner, тип, lifecycle, cancellation, backpressure и failure
  semantics; циклические связи имеют termination и re-entrancy rules.
- SIP/media adapter не ждёт ASR, LLM, TTS или отчёт; обязательные реакции на `BYE`, `CANCEL`, `OPTIONS`,
  `re-INVITE`/`UPDATE`, hold/resume и media/transport failure обрабатываются на своём уровне.
- Аудио и крупные текстовые payload идут напрямую по data plane, не через Dispatcher.
- Закрытие канала делает stale result безвредным; закрытый канал не используется для нового поколения.
- Только authoritative final ASR result меняет FSM и разрешает TTS.
- Skill & Prompt Manager получает только разрешённые FSM skill/profile и формирует версионируемый `LlmRequest`; он не
  исполняет действия и не меняет смысл пользовательского текста.
- LLM Facade является единственным владельцем Ollama HTTP IPC и не принимает prompt policy или SIP-решения.
- RAG evidence обязано связывать ответ с локальными source IDs; отсутствие достаточного hit переводит answer path в
  unknown-answer/offer-transfer, а не в молчаливое использование pretraining.
- Speculative path, если появится вне critical demo-path, не может выполнить transfer, hangup или другое необратимое
  действие.
- TTS playback отменяется при barge-in, а новый ответ не смешивается со старым.
- LLM не получает произвольного доступа к SIP API.
- Native patch/isolation решения C1/C2/C3/C4 сохраняются в реализации и evidence.

## 12. Test plan и evidence

Каждый child plan фиксирует собственные тесты. На map-level обязательны следующие группы:

| Группа | Минимальное evidence |
|---|---|
| Boundary contracts | Topology всех узлов/рёбер, cycle register, contract registry revision и propagation checkpoint после каждого компонента |
| Runtime/control | Чистый запуск, config constants, lifecycle, допустимые transitions и повторное закрытие каналов |
| SIP/media | Установка/ответ/завершение вызова, PCMU/8000/1, RTP callbacks и protocol-event responsiveness во время ограниченной по времени работы |
| Speech | VAD flags, partial/final hypotheses, soft/hard endpoint, ровно один authoritative final turn |
| RAG | Offline corpus/index build, embedding query через Ollama или owner-approved retrieval baseline, top-k source IDs/scores, relevance threshold и unknown-answer negative case |
| Answer | Skill/profile selection, versioned `LlmRequest`, локальный RAG с source-aware `KnowledgeContext`, structured LLM action, context continuation и безопасное unknown-answer решение |
| Playback | Первый полезный TTS-фрагмент, прямой PCMU playback, остановка при barge-in и stale-generation suppression |
| Transfer/report | Явный запрос/подтверждение transfer на fake operator, context snapshot и итоговый `report.md` без аудиофайла проекта |
| Integration | Чистый запуск обязательного demo-flow на одном разговоре и сохранённые timestamps для последующего latency анализа |

Map-level evidence root: `artifacts/implementation/002-mvp-media-and-speech-integration/`. Под карта interaction map
использует `interaction-map/`; дочерние component roots — `002-A/`–`002-H/`, `002-I.0/`, `002-I.1/` и `002-J/`. Если проверка временно не выполняется, она получает стабильный `evidence_id`, owner, причину,
команду явного запуска и условие promotion; пропуск не считается pass.

## 13. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-MAP-001` | Map-002 | Карта 4 не прошла отдельный owner review | Создание execution-разрешений для initial child plans `002-A`–`002-H` и `002-J` | project owner | Этот документ, review package и map-level audit | `closed: initial graph owner review accepted 2026-09-02; I.0 has separate gate` |
| `B-002-MAP-002` | Map-002 | Не создана или не принята `Map-002-I` с topology, циклами и propagation rules | Сборка компонентов на типизированных boundary | project owner | `plan-002-I-boundary-interaction-map.md` и `M4-I-G0` | `closed: Map-002-I accepted 2026-09-02` |
| `B-002-MAP-003` | Map-002 | В answer path отсутствует source-aware RAG evidence или не принят embedding/retrieval baseline | Answer path gate и утверждение применимости технологии в докладе | project owner | `002-G/real-provider-probe.json`, saved index, source trace и `M4-G3` | `resolved — real embedding/index/query/chat evidence accepted 2026-09-03` |
| `B-002-MAP-004` | Map-002 | После J4 preflight отсутствовала утверждённая object model для call-session orchestration | J4 и карта 4 closeout | project owner | `002-J/j4-preflight.md`, Map-I revision 15, `002-I.0` | `resolved: I.0 complete and composition evidence accepted 2026-09-03` |
| `B-002-MAP-005` | Map-002 / J4 | Не доказан fresh live SIP/RTP full-flow через runtime wiring существующих typed input methods, соединяющее live `SipMediaAdapter` ingress/egress с speech/AI composition и paced TTS | Full J4, J5 и карта 4 closeout | project owner | [`002-J/j4-integration-gap.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-integration-gap.md), Map-I revision 21, `002-I.1` evidence | `resolved: base path r4; corrective full matrix r20` |
| `B-002-MAP-006` | Map-002 / J4/J5 | Обязательная clean-start scenario matrix не сведена в один acceptance gate после базового live path | Full J4, J5 и карта 4 closeout | project owner | `002-I.1` live evidence, J4 scenario matrix | `resolved: r20 6/6 checks, exit code 0; J5 synchronized` |

Child plans обязаны создать собственные blocker registers. Новая native incompatibility, нарушение control/data-plane
границ, неподтверждённая обязательная реакция или failure критического demo-flow немедленно блокируют зависимый child
plan до evidence-backed owner decision.

## 14. Реестр fallback и deferred

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| `none` | Новых fallback и намеренных упрощений карта не вводит | Согласованные cuts supermap уже являются scope boundary | `roadmap.md` и соответствующие будущие closeout | `none` |

Уже принятые process/native boundaries C1/C2/C3/C4 не считаются новым fallback этой карты: они являются входным
baseline и должны сохраняться без молчаливой замены.

## 15. Критерии закрытия карты и следующий переход

Карта 4 может получить статус `complete` только если:

- все обязательные child plans прошли отдельный owner review и имеют closeout;
- все исполнительные child plans `002-A`–`002-H` и `002-J` предоставили наблюдаемое evidence своих каналов, lifecycle,
  cancellation и, для `002-F`, prompt/profile contract;
- `Map-002-I` имеет принятую topology, cycle register и contract registry, а propagation checkpoint зафиксирован после каждого компонента;
- `002-J` прошёл единый полный clean-start demo-flow: J1–J3, isolated J4 lanes, базовый live SIP/RTP path и full
scenario matrix barge-in/follow-up/unknown-answer/transfer/report приняты в r20;
- demo-flow содержит хотя бы один ответ с подтверждёнными source IDs локальной базы и отдельный неизвестный вопрос,
  не замаскированный встроенными знаниями модели;
- обязательные протокольные реакции проверены не только на `BYE`, но и на применимых остальных событиях;
- документы-владельцы, document registry, task backlog и evidence index синхронизированы;
- остаточные latency, quality, regression и production gaps переданы в следующую карту или backlog.

Следующий переход — карта 5 из supermap: системное тестирование и исправления. Она не стартует до closeout карты 4,
если owner отдельно не согласует независимую проверку, не изменяющую её write-set.

Текущий статус карты: `complete`; initial owner review child plans A–H/J принят, successor `002-I.0` и `002-I.1`
прошли собственные closeout, `002-A`–`002-H` и `002-J` закрыты статусом `complete`. Map-I revision 21 содержит
propagation checkpoints A–H, I.0 и I.1, owner decision по object model, real RAG/chat, real ASR/VAD/endpointing,
RTP/playback и full live scenario evidence.
`002-J` закрыл `B-002-J-004` и `B-002-MAP-006` прогоном `j4-full-live-20260904-r20`: один clean-start call доказал
follow-up, barge-in, unknown-answer/transfer, report и SIP/RTP path. Карта 4 закрыта; остатки переданы в карту 5 и
backlog.
