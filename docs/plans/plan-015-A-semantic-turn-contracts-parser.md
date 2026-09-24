# Plan-015-A: typed semantic-turn contracts и deterministic parser

Уровень: `child plan`  
Статус: `complete 2026-09-22; ru-semantic-turn-v1`  
Родитель: [`Map-015`](plan-015-semantic-turn-understanding.md)  
Зависимость: `015-I complete`, принятая contract revision  
Evidence root: `artifacts/implementation/015-semantic-turn-understanding/015-A/`

## 1. Цель и результат

Реализовать typed `DialogueExpectation`, вариантные `DialogueAct`, `SemanticTurn` и владельца
`SemanticTurnParser`, который детерминированно выделяет управляющий prefix и содержательный residual без изменения FSM,
ContextStore, retrieval или SIP.

## 2. Materialized rules

| Источник | Правило | Применение | Проверка / stop condition |
|---|---|---|---|
| `015-I` accepted revision | Producer contract сначала, затем consumer | Реализуются только принятые fields/signatures | Revision изменилась — stop/replan |
| [`requirements.md`](../requirements.md) | Dialogue manager, а не parser/LLM, владеет transfer и call state | Parser только размечает final text | State/SIP side effect — stop |
| [`technical-specification.md`](../technical-specification.md) | Только final ASR text является основанием authoritative решения | Parser принимает `FinalUserTurn`, не partial hypothesis | Partial input path — stop |
| [`ADR-005`](../decisions/ADR-005-semantic-turn-understanding.md) | Parser выдаёт ordered acts и не исполняет их | Pure semantic owner без FSM/SIP calls | Parser мутирует state — stop |
| [`development-guidelines.md`](../development-guidelines.md) §2 | Typed-first, owner object, без raw dict target API | Frozen dataclasses/enums/union и parser class | Mapping/stringly API — stop |
| [`development-guidelines.md`](../development-guidelines.md) §1, §6.1 | Узкий slice; красная unit/fixture ошибка исправляется в scope | Только contracts/parser/tests | Новый component boundary — gap |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Субагент соблюдает write-set и передаёт diff/tests/evidence | Допускается delegation после I | Общий файл B/C изменён — stop |
| [`documentation-process.md`](../documentation-process.md) | Фактические contracts после acceptance синхронизируются в owner docs; registry/backlog проверяются | A передаёт contract handoff, общие docs меняет main executor | Самостоятельная правка shared docs — stop |
| [`roadmap.md`](../roadmap.md) §13.5 | После freeze только critical corrective scope | A реализует только parser доказанного compound-turn defect | Расширение до open-domain NLU — stop |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Self-contained write-set/blockers/tests/closeout обязателен | Этот plan материализует A scope | Новый gap без replan — stop |

## 3. Scope, owner и write-set

Входит:

- contracts: raw identity, ordered acts, source spans, target/decision/content и parse diagnostics;
- expectation `none`/confirmation с pending target;
- unambiguous yes/no, polite variants, explicit operator request, residual question;
- default ordinary knowledge request preserving authoritative content;
- ambiguity policy без LLM fallback;
- unit/contract fixtures на русском языке.

Не входит: FSM transitions, operation IDs, ContextStore, retrieval score, LLM/Ollama, configuration threshold.

Предлагаемый write-set после I-confirmation:

- `src/sip_bot/understanding/__init__.py`;
- `src/sip_bot/understanding/contracts.py`;
- `src/sip_bot/understanding/parser.py`;
- `tests/unit/test_semantic_turn_parser.py`;
- этот plan и собственный evidence.

Все runtime/FSM/retrieval/config/common docs защищены. `SemanticTurnParser` владеет grammar и parse invariants; свободные
normalization helpers допустимы только как private pure functions этого owner.

### 3.1. Source-map

| Область | Вход | Выход/изменение | Protected consumer |
|---|---|---|---|
| Contracts | accepted I revision | Typed expectation/act/turn definitions | FSM/pipeline до B не меняются |
| Parser owner | final turn + expectation | Ordered acts + diagnostics | Никаких state/network calls |
| Fixtures/tests | Russian phrase matrix | Exact acts/spans/order | Live/RAG fixtures не меняются |

## 4. Required behavior

Минимальная матрица:

| Input + expectation | Ordered output |
|---|---|
| `Нет.` + transfer confirmation | `RejectPendingAct` |
| `Нет, спасибо, не надо.` | `RejectPendingAct` |
| `Нет, не надо. Почему небо голубое?` | `RejectPendingAct`, `KnowledgeRequestAct` |
| `Да, соедините.` | `ConfirmPendingAct` |
| `Да, но сначала скажите, почему небо голубое?` | `ConfirmPendingAct`, `KnowledgeRequestAct` |
| `Переведите меня на оператора.` + none | `TransferRequestAct` |
| `Почему небо голубое?` + none | `KnowledgeRequestAct` |
| неоднозначное подтверждение | не исполнять confirm/reject; typed clarification/default policy из I revision |

Spans не перекрываются, residual не пустой после trim punctuation/polite connective, исходный `FinalUserTurn` не
переписывается. Parser не делает retrieval и не определяет RAG relevance.

## 5. Slices, tests и blockers

1. Contracts с validation/invariants и exact serialization diagnostics.
2. Parser grammar/tokenization и expectation-aware ordered output.
3. Positive/negative/compound/ambiguous corpus tests; property checks на span preservation.
4. Target CPython 3.14t import/operation/GIL probe; native imports не добавляются.

| ID | Срез | Триггер | Блокируется | Владелец | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-015-A-001` | 1 | I revision требует нового cross-thread lifecycle | A/B | project owner | contract audit | `none until triggered` |
| `B-015-A-002` | 2 | Надёжный fast path требует новой NLP/model dependency | A | project owner | corpus failures after corrective pass | `none until triggered` |
| `B-015-A-003` | 3 | Ambiguous input приводит к критичному act | A/B | executor | failing unit evidence | `none until triggered` |

Acceptance: unit/contract matrix зелёная; no state/network/model calls; exact types экспортированы; GIL остаётся
выключенным; handoff содержит diff, commands/exit codes и accepted output revision. Итоговый статус только
`complete`/`blocked`.

### 5.1. Owner review

Отдельных вопросов нет: отсутствие LLM fallback, compound-reject и compound-positive/reconfirmation policy уже
отражены в Map-015/ADR-005. Любая необходимость model dependency или нового ambiguity policy является gap и
возвращается главному executor.

### 5.2. Process invariant audit

- Plan допускает субагента только после complete I и только в перечисленном write-set.
- Subagent handoff обязан содержать diff, runtime, commands/exit codes, failures и contract revision; main executor
  повторяет targeted tests.
- Ошибки grammar/fixture в scope исправляются без снижения acceptance; partial closeout запрещён.

### 5.3. Architecture invariant audit

- Parser владеет только интерпретацией text+expectation; FSM state и SIP actions защищены.
- Output только typed objects; raw dict/string action API запрещён.
- Parser stateless/per-call data не удерживает вне входного SemanticTurn; новый lifecycle/queue не вводится.
- Raw `FinalUserTurn` identity/generation/revision сохраняются в target contract.

## 6. Fallback и closeout

LLM/parser model, legacy raw-turn passthrough и regex, исполняющий SIP action, отсутствуют. Обычный текст →
`KnowledgeRequestAct` является основной semantic policy, а не compatibility fallback.

Closeout синхронизирует только фактический contract handoff; общие architecture/registry документы меняет главный
executor после проверки.

## 7. Closeout

Контракты и parser реализованы по `semantic-turn-I1`. Target CPython 3.14t: `16 passed`; GIL до/после import и parse
остаётся выключенным. Evidence: [`015-A/closeout.md`](../../artifacts/implementation/015-semantic-turn-understanding/015-A/closeout.md).
Новые зависимости и blockers отсутствуют; `015-B` разблокирован по producer contract.
