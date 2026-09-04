# Map-002-I: карта взаимодействий и контрактов карты 4

Уровень: `map`  
Статус: `complete`  
Owner review: `accepted` — owner review принят `2026-09-02`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Родительская supermap: [`roadmap.md`](../roadmap.md)

Дата подготовки: `2026-09-02`  
Ревизия: `21` — owner decisions по media profile, event bus, VAD, RAG и asyncio/thread exchange уточнены `2026-09-03`; propagation checkpoints
`002-A` и `002-B` приняты `2026-09-03`, `002-C`/`002-D`/`002-E` propagated, `002-F`/`002-G`/`002-H` реализованы
и приняты main executor `2026-09-03`; real embedding/RAG, latency и RTP/playback evidence закрыты. После owner
 decision `2026-09-03` создан successor plan `002-I.0` для call-session orchestration и композиции существующих owners;
I.0 deterministic composition и real component evidence приняты `2026-09-03`; J4 component/composition lanes прошли
clean-start, но application runtime wiring живых рёбер не выполнен. Для этого подготовлен successor plan `002-I.1`,
owner review которого принят `2026-09-03`, execution начат; deterministic runtime wiring и real AI composition
checkpoint добавлены в `002-I.1` evidence; свежий базовый live SIP/RTP full-flow принят по `live-gate-20260903-r4`,
а полная scenario matrix и J4/J5 closeout приняты по `002-J/j4-full-live-20260904-r20`.

Этот документ является обязательной под картой карты 4. Он описывает topology взаимодействий, циклы и правила
итерационного уточнения boundary-контрактов. Он не реализует компоненты и не фиксирует окончательные Python-типы до
получения фактических выходов соответствующего компонента.

## 1. Цель и результат

До сборки компонентов получить явную карту того, кто с кем взаимодействует, по какому plane, в каком направлении и с
какой ответственностью. Затем, по мере появления каждого компонента, уточнять типы его выходов, сопоставлять их со
входами потребителей, создавать contract tests/stubs и выпускать новую ревизию карты контрактов.

Результатом являются:

- topology всех узлов и направленных рёбер карты 4;
- явный register циклических взаимосвязей и правил возврата событий/команд;
- реестр candidate-контрактов с producer, consumer, owner, lifecycle, cancellation, backpressure и failure policy;
- итерационный порядок propagation контрактов от фактически проверенного компонента к его потребителям;
- contract fixtures и evidence, показывающие, что интеграция не собирается на несовместимых предположениях.

## 2. Граница

### Входит

- SIP/media, audio, VAD, Turn Detector, ASR, Transcript Assembler, Dispatcher/Dialogue FSM, context/KB,
  local RAG retrieval/embedding boundary, Skill & Prompt Manager, LLM, TTS,
  playback, transfer и report boundaries;
- разделение control plane и data plane для каждого ребра;
- типизация потоков, сообщений, событий, команд и результатов отмены;
- lifecycle channel, закрытие, stale-result policy, backpressure и re-entrancy;
- двунаправленные рёбра и циклы, возникающие при protocol events, barge-in, cancellation, transfer и multi-turn context;
- правила обновления контрактов после каждого реализованного/проверенного компонента.

### Не входит

- реализация самих компонентов;
- выбор нового SIP/RTP stack или новой модели;
- окончательная реализация всех Python-классов до появления component evidence;
- молчаливое превращение candidate-типа в принятый контракт;
- пропуск boundary-map под предлогом того, что компоненты «соединяются очевидно».

### Protected baseline

- Dispatcher владеет control plane, но payload не проходит через него;
- SIP/media adapter самостоятельно отвечает на `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume и
  media/transport failure;
- закрытие канала прекращает доставку stale payload; отдельные поколения не обязательны;
- только authoritative final ASR result может изменить FSM и разрешить TTS;
- Skill & Prompt Manager отдельно собирает версионируемый prompt из финального хода, контекста/знаний и разрешённого
  FSM-профиля; пользовательский текст не подменяется молча;
- RAG answer path использует source-aware `KnowledgeContext`; model-only ответ не является заменой retrieval evidence;
- LLM выдаёт structured decision, а не произвольную SIP-команду;
- C3 остаётся отдельным Ollama process через HTTP IPC;
- PCMU/G.711 mu-law, внутренний PCM S16LE mono 8 kHz и один параллельный разговор.

## 3. Извлечённые правила

| Источник | Правило | Следствие для этой карты | Проверка |
|---|---|---|---|
| [`architecture.md`](../architecture.md) | Control/data plane разделены, Dispatcher не переносит payload | Каждое ребро получает plane и владельцев producer/consumer | Topology и architecture audit |
| [`technical-specification.md`](../technical-specification.md) | Каналы ограничены, имеют lifecycle и cancellation | В contract registry обязательны close/backpressure/stale-result поля | Contract fixtures и close/re-close tests |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM предлагает, FSM исполняет | Structured decision возвращается в control plane, SIP action проходит через FSM | Decision validation test |
| [`ADR-003`](../decisions/ADR-003-free-threaded-python.md) | Native boundaries проверяются и изолируются явно | Process edge C3 описывается как отдельный boundary, не скрывается в adapter | Import/operation evidence |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Для сборки нескольких компонентов обязателен interaction topology и propagation контрактов | Ни один component child plan не стартует без актуальной ревизии этой карты | Map/child-plan gate |

## 4. Узлы topology

| ID | Узел | Владелец поведения | Основные выходы | Основные входы |
|---|---|---|---|---|
| `N1` | SIP/media adapter | SIP/media adapter | protocol events, call events, PCMU/RTP frames, media failures | SIP commands, media lifecycle commands, paced PCM |
| `N2` | Media format adapter и ptime framer | media format owner | `PcmFrame` media `ptime`, PCMU/RTP egress | PCMU/RTP ingress, paced PCM egress |
| `N3` | PCM fan-out и bounded audio channels | channel owner | bounded PCM streams для VAD и ASR boundary, channel events | `PcmFrame`, open/close/reconfigure |
| `N4` | ASR input accumulator/chunker | ASR input boundary owner | `AsrAudioChunk`, flush/overrun events | media `PcmFrame`, timer, endpoint/close/cancel |
| `N5` | VAD | VAD | `VadDecision`, speech events | `PcmFrame` |
| `N6` | Turn Detector/endpointing | endpointing owner | turn-boundary events | `VadDecision`, speech lifecycle |
| `N7` | Streaming ASR | ASR adapter | `AsrHypothesis` partial/final, ASR errors | `AsrAudioChunk`, cancel/close |
| `N8` | Transcript Assembler | Transcript Assembler | stable text, `FinalUserTurn` | ASR hypotheses, endpoint events |
| `N9` | Main Dispatcher/Dialogue FSM и process-local Control Event Bus | Dispatcher/FSM + control bus | channel/control commands, approved actions, context lifecycle, typed control fan-out | normalized protocol/application events, structured decisions |
| `N9a` | `CallSession` / active-call composition object | Dispatcher/application composition | session lifecycle, scoped component handles, cancellation/generation and context/report hooks | Dispatcher control, SIP/media events and component results |
| `N10` | Context store и curated KB/retrieval coordinator | context owner | `ContextSnapshot`, `KnowledgeQuery`, report input | finalized turns, state/close events |
| `N10a` | Skill & Prompt Manager | prompt/skill owner | versioned `LlmRequest`, prompt diagnostics | final user turn, context/knowledge, FSM-approved skill/profile |
| `N10b` | Local retrieval index / embedding adapter | retrieval boundary owner | `KnowledgeHit`, `KnowledgeContext`, index evidence | `KnowledgeQuery`, corpus chunks, embedding results |
| `N11` | LLM Facade | local inference facade owner | internal stream events, `StructuredDecision`, answer text, inference status, embedding results | typed `LlmRequest`, `EmbeddingRequest`, cancellation/control |
| `N12` | Ollama inference process | Ollama/HTTP boundary owner | external JSON/stream response | facade HTTP request/cancel |
| `N13` | TTS adapter | TTS adapter | arbitrary-size `TtsPcmChunk`, TTS status | approved answer text, cancellation |
| `N14` | TTS output buffer/framer/pacer | playback boundary owner | paced `PcmFrame` с media `ptime`, flush/cancel status | arbitrary TTS PCM chunks, media clock, playback cancellation |
| `N15` | Playback channel | playback owner | playback status, cancellation outcome | paced `PcmFrame`, playback commands |
| `N16` | Fake operator / transfer peer | local test stand | transfer result, remote protocol events | transfer signaling |
| `N17` | Context snapshot/report builder | report builder | `report.md` | bounded context, terminal outcome and approved report inputs |

Узел может быть реализован несколькими потоками или процессами, но process boundary сам является отдельным boundary и
не отменяет типизацию сообщений по обе стороны.

## 5. Первоначальная карта рёбер

Это topology-карта, а не окончательный API. В колонке «Candidate type» намеренно указаны типы-кандидаты; authoritative
тип появляется после component evidence и propagation checkpoint.

| Edge | Направление | Plane | Candidate type | Producer → consumer | Обязательная семантика |
|---|---|---|---|---|---|
| `E1` | `N1 → N9` | control | `NormalizedSipEvent` | SIP adapter → Dispatcher | Нормализовать событие, не задерживать локальный SIP-ответ |
| `E2` | `N9 → N1` | control | `SipCommand` | Dispatcher → SIP adapter | Только FSM выдаёт semantic `answer`/`hangup`/`transfer`/media commands |
| `E3` | `N1 → N2` | data | `PcmuRtpFrame` | media → format adapter | PCMU payload/sequence/timestamp сочетаются с per-call profile из SDP/PJMEDIA |
| `E3a` | `N1 → N2` | control | `NegotiatedMediaProfile` | SIP/media adapter → format adapter | Codec, payload type, `ptime`, rate, channels и frame size извлекаются для конкретного звонка; hard-coded 20 ms запрещён |
| `E4` | `N2 → N3` | data | `PcmFrame` | format adapter → PCM fan-out | Внутренний PCM frame использует актуальный per-call media profile |
| `E5` | `N3 → N5` | data | `PcmFrame` | PCM fan-out → VAD | VAD получает кадры без ожидания ASR chunk |
| `E6` | `N3 → N4` | data | `PcmFrame` | PCM fan-out → ASR accumulator | Bounded input, timer/flush и discard policy явны |
| `E7` | `N4 → N7` | data | `AsrAudioChunk` | accumulator → ASR | Media frames собираются в настраиваемый ASR chunk; hard endpoint flush-ит остаток |
| `E8` | `N5 → N6` | control/data | `VadDecision` | VAD → endpointing | Фрейм, confidence/decision и timestamp должны быть согласованы |
| `E9` | `N6 → N8` | control | `EndpointEvent` | endpointing → assembler | Soft/hard endpoint и resume должны быть различимы |
| `E10` | `N7 → N8` | data | `AsrHypothesis` | ASR → assembler | Partial/final revision не накапливается как независимый текст |
| `E11` | `N8 → N10a` | data | `FinalUserTurn` | assembler → Skill & Prompt Manager | Только authoritative final turn запускает обязательный answer path |
| `E12` | `N8 → N9` | control | `UtteranceFinalized` / `SpeechEvent` | assembler → FSM | FSM получает только события, нужные для перехода состояния |
| `E13` | `N10 → N10a` | data | `ContextSnapshot` | context store → Skill & Prompt Manager | Контекст имеет границу размера и сохраняемую ревизию |
| `E14` | `N11 → N12` | data/control | `LlmRequest` / `EmbeddingRequest` / `CancelRequest` | LLM Facade → Ollama | Единственный внешний process boundary, mapping timeout/cancel обязателен |
| `E15` | `N12 → N11` | data/control | `LlmStreamEvent` / `EmbeddingResponse` / `InferenceStatus` | Ollama → LLM Facade | Внешний JSON/stream преобразуется во внутренние typed events |
| `E16` | `N11 → N9` | control | `StructuredDecision` | LLM Facade → Dispatcher | Валидируется до любого необратимого действия |
| `E17` | `N11 → N13` | data | `AnswerTextChunk` | LLM Facade → TTS | Передача разрешается соответствующим control event, Dispatcher не проксирует текст |
| `E18` | `N9 → N13` | control | `TtsCommand` / `AnswerApproval` | FSM → TTS | Открыть/закрыть поток и разрешить озвучивание |
| `E19` | `N13 → N14` | data | `TtsPcmChunk` | TTS → output buffer | Размер входного chunk не обязан совпадать с media `ptime` |
| `E20` | `N14 → N15` | data | `PcmFrame` | output buffer → playback | Re-frame и pacing выполняются по media clock |
| `E21` | `N9 → N15` | control | `PlaybackCommand` / `ChannelClose` | FSM → playback | Close идемпотентен, stale chunks не доставляются |
| `E22` | `N15 → N9` | control | `PlaybackEvent` | playback → FSM | Started/stopped/failed/cancelled меняют только разрешённые состояния |
| `E23` | `N15 → N2` | data | `PcmFrame` | playback → media egress | PCM → PCMU выполняется format/media layer |
| `E24` | `N2/N3 → N9` | control | `SpeechEvent` / `MediaFailure` | media/audio boundary → FSM | `barge_in`, RTP timeout и media failure должны быть наблюдаемы |
| `E25` | `N9 → N10` | control/data | `TurnRecord` / `StateEvent` | FSM → context store | Контекст сохраняется в процессе, не только в конце звонка |
| `E26` | `N10 → N17` | data | `ContextSnapshot` / `TerminalOutcome` | context → report | Итоговый отчёт текстовый, аудио проектом не создаётся |
| `E27` | `N9 → N17` | control | `ReportCommand` | FSM → report builder | Запускать после normal hangup или transfer |
| `E28` | `N9 → N16` | control | `TransferCommand` | FSM/SIP adapter → fake operator | Transfer только явный и подтверждённый |
| `E29` | `N16 → N1/N9` | control | `TransferResult` / `ProtocolEvent` | fake operator/SIP → adapter/FSM | Результат transfer и terminal protocol event не теряются |
| `E30` | любой producer → channel owner | control | `Cancel` / `Close` | owner → producer/consumer | Закрытие отбрасывает stale payload и не требует поколений |
| `E31` | `N9 → N10a` | control | `SkillSelection` / `PromptPolicy` | FSM → Skill & Prompt Manager | FSM разрешает skill, generation profile и ограничения ответа; менеджер не меняет переход состояния |
| `E32` | `N10a → N11` | data/control | `LlmRequest` | Skill & Prompt Manager → LLM Facade | Версия шаблона/profile, output schema и границы пользовательских данных сохраняются в запросе |
| `E33` | `N9 ⇄ N9a` | control | `ControlMessage` / `SessionLease` | Dispatcher ⇄ CallSession | Dispatcher создаёт и закрывает один session scope, CallSession маршрутизирует только typed control; data payload не проходит через boundary |
| `E38` | `N9 → N11` | control | `LlmControl` / `CancelRequest` | FSM → LLM Facade | Отмена и закрытие inference не ждут завершения генерации |
| `E34` | `N10 → N10b` | data/control | `KnowledgeQuery` / `CorpusChunk` | context/KB coordinator → retrieval index | Runtime query и offline indexing явно различаются; corpus не читается Ollama сам по себе |
| `E35` | `N10b → N11` | data/control | `EmbeddingRequest` | retrieval index → LLM Facade | Embedding-вызов использует typed operation фасада, а не прямой HTTP из retrieval-кода |
| `E36` | `N11 → N10b` | data | `EmbeddingResponse` | LLM Facade → retrieval index | Ответ `/api/embed` преобразуется и проверяется до similarity search |
| `E37` | `N10b → N10a` | data | `KnowledgeContext` / `KnowledgeHit` | retrieval index → Skill & Prompt Manager | Передаются top-k, scores, source IDs и признак достаточности контекста |

## 5.1. Явные преобразования и накопители на границах

| Boundary | Входная гранулярность | Состояние boundary | Выходная гранулярность | Владелец времени/flush |
|---|---|---|---|---|
| `B1` media → internal PCM | PCMU/RTP и callback frame по per-call profile из SDP/PJMEDIA | format state, sequence/timestamp и bounded frame buffer | PCM S16LE mono 8 kHz media frames с profile metadata | Media format adapter/media clock |
| `B2` PCM → ASR | media frames с per-call `ptime` | ASR accumulator, bounded storage, target size и flush timer | `AsrAudioChunk` (начальный target около 1 s) | ASR input accumulator |
| `B3` TTS → playback | произвольные потоковые `TtsPcmChunk` | output buffer, tail state, cancellation и pacing clock | PCM media frames по тому же per-call `ptime` | TTS output framer/pacer |
| `B4` Ollama → internal LLM API | внешний HTTP JSON/stream chunks | stream decoder, request lifecycle, timeout/cancel state | typed `LlmStreamEvent`, `StructuredDecision`, status | LLM Facade |
| `B5` dialogue/context → LLM request | `FinalUserTurn`, `ContextSnapshot`, `KnowledgeContext`, `SkillSelection` | template/profile registry, prompt version, output schema и delimiters пользовательских данных | typed `LlmRequest` | Skill & Prompt Manager |
| `B6` query → retrieval context | пользовательский вопрос и query context | query embedding, local vector index, similarity scoring и relevance threshold | source-aware `KnowledgeHit` / `KnowledgeContext` | Local retrieval index / embedding adapter |

Для `B2` VAD получает media frames напрямую и не ждёт заполнения ASR chunk. При достижении target size или истечении
flush timer accumulator выдаёт chunk; при hard endpoint, close или cancellation выдаётся укороченный остаток. Для `B3`
неполный хвост выдаётся только по явному правилу завершения, а при barge-in отбрасывается. В этих границах обычная
очередь является лишь внутренним примитивом bounded delivery и не заменяет stateful accumulator, timer, re-framer или
pacer.

## 6. Явные циклы и их условия завершения

| Cycle | Цепочка | Что возвращается | Условие завершения |
|---|---|---|---|
| `C1` | `N1 ⇄ N9` SIP lifecycle | `ProtocolEvent` наверх, `SipCommand` вниз | Terminal call state и закрытие всех call channels; локальная SIP-реакция не ждёт обратного события |
| `C2` | `N2 → N3 → N4/N5/N6/N7/N8 → N9 → N15 → N2` barge-in | Speech event закрывает playback, playback отдаёт cancellation outcome | Playback channel закрыт, новый user turn получил новый входной канал |
| `C3` | `N8 → N10a → N11 → N12 → N11 → N9 → N10/N13 → N9` dialogue turn | Decision, context update, answer approval и playback status | Финализирован answer outcome или terminal/cancel event |
| `C4` | `N9 → N1 → N16 → N1/N9` transfer | Transfer result и новые protocol events | Fake operator подтверждён либо transfer завершён ошибкой/отменой |
| `C5` | `N9 ⇄ N2/N3/N4/N7/N13/N14/N15` channel lifecycle | Open/reconfigure/close и status events | Channel закрыт идемпотентно, producer/consumer остановлены |
| `C6` | `N10 → N10a → N11 → N12 → N11 → N9 → N10` context/inference | Context snapshot и skill/profile на входе, structured result через FSM и обновление context на выходе | Inference завершён, отменён или признан stale; результат закрытого канала не публикуется |
| `C7` | `N10 → N10b → N11 → N12 → N11 → N10b → N10a` RAG query | Query embedding, source-aware hits и relevance decision | Контекст найден, признан недостаточным, отменён или завершён ошибкой; непроверенный model-only answer не маркируется RAG |

Каждый cycle получает в contract registry владельца termination condition, направление cancellation и правило
re-entrancy. В частности, remote `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume и RTP/media failure
могут прийти внутри любого цикла и не должны превращаться в ожидание завершения LLM/TTS.

## 7. Итерационный propagation-процесс

Работа выполняется волнами. Между волнами карта контрактов получает ревизию; старые candidate-типы не считаются
действующими после изменения authoritative producer.

1. **I0 — topology baseline.** Зафиксировать узлы, рёбра, control/data plane и циклы из этого документа. Указать
   candidate-типы и неизвестные поля, не выдавая их за API.
2. **I1 — первый component output.** После проверки первого компонента записать фактические выходы: тип, формат,
   единицу времени/размер фрейма, lifecycle, ошибки и cancellation. Сопоставить каждый выход с потребителями.
3. **I2 — input propagation.** Для каждого потребителя обновить входной contract, создать stub/fixture и contract test.
   Если consumer не может принять output без преобразования, преобразование становится явным adapter boundary.
4. **I3 — next component.** Реализовать/проверить следующий компонент только на актуальной ревизии входов. Его выходы
   снова проходят I1–I2.
5. **I4 — cycle review.** После появления обратного события или команды обновить cycle register: termination,
   cancellation, re-entrancy и поведение при terminal event во время другого действия.
6. **I5 — integration handoff.** Только после закрытия контрактов конкретного набора рёбер разрешить их сквозную сборку.

Рекомендуемый порядок authoritative outputs: `N1/N2` media, `N3/N4/N5/N6` speech, `N7` control, `N8/N9/N10` context,
`N10b` retrieval/embedding, `N10a/N11/N12` LLM, `N13/N14/N15` TTS/playback, затем `N16/N17` transfer/report/integration. Deterministic stubs и контрактные тесты для
независимых рёбер можно готовить параллельно; фактический GPU inference и зависимая сборка идут последовательно.

## 8. Реестр контрактов

Для каждого ребра ведётся строка минимум с такими полями:

| Поле | Смысл |
|---|---|
| `contract_id` и `revision` | Стабильная идентификация и версия boundary |
| `producer`, `consumer`, `owner` | Кто формирует, читает и отвечает за semantics |
| `plane`, `transport` | Control/data и конкретный channel/process/HTTP boundary |
| `type/schema` | Фактический тип или candidate с явным статусом |
| `stream/message/event` | Способ доставки и граница фрейма |
| `input/output framing` | Гранулярность входа и выхода, unit/size, преобразование и допустимый tail |
| `buffer/timer/clock` | Где хранится состояние, кто владеет bounded storage, flush timer и pacing clock |
| `lifecycle` | Open, active, close, re-close и terminal semantics |
| `backpressure` | Ограничение очереди и реакция на отставание consumer |
| `cancellation` | Кто и как прекращает producer/consumer |
| `stale policy` | Что происходит с данными закрытого канала |
| `failure` | Ошибка, timeout, protocol event и recovery handoff |
| `evidence` | Fixture, contract test, smoke или runtime evidence |

Реестр хранится в evidence root карты: `artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/`.
После появления application source tree его зеркальная machine-readable форма может быть вынесена в `src/contracts/`,
но владельцем нормативного contract registry остаётся map-level документ/его evidence, пока отдельным решением не
назначен другой владелец.

Для LLM/RAG-boundary в реестре отдельно фиксируются `SkillSpec`, `PromptSpec`, `GenerationProfile`, `KnowledgeQuery`,
`EmbeddingRequest`, `EmbeddingResponse`, `KnowledgeHit`, `KnowledgeContext`, `LlmRequest` и `PromptDiagnostics`.
Минимально в `KnowledgeContext` должны быть source IDs, исходные фрагменты, scores и признак достаточности. В
`LlmRequest` должны быть `call_id`, `turn_id`, `skill_id`, версии шаблона/profile и output schema, ссылки на
knowledge context, финальный пользовательский текст, ограничения длины/формата ответа и маркер
authoritative/speculative режима. Это candidate-схемы до component evidence, а не преждевременный public API.

### 8.1. Propagation checkpoint `002-A`

`002-A` materialized и проверил runtime-to-control foundation на целевом executable
`/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` в Ubuntu-24.04/WSL2. Evidence находится в
`artifacts/implementation/002-mvp-media-and-speech-integration/002-A/` и включает contract fixture, lifecycle traces,
target runtime probe и target unit/contract test run.

Authoritative output этого checkpoint-а — control-only envelope `ControlEvent` со следующими полями:

- `kind`: `call_open`, `call_close`, `channel_open`, `channel_close` или `terminal`;
- `call_id`, optional `channel_id` и optional `channel_generation` с согласованной областью действия;
- monotonic runtime-local `sequence` и наблюдение `timestamp_ns`;
- immutable typed `payload`: `CallOpen`, `CallClose`, `ChannelOpen`, `ChannelClose` или `Terminal`;
- `ControlEventSink` как минимальная boundary для будущего Dispatcher/FSM, без subscription semantics в этом checkpoint-е.

Зафиксированные lifecycle semantics: один active call, scoped channel handles, idempotent close/re-close, cancellation
при закрытии, новые channel generations после переоткрытия и discard stale dispatch с закрытого старого handle. Terminal
event публикуется до закрытия scoped channels и call. Аудио, крупный текст, ASR/TTS streams и RAG fragments этим
контрактом не переносятся.

Этот checkpoint уточняет внутренний runtime/control contract и не объявляет готовыми SIP/media edges `E1`–`E4` или
Dispatcher/event-bus semantics `N9`; они передаются следующим child plans и проходят собственные propagation gates.

### 8.2. Propagation checkpoint `002-B`

`002-B` materialized SIP/media boundary на target runtime Ubuntu-24.04/WSL2,
user `sipbot`, executable
`/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`, с PJSUA2/PJMEDIA `2.17`
и approved Baresip peer из `001-S`. Полный contract/evidence record находится в
[`propagation-002-B.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-B.md).

Authoritative output `002-B` для edges `N1 → N2`, `N2 → N3` и
`N2/N3 → N9`:

- active audio выбирается из фактического `CallInfo.media`; его
  неотрицательный `CallMediaInfo.index` сохраняется в call scope и передаётся
  одинаково в `getStreamInfo(index)` и `getAudioMedia(index)`. Wildcard `-1`
  для profile extraction запрещён;
- `NegotiatedMediaProfile` публикует на каждый звонок codec/payload types,
  `ptime_ms`/`frame_time_usec`, sample rate, channels, PCM bits и frame
  dimensions. На принятом stand подтверждены PCMU, payload `0`, 20 ms,
  8 kHz, mono, 160 samples и 320 bytes S16LE;
- `PcmFrame` переносит `call_id`, `channel_id`, `generation`, sequence,
  `timestamp_ns`, PCM S16LE bytes и negotiated profile. Ingress и egress
  обслуживаются двумя bounded direct channels внутри `PcmAudioBridge`; audio
  payload не проходит через Dispatcher/event bus;
- media events содержат выбранный `media_index`; transport events уже несут
  соответствующий media index. Local SIP/protocol reply выполняется в
  adapter и не ждёт Dispatcher/AI;
- media-state/re-INVITE с изменением profile/index создаёт новую bridge
  generation. Close, remote BYE, transport/media failure останавливают оба
  направления, закрывают каналы и release-ят native media port до endpoint
  teardown; stale generation не доставляется новому consumer.

Verified evidence: B3 corrective target rerun `1 passed, 2 deselected`, full
target B integration `3 passed`, а remote-BYE application run зафиксировал 10
ingress и 10 egress frames без callback errors или queue drops. Это передаёт
фактический контракт в `002-C`; собственные conversion/re-framing/timer tests
`002-C` остаются обязательными.

### 8.3. Propagation checkpoint `002-C` → `002-D`

`002-C` принят main executor `2026-09-03` на основании closeout, target/live
evidence и повторного host-прогона. Для рёбер `N3 → N5`, `N3 → N4` и
`N4 → N7` authoritative стали следующие границы:

- `PcmFrame` передаётся напрямую в независимые bounded subscriptions `vad` и
  `asr_input_accumulator`; переполнение одного consumer не блокирует другой;
- `AsrAudioChunk` имеет единственный источник истины
  `sip_bot.media.asr_chunker.AsrAudioChunk`. Он несёт
  `call_id/channel_id/generation`, sequence/timestamp, PCM S16LE, полный
  `NegotiatedMediaProfile`, `FlushReason` и `is_final`;
- target/timer/hard-endpoint/close/cancel semantics и bounded overflow являются
  частью boundary, а не внутренней деталью ASR.

При I1 была обнаружена и исправлена ошибка propagation: в D существовал второй
одноимённый `AsrAudioChunk` с несовместимой схемой. Speech layer теперь
переиспользует тип C; явный contract-тест проверяет identity типа и передачу
живого chunk в `StreamingAsrAdapter`. Это corrective pass D, зафиксированный в
[`propagation-002-C.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-C.md).

### 8.4. Propagation checkpoint `002-D` → `002-E`/`002-F`

`002-D` принят main executor `2026-09-03`. Фактические speech outputs:

- `VadDecision` (`N5 → N6`) содержит исходный lifecycle scope, sequence,
  timestamp, duration, decision/confidence и source;
- `EndpointEvent` (`N6 → N8`) различает speech start, pause candidate, soft
  endpoint, resume и authoritative hard endpoint; hard endpoint — единственное
  основание финализации;
- `AsrHypothesis` (`N7 → N8`) является revisioned speculative data, а
  `TranscriptUpdate` — snapshot стабильного префикса и изменяемого хвоста;
- `FinalUserTurn` (`N8 → N10a`) является единственным authoritative текстовым
  payload с `call_id/channel_id/generation/turn_id`, revision, timestamp и
  `hard_endpoint` boundary.

В control plane для FSM передаётся только небольшое speech lifecycle event
(`SpeechEvent`, включая `hard_endpoint`/`barge_in`). Сам `FinalUserTurn` не
публикуется в Event Bus: он передаётся в FSM отдельным typed data-plane
входом, а тот же payload напрямую доступен Skill & Prompt Manager. Это
устраняет прежнее смешение текста с control event и проверено отрицательным
bus-contract тестом. Реальный native WebRTC operation и heavy faster-whisper
inference остаются отдельными controlled checks из утверждённого scope D, но
детерминированная application boundary и no-GIL import evidence закрыты.

Подробности и тесты зафиксированы в
[`propagation-002-D.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-D.md).

### 8.5. Propagation checkpoint `002-E` → `002-F`/`002-G`/`002-H`/`002-J`

`002-E` принят main executor `2026-09-03`. Фактический control contract:

- process-local `ControlEventBus` — bounded FIFO fan-out с close/unsubscribe,
  non-blocking overflow reporting и call scope;
- `Dispatcher` владеет последовательным запуском FSM, но не переносит PCM,
  ASR/TTS streams, RAG fragments или authoritative final text;
- control outputs включают `SpeechEvent`, `StructuredDecision`,
  `DialogueCommand`, `PlaybackEvent`, `TransferResult` и lifecycle envelopes;
  action allowlist проверяет решение до semantic SIP/transfer/hangup command;
- terminal, barge-in, cancellation и re-entry закрывают соответствующие
  channels идемпотентно и отбрасывают stale outcomes.

`FinalUserTurn` помечен как data-plane payload и не принимается Event Bus.
FSM получает его прямым методом входа; control bus получает только события,
необходимые для переходов. Это соответствует ADR-004 и правилам control/data
plane. E unit/contract evidence и state trace приняты; Windows-only failures
при полном прогоне относятся к отсутствующему `baresip` executable и не
являются дефектом E.

Подробности зафиксированы в
[`propagation-002-E.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-E.md).

### 8.6. Propagation checkpoint `002-F` → `002-G`/`002-J`

`002-F` принят main executor `2026-09-03`; его deterministic scope и последующий real embedding/RAG probe закрыты.
Фактические typed
контракты F:

- `ContextTurn`, `ContextSnapshot`, `FinalUserTurn` и `ContextStore` для text-only bounded persistence; один звонок
  хранится в `data/dialogues/<call_id>/conversation.jsonl`;
- `KnowledgeQuery`, `KnowledgeHit`, `KnowledgeContext`, `EmbeddingRequest`, `EmbeddingResponse` и
  `EmbeddingProvider` как application/retrieval seam к embedding-операции фасада;
- `SkillSpec`, `PromptSpec`, `GenerationProfile`, `PromptDiagnostics` и `LlmRequest` как версионируемый request
  boundary между prompt manager и LLM Facade.

`FinalUserTurn` приходит в F напрямую как data-plane payload; его authoritative text сохраняется отдельно от
нормализованных `embedding_text`, `lexical_terms` и `phrases`. F не обращается к Ollama напрямую: deterministic fake
backend/index проверяет shape, source IDs, scores, threshold и unknown-answer path. Поэтому downstream получает уже
типизированный embedding request и `LlmRequest`, но не получает права считать реальный embedding/RAG runtime доказанным.

Передача в `002-G`: G владеет transport mapping `EmbeddingRequest`/`EmbeddingResponse` и chat `LlmRequest` через
существующую HTTP boundary Ollama. Передача в `002-J`: source IDs, context sufficiency и prompt diagnostics должны
попасть в отчёт без публикации большого payload через control bus. До настоящего local Ollama probe F остаётся
`complete`; lexical fallback автоматически не включается. Real probe evidence находится в G artifact.

Подробности и тесты зафиксированы в
[`propagation-002-F.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-F.md).

### 8.7. Propagation checkpoint `002-G` → `002-H`/`002-J`

`002-G` принят main executor `2026-09-03`. Фактический typed output boundary:

- `LlmStreamEvent` со `STARTED`/`DELTA`/`DECISION`/`COMPLETED`/`CANCELLED`/`ERROR`, operation/call/turn identity и
  timestamps;
- `InferenceStatus`, `CancelRequest` и `LatencyTrace` для lifecycle, cancellation и измерения от final user turn;
- `StructuredDecision` как небольшой control-plane результат для Dispatcher/FSM; SIP/transfer действия модель не
  исполняет;
- `EmbeddingResponse` как typed результат отдельной операции F/G, без раскрытия Ollama JSON остальным consumers.

G принимает F `LlmRequest` и embedding operation через Facade, не меняет direct data-plane text и не публикует prompt,
RAG fragments или stream payload через Event Bus. Real Ollama evidence подтверждает `/api/embed` positive/negative RAG
path и `/api/chat` structured answer. При `think=false`, `temperature=0.1`, `num_predict=96` first usable output составил
`282.8241 ms`, полный результат — `1230.582814 ms` от final user turn.

Передача в `002-H`: разрешённый текстовый stream и cancellation/stale policy идут в TTS/playback path. Передача в
`002-J`: structured decision, source diagnostics и latency evidence идут в report/demo path. Остаточное ограничение —
серверный cancellation acknowledgement Ollama не заявляется; клиентское закрытие HTTP stream и suppression stale
result проверены.

Подробности и тесты зафиксированы в
[`propagation-002-G.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-G.md).

### 8.8. Propagation checkpoint `002-H` → `002-J`

`002-H` принят main executor `2026-09-03`. Фактический output/playback contract:

- `TtsPcmChunk` несёт `operation_id`, call/channel/generation/sequence, PCM S16LE и полный per-call
  `NegotiatedMediaProfile`; XTTS chunk size не считается media `ptime`;
- `TtsOutputBuffer` агрегирует произвольные chunks, создаёт точные `PcmFrame` и отдельно обрабатывает успешный tail и
  cancellation/drop;
- `MediaPacer` выдаёт frame только по negotiated media clock, а `PlaybackChannel` владеет lifecycle, barge-in,
  close/cancel и direct `send_frame` data-plane callback;
- `PcmAudioBridge` принимает `PcmFrame` в PJMEDIA port, а codec/RTP преобразование выполняется media layer. Фактический
  approved `001-S` профиль — PCMU/8000/1, payload `0`, `ptime=20 ms`, `160 samples`;
- при barge-in старый playback channel закрывается, producer отменяется, stale TTS push отклоняется, post-cancel
  frames от `PlaybackChannel` не отправляются; inbound media продолжает поступать.

Доказательства deterministic, target no-GIL, XTTS, PCMU и RTP сохранены в
[`002-H`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-H/), включая
[`rtp-barge-in.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-H/rtp-barge-in.json).
`002-J` получает этот output contract и может использовать его только вместе с собственным end-to-end evidence;
H не заявляет за J полный demo-flow.

### 8.9. Propagation checkpoint `002-J` preflight

Главный executor принял J1–J3 и выполнил J4 preflight `2026-09-03`. Component
contracts A–H остаются валидными, но сквозная сборка остановлена: в текущем
write-set нет production-level владельца call-session orchestration, который
соединяет SIP/media callbacks, PCM fan-out/chunker, speech ingress,
RAG/prompt, LLM stream, TTS/playback, FSM, transfer и report. `conversation.jsonl`
может использоваться как внутренний журнал, но не является обязательным
артефактом; обязательным результатом звонка остаётся `report.md`.

Новые узлы/рёбра и новые ownership не назначаются этой ревизией молча. Gap
зарегистрирован как `B-002-J-005` (APG 6.1 category 4) и вынесен на owner
review; evidence находится в
[`002-J/j4-preflight.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-preflight.md). 

### 8.10. Owner decision и successor plan `002-I.0`

Владелец проекта уточнил, что в MVP остаются один Dispatcher и один
одновременный звонок, но это не объединяет концептуальные сущности. `Dispatcher`,
`CallSession` и `DialogueFSM` должны быть разными классами и объектами; их
допускается временно разместить в одном Python-модуле. Dispatcher владеет
порядком control-plane и единственным active-session slot, CallSession —
per-call composition/lifecycle, DialogueFSM — semantic state и действиями.

Локальный no-GIL preflight подтвердил, что PJSUA2/PJMEDIA `2.17` способен
обслуживать несколько вызовов (`maxCalls=4` в текущем target default) через
отдельные `Call` и общий primary conference bridge. Это не расширяет MVP:
multi-call execution остаётся deferred, а `call_id`-scoped object mapping
сохраняется как future-compatible invariant. Подробное evidence находится в
[`pjsua-capacity-probe.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/pjsua-capacity-probe.md).

Для устранения gap создан отдельный successor child plan
[`plan-002-I.0-call-session-orchestration-and-state.md`](plan-002-I.0-call-session-orchestration-and-state.md), а не
`002-K`. Он должен определить typed edges между уже существующими Dispatcher,
DialogueFSM и новым per-call CallSession, реализовать one-call composition и
вернуть propagation revision карте до возобновления J4. Новые Dispatcher или
DialogueFSM создавать нельзя. Обязательный итоговый артефакт — `report.md`;
внутренний `conversation.jsonl` остаётся необязательным implementation detail.

### 8.11. Propagation checkpoint `002-I.0` / composition boundary

Deterministic implementation checkpoint `2026-09-03` подтвердил фактическую
границу без создания второго Dispatcher или DialogueFSM:

- `Dispatcher` остаётся существующим process-local сериализатором control plane
  и получил один `active_session` slot;
- `CallSession` — новый отдельный per-call object с `call_id`, `generation`,
  `CallScope`, `SessionLease`, cancellation и idempotent close;
- `SessionComponent.close(reason)` — минимальный lifecycle hook для scoped owners;
- `ControlMessage` принимает существующие typed control messages:
  `ControlEvent`, `NormalizedSipEvent`, `SpeechEvent`, `StructuredDecision`,
  `PlaybackEvent` и `TransferResult`;
- `FinalUserTurn` и прочие data-plane payload не принимаются Dispatcher при
  активной session и должны идти напрямую в своих consumers;
- после terminal control/event session закрывается, lease старого поколения
  перестаёт приниматься, а следующий call получает новую generation.

Это checkpoint `I0-1`/часть `I0-2`, а не closeout I.0: полная application
composition всех A–H owners и clean-start J4 ещё не доказаны. Evidence находится
в `artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/`.

### 8.12. Propagation checkpoint `002-I.0` / named composition owners

Корректирующий implementation pass `2026-09-03` материализовал следующий
участок composition boundary:

- `SessionBindings` именованно связывает SIP/media, speech, context, LLM, TTS,
  transfer и report owners с конкретной `CallSession`;
- `CallComposition` использует уже существующие `Dispatcher`, `CallSession` и
  `DialogueFSM`, принимает `FinalUserTurn` напрямую в `ContextStore` и FSM,
  а compact control events передаёт через Dispatcher;
- `KnowledgeContext` сохраняется в composition для source-aware report path;
  report строится после завершения перехода FSM в terminal, поэтому промежуточный
  `REPORT` command не читает ещё не завершённое semantic state;
- один и тот же `CallScope` принадлежит RuntimeCoordinator/CallSession и
  `DialogueFSM.channels`; скрытого второго lifecycle scope не создаётся;
- `CALL_OPEN` при заранее собранной session идемпотентно доходит до FSM, а
  повторное событие не создаёт новый call или новый FSM.

Фактические границы подтверждены новым integration test
`tests/integration/test_application_composition.py`: SIP event → existing FSM →
direct final turn/context → typed decision → playback lifecycle → terminal →
однократный `report.md`. Это всё ещё deterministic composition evidence, не
замена heavy model и live SIP/RTP J4 evidence.

### 8.13. Propagation checkpoint `002-I.0` / direct conversation pipeline

Корректирующий implementation pass `2026-09-03` уточнил не только состав
владельцев, но и рабочий путь между ними:

- `CallOwners`/`SessionBindings` теперь явно включают `retrieval` и `prompt`,
  поэтому RAG index и Skill & Prompt Manager не прячутся за безымянным
  `object`-набором;
- `ConversationPipeline` принимает только authoritative `FinalUserTurn`,
  в worker thread строит `KnowledgeQuery`, выполняет source-aware retrieval
  через typed `LlmFacade.embed`, собирает `LlmRequest` через
  `SkillPromptManager` и передаёт наружу только `StructuredDecision` через
  Dispatcher;
- утверждённый текст ответа идёт напрямую в `TtsStreamPort` как
  `ApprovedTextChunk`, PCM — через прямой `audio_sink`; transfer выполняется
  отдельным worker и возвращает только typed `TransferResult` в Dispatcher;
- `CallSession.dispatch_data` сериализует короткое изменение прямого payload и
  FSM с control transition на общем session lock, но сам payload через
  Dispatcher не проходит; отмена закрывает активные LLM/TTS operations и
  stale output не публикуется;
- worker pipeline не блокирует dispatcher: retrieval, HTTP stream, TTS и
  transfer не выполняются внутри FSM transition.

Граница подтверждена `tests/integration/test_conversation_pipeline.py` на
детерминированных owner doubles и локальных typed contracts. Это закрывает
composition contract, но не подменяет отдельные real ASR/XTTS/GPU gates и
full-flow J4 evidence.

### 8.14. Propagation checkpoint `002-I.0` / real composition corrective pass

Main executor выполнил последовательные main-only проверки на target
free-threaded CPython 3.14.7t:

- реальный answer path подтвердил `LocalKnowledgeIndex` с
  `embeddinggemma`, source-aware `KnowledgeContext`, dynamic closed output
  schema на `LlmFacade → Ollama`, structured decision и XTTS PCM output;
- реальный media/speech path подтвердил `PCMU-compatible 20 ms PCM frames →
  AsrChunker → patched faster-whisper/CTranslate2 → VAD/TurnDetector/
  TranscriptAssembler → authoritative FinalUserTurn`;
- insufficient RAG path сформировал `offer_transfer`, approved text прошёл
  через XTTS, typed transfer ушёл в локальный `FakeOperator`, а terminal path
  создал ровно один `report.md`;
- output-schema ошибка с лишним полем модели и отсутствие transfer owner в
  первом probe получили corrective pass. Assertions не ослаблялись, первый
  красный результат сохранён в evidence history;
- во всех этих процессах `sys._is_gil_enabled() == False`. Детальные raw
  результаты находятся в `002-I.0` evidence root.

Таким образом, I.0 composition contract закрыт. J4 clean-start component/composition
lanes прошли, но map-level live SIP-driven full matrix не закрыт: физический
SIP media path пока не соединён с speech/AI pipeline и paced TTS egress.

### 8.15. J4 integration audit и blocker runtime wiring (historical revision 19)

J4 runner дал exit code `0` для target regression, real answer composition и
real ASR/media/transfer composition. Это достаточное evidence соответствующих
отдельных lanes, но не одного Baresip→ASR→LLM→TTS→Baresip вызова. В исходном
дереве не выполнялись вызовы существующих typed input-методов в живом
application execution loop: `SipMediaAdapter.next_ingress_frame()` не
прокачивался в `PcmFanOut.publish()`, speech path не передавал свои результаты
в `ConversationPipeline.submit_final_turn()`, а TTS output не доходил через
`TtsOutputBuffer.push()`/`PlaybackChannel.pump()` до
`SipMediaAdapter.enqueue_egress_frame()`. `002-I.1` теперь материализует эти
вызовы в `CallRuntimeWiring`; deterministic edge и real AI composition gates
прошли, но fresh live SIP/RTP full-flow ещё не подтверждён.

Это не требует нового delivery-owner или нового semantic application
component. Требуется явная runtime wiring в основном `asyncio` loop; между
worker-потоками допускаются только bounded thread-safe queues. Вызов typed
input-метода получателя является materialization соответствующего in-process
ребра. Gap зарегистрирован как `B-002-I-006` и связан с `B-002-J-006`;
конкретный corrective action вынесен в
[`plan-002-I.1-live-call-asyncio-wiring.md`](plan-002-I.1-live-call-asyncio-wiring.md).

### 8.16. Owner decision и corrective plan `002-I.1` (historical revision 19)

Для снятия blocker принят следующий принцип runtime exchange:

- основной поток приложения содержит один `asyncio` event loop;
- Dispatcher и Control Event Bus работают как задачи этого loop, но не
  становятся маршрутизаторами audio/text payload;
- внутри loop producer вызывает typed input-метод consumer напрямую либо
  использует локальную `asyncio.Queue`;
- между потоками используется bounded thread-safe queue; `asyncio.Queue` не
  используется как межпоточный transport;
- native PJSUA2/PJMEDIA callbacks, пришедшие из другого потока, проходят через
  thread-safe bridge, после чего основная asyncio-задача вызывает consumer
  method;
- не создаются новые Dispatcher, FSM, event bus, universal data bus или
  delivery-owner.

`002-I.1` должен последовательно проверить exact input methods уже созданных
consumer-ов, реализовать их вызов в runtime и доказать полный live path.
Execution order и signatures находятся в §6–§8 нового plan-file; на момент
revision 19 до его owner review и closeout `B-002-I-006`/`B-002-J-006` оставались открытыми.

### 8.17. Execution checkpoint `002-I.1` (revision 19)

На ревизии 19 приняты как промежуточное evidence следующие факты:

- `CallRuntimeWiring` materializes existing typed data-plane methods on one
  main-thread `asyncio` loop; only bounded `queue.Queue` bridges the ASR worker;
- `PcmFrame → PcmFanOut → SpeechIngress/AsrChunker → StreamingAsrAdapter →
  FinalUserTurn` and the direct `FinalUserTurn → ConversationPipeline` path
  pass deterministic integration tests;
- `TtsPcmChunk → TtsOutputBuffer → MediaPacer → PlaybackChannel →
  SipMediaAdapter.enqueue_egress_frame` passes deterministic integration tests;
- a terminal `REMOTE_HANGUP` is handled while ASR backend work is blocked;
- target CPython 3.14.7t imports the combined PJSUA2, faster-whisper, torch and
  XTTS environment with GIL disabled; real offline ASR/RAG/Ollama/XTTS
  composition also passed and produced report/TTS evidence.

Raw results: [`002-I.1 evidence`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.1/README.md).
Этот checkpoint был подготовлен до fresh live gate и сам по себе не закрывал `I1-8`: один свежий Baresip call using
the new runtime wiring оставался обязательным.

### 8.18. Propagation checkpoint `2026-09-04` (revision 21)

Главный executor выполнил fresh live gate после materialization runtime-рёбер и обязательного pre-call warmup.
`live-gate-20260903-r4/live-i1-gate.json` имеет `status=pass`: peer установил SIP/RTP в обе стороны с PCMU/8000/mono,
`CallRuntimeWiring` передал media в speech path, полный ASR-текст дошёл до source-aware RAG/LLM, а paced TTS вернулся
в тот же RTP-call. Зафиксированы `pipeline_errors=[]`, `wiring errors=0`, `gil_enabled=false` и итоговый `report.md`.

Это закрыло `B-002-I-006` и связанный `B-002-J-006`, то есть первоначальный gap отсутствовавшего live application
driver. Дополнительный единый gate `002-J/j4-full-live-20260904-r20` имеет `status=pass`: follow-up с context,
barge-in с cancellation старого playback, unknown-answer/transfer и `report.md` подтверждены одним вызовом.
`B-002-I-007`, `B-002-J-004` и `B-002-MAP-006` resolved; I.1/J4/J5 evidence принято, карта закрывается.

## 9. Source-map и write-set

| Область | Путь | Текущее состояние | Допустимое изменение |
|---|---|---|---|
| Interaction map | `docs/plans/plan-002-I-boundary-interaction-map.md` | Этот APG map-file | Уточнять topology, cycles, candidate/accepted status и propagation rules |
| Contract evidence | `artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/` | Созданы propagation checkpoints `002-A`–`002-H` | Дальше добавлять registry, fixtures, cycle register и revision evidence по child plans |
| Session composition code | `src/sip_bot/control/dispatcher.py`, `src/sip_bot/dialogue/actions.py`, `src/sip_bot/dialogue/fsm.py`, `src/sip_bot/runtime_composition.py`, `src/sip_bot/conversation_pipeline.py` | `SessionBindings`, shared CallScope binding, serialized direct data handoff и deterministic `ConversationPipeline` materialized by I.0; live receiver methods invoked by `CallRuntimeWiring` | I.1 added only runtime loop wiring; no new Dispatcher/FSM/delivery owner |
| Composition tests/evidence | `tests/contract/test_call_session.py`, `tests/integration/test_application_composition.py`, `tests/integration/test_conversation_pipeline.py`, `tools/real_composition_probe.py`, `tools/real_media_composition_probe.py`, `tools/j4_clean_start_probe.py`, `tools/j4_full_live_gate.py` и I.0/I.1/J4 evidence | I0-1…I0-5 deterministic/real composition pass; I.1 and J4 r20 prove live edge invocation and full scenario matrix | Closed by actual producer/consumer methods and one live SIP→AI→SIP call |

Запрещено изменять этим документом исполненные `001-*` планы и их evidence, молча переписывать архитектурные решения,
протаскивать payload через Dispatcher или вводить новый IPC. Архитектурный документ обновляется только если уточнённый
контракт становится устойчивым owner-level решением.

## 10. Owner review

| Вопрос | Предлагаемое решение | Последствие | Статус |
|---|---|---|---|
| Нужна ли отдельная interaction map до component integration? | Да, это обязательная под карта карты 4 | Child plans не собирают компоненты на неявных границах | `resolved: owner review accepted 2026-09-02` |
| Откуда берутся media `ptime` и прочие параметры? | Из согласованного SDP и соответствующих словарей/объектов PJMEDIA для каждого звонка | `002-B` публикует `NegotiatedMediaProfile`, C/H используют его; значения не зашиваются глобально | `resolved: owner review accepted 2026-09-02` |
| Нужен ли process-local control event bus? | Да; singleton только внутри application process, control plane only | Подписчики получают typed events/commands, PCM и крупный text payload идут напрямую | `resolved: ADR-004, owner review accepted 2026-09-02` |
| Нужны ли отдельные boundary components для преобразований? | Да; media format/framer, PCM fan-out, ASR accumulator и TTS output framer/pacer являются самостоятельными владельцами поведения | Очередь не считается заменой накопителя, таймера, re-framer или pacing | `resolved` |
| Нужен ли внутренний фасад для Ollama? | Да; `LLM Facade` предоставляет typed API и единолично владеет HTTP IPC к Ollama | Остальные компоненты не знают внешний JSON/stream протокол | `resolved` |
| Нужен ли отдельный Skill & Prompt Manager? | Да; он выбирает разрешённый skill/profile и собирает версионируемый `LlmRequest` между context/FSM и фасадом | Влияние prompt-инструкций на latency/quality измеряется отдельно; FSM и фасад не смешиваются с prompt policy | `resolved` |
| Может ли Skill & Prompt Manager менять смысл пользовательского текста? | Нет; текст подставляется как данные с явными границами, а менеджер меняет только разрешённые инструкции и формат запроса | Prompt injection и скрытая нормализация не становятся непроверяемым поведением | `resolved` |
| Фиксируем ли все Python-типы заранее? | Нет; topology и candidate schemas фиксируются заранее, authoritative types уточняются итеративно | После каждого component output обновляется contract revision и consumers | `resolved` |
| Является ли RAG обязательным для demo answer path? | Да; ответ должен опираться на source-aware `KnowledgeContext`, а model-only ответ не считается RAG-evidence | Применимость технологии демонстрируется отдельно от общих знаний модели; unknown-answer проверяется по relevance threshold | `resolved` |
| Какой retrieval baseline готовить первым? | Проверить локальный Ollama `/api/embed` через typed Facade operation и компактный локальный индекс; точная embedding-модель и формат индекса — execution decision `002-F` | Не вводится Chroma/Qdrant/FAISS без необходимости; провал embedding-кандидата требует owner decision о lexical path | `resolved; candidate execution pending` |
| Как учитывать циклы? | Явным cycle register с termination/cancellation/re-entrancy | Remote protocol event может прервать любой долгий цикл | `resolved` |
| Может ли Dispatcher переносить payload? | Нет | Control events/commands идут через Dispatcher, audio/text payload — напрямую | `resolved` |
| Можно ли готовить propagation tests параллельно? | Да при disjoint write-set и фиксированной ревизии входного контракта | Integration и GPU-heavy execution остаются зависимыми | `resolved` |
| Кто владеет сквозным call-session orchestration? | `Dispatcher` владеет control ordering и active-session slot; отдельный `CallSession` — per-call composition/lifecycle; `DialogueFSM` сохраняет semantic ownership | I.0 уточняет typed edges и размещение классов без нового процесса | `resolved: owner decision and I.0 execution accepted 2026-09-03` |
| Нужен ли обязательный `state.json`? | Нет; это не входное требование и не обязательный артефакт. Live semantic state остаётся у `DialogueFSM`, `conversation.jsonl` может вестись `ContextStore` как внутренний журнал, а `report.md` — единственный обязательный итоговый артефакт | I.0 не проектирует schema/restore для `state.json`; проверяет только lifecycle контекста и финализацию отчёта | `resolved: owner clarification 2026-09-03` |
| Ограничивает ли PJSUA2/PJMEDIA MVP одной сессией? | Нет; библиотека поддерживает несколько `Call`, но multi-call application остаётся вне MVP | I.0 проверяет только single-call composition и сохраняет `call_id` mapping | `resolved: capacity preflight` |
| Как материализуются прямые data-plane рёбра? | Вызовом typed input-метода получателя; отдельный delivery-owner не создаётся | В основном `asyncio` loop допустим прямой вызов/локальная `asyncio.Queue`; между потоками — только bounded thread-safe queue | `resolved: owner clarification 2026-09-03; 002-I.1 owner review accepted, execution in progress` |

## 11. Process и architecture audit

- Карта описывает узлы, рёбра, циклы и propagation, а не только список компонентов.
- Каждое ребро имеет plane, producer, consumer, owner, candidate/accepted type, lifecycle, cancellation, backpressure,
  stale policy и failure semantics.
- Окончательный тип не объявляется принятым до component evidence и contract test.
- Обратные события и команды не скрываются за односторонней стрелкой.
- Новый adapter или conversion boundary получает отдельную запись и не вводится молча.
- Для каждого in-process edge фиксируется exact input method consumer и контекст его вызова; procedural wiring не объявляется новым owner/component.
- Основной runtime loop — один `asyncio` loop в основном потоке; `asyncio.Queue` не используется между worker-потоками.
- Подготовка `LlmRequest` отделена от FSM и Ollama IPC; prompt/profile version и состав контекста входят в evidence.
- RAG не сводится к встроенным знаниям модели: corpus, retrieval operation, source IDs, scores и relevance threshold
  имеют отдельные owner/contracts/evidence.
- Каждая итерация обновляет карту контрактов и downstream contract tests до следующей сборки.
- Проверки не используют безымянные `skip`/`xfail`, а отложенные boundary evidence получают owner и condition.

## 12. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-I-001` | Map-002-I | Interaction map не прошла owner review | Component integration и создание execution-разрешений child plans | project owner | Этот документ, topology/cycle/contract audit | `closed: owner review accepted 2026-09-02` |
| `B-002-I-002` | Map-002-I | Фактический output producer не совпал с candidate contract | Зависимые consumers и соответствующий integration edge | owner соответствующего child plan | Component evidence + новая revision registry | `resolved — C→D AsrAudioChunk mismatch исправлен в corrective pass; revision 5` |
| `B-002-I-003` | Map-002-I | Не определены или не проверены `SkillSpec`/`PromptSpec`/`GenerationProfile`/`LlmRequest` для authoritative path | Сборка `002-F` и `002-G`, а также сопоставимый LLM benchmark | owner `002-F`/`002-G` | Prompt contract fixture и propagation checkpoint | `resolved — deterministic contracts и G transport evidence приняты 2026-09-03` |
| `B-002-I-004` | Map-002-I | RAG не возвращает source-aware context либо answer path не отличает model-only ответ от ответа по базе | `002-F`, `002-G`, Answer path gate и доклад | owner `002-F`/`002-G`; project owner при смене retrieval baseline | RAG fixture, source trace, relevance/unknown-answer evidence | `resolved — real embedding positive/negative path и source-aware chat evidence приняты 2026-09-03` |
| `B-002-I-005` | Map-002-I / J4 | Не был утверждён владелец сквозного call-session orchestration | J4, Map-002 closeout и новые propagation edges | project owner | [`002-J/j4-preflight.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-preflight.md) | `resolved: owner decision 2026-09-03; successor I.0 required` |
| `B-002-I-006` | Map-002-I / J4 | Не доказан fresh live SIP/RTP full-flow через runtime wiring существующих typed input-методов между SIP ingress, speech/AI и paced TTS egress | Live SIP-driven J4, J5 и Map-002 closeout | project owner | [`002-J/j4-integration-gap.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-integration-gap.md), [`002-I.1 evidence`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.1/README.md) | `resolved: base live path proven by live-gate-20260903-r4; remaining scenario matrix is tracked separately` |
| `B-002-I-007` | Map-002-I / J4/J5 | Обязательная protocol/interruption/multi-turn/transfer scenario matrix ещё не принята одним clean-start gate | Map-I closeout, J4, J5 и Map-002 closeout | project owner | `002-I.1` live evidence and J4 scenario matrix | `resolved: r20 has 6/6 checks and exit code 0` |

## 13. Test/evidence и closeout

Минимальное evidence карты:

- topology table с полным набором nodes/edges;
- cycle register для `C1`–`C6` с termination/cancellation/re-entrancy;
- contract registry с ревизиями и статусом candidate/accepted;
- evidence преобразований `ptime → PCM frame → ASR chunk` и `TTS chunk → paced PCM frame`, включая timer/flush, bounded
  storage, tail и cancellation behavior;
- typed API и stream/cancellation evidence `LLM Facade` на границе с Ollama, включая отдельную embedding-операцию;
- fixture/contract test `Skill & Prompt Manager`: корректный выбор skill/profile, prompt version, delimiters,
  `LlmRequest` и отсутствие молчаливого изменения пользовательского текста;
- RAG fixture/contract test: offline corpus/index build, `/api/embed` query, top-k source-aware hits, threshold и
  unknown-answer при отсутствии достаточного контекста;
- RAG evidence: версия корпуса и embedding-модели, chunk/index parameters, query latency, scores, source IDs и
  подтверждение передачи выбранных фрагментов в prompt;
- prompt/profile benchmark evidence: время от финального хода до первого полезного результата и полное время генерации
  при сохранённых версиях шаблона, profile и output schema;
- хотя бы один stub/fixture и contract test на каждое закрытое обязательное ребро;
- запись propagation checkpoint после каждого component child plan;
- audit, подтверждающий, что Dispatcher не переносит payload, SIP adapter не ждёт модели, а каждое live in-process edge вызывает typed input-метод consumer-а.

Карта `Map-002-I` закрывается только после owner approval topology и правил propagation, а также после того, как
каждый обязательный edge передан в соответствующий child plan с собственной acceptance и blocker register. Её closeout
не означает, что компоненты интегрированы: это разрешает переход к последующей итерации component implementation.

Текущий статус: `complete; topology owner review принят 2026-09-02; propagation checkpoints 002-A–002-H, 002-I.0
и 002-I.1 recorded; revision 21 фиксирует base live-gate-20260903-r4 и full scenario gate
002-J/j4-full-live-20260904-r20. B-002-I-006, B-002-I-007 и связанные J4/Map-002 blockers закрыты; I.1, J4 и J5
приняты, downstream map closeout синхронизирован`.
