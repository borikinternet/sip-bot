# Карта 015: семантический ход и корректная маршрутизация составной реплики

Уровень: `map`  
Идентификатор: `Map-015`  
Статус: `complete`  
Дата: `2026-09-22`  
Родитель: [`roadmap.md`](../roadmap.md)  
Evidence root: `artifacts/implementation/015-semantic-turn-understanding/`

## 1. Цель и проверяемый результат

Устранить два доказанных последним live-звонком semantic-path дефекта без передачи control decisions большой LLM:

1. одна финальная ASR-реплика может содержать несколько действий, например отказ от перевода и новый вопрос;
2. RAG может найти правильный первый fragment выше конфигурационного threshold, но вернуть `sufficient=false` из-за
   дополнительных непрозрачных lexical/semantic условий.

Проверяемый результат:

- `FinalUserTurn` преобразуется в typed `SemanticTurn` с упорядоченными dialogue acts;
- `Нет, не надо. Почему небо днём голубое?` сначала отклоняет pending transfer, затем запускает retrieval/answer для
  содержательной части того же хода;
- `Да, соедините, но сначала ответьте ...` не начинает transfer немедленно: бот отвечает на content и после playback
  повторно спрашивает подтверждение перевода;
- исходный текст сохраняется в контексте один раз, acts и их spans наблюдаемы в evidence/report;
- явное подтверждение, отказ, прямая просьба об операторе, обычный вопрос и unknown-answer сохраняют согласованную FSM
  semantics;
- configured RAG threshold и фактические условия `sufficient` становятся согласованными и наблюдаемыми;
- positive/paraphrase/negative evaluation, state-machine/integration tests и повторный registered live call зелёные.

## 2. Почему это карта

Работа имеет пять самостоятельных acceptance boundary: topology/contracts, semantic parser, FSM/runtime integration,
RAG relevance и live validation. Их нельзя закрыть одним code diff или одним тестом. Карта разложена на `015-I`,
`015-A`–`015-D`; каждый code/evidence пункт имеет отдельный self-contained plan и blocker register.

## 3. Применимые правила и их materialization

| Источник | Материализованное правило | Влияние | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Dialogue manager владеет состоянием и эскалацией; LLM не исполняет SIP-команды произвольным текстом | Semantic parser формирует typed acts, а необратимые действия применяет FSM | state-machine/transfer tests | Parser самостоятельно вызывает SIP/transfer |
| [`architecture.md`](../architecture.md) | `FinalUserTurn` и крупный текст идут напрямую по data plane; Dispatcher/Event Bus обслуживает control plane | Новые text payload не проходят через bus; materialization — методы consumers | topology/source audit | Появляется delivery owner или text bus |
| [`technical-specification.md`](../technical-specification.md) | Финальный ASR text является единственным основанием authoritative решения; insufficient RAG обязан вести к unknown-answer | Parser принимает только final turn; relevance correction не разрешает model-only answer | contract/RAG evaluation | Partial ASR меняет FSM либо negative RAG становится answer |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM, prompt manager и FSM имеют разные ownership | Parser не объединяется с answer LLM и не обходит action validation | boundary tests | Свободный LLM output исполняется как control action |
| [`ADR-005`](../decisions/ADR-005-semantic-turn-understanding.md) | Один user turn представляется упорядоченным набором acts; raw text сохраняется один раз | Контракты и ordering являются baseline карты | contract/context tests | Реализация снова предполагает один intent на turn |
| [`development-guidelines.md`](../development-guidelines.md) §1–§3 | Typed-first, владелец поведения, iterative propagation, direct consumer method; no delivery owner | `015-I` фиксирует revision, A/C могут идти параллельно только после неё, B/D потребляют принятую revision | I0–I5 checkpoints | Consumer реализуется до authoritative producer contract |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Субагент работает только по self-contained plan/write-set; общий integration и GPU gate проверяет главный executor | A и C допускают параллельную делегацию при непересекающихся write-set; B/D последовательны | handoff + main audit | Пересечение write-set или самостоятельное архитектурное решение |
| [`development-guidelines.md`](../development-guidelines.md) §6–§8 | Красный тест текущего scope исправляется; обязательный gate нельзя компенсировать; child closeout только complete/blocked | Каждый child имеет собственное acceptance и corrective pass | raw commands/evidence | Partial/foundation claim либо пропущенный mandatory test |
| [`documentation-process.md`](../documentation-process.md) | Архитектура, ТЗ, ADR, roadmap и registry имеют разных владельцев; после Markdown — registry audit | Фактическая topology идёт в architecture, конкретные контракты в ТЗ, причина в ADR | registry/backlog audit | Дублирующие расходящиеся нормы |
| [`roadmap.md`](../roadmap.md) §13.5 | После code/demo freeze допускаются только изменения, закрывающие конкретный обязательный demo-flow | Map-015 исправляет воспроизведённую потерю вопроса и ложный отказ в обязательном диалоге, а не добавляет произвольную функцию | live defect evidence + scope audit | Работа расширяется за пределы corrective flow |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | FSM/typed-boundary/user-flow change требует полного gate, child plans, blockers и closeout | Этот map и пять child plans материализуют scope | APG audit до execution и closeout | Открытый category-4 gap |

## 4. Граница задачи

```text
Входит:
  typed DialogueExpectation, DialogueAct и SemanticTurn;
  state-aware deterministic SemanticTurnParser;
  compound reject/confirm plus residual content;
  explicit operator request и ordinary knowledge request;
  ordered act application through existing FSM/pipeline owners;
  one-write raw ContextStore policy и semantic diagnostics;
  correction and observability of RAG sufficient policy on an expanded immutable suite;
  target-runtime tests and registered live evidence.

Не входит:
  LLM semantic-parser fallback;
  новая intent/slot neural model и её обучение;
  изменение ASR/VAD/endpointing, SIP/PJMEDIA, TTS или audio topology;
  смена embedding/chat model, vector DB или RAG corpus;
  production-grade open-domain NLU claim.

Protected baseline:
  один активный звонок; Dispatcher/FSM control ownership;
  direct text/audio data plane; обязательный source-aware RAG;
  unknown-answer → offer-transfer и explicit transfer requirement;
  free-threaded CPython target runtime и текущие process boundaries.

Рабочее дерево:
  содержит результаты предыдущих карт; unrelated changes сохраняются и не входят в write-set.
```

Не включённый LLM parser не является fallback или обещанным deferred acceptance. Его добавление потребует отдельного
evidence-driven плана после корпуса неоднозначных реплик.

### 4.1. Source-map и map-level write-set

| Область | Текущее поведение | Целевое поведение | Файлы/owner | Plan |
|---|---|---|---|---|
| Final text boundary | `FinalUserTurn` сразу сохраняется и передаётся FSM | Final text сначала становится `SemanticTurn` | `speech/contracts.py`, новый semantic owner | I/A |
| Dialogue expectation | Скрыта в `DialogueFSM.state`/pending action | Read-only typed expectation | `dialogue/fsm.py` | I/B |
| Compound routing | Весь текст классифицируется как одно confirmation | Ordered control/content acts | `runtime_composition.py`, `conversation_pipeline.py`, FSM | B |
| Transfer reconfirmation | Нет отдельной application-owned короткой реплики | Typed playback command + configured short question через существующий TTS path | dialogue command, pipeline, `config/constants.py` | I/B |
| Context/report | Raw user text есть, semantic outcome не объяснён | Raw once + acts/applied outcomes diagnostics | `context/store.py`, `report/builder.py` | B/D |
| Retrieval sufficiency | Config threshold не объясняет дополнительные gates | Frozen evaluation и все effective criteria/reason codes | `retrieval/query_builder.py`, `index.py`, evaluation | C |
| Live proof | Последний call содержит false unknown/lost questions | Registered compound scenario с записью и trace | live tools/stand/evidence | D |

Кодовые write-set разделены child plans. Общие `report/builder.py`, config и документы изменяются последовательно
главным executor; исполненные планы и исторические artifacts защищены.

## 5. Interaction topology и propagation

Baseline revision до source audit: `semantic-turn-I0-candidate`.

```text
DialogueFSM --DialogueExpectation--> SemanticTurnParser
                                           ▲
TranscriptAssembler --FinalUserTurn--------┘
                                           │ SemanticTurn[acts]
                                           ▼
                            ConversationPipeline / CallComposition
                                 │                         │
                     control act │                         │ knowledge request
                                 ▼                         ▼
                            DialogueFSM              retrieval → prompt → LLM
                                 │                         │
                                 └──── typed decision ─────┘
```

Candidate materialization methods, обязательные к подтверждению в `015-I`:

- `DialogueFSM.current_expectation() -> DialogueExpectation`;
- `SemanticTurnParser.parse(FinalUserTurn, DialogueExpectation) -> SemanticTurn`;
- `ConversationPipeline.submit_semantic_turn(SemanticTurn) -> bool`;
- `CallComposition.accept_semantic_turn(SemanticTurn) -> bool`;
- `DialogueFSM.handle(DialogueAct)` для state/control semantics;
- direct retrieval input получает `KnowledgeRequestAct.content`, а не весь confirmation turn.

Ordering cycle для отрицательного compound turn:

```text
AWAITING_TRANSFER_CONFIRMATION
  → RejectTransferAct
  → LISTENING
  → KnowledgeRequestAct
  → THINKING / START_INFERENCE
  → answer | offer_transfer
```

Цикл для положительного compound turn:

```text
AWAITING_TRANSFER_CONFIRMATION
  → ConfirmTransferAct + KnowledgeRequestAct
  → сохранить PendingTransferReconfirmation, не выполнять transfer
  → THINKING → answer/clarify playback
  → повторный offer-transfer playback
  → AWAITING_TRANSFER_CONFIRMATION
  → новое pure confirm → TRANSFERRING
```

Если content path сам возвращает `offer_transfer`, этот playback закрывает обязанность повторного вопроса и второй
одинаковый offer не создаётся. `clarify` удерживает pending reconfirmation до последующего содержательного ответа;
barge-in отменяет текущий playback, но сам по себе не стирает pending intent.

Acts применяются последовательно в основном loop. Отдельная очередь, Event Bus payload или delivery component не
вводятся. Межпоточная LLM/RAG/TTS работа сохраняет существующие bounded/control-result boundaries.

## 6. Audit владельцев поведения

| Поведение | Владелец | Основание |
|---|---|---|
| Интерпретация text + expectation в acts | `SemanticTurnParser` | Владеет grammar/policy и typed semantic output, но не call state |
| Expected response и pending transfer target | `DialogueFSM` | Владеет текущим semantic state и допустимыми переходами |
| Последовательное применение acts | `DialogueFSM` через существующую composition | Только FSM может изменить state или разрешить transfer/inference |
| Хранение raw user turn | `ContextStore` | Владеет bounded conversation history; derived span не дублируется |
| Query normalization/retrieval sufficiency | query builder / local index | Владеют query contract, scoring и source-aware context |
| Direct method orchestration | существующая `ConversationPipeline`/`CallComposition` | Процедурное связывание не получает нового владельца доставки |

### 6.1. Process invariant audit

| Инвариант | Применимость | Проверка/evidence |
|---|---|---|
| Узкие slices и binary child closeout | Полностью применим | I/A/B/C/D имеют отдельные acceptance/blockers; map ждёт все complete |
| Iterative contract propagation | Полностью применим | I revision предшествует A/C; A handoff предшествует B; D только после B/C |
| Делегирование по непересекающемуся write-set | Применим к A/C | Self-contained files; integration/docs/GPU остаются main executor |
| Corrective pass для красных tests | Полностью применим | Каждый child материализует category 1–4 protocol |
| Document registry/backlog integrity | Полностью применим | Checks выполняются сейчас и при каждом closeout |

### 6.2. Architecture invariant audit

| Инвариант | Затронутая boundary | Проверка/evidence |
|---|---|---|
| FSM единственный владелец semantic call state | Parser → FSM | Parser tests запрещают state/SIP side effects; FSM state tests |
| Text data plane не проходит через Event Bus | SemanticTurn/content edges | Source/topology audit и integration spy |
| Direct consumer method не создаёт delivery owner | Parser/composition/pipeline | `015-I` exact methods и отсутствие нового facade/queue |
| RAG обязателен, model-only answer запрещён | KnowledgeRequest → retrieval | Positive/negative source-aware suite и unknown-answer regression |
| Cancellation/generation защищают stale work | Compound act → inference/playback | B/D stale, BYE, barge-in tests |
| no-GIL/process baseline не меняется | Affected target runtime | CPython 3.14t import/operation evidence |

## 7. Owner review

| Вопрос | Рекомендуемое решение | Последствие | Статус |
|---|---|---|---|
| Нужен ли LLM parser в обязательном scope | Нет; сначала typed deterministic parser и измеренный corpus, без скрытого fallback | Карта не добавляет второй inference до RAG | `resolved by prior discussion; confirm with map review` |
| Что делать с `нет ... <новый вопрос>` | Применить reject, затем обработать residual knowledge request в том же semantic turn | Текущий live defect устраняется без потери текста | `resolved by owner discussion` |
| Что делать с `да ... <содержательный остаток>` | Не переводить немедленно: ответить на residual content и после ответа повторно спросить подтверждение; transfer разрешён только новым подтверждением | FSM хранит scoped pending reconfirmation и не теряет вопрос | `resolved by owner 2026-09-22` |
| Как исправлять RAG relevance | Расширить immutable suite и менять policy только при сохранении positive/negative gates; не подгонять один WAV | Configured threshold и sufficiency становятся доказуемыми | `resolved by existing Map-012 rules` |

Открытых owner-review вопросов нет. Групповой review карты и child plans завершён 2026-09-22; execution разрешается по
графу зависимостей без отдельного пересогласования каждого child plan, пока не возникает новый category-4 gap.

## 8. Child plans и граф исполнения

| Plan | Scope | Зависимость | Evidence root | Review status |
|---|---|---|---|---|
| [`015-I`](plan-015-I-semantic-turn-boundary-map.md) | Фактическая topology, типы, methods, cycles и propagation revision | Map review | `.../015-I/` | `complete; semantic-turn-I1` |
| [`015-A`](plan-015-A-semantic-turn-contracts-parser.md) | Typed contracts и deterministic parser | `015-I complete` | `.../015-A/` | `complete; ru-semantic-turn-v1` |
| [`015-B`](plan-015-B-dialogue-routing-integration.md) | FSM expectation, ordered acts, context/pipeline routing | `015-A complete` | `.../015-B/` | `complete; deterministic gate pass` |
| [`015-C`](plan-015-C-rag-sufficiency-corrective.md) | Query/relevance evaluation и corrective policy | `015-I complete`; может идти параллельно A | `.../015-C/` | `complete; frozen suite 12/12` |
| [`015-D`](plan-015-D-semantic-live-gate.md) | Integration, target runtime, registered live call и closeout | `015-B`, `015-C`, Plan-014 live closeout | `.../015-D/` | `complete; live-v7 PASS` |

```text
015-I
  ├── 015-A ── 015-B ──┐
  └── 015-C ────────────┼── 015-D ── map closeout
Plan-014 closeout ──────┘
```

`015-A` и `015-C` допускают параллельных субагентов только после принятой revision `015-I`, с непересекающимися code
write-set. Общие документы, integration и GPU/live gate изменяет и проверяет главный executor.

## 9. Map-level blocker register

| ID | Срез | Триггер | Что блокируется | Владелец | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-015-001` | B/D | Не была определена positive confirmation policy с residual content | Compound-positive routing | project owner | owner decision §7 | `resolved 2026-09-22: answer, then ask confirmation again` |
| `B-015-002` | I | Фактический runtime не позволяет ordered acts без нового delivery/orchestration owner | Все code plans | project owner | source audit + interaction map | `none until triggered` |
| `B-015-003` | C | Positive и negative RAG suite нельзя разделить текущим index/query policy без новой model/reranker boundary | C/D | project owner | immutable evaluation before/after corrective pass | `none until triggered` |
| `B-015-004` | D | Plan-014 не закрывает authoritative multi-turn speech boundary | Registered live gate | main executor | Plan-014 closeout/evidence | `resolved by Plan-014 registered r8` |
| `B-015-005` | D | Обязательный target/GPU/SIP stand недоступен после corrective retry | Live closeout | project owner | command/raw output | `none until triggered` |

## 10. Test/evidence gate

- unit contracts/parser: spans, ordering, confidence/ambiguity policy и preservation raw text;
- state-machine: pure yes/no, compound reject+question, compound confirm+question+reconfirmation, explicit transfer и stale/cancel;
- context: raw user turn ровно один раз, derived acts только в diagnostics;
- RAG: expanded immutable positive/paraphrase/contextual/negative suite, scores, lexical support и все sufficiency
  conditions в evidence;
- integration: `SemanticTurn → FSM → retrieval → LLM decision → TTS` без text Event Bus;
- target runtime: selected stable CPython 3.14t, GIL off before/after affected imports and operation tests;
- live: registered FreeSWITCH call, stereo recording, report, exact semantic trace и question answer;
- regression: unknown-answer/offer-transfer, direct transfer, barge-in, BYE/media lifecycle и affected suite.

Красный mandatory test классифицируется по `development-guidelines.md` §6.1. Ошибка реализации/fixture текущего write-set
исправляется и повторяется; только доказанный category-4 gap регистрируется как blocker.

## 11. Fallback/deferred register

| Что | Статус | Условие |
|---|---|---|
| LLM semantic-parser fallback | `not in scope; not implemented` | Новая карта только после corpus evidence неоднозначных формулировок |
| Neural intent/slot classifier | `not in scope` | Отдельный model/runtime/license/quality decision |
| Compatibility passthrough старого `FinalUserTurn → FSM` | `forbidden` | После propagation не сохраняется второй authoritative path |

Намеренных упрощений acceptance и deferred mandatory evidence нет.

## 12. Closeout gate

Карта получает `complete` только после `complete` всех обязательных child plans, принятой `semantic-turn` contract
revision, зелёной expanded RAG suite, target-runtime evidence, registered live call и синхронизации ADR/architecture/
technical-specification/roadmap/registry/backlog. Частичные `foundation`/`arch-ready` claims запрещены.

## 13. Execution closeout 2026-09-22

Все обязательные child plans `015-I`, `015-A`–`015-D` завершены. Принятая topology materialized без нового delivery
owner: final ASR text преобразуется в typed ordered acts, FSM остаётся владельцем semantic state, а knowledge content
передаётся существующему pipeline прямым методом. Expanded RAG suite завершилась `12/12`; все решения sufficiency
наблюдаемы в evidence/report.

Authoritative registered gate
[`015-D/live-v7`](../../artifacts/implementation/015-semantic-turn-understanding/015-D/live-v7/map015-semantic-live-gate.json)
завершился `status=pass` для трёх сценариев: compound reject+question, compound confirm+question+reconfirmation с
barge-in и compound unknown с единственным offer. Прямой запрос оператора выполняется и при pending confirmation;
неоднозначный текст по-прежнему не инициирует критическое действие. Host gate: `284 passed, 2 skipped`, CPython
3.14.7t free-threading, GIL off. Открытых blockers и deferred mandatory evidence нет; Map-015 закрыта `complete`.
