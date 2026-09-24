# Архитектура MVP

Статус: черновик, уточняется вместе с выбором VoIP-стека и реализацией.

Документ является источником сквозных архитектурных решений. Цели, границы MVP и пользовательские сценарии описаны в [постановке задачи](requirements.md). Конкретные технические ограничения, конфигурация и критерии проверки описаны в [техническом задании](technical-specification.md).

## 1. Архитектурный принцип

Система разделяется на два плана:

- **control plane** — события, команды, состояние разговора, управление жизненным циклом компонентов и каналов;
- **data plane** — аудио- и текстовая полезная нагрузка, передаваемая между компонентами.

Центральный `Main Dispatcher` является владельцем control plane, порядка его обработки и единственного активного
call-session slot в MVP. Внутренним механизмом fan-out control plane является process-local singleton `Control Event Bus`: он доставляет typed control events/commands нескольким
подписчикам, но не переносит PCM, media frames, ASR/TTS streams, крупные тексты или RAG-фрагменты. Dispatcher остаётся
владельцем смысловых переходов и действий; bus владеет только подписками, bounded delivery и их lifecycle. Он не является
транзитным узлом для аудиофреймов и текстовых потоков.

Dispatcher управляет тем, какие каналы существуют, кто к ним подключён и когда они открываются или закрываются. После открытия канала полезная нагрузка передаётся непосредственно между producer и consumer.

Один active-call slot не означает смешения концептуальных сущностей. `Dispatcher`,
`CallSession` и `DialogueFSM` являются разными классами и объектами: Dispatcher
владеет control ordering и ссылкой на active session, `CallSession` связывает
per-call lifecycle/component handles, а Dialogue FSM владеет semantic state,
transition guards и разрешёнными действиями. Для MVP эти классы допускается
разместить в одном Python-модуле, если их ownership и typed boundaries остаются
раздельными. `RuntimeCoordinator` отвечает за низкоуровневый runtime/channel
lifecycle, а `ContextStore` — за bounded text context и, при необходимости,
внутренний журнал. Единственный обязательный внешний артефакт после звонка —
`report.md`, который финализирует report owner; live FSM state не дублируется в
ContextStore.

Финализированный пользовательский ход является data-plane payload. `FinalUserTurn` передаётся напрямую в
`SemanticTurnParser`, который читает immutable `DialogueExpectation` текущей FSM и выдаёт `SemanticTurn` с
упорядоченными typed dialogue acts. `CallComposition` сохраняет исходный текст в `ContextStore` ровно один раз и
последовательно вызывает методы FSM для acts; содержательный `KnowledgeRequestAct` напрямую материализуется во вход
`ConversationPipeline`. В Event Bus/Dispatcher попадают только компактные lifecycle events, decisions и commands.
Event Bus обязан отклонять `FinalUserTurn`, `SemanticTurn` и другие data-plane payload даже если текст формально
ограничен по размеру.

## 2. Компоненты и потоки

```text
                           control plane
       SIP events ───────────────────────────────┐
                                                  ▼
                                      Main Dispatcher
                                      / Dialogue FSM
                                       │ commands
                                       ▼
                                   SIP adapter

RTP/PCMU ──> SIP/media ──> format/framer ──> PCM fan-out ──┬─> VAD ──> Turn Detector
                                                           │
                                                           └─> ASR input accumulator
                                                               (bounded buffer + timer)
                                                                        │ ASR chunks
                                                                        ▼
                                                                       ASR
                                                                        │
                                                               Transcript Assembler
                                                                        │ FinalUserTurn
                                                                        ▼
                                                               SemanticTurnParser
                                                          DialogueExpectation │ SemanticTurn
                                                        Dialogue FSM ◄────────┘
                                                              │ knowledge request
                                                              ▼
                                                             Skill & Prompt Manager
                                                                         │ LlmRequest
                                                                         ▼
                                                                  LLM Facade
                                                               │ HTTP IPC │
                                                               ▼         ▼
                                                          Ollama process  Dispatcher
                                                                        │ approval
                                                                        ▼
                                                                       TTS
                                                                        │ arbitrary PCM chunks
                                                                        ▼
                                                             output buffer/framer/pacer
                                                                        │ ptime PCM frames
                                                                        ▼
                                                                   playback channel
                                                                        │
                                                               media egress ──> RTP/PCMU
```

Логические роли компонентов:

- `SIP adapter` реализует SIP-сигнализацию, SDP, RTP/RTCP и медиатайминг конкретного VoIP-стека.
- `Media format/framer` декодирует входящий PCMU в согласованный внутренний PCM-формат, выдаёт кадры с media `ptime` и
  кодирует исходящий PCM обратно в PCMU; все эти параметры берутся из per-call profile, согласованного по SDP и словарям/объектам PJMEDIA.
- `PCM fan-out` распределяет bounded поток внутренних кадров между VAD, ASR input accumulator и playback path; он не
  заменяет семантические adapters на границах.
- `ASR input accumulator` собирает кадры media `ptime` в настраиваемые ASR chunks (начальный кандидат — около 1 s),
  использует bounded storage и timer-driven flush, а не простую безграничную очередь.
- `VAD` получает аудио напрямую из data plane и выдаёт покадровые признаки наличия речи. Рабочим application/live
  candidate является `WebRtcVadCandidate` на patched `webrtcvad-wheels 2.0.14`, с mode из `VAD_MODE`; amplitude
  backend остаётся только deterministic test double. Поскольку Python binding WebRTC VAD публикует только boolean,
  `VadProcessor` дополнительно применяет inspectable per-call energy gate: измеряет RMS dBFS, устойчиво оценивает noise
  floor по скользящему низкому квантилю, ограничивает скорость его роста, ведёт сглаженный speech level и подтверждает
  raw positive настраиваемым порогом. Короткий энергетический onset и спектральный hangover обрабатываются отдельно,
  чтобы фильтрация фона не удлиняла внутривыходовую паузу. Это внутренняя политика VAD owner, а не новый data-plane edge.
- Near-end reference строится не по единичному пику, а по устойчивому квантилю подтверждённых достаточно энергичных
  кадров текущего звонка. Обычное принятие речи и barge-in имеют разные пороги: слабый акустический возврат может быть
  отклонён без изменения playback state, а подтверждённая ближняя речь в уже открытом ходе материализует существующий
  `BARGE_IN` control event. Отдельная media-reference/AEC edge для этого baseline не вводится.
- `Turn Detector / Endpointing` агрегирует VAD-признаки и определяет начало, продолжение, кандидатный и окончательный конец пользовательского хода.
- `Streaming ASR` получает аудио напрямую из data plane и выдаёт изменяющиеся текстовые гипотезы вместе с typed
  model evidence. Production faster-whisper сохраняет `no_speech_prob`, средний `avg_logprob`, compression ratio и
  диагностику временной границы сегмента. Финальная гипотеза, квалифицированная как no-speech, атомарно освобождает
  matching assembler/pending endpoint и не создаёт `FinalUserTurn`; текст модели не фильтруется по содержимому.
- `TurnDetector` является единственным владельцем `turn_id`. Только после достижения `min_speech_ms` его фактический
  идентификатор хода прикрепляется к квалифицированным PCM frames и затем без переименования проходит через
  `AsrAudioChunk` и `AsrHypothesis` к `Transcript Assembler`. Короткие положительные bursts, не ставшие пользовательским
  ходом, в ASR accumulator не попадают. Pending endpoint и assembler хранятся по `turn_id`, поэтому несколько
  последовательных ходов безопасны при отстающем ASR worker и не перезаписывают transcript scope друг друга.
- `Transcript Assembler` собирает единую текущую гипотезу из partial-результатов ASR, отделяя явно подтверждённый backend-ом стабильный префикс от изменяемого хвоста и выдавая финальный текст после endpointing. Общий префикс двух последовательных гипотез сам по себе стабильностью не считается: ранняя ошибка ASR может повториться и затем исчезнуть.
- `SemanticTurnParser` является stateless owner детерминированной интерпретации финального текста с учётом read-only
  ожидания FSM. Он выделяет явное подтверждение/отказ, прямую просьбу об операторе и содержательный residual как
  ordered typed acts, но не меняет call state, не вызывает SIP/RAG/LLM и не создаёт отдельный delivery channel.
- `DialogueExpectation` уточняет смысл коротких контекстных ответов, но не перекрывает самодостаточное намерение:
  явная просьба перевести на оператора остаётся `TransferRequestAct` и при ожидаемом подтверждении перевода.
- `Dialogue FSM` остаётся единственным владельцем semantic state и transfer policy. Составной отказ сначала снимает
  pending transfer, после чего residual запускает обычный knowledge path. Составное подтверждение не переводит
  немедленно: после ответа на residual FSM повторно спрашивает подтверждение, и только новый pure confirm разрешает
  transfer. Raw turn хранится один раз, а applied/ignored acts попадают в диагностический trace отчёта.
- Реализация faster-whisper строит каждую partial-гипотезу на растущем PCM-префиксе текущего user turn; negotiated
  8 kHz mono PCM явно ресемплируется на требуемые моделью 16 kHz. После hard endpoint префикс сбрасывается, чтобы
  следующий turn не наследовал предыдущий текст.
- `speculative LLM/retrieval` может получать стабильный промежуточный текст и готовить предварительный анализ, но не изменяет состояние диалога и не запускает TTS.
- `Skill & Prompt Manager` выбирает разрешённый навык, применяет версионируемый шаблон и generation profile,
  объединяет финальный пользовательский ход с контекстом/знаниями и формирует typed `LlmRequest`. Он не выполняет
  SIP-команды, не владеет FSM и не является HTTP-клиентом Ollama; пользовательский текст передаётся как данные и не
  должен молча переписывать смысл запроса.
- `LLM Facade` предоставляет остальным компонентам внутренний typed API, принимает `LlmRequest`, владеет единственным HTTP IPC к Ollama,
  преобразует внешний stream/JSON в внутренние типы и отвечает за cancellation/status. Ни один другой компонент не
  обращается к Ollama напрямую.
- `TTS` получает одобренный текстовый поток и выдаёт произвольные PCM chunks.
- Статическое greeting после `CALL_ANSWERED` не проходит через LLM/RAG: `Dialogue FSM` выдаёт компактный
  `PLAY_GREETING`, а `ConversationPipeline` передаёт конфигурационный текст существующему TTS path. Speech ingress уже
  открыт, поэтому тот же playback generation/cancellation contract обеспечивает barge-in; PCM не проходит через
  Dispatcher.
- Статическое повторное подтверждение перевода использует тот же принцип: FSM выдаёт компактный
  `PLAY_TRANSFER_CONFIRMATION`, а pipeline подставляет `TRANSFER_CONFIRMATION_TEXT` и запускает существующий TTS path.
  Вопрос не проходит через answer LLM/RAG и остаётся interruptible.
- `TTS output buffer/framer/pacer` накапливает и переформатирует поток TTS в media-кадры с `ptime`, выдавая их по
  media clock и корректно закрываясь/отменяясь при barge-in.
- Накопление TTS является receiver-owned dynamic accumulation: текущая длина буфера изменяется при добавлении и
  чтении chunks, но storage остаётся bounded и имеет явный high-water/backpressure или error policy. Это не означает
  фиксированный буфер размера одного chunk/ответа и не разрешает truly unbounded memory. PJMEDIA callback извлекает
  ровно один negotiated `PcmFrame` за такт; он не ждёт producer и не получает тишину из того же TTS-буфера.
- Пока вызов отвечен и media clock активен, callback выдаёт один PCMU-кадр на каждый negotiated tick: из TTS-буфера
  в режиме playback и из выбранного comfort-noise источника в idle/preroll/draining. Пустой TTS-буфер в режиме
  `PLAYING` считается underrun и не маскируется как штатная тишина. В live acceptance непрерывность проверяется по
  окну `200 OK` на `INVITE` → `BYE`/`media_stopped`, `ptime`, adapter egress и peer RTP receive/loss counters;
  длительность Baresip WAV остаётся отдельным recording diagnostic.
- `Dialogue/LLM path` связывает `Dialogue FSM`, `Skill & Prompt Manager` и `LLM Facade`: FSM разрешает действие и
  generation policy, менеджер промптов собирает запрос, фасад выполняет inference. В текущем C3-baseline inference
  выполняется локальным native-сервисом в отдельном процессе.
- `Main Dispatcher / Dialogue FSM` проверяет действия, изменяет состояние, управляет каналами, отменяет активные операции и отправляет команды SIP-адаптеру.
- `RuntimeReadinessCoordinator` владеет только runtime-scoped состоянием и single-flight aggregate warmup. Он может быть
  запущен явным background-trigger-ом; `ApplicationRuntime.start()` не выполняет тяжёлую подготовку синхронно.
- `IncomingCallReadinessGate` является узким runtime-компонентом с самостоятельным pending-call lifecycle: он связывает
  событие incoming `call_started` после локального `180` с общим coordinator result и вызывает только typed
  `answer()`/`reject()` SIP-адаптера. При `RUNNING` gate ожидает уже идущий warmup, при `NOT_STARTED` запрашивает его
  запуск как fallback. Gate не владеет LLM, медиа, Dispatcher или доставкой payload.

LLM не передаёт SIP-команды напрямую. Содержательный текст ответа может идти в TTS по data plane, но действия `transfer`, `hangup` и другие изменения состояния проходят через Dispatcher.

### 2.1. Вместимость PJSUA2/PJMEDIA

PJSUA2 поддерживает несколько одновременных объектов `Call`; в принятой target
конфигурации `EpConfig.uaConfig.maxCalls` имеет значение `4`, а compile-time
верхняя граница задаётся `PJSUA_MAX_CALLS`. Media-объекты вызовов подключаются
к одному основному PJMEDIA conference bridge. Это оставляет будущую модель
`call_id → CallSession/media context` совместимой с библиотекой.

Многозвонковость не входит в MVP: конфигурационный baseline ограничен одним
разговором, а текущий application `SipMediaAdapter` хранит один `_CallContext`.
Проверка capacity и источники зафиксированы в
[`pjsua-capacity-probe.md`](../artifacts/implementation/002-mvp-media-and-speech-integration/002-I.0/pjsua-capacity-probe.md).

### 2.2. Протокольная реакция и прикладные события

`SIP adapter` разделяет два уровня control plane:

- **протокольная реакция** — обработка SIP/RTP-транзакций и обязательных ответов в собственном callback/transaction
  контексте, без ожидания Dispatcher, ASR, LLM, TTS или отчёта;
- **прикладное событие** — нормализованное уведомление Dispatcher, если изменение протокола влияет на состояние
  разговора или требует решения FSM.

К первому уровню относятся, например, ответы на `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, подтверждение
изменения media-направления при hold/resume, а также локальная реакция на RTP timeout или transport error. BYE — лишь
один из проверяемых сценариев, а не специальное архитектурное исключение.

Для входящего `INVITE` жизненный цикл разделён на два шага. SIP adapter немедленно отправляет явный `180 Ringing`,
не ожидая Dispatcher или AI, и публикует событие `call_started` с признаком pending answer. Затем основной `asyncio`
loop передаёт событие общему readiness coordinator: если runtime уже `READY`, adapter получает команду явного `200 OK`;
если warmup `RUNNING`, звонок ждёт тот же результат; если warmup `NOT_STARTED`, coordinator запускает его один раз вне
native callback и не блокируя SIP polling, после успешного завершения отправляется `200 OK`. При ошибке прогрева отправляется явный `503`
без direct/CPU/model fallback. Remote `CANCEL`, `BYE`, media/transport failure во время ожидания закрывает pending
admission; поздний результат прогрева не может ответить или открыть media у закрытого звонка.

Ко второму уровню относятся события вроде `call_ended`, `remote_hold_started`, `remote_resumed`, `media_reconfigured`,
`rtp_timeout` и `media_failed`. Dispatcher может изменить FSM или закрыть каналы, но его недоступность не должна
мешать SIP adapter выполнить обязательную протокольную реакцию.

### 3.1. Граница процесса C3

Для принятого C3-baseline основной процесс остаётся free-threaded CPython-процессом и не импортирует native inference
runtime. Локальный Ollama-сервис с bundled native `llama.cpp` runner запускается отдельным процессом. `LLM Facade` в
основном процессе является единственным владельцем этой границы: HTTP через `127.0.0.1` является его IPC-границей и
не означает обращения к облачному или иному внешнему сервису.

Внутренний typed API фасада предоставляет запрос, поток частичных результатов, финальное структурированное решение,
статус и cancellation. Через HTTP IPC фасад передаёт запрос и получает поток/результат генерации, выполняя явное
преобразование внешнего JSON/stream в внутренние типы. Dispatcher не проксирует через себя текст запроса или ответа: он
получает только структурированное решение через обычный control plane и сам проверяет его допустимость. Текст
авторитетного ответа после разрешения может идти из фасада в TTS по data plane.

Закрытие HTTP-потока при перебивании не публикует результат как актуальное решение. Для MVP это считается достаточной
защитой от stale result; отдельного подтверждения жёсткой отмены внутри native inference-процесса текущий backend не
предоставляет, и это остаётся явно зафиксированным ограничением.

### 3.2. Граница Skill & Prompt Manager

`Skill & Prompt Manager` является отдельной прикладной границей между состоянием диалога/контекстом и inference-фасадом.
Он получает финализированный пользовательский ход, разрешённый FSM `skill_id` или режим обработки, компактный snapshot
контекста, найденные фрагменты знаний и ограничения ответа. На их основе менеджер выбирает версию шаблона, применяет
generation profile и формирует единый typed `LlmRequest` для `LLM Facade`.

Шаблон, skill policy, output schema и generation profile должны иметь стабильные идентификаторы/версии. Это позволяет
сравнивать модели на одинаковом prompt-контракте и отдельно измерять влияние формулировки инструкции на задержку,
длину ответа и качество. Менеджер не принимает SIP-решений, не обходит Dispatcher/FSM и не подменяет retrieval.
В MVP их определения являются именованными константами `config/constants.py`; динамическая настройка через отдельную
административную подсистему не требуется.

Default package материализуется единственной factory `src/sip_bot/prompt/defaults.py`. Текст skill instruction и полный
template не принадлежат live/probe runner'ам: они редактируются как `DEFAULT_SKILL_INSTRUCTION` и
`PROMPT_TEMPLATE_TEXT`, а `SkillPromptManager` выполняет только проверяемую подстановку typed context/RAG/user data.

### 3.3. Локальный RAG-контур

RAG является обязательной частью демонстрационного answer path. `Context/KB Manager` владеет подготовленным корпусом,
разбиением документов на фрагменты, метаданными источников, индексом и поиском. Он возвращает `KnowledgeHit`/`KnowledgeContext`
с идентификаторами источников и оценками релевантности; эти данные передаются в `Skill & Prompt Manager` и явно
включаются в `LlmRequest`.

Первый технический кандидат для semantic retrieval — локальный вызов Ollama `/api/embed`. Embedding-модель создаёт
векторы при подготовке индекса и для поискового запроса; хранение индекса, similarity search и порог «достаточно ли
релевантен контекст» остаются ответственностью приложения. Вызов embeddings может использовать тот же `LLM Facade`
как отдельную typed-операцию, но поиск и prompt composition не переносятся в Ollama.

Индексация выполняется заранее, до звонка. Во время разговора выполняются только query embedding, локальный поиск и
передача ограниченного числа фрагментов в prompt. Ответ модели без найденного и зафиксированного локального контекста
не считается RAG-evidence; при недостаточной релевантности применяется обычное правило unknown-answer/offer-transfer.

Offline и online lifecycle разделены typed artifact boundary. Offline path валидирует versioned corpus package,
детерминированно нормализует/chunk-ит Markdown, получает embeddings через `LLM Facade`, проверяет candidate index и
атомарно публикует immutable `rag-index-v1`. Online path только загружает и проверяет готовый artifact, выполняет query
embedding и локальный retrieval; повторная векторизация корпуса в startup/call path запрещена. Один звонок использует
один knowledge snapshot, hot reload во время разговора не выполняется.

История передаётся retrieval не безусловно: она нужна для явной анафоры и коротких эллиптических follow-up, но не
должна заражать новый самостоятельный вопрос старой темой. При `sufficient=false` низкорелевантные hits сохраняются в
диагностике/report, но `Skill & Prompt Manager` не вставляет их как знания в prompt и разрешает только
`offer_transfer` с явным сообщением об ограничении и вопросом о подключении оператора.

Решение sufficiency является наблюдаемым typed результатом: вместе с final boolean сохраняются reason code,
configured/effective threshold, semantic-only threshold, lexical-semantic floor, top semantic score, фактическая и
требуемая lexical support и число содержательных query terms. Разговорная рамка запроса не увеличивает denominator
lexical gate; самостоятельный новый вопрос не наследует retrieval context старой темы.

### 3.4. Pre-call readiness и прогрев

Тяжёлые AI-провайдеры являются ленивыми: импорт, создание объекта или наличие файла модели не доказывают готовность к
первому inference. Поэтому application runtime перед финальным допуском звонка последовательно выполняет readiness stages:
строит/загружает RAG embedding index, выполняет короткий structured chat через `LlmFacade`, запускает ASR на
беззвучном входе через тот же 8 kHz → 16 kHz boundary и получает первый реальный PCM chunk от TTS. Каждый stage
фиксирует elapsed time и результат; ошибка или незавершённый результат оставляет runtime неготовым, не отправляет
`200 OK` и не открывает media. В live incoming режиме до завершения этих stages допускается только локальный
provisional `180 Ringing`; это не считается установленным разговором.

Stages выполняются последовательно, поскольку MVP использует одну GPU. Их дисковая активность переносится на bootstrap,
до звонка: пользовательская задержка разговора не должна включать загрузку весов, построение CUDA-кэшей или первый
запрос к Ollama. Это не означает постоянное удержание всех весов в GPU: фактическая резидентность и расход VRAM
фиксируются в evidence. В live gate peer запускается только после успешного `WarmupReport`.

## 3. Control plane

Через Dispatcher проходят:

- события SIP и жизненного цикла звонка;
- события `speech_started`, `pause_candidate`, `soft_endpoint`, `speech_resumed`, `hard_endpoint` и `utterance_final`;
- результаты ASR, необходимые для принятия решения;
- выбор `skill_id`, prompt policy и generation profile, разрешённые FSM для текущего состояния;
- структурированное решение LLM;
- ошибки и таймауты компонентов;
- команды открытия, закрытия, подключения и отключения каналов;
- команды `answer`, `hangup`, `transfer`;
- команды отмены ASR, LLM и TTS;
- фиксация состояния разговора и запуск пост-обработки отчёта.

Dispatcher не должен выполнять блокирующие операции и не должен ожидать завершения LLM, TTS или длительной операции SIP. Все длительные операции возвращают результат событием.

Низкоуровневый SIP-адаптер самостоятельно выполняет обязательные протокольные ответы, которым нельзя задерживаться
из-за Dispatcher: это могут быть `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, а также реакции на изменения RTP
или транспортные ошибки. Если событие имеет прикладной смысл, adapter дополнительно передаёт нормализованное событие
Dispatcher; ответ на протокол не зависит от обработки этого события.

## 4. Data plane

По data plane непосредственно передаются:

- PCM-аудио между media-слоем, VAD, ASR и TTS;
- промежуточные и финальные текстовые результаты ASR через `Transcript Assembler`;
- стабильный промежуточный текст в speculative LLM/retrieval pipeline;
- финальный текст пользовательского хода в `Skill & Prompt Manager`;
- `ContextSnapshot`, `KnowledgeContext` и выбранный skill-профиль в `Skill & Prompt Manager`;
- `KnowledgeQuery`, `KnowledgeHit` и `KnowledgeContext` между context/retrieval boundary и prompt manager;
- типизированный `LlmRequest` между `Skill & Prompt Manager` и `LLM Facade`;
- поток текстового ответа между LLM и TTS;
- потоковый ответ LLM через `LLM Facade` и HTTP IPC к Ollama;
- накопленные ASR chunks и переформатированные TTS media frames через специализированные boundary adapters;
- при необходимости — фрагменты retrieval-контекста между worker-компонентами.

Потоки данных не должны изменять состояние Dispatcher напрямую. Для каждого канала и каждого преобразования заранее
определяется владелец записи, владелец чтения, формат данных, политика переполнения, правило таймера/flush и правила
закрытия. Очередь является только механизмом доставки: она не заменяет accumulator, re-framer, pacer или фасад
процессной границы.

Для MVP предпочтителен фиксированный внутренний аудиоформат: PCM S16LE, mono, 8 kHz, с небольшими фреймами фиксированной длительности. RTP, PCMU и сетевые sequence/timestamp остаются внутри media-слоя.

Каналы должны быть ограниченными по размеру. Производитель не должен бесконечно накапливать звук или текст, если consumer отстал или остановлен.

### 4.1. Карта взаимодействий и итерационное уточнение контрактов

Схема компонентов выше является логическим overview и не заменяет карту boundary-взаимодействий. До сборки компонентов
должны быть явно перечислены узлы, направленные и обратные рёбра, control/data plane, producer, consumer, владелец
поведения, тип payload/event, lifecycle, backpressure, cancellation, stale-result policy и failure semantics.

Особенно явно фиксируются циклы: `SIP adapter ⇄ Dispatcher`, barge-in через media ingress и playback cancellation,
dialogue turn через LLM/context/FSM, transfer через SIP и fake operator, а также общий lifecycle каналов. Для каждого
цикла задаются termination и re-entrancy rules; односторонняя стрелка не считается полным описанием boundary.

Окончательные типы не обязаны быть известны до проверки producer. После появления каждого компонента его фактические
выходы инвентаризируются, сопоставляются с потребителями, а входные типы и contract tests распространяются на следующую
boundary новой ревизией contract registry. Детальная карта этой работы принадлежит
[`Map-002-I`](plans/plan-002-I-boundary-interaction-map.md), а не этому общему архитектурному overview.

## 5. Жизненный цикл каналов

Dispatcher отвечает за операции:

1. создать канал;
2. подключить producer и consumer;
3. открыть канал;
4. приостановить или перенастроить поток;
5. закрыть канал с отменой доставки;
6. удалить канал после завершения компонентов.

Закрытие канала имеет следующие свойства:

- накопленные данные после закрытия отбрасываются;
- запись в закрытый канал не блокируется и не доставляет данные consumer;
- старый канал не переиспользуется для нового этапа разговора;
- закрытие является идемпотентным;
- завершение producer и consumer не требует участия Dispatcher в переносе уже накопленной полезной нагрузки.

Отдельные идентификаторы поколений не являются обязательными для корректности. Устаревший результат должен исчезать вследствие закрытия соответствующего канала. Идентификатор этапа может использоваться дополнительно для диагностики и журналирования.

При перебивании закрывается исходящий канал TTS/playback, но входящий RTP/ASR-канал остаётся открытым. При завершении звонка закрываются все каналы разговора.

## 6. Формирование пользовательского хода

`VAD`, `Turn Detector` и `Transcript Assembler` решают разные задачи:

- VAD классифицирует небольшие аудиофреймы как речь или отсутствие речи;
- Turn Detector по последовательности VAD-решений определяет границы пользовательского хода;
- Transcript Assembler заменяет partial ASR-гипотезу целиком и не допускает накопления исправленных фрагментов в одном тексте; stable prefix продвигается только из явного поля ASR, а не из случайного совпадения соседних revisions.

В MVP используется двухступенчатая эвристика endpointing:

1. После начала тишины создаётся `pause_candidate`.
2. Через настраиваемый soft endpoint, ориентировочно 250–300 ms, стабильный префикс можно передать в speculative pipeline.
3. Если речь возобновилась, текущий ход продолжается, а speculative-канал закрывается.
4. После настраиваемого hard endpoint текущий ход финализируется. Для принятого WebRTC VAD phone baseline Map-008
   выбрала `520 ms` как минимальное значение, не дробящее контролируемую 480-ms внутривыходовую паузу на 20-ms frame
   clock; это остаётся конфигурационным ориентиром около 500 ms, а не отдельным SLA.

Сигнал LLM или другого компонента о том, что текст выглядит законченным, может использоваться как advisory `completion_hint`. Он не заменяет VAD и endpointing и не может самостоятельно менять состояние звонка.

Пользовательский ход может содержать несколько предложений. Семантическое дробление на отдельные предложения не является обязательным для MVP.

Порог hard endpoint входит в `T_endpointing` и общий бюджет задержки, а не добавляется к нему после работы модели. Поэтому speculative-обработка предназначена в том числе для сокрытия части задержки LLM и retrieval до финализации хода.

## 7. Параллелизм и синхронизация

Dispatcher последовательно изменяет состояние разговора и выполняется в основном потоке приложения. Основной поток
строится на одном `asyncio` event loop: Dispatcher и control event bus работают как задачи этого loop, а loop также
обслуживает лёгкие polling-, timer- и lifecycle-операции. `asyncio` здесь является механизмом выполнения, а не новым
архитектурным владельцем данных и не причиной переноса payload через Dispatcher.

Внутри одного event loop producer передаёт данные typed input-методу consumer напрямую либо через локальную
`asyncio.Queue`. Между worker-потоками используется только bounded thread-safe queue; `asyncio.Queue` не предназначена
для межпоточного обмена. Нативные callbacks PJSUA2/PJMEDIA, пришедшие из чужого потока, сначала попадают в такой bridge,
после чего основная asyncio-задача вызывает typed input-метод получателя.

Тяжёлые ASR/TTS операции выполняются в worker-потоках, а LLM остаётся отдельным локальным процессом через HTTP
Facade. Основной loop запускает и отменяет эти операции и принимает их компактные control results, но не выполняет
тяжёлое inference синхронно.

Переход через канал должен быть неблокирующим или иметь короткий, явно ограниченный timeout. Нельзя вызывать LLM, ASR или TTS из RTP callback-а и нельзя передавать аудиофреймы через Dispatcher.

Приоритет free-threaded CPython и проверка того, что native-модули не включают GIL обратно, описаны в [ADR-003](decisions/ADR-003-free-threaded-python.md).

## 8. Применение к кандидатам VoIP-стека

- В принятом варианте **PJSUA2 + PJMEDIA** `AudioMediaPort` напрямую связывается с audio channels, а SIP-события и команды идут через Dispatcher.
  Для free-threaded CPython generated SWIG binding должен собираться с двумя compatibility-патчами; их точное содержимое и
  порядок применения принадлежат [C1 plan](plans/plan-001-C1-sip-pjsua2-pjmedia.md), а не этому архитектурному документу.
- В варианте **Sofia-SIP + aiortp** SIP control callbacks и RTP tasks используют тот же логический контракт; asyncio может быть механизмом реализации data plane.
- В варианте **Baresip отдельным процессом** control plane проходит через control protocol, а audio data plane использует отдельный аудиомост или IPC и не смешивается с командами.

## 9. Открытые вопросы

- конкретный тип bounded channel или ring buffer;
- состав и границы `Media format/framer`, `PCM fan-out`, `ASR input accumulator` и `TTS output buffer/framer/pacer`;
- целевой размер ASR chunk (начальный кандидат — около 1 s), timer/flush policy и допустимое перекрытие соседних chunks;
- media `ptime` для входного/выходного кадра и преобразование произвольного размера TTS chunk в paced media frames;
- внутренний typed API `LLM Facade`, включая stream events, structured result, status, timeout и cancellation mapping;
- typed embedding-операцию через `LLM Facade`, локальный vector/lexical index, query latency и порог релевантности RAG;
- граница `Skill & Prompt Manager`: registry skills/templates, выбор `skill_id`, prompt version, generation profile и
  схема `LlmRequest`;
- политика переполнения для входящего аудио и текстовых потоков; для исходящего TTS принято dynamic bounded
  accumulation с явным high-water/backpressure/error поведением, а точный механизм проверяется в `005-E`;
- конкретный VAD и его проверка на no-GIL или изоляция native-модуля;
- настройка soft/hard endpointing и устойчивость к возобновлению речи;
- формат partial/final результатов и стабильного префикса в `Transcript Assembler`;
- способ согласования текстового потока LLM с разрешением Dispatcher на озвучивание;
- детали production SIP-adapter поверх принятого PJSUA2/PJMEDIA baseline; feasibility и обязательные generated-SWIG patches
  закрыты в [C1 plan](plans/plan-001-C1-sip-pjsua2-pjmedia.md).

## Связанные документы

- [Постановка задачи](requirements.md)
- [Техническое задание](technical-specification.md)
- [Процесс ведения документации](documentation-process.md)
- [ADR-001: Разделение LLM и менеджера диалога](decisions/ADR-001-llm-and-dialogue-manager.md)
- [ADR-002: Выбор локальной LLM для MVP](decisions/ADR-002-llm-model-selection.md)
- [ADR-003: Приоритет free-threaded CPython](decisions/ADR-003-free-threaded-python.md)
