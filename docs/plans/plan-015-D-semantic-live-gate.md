# Plan-015-D: сквозной semantic-turn и RAG live gate

Уровень: `child plan`  
Статус: `complete`  
Родитель: [`Map-015`](plan-015-semantic-turn-understanding.md)  
Зависимости: `015-B complete`, `015-C complete`, Plan-014 live closeout  
Evidence root: `artifacts/implementation/015-semantic-turn-understanding/015-D/`

## 1. Цель и результат

Проверить на target runtime и зарегистрированном FreeSWITCH-тракте, что составная реплика корректно проходит
`ASR final → SemanticTurn → FSM → RAG → LLM → TTS`, не теряет content, не дублирует context, не ломает transfer и
оставляет достаточное evidence для закрытия Map-015.

## 2. Materialized rules

| Источник | Правило | Применение | Проверка / stop condition |
|---|---|---|---|
| `015-I`–`015-C` | Integration использует только принятые revisions и handoffs | Перед deploy проверить фактический diff/contracts | Незакрытый predecessor — stop |
| [`requirements.md`](../requirements.md) | Полный русский source-aware диалог, barge-in, transfer и end-to-end latency оцениваются с точки зрения пользователя | Registered matrix проверяет слышимый ответ и control outcomes | Synthetic-only pass — stop |
| [`architecture.md`](../architecture.md) | Control/data plane разделены; protocol reaction не ждёт AI; FSM валидирует действия | Live trace сверяет direct semantic payload и compact control | Text через bus или SIP ждёт AI — stop |
| [`technical-specification.md`](../technical-specification.md) | Readiness до 200 OK, final-ASR authority, unknown/transfer/report contracts обязательны | Gate использует production readiness и сохраняет полный report | Обход readiness/production path — stop |
| [`development-guidelines.md`](../development-guidelines.md) §6 | Обязательны state/integration, protocol during AI, barge-in, cancellation, multi-turn, unknown/transfer | Gate содержит semantic scenario и affected resilience | Зелёный соседний тест вместо mandatory — stop |
| [`development-guidelines.md`](../development-guidelines.md) §5 | Target — stable free-threaded CPython; native/GIL evidence обязательно | Выбранный executable и imports фиксируются | GIL on/обычный Python — stop |
| [`development-guidelines.md`](../development-guidelines.md) §4 | GPU/live и финальную сверку выполняет главный executor | Субагент может подготовить fixtures, но не закрыть live gate отчётом | Непроверенный handoff — stop |
| [`documentation-process.md`](../documentation-process.md) | После фактического pass обновляются owner docs, registry/backlog | Closeout синхронизирует ADR/architecture/ТЗ/roadmap | Исторический plan заменяет owner doc — stop |
| [`roadmap.md`](../roadmap.md) §13.5 | Rehearsal reserve допускает только critical fixes | D проверяет corrective Map-015 и не добавляет demo feature | Scope expansion — stop |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Mandatory live evidence нельзя выдать за pass при пропуске; closeout binary | D хранит raw evidence и закрывает child/map только полностью | Deferred/synthetic evidence выдано за live — stop |

## 3. Scope и write-set

Входит: integration harness/fixtures, target deployment, deterministic pre-gates, registered live call, stereo recording,
semantic/RAG/FSM report trace, latency/counters, affected regression и docs closeout.

Не входит: новая parser/RAG policy после predecessor closeout без corrective re-open; смена models/corpus/SIP stand;
ручная подмена live transcript ради pass.

Write-set: integration/live tools только в пределах accepted contracts, targeted tests/fixtures, собственный evidence,
Map-015/ADR-005/architecture/technical-specification/roadmap/registry/backlog closeout. Общие production files меняются
только как corrective category-1 defect и требуют повторить B/C gates.

### 3.1. Source-map

| Область | Источник | Evidence/result |
|---|---|---|
| Runtime/deploy | systemd service, selected CPython 3.14t, live runner | exact executable/GIL/service versions |
| AI readiness | existing runtime coordinator/Ollama/ASR/TTS | warm operation results before 200 OK |
| SIP/media | FreeSWITCH queue/registered bot/stereo recorder | call UUID, signalling timeline, RTP counters, WAV |
| Semantic path | parser/composition/FSM/pipeline | raw turn, acts, ordering, operation IDs, outcomes |
| RAG/LLM | active science index/facade | query diagnostics, sources, decision/latency |
| Closeout docs | ADR/architecture/ТЗ/roadmap/registry/backlog | synchronized accepted baseline |

## 4. Mandatory scenario matrix

1. Обычный вопрос с разговорной обёрткой получает source-aware science answer, не false unknown.
2. Unknown question вызывает дословный offer-transfer.
3. `Нет, не надо. Почему небо днём голубое?` создаёт один raw user turn, reject + knowledge acts и science answer.
4. Pure `нет` отклоняет перевод и не запускает inference.
5. Explicit operator request запускает configured transfer без answer LLM.
6. Pure confirmed transfer выполняется сразу; compound confirm+question сначала получает ответ, затем повторный вопрос
   о переводе, и только новое подтверждение выполняет transfer.
7. Если compound content сам завершился unknown-answer/offer-transfer, предложение звучит один раз и становится
   повторным подтверждением того же pending transfer.
8. `clarify` и barge-in не теряют pending reconfirmation; reject/BYE/successful transfer очищают его.
9. Report содержит raw text, parse acts/outcomes, pending/reconfirmation lifecycle, RAG source/sufficiency reason и
   final FSM trace.

## 5. Slices и blocker register

1. Clean deterministic/target-runtime pre-gate.
2. Real embedding/chat/TTS warm gate без звонка.
3. Registered SIP live scenario со stereo recording.
4. Audio/report/log reconciliation, affected suite и document closeout.

| ID | Срез | Триггер | Блокируется | Владелец | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-015-D-001` | 1 | Predecessor handoff/revision расходится с production code | Все D | main executor | diff/contract audit | `none until triggered` |
| `B-015-D-002` | 2/3 | GPU/SIP/FreeSWITCH stand недоступен после corrective retry | Live closeout | project owner | raw command/log | `none until triggered` |
| `B-015-D-003` | 3 | ASR final не соответствует слышимой compound phrase из-за незакрытого Plan-014 defect | Live closeout | Plan-014/main executor | recording/transcript/turn trace | `resolved by Plan-014 registered r8` |
| `B-015-D-004` | 3 | Semantic answer проходит, но protocol/media regression красный | D/map | main executor; owner only category 4 | logs/counters/recording | `none until triggered` |

### 5.1. Owner review

Новых вопросов нет: Map-015 positive-compound policy разрешена owner. Любое изменение models/corpus/SIP stand или
acceptance matrix является новым scope и останавливает зависимую работу.

### 5.2. Process invariant audit

- D исполняет главный executor после проверки predecessor diffs/evidence; отчёт субагента не закрывает live gate.
- Каждый красный result сначала классифицируется; category 1/2 получает corrective rerun, category 3/4 — raw evidence.
- Mandatory scenario не заменяется synthetic unit test; deferred live evidence не выдаётся за pass.
- Child/map status и registry/backlog обновляются только после полного reconciliation.

### 5.3. Architecture invariant audit

- Registered live path использует те же production contracts/readiness/models, а не отдельный demo shortcut.
- Semantic text не проходит через Event Bus; SIP/protocol reaction не ждёт AI pipeline.
- FSM validates transfer/answer actions; LLM не получает прямой SIP control.
- BYE/barge-in/cancel и call generation прекращают stale semantic/inference/playback work.
- RAG answer остаётся source-aware, unknown context — offer-transfer.

## 6. Evidence и closeout

Сохраняются exact executable/runtime/GIL, service/model versions, commands/exit codes, stereo WAV, caller/bot
transcripts, conversation JSONL, report, semantic trace, RAG per-case diagnostics, FSM transitions, RTP/media counters и
latency points. Расхождение записи и событий анализируется по фактической call timeline, а не выравнивается фиктивной
тишиной.

Fallback/deferred mandatory evidence: `none`. Child становится `complete` только при зелёной матрице и документационной
синхронизации либо `blocked` по конкретному category-4 blocker. После D главный executor закрывает Map-015; partial или
foundation closeout запрещён.

## 7. Execution closeout 2026-09-22

- predecessor audit: `015-B`, `015-C` и Plan-014 закрыты зелёными evidence; production contracts совпали с accepted
  revision `semantic-turn-I1`;
- immutable fixture package: [`fixtures-v5`](../../artifacts/implementation/015-semantic-turn-understanding/015-D/fixtures-v5/manifest.json);
- authoritative aggregate:
  [`live-v7/map015-semantic-live-gate.json`](../../artifacts/implementation/015-semantic-turn-understanding/015-D/live-v7/map015-semantic-live-gate.json),
  `status=pass`, три сценария и все обязательные semantic/RAG/runtime checks зелёные;
- compound negative сохранил raw turn один раз, применил `reject_pending`, затем residual `knowledge_request`, pure
  reject не запускал inference, explicit request выполнил перевод;
- compound positive с barge-in сохранил pending intent, озвучил содержательный ответ, выполнил статическое повторное
  подтверждение и перевёл только после нового pure confirm;
- compound positive с unknown content озвучил offer ровно один раз, последующий отказ был typed, новый unknown снова
  предложил перевод, а явная просьба об операторе выполнила transfer;
- corrective category-1 defect live-v6: явная просьба об операторе при pending confirmation ошибочно попадала в RAG.
  Parser исправлен так, что expectation уточняет только контекстные ответы и не подавляет self-contained
  `TransferRequestAct`; регрессионный тест добавлен и live-v7 зелёный;
- полный host gate: CPython 3.14.7t free-threading, GIL off, `284 passed, 2 skipped`; runtime errors во всех трёх live
  results отсутствуют.

Evidence reconciliation: [`closeout.md`](../../artifacts/implementation/015-semantic-turn-understanding/015-D/closeout.md).
Открытых blockers и deferred mandatory evidence нет; Plan-015-D закрыт `complete`.
