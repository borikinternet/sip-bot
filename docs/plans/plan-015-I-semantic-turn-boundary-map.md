# Plan-015-I: interaction map семантического хода

Уровень: `child plan / interaction map`  
Статус: `complete 2026-09-22; revision semantic-turn-I1 accepted`  
Родитель: [`Map-015`](plan-015-semantic-turn-understanding.md)  
Evidence root: `artifacts/implementation/015-semantic-turn-understanding/015-I/`

## 1. Цель и результат

До code integration провести фактический source audit пути
`FinalUserTurn → ContextStore/FSM/ConversationPipeline → retrieval`, зафиксировать authoritative producer/consumer
contracts, ordering cycles и выпустить revision `semantic-turn-I1`. План не реализует parser или routing.

Результат считается проверенным, когда для каждого ребра известны typed payload, точный consumer input method, execution
context, lifecycle, error/cancel/stale policy и propagation checkpoint для `015-A`–`015-D`.

## 2. Извлечённые правила

| Источник | Правило | Применение | Проверка / stop condition |
|---|---|---|---|
| [`development-guidelines.md`](../development-guidelines.md) §3 | До интеграции двух и более компонентов нужна interaction map; типы проходят I0–I5 | Source audit предшествует code plans | Новый owner/edge не описан — stop |
| [`development-guidelines.md`](../development-guidelines.md) §2 | Поведение принадлежит owner данных/invariants; typed boundary не откатывается в raw mapping | Зафиксировать parser/FSM/retrieval owners и dataclasses/enums | `dict`/metadata как target contract — stop |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) §5.7A | Для каждого in-process edge нужен точный typed input-метод; прямой вызов не требует delivery owner | Инвентаризировать методы и execution context | Новый delivery facade без lifecycle — stop |
| [`requirements.md`](../requirements.md) | Dialogue manager владеет transfer/эскалацией; final text должен приводить к полноценному контекстному диалогу | Audit не передаёт SIP ownership parser'у и сохраняет содержательный residual | owner/edge audit | Parser исполняет SIP action — stop |
| [`architecture.md`](../architecture.md) §1, §5 | Text payload идёт по direct data plane, control — через dispatcher/FSM | SemanticTurn не публикуется целиком в Event Bus | Крупный text payload идёт через bus — stop |
| [`technical-specification.md`](../technical-specification.md) | Только final ASR text авторитетно меняет FSM; unknown/transfer paths валидируются менеджером | Partial hypotheses вне новой boundary; actions остаются validated | source map | Partial text или parser обходит FSM — stop |
| [`ADR-005`](../decisions/ADR-005-semantic-turn-understanding.md) | Один final turn может иметь ordered acts; raw context не дублируется | Карта фиксирует ordering и context edge | Один-act passthrough остаётся параллельным authoritative path — stop |
| [`development-guidelines.md`](../development-guidelines.md) §4, §8 | Субагент не решает gap; child закрывается только complete/blocked | Этот docs/shared-contract plan исполняет главный executor | Partial closeout — stop |
| [`documentation-process.md`](../documentation-process.md) | Architecture/ТЗ/ADR/roadmap/registry имеют отдельных владельцев | I revision синхронизирует только соответствующие owner docs и запускает registry/backlog checks | Расходящиеся дубли — stop |
| [`roadmap.md`](../roadmap.md) §13.5 | После freeze разрешён только corrective mandatory demo-flow | I ограничен topology для доказанного live defect | Новая функциональность вне Map-015 — stop |

## 3. Scope и write-set

Входит: чтение production/runtime/tests; contract inventory; узлы/рёбра/циклы; exact method proposal; I1 revision;
propagation checklist. Не входит: Python implementation, изменение runtime behavior, тестовые обходы.

Допустимый write-set:

- этот plan и родительский Map-015;
- `docs/architecture.md`, `docs/technical-specification.md` только после принятия фактической revision;
- собственный evidence root;
- registry/roadmap синхронизация главным executor.

Protected: исполненные планы 002/012/013, source code, историческое evidence.

## 4. Source-map

| Узел | Фактический источник для audit | Что инвентаризируется |
|---|---|---|
| Speech output | `speech/contracts.py`, `transcript_assembler.py`, `ingress.py` | `FinalUserTurn`, identity/generation/revision |
| Runtime wiring | `runtime_wiring.py`, `tools/run_live_bot.py` | main-loop callback и thread boundary |
| Pipeline | `conversation_pipeline.py` | turn cache, operation ID, inference start/cancel |
| Composition/context | `runtime_composition.py`, `context/store.py` | one-write policy, direct FSM call |
| Dialogue | `dialogue/fsm.py`, `dialogue/actions.py`, events | state expectation, transition ordering, terminal actions |
| Retrieval | `retrieval/query_builder.py`, `retrieval/index.py` | authoritative query text и sufficiency diagnostics |
| Report | `report/builder.py` | raw turn, semantic trace, RAG trace |

## 5. Candidate edges и exact consumer methods

`015-I` проверяет и либо принимает, либо корректирует следующие signatures до начала A/B/C:

| Edge | Payload | Consumer method | Context |
|---|---|---|---|
| FSM → parser | `DialogueExpectation` | `DialogueFSM.current_expectation()` read-only result передаётся в `SemanticTurnParser.parse(...)` | main loop |
| Assembler → parser | `FinalUserTurn` | `SemanticTurnParser.parse(turn, expectation)` | main loop, direct |
| Parser → pipeline/composition | `SemanticTurn` | `ConversationPipeline.submit_semantic_turn(turn)` | main loop, direct |
| Composition → context | raw `FinalUserTurn` identity/text | `ContextStore.append_user(...)` ровно один раз | main loop, direct |
| Composition → FSM | ordered `DialogueAct` | `DialogueFSM.handle(act)` | main loop, sequential |
| Content act → inference | typed content cached by pipeline before FSM emits `START_INFERENCE` | existing command observer consumes compact operation ID | direct payload + control result |
| FSM → static reconfirmation playback | compact typed command without question text payload | existing pipeline/TTS consumer resolves configured `TRANSFER_CONFIRMATION_TEXT` | control command + direct TTS payload |
| Query → retrieval | `KnowledgeQuery` built from content act | `LocalKnowledgeIndex.query(...)` | existing worker |

## 6. Cycles и termination

- Reject cycle: expectation → reject act → `LISTENING`; следующий knowledge act может перейти в `THINKING`.
- Offer cycle: insufficient RAG → `offer_transfer` playback → `AWAITING_TRANSFER_CONFIRMATION` → новая expectation.
- Pure-confirm transfer cycle: accepted confirmation без content → `TRANSFERRING`.
- Compound-positive cycle: confirm + content сохраняет typed pending reconfirmation, выполняет content path, после
  answer playback повторно предлагает transfer и только новое pure confirmation переводит в `TRANSFERRING`.
- Если content path сам вернул `offer_transfer`, этот playback считается повторным вопросом и не дублируется.
- `clarify` и barge-in не завершают pending reconfirmation; reject, successful transfer, BYE/terminal и call close
  завершают его.
- Cancellation: barge-in/BYE/call generation rules остаются существующими; semantic acts с неактуальным lease не
  применяются.
- Re-entrancy: FSM commands могут синхронно наблюдаться pipeline, но act iteration не должна повторно войти в parser.

## 7. Owner review

Новых вопросов нет: Map-015 §7 зафиксировал compound-positive policy. Обнаруженный новый owner, queue, IPC или
необходимость изменить эту policy регистрируется как gap, а не решается в этом plan.

### 7.1. Process invariant audit

- Scope ограничен read-only source audit и документальной contract revision; code write запрещён.
- I0–I4 выполняются последовательно главным executor; delegation неприменимо из-за общих документов и owner audit.
- Красный finding не «исправляется» adapter'ом: category-4 topology gap оформляется blocker.
- Registry/backlog checks обязательны при closeout.

### 7.2. Architecture invariant audit

- Проверяются разделение control/data plane, direct consumer methods и отсутствие нового delivery owner.
- Проверяются все обратные рёбра `act → FSM command → pipeline result`, termination/cancellation/re-entrancy.
- `ContextStore` не становится владельцем live FSM state; Event Bus не получает full semantic text.
- Plan-014 authoritative `turn_id`/generation остаётся protected speech identity boundary.

## 8. Implementation slices и blocker register

1. `I0`: инвентаризировать фактические producers/consumers и текущие tests.
2. `I1`: определить contract fields/errors/lifecycle и exact methods.
3. `I2`: перечислить fixtures/consumer updates для A/B/C.
4. `I4`: проверить cycles, terminal/cancel/re-entrancy.
5. Выпустить revision и handoff.

| ID | Срез | Триггер | Блокируется | Владелец | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-015-I-001` | I1 | Нужен новый delivery/orchestration owner | A/B/C | project owner | source/interaction audit | `not triggered; direct methods sufficient` |
| `B-015-I-002` | I4 | Нельзя упорядочить acts без изменения main-loop/thread model | B/D | project owner | cycle trace | `not triggered; sequential main-loop application` |
| `B-015-I-003` | I1 | Требуется изменить protected ASR identity contract | Все | project owner | Plan-014 revision audit | `not triggered; identity preserved` |

## 9. Test/evidence и closeout

Проверки: `rg`/source audit, существующие contract/state tests inventory, документационная consistency и
`python tools/check_document_registry.py`. Runtime/GPU tests неприменимы: code не меняется.

Fallback/deferred register: `none`; plan не создаёт code path и не откладывает обязательное executable evidence.

Итоговый статус только `complete` с revision/handoff либо `blocked` с concrete category-4 gap. Отчёт обязан указать
фактические signatures, changed docs, registry result и какие планы разблокированы.

## 10. Closeout

Source audit завершён. Принята revision [`semantic-turn-I1`](../../artifacts/implementation/015-semantic-turn-understanding/015-I/contract-revision.md):
protected `FinalUserTurn` сохраняется как source identity, parser создаёт ordered typed acts, materialization выполняют
методы существующих consumers в main loop. Новый owner/queue/IPC не требуется; `015-A` и `015-C` разблокированы.
