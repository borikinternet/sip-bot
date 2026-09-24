# Plan-015-B: Dialogue FSM и ordered semantic-act routing

Уровень: `child plan`  
Статус: `complete 2026-09-22; full deterministic gate pass`  
Родитель: [`Map-015`](plan-015-semantic-turn-understanding.md)  
Зависимости: `015-I complete`, `015-A complete`  
Evidence root: `artifacts/implementation/015-semantic-turn-understanding/015-B/`

## 1. Цель и результат

Материализовать принятую semantic-turn boundary в существующих `DialogueFSM`, `CallComposition` и
`ConversationPipeline`: FSM публикует typed expectation, acts применяются последовательно, raw user turn записывается
один раз, а knowledge content запускает существующий inference path после разрешённых state transitions.

## 2. Materialized rules

| Источник | Правило | Применение | Проверка / stop condition |
|---|---|---|---|
| `015-I`/`015-A` handoff | Consumer использует фактический producer contract без переизобретения adapter | Exact accepted types/methods | Нужен bridge/raw mapping — stop |
| [`requirements.md`](../requirements.md) | Dialogue manager владеет состоянием, эскалацией, перебиваниями и structured call actions | Pending reconfirmation и transfer остаются FSM state/policy | Parser/pipeline исполняет SIP — stop |
| [`architecture.md`](../architecture.md) | FSM владеет semantic state; text payload идёт напрямую, control result — через dispatcher path | FSM не получает SIP power parser'у; pipeline cache сохраняет direct text | SemanticTurn проходит через Event Bus — stop |
| [`technical-specification.md`](../technical-specification.md) | Positive confirmation переводит, explicit request переводит без LLM; final text авторитетен | Compound-positive owner override материализован как answer-then-reconfirm, pure confirm сохраняет transfer | Raw/partial text обходит validation — stop |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md) | Необратимые действия проверяет dialogue manager | Transfer/answer остаются validated commands | Parser/LLM исполняет transfer — stop |
| [`ADR-005`](../decisions/ADR-005-semantic-turn-understanding.md) | Ordered acts, one-write raw context, no parallel authoritative legacy path | Старый `FinalUserTurn → FSM` удаляется после propagation | Два пути меняют FSM — stop |
| [`development-guidelines.md`](../development-guidelines.md) §3 | Direct consumer method — materialization; новый delivery owner не нужен | Используются exact methods I revision | Новый facade только для wiring — stop |
| [`development-guidelines.md`](../development-guidelines.md) §6.1 | State/integration failures текущего scope исправляются и rerun | Targeted + affected regression | Ослабление assertion/skip — stop |
| [`documentation-process.md`](../documentation-process.md) | Architecture/ТЗ/ADR и registry синхронизируются у своих владельцев | B closeout передаёт фактические transitions/contracts main executor | Plan становится единственным owner нормы — stop |
| [`roadmap.md`](../roadmap.md) §13.5 | После freeze только mandatory corrective flow | B закрывает воспроизведённую потерю вопроса | Новый dialogue feature вне матрицы — stop |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | FSM/user scenario change требует state tests, blockers и full closeout | B содержит explicit matrix/corrective protocol | Partial pass объявлен complete — stop |

## 3. Scope и write-set

Входит:

- read-only/current `DialogueExpectation` от FSM;
- ordered handling semantic acts и terminal-act policy;
- cache content act до компактного `START_INFERENCE` command;
- сохранение operation/generation/stale/cancel invariants;
- raw context once и semantic trace для отчёта;
- удаление старого authoritative direct `FinalUserTurn → FSM` path;
- unit/state/integration tests.

Не входит: parser grammar, RAG scoring, prompt content, LLM/TTS/SIP implementation, Event Bus topology.

Допустимый write-set после I/A handoff:

- `src/sip_bot/dialogue/fsm.py`, необходимые dialogue contracts/exports;
- `src/sip_bot/runtime_composition.py`;
- `src/sip_bot/conversation_pipeline.py`;
- `src/sip_bot/runtime_wiring.py` только в точке accepted input materialization;
- `src/sip_bot/report/builder.py` для semantic diagnostics;
- `config/constants.py`, `src/sip_bot/config.py` только для именованного `TRANSFER_CONFIRMATION_TEXT`;
- targeted unit/integration tests;
- этот plan и собственный evidence.

Остальная конфигурация, retrieval, speech/VAD/ASR, SIP/media и TTS implementation защищены.

### 3.1. Source-map

| Область | Текущий input/behavior | Целевой consumer/change |
|---|---|---|
| FSM | `FinalUserTurn` special-case, exact-string confirmation | `DialogueAct` handlers + typed current expectation |
| Pipeline | Кэширует whole final turn по предполагаемому operation ID | Кэширует content act до authoritative FSM start command |
| Composition | Append raw + direct FSM whole turn | Append raw once + ordered act iteration |
| Runtime wiring | Final turn вызывает `submit_final_turn` | Final turn parsed once, затем `submit_semantic_turn` |
| Report | Raw context/RAG/FSM only | Parse acts, applied/ignored outcome and reason |
| Static reconfirmation | Нет отдельного application-owned вопроса | Configured short text, compact FSM command, existing TTS path |
| Tests | Single-intent confirmation cases | Compound ordering/context/stale matrix |

## 4. Interaction и ordering acceptance

- `submit_semantic_turn()` проверяет call lease/generation до записи или act application;
- raw final text попадает в `ContextStore` один раз независимо от количества acts;
- reject pending transfer переводит `AWAITING_TRANSFER_CONFIRMATION → LISTENING`;
- следующий knowledge act того же turn получает новый operation ID и запускает один inference;
- pure negative не запускает inference;
- explicit transfer request исполняется через существующий validator/command path;
- pure positive confirmation без content исполняет transfer через существующий validator/command path;
- positive confirmation с content не переводит немедленно: FSM сохраняет scoped pending reconfirmation, запускает
  content inference, после ответа повторно предлагает transfer и ждёт новое подтверждение;
- если content result уже `offer_transfer`, этот playback является повторным вопросом и не дублируется;
- `answer` playback completion запускает configured static reconfirmation; `clarify` удерживает pending intent до
  последующего ответа; static question не проходит через answer LLM/RAG;
- barge-in отменяет текущий playback, но pending reconfirmation сохраняется до следующего завершённого content path;
- pending reconfirmation очищается при pure reject, successful transfer, BYE/terminal и call-generation close;
- BYE/cancel между acts прекращает дальнейшее применение;
- barge-in/stale result/generation rules не ослабляются;
- report различает raw turn, parse acts, applied/ignored outcome и reason.

## 5. Slices и blockers

1. FSM expectation и typed act handlers с state tests.
2. Composition/pipeline materialization, operation cache и one-write context.
3. Semantic report trace и stale/cancel/terminal integration tests.
4. Affected regression на target runtime.

| ID | Срез | Триггер | Блокируется | Владелец | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-015-B-001` | 1 | Positive compound policy не была принята | B/D | project owner | Map-015 owner-review | `resolved 2026-09-22: answer then reconfirm` |
| `B-015-B-002` | 2 | Ordered acts требуют нового queue/delivery owner | B/D | project owner | source/cycle audit | `none until triggered` |
| `B-015-B-003` | 2 | Существующий operation-id contract не допускает второго act того же turn | B/D | executor, затем owner при category 4 | failing contract + corrective pass | `none until triggered` |
| `B-015-B-004` | 3 | Context/report не могут сохранить trace без изменения required artifact format | B/D | project owner | report contract evidence | `none until triggered` |

### 5.1. Owner review

Открытых вопросов нет. Positive confirmation с residual content сохраняет pending reconfirmation, отвечает на content
и повторно спрашивает перевод; решение принято owner 2026-09-22 и не выносится повторно.

### 5.2. Process invariant audit

- B исполняется только после complete I/A и принятого owner decision; параллельная правка shared FSM/pipeline запрещена.
- Red state/integration test категории 1/2 исправляется в write-set и rerun; category 4 требует evidence и stop.
- Main executor проверяет любой delegated handoff; фактический B предпочтительно исполняется последовательно из-за
  shared orchestration files.
- Registry/backlog и owner docs синхронизируются только после accepted behavior.

### 5.3. Architecture invariant audit

- FSM остаётся единственным owner state/transfer; parser act — входное предложение, не исполненная команда.
- Semantic text materialized прямыми methods; Event Bus получает только compact existing control commands/results.
- Operation ID/generation/cancel/stale semantics сохраняются для каждого запущенного content act.
- ContextStore хранит raw text once и не дублирует derived request как новый пользовательский ход.
- После propagation старый authoritative `FinalUserTurn → FSM` path отсутствует.
- Static reconfirmation повторяет greeting pattern: compact command, configured text и существующий direct TTS path,
  без нового media/delivery owner.

## 6. Test/evidence и closeout

Обязательны: unit FSM matrix; context no-duplicate; pipeline compound turn; explicit/confirmed/declined transfer;
unknown-answer loop; stale/cancel/BYE; affected full suite; CPython 3.14t GIL probe. GPU/live не выполняются в B и не
считаются закрытыми — они принадлежат D.

Fallback register: `none`; старый direct raw-turn path не сохраняется. Итоговый статус только `complete` после всех
acceptance и handoff в D либо `blocked` по доказанному category-4 gap.

## 7. Closeout

Материализованы exact methods `current_expectation()`, `submit_semantic_turn()`, `accept_semantic_turn()` и
`DialogueFSM.handle(DialogueAct)`. Legacy `FinalUserTurn → FSM` path удалён. Compound reject/confirm, explicit transfer,
one-write context, static re-confirmation, semantic report trace, stale/cancel/BYE и affected runtime regression
проходят. Target CPython 3.14t: `282 passed, 2 skipped`; GIL before/after `false`. Blockers не сработали. Evidence:
[`015-B/closeout.md`](../../artifacts/implementation/015-semantic-turn-understanding/015-B/closeout.md).
