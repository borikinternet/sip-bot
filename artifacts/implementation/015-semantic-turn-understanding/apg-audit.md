# Map-015 APG audit

Дата: `2026-09-22`  
Проверяемые документы: `Map-015`, `015-I`, `015-A`–`015-D`, `ADR-005`  
Результат: `PASS — planning and execution closeout complete`  
Execution status: `complete 2026-09-22`

## 1. Scope и classification

- Изменяются typed boundaries, Dialogue FSM behavior, compound user scenario и RAG sufficiency: полный APG обязателен.
- Исходная работа содержит пять самостоятельных acceptance boundaries, поэтому оформлена картой с пятью child plans,
  а не одним частично исполняемым plan-file.
- Scope является post-freeze corrective work: он закрывает воспроизведённые потерю содержательного вопроса и ложный
  unknown-answer в обязательном demo-flow. Новая open-domain NLU-функция не добавляется.
- LLM semantic parser и neural intent classifier явно находятся вне scope и не выданы за deferred mandatory evidence.

## 2. Mandatory block audit

| APG block | Map-015 | 015-I | 015-A | 015-B | 015-C | 015-D | Result |
|---|---|---|---|---|---|---|---|
| Goal/verifiable result | yes | yes | yes | yes | yes | yes | pass |
| Materialized applicable rules | yes | yes | yes | yes | yes | yes | pass |
| Scope/protected baseline | yes | yes | yes | yes | yes | yes | pass |
| Source-map/write-set | yes | yes | yes | yes | yes | yes | pass |
| Behavior owner audit | map + ADR | topology owners | parser owner | FSM/pipeline owners | retrieval owner | accepted owners | pass |
| Owner-review table/status | resolved | none new | none | resolved inherited | none | none | pass |
| Process invariant audit | yes | yes | yes | yes | yes | yes | pass |
| Architecture invariant audit | yes | yes | yes | yes | yes | yes | pass |
| Interaction topology/propagation | map I0 | authoritative task | consumes I | consumes I/A | consumes I | consumes B/C | pass |
| Implementation slices | graph | I0–I4 | 4 | 4 | 4 | 4 | pass |
| Blocker register | yes | yes | yes | yes | yes | yes | pass |
| Test/evidence plan | yes | docs audit | unit/contract/runtime | state/integration/runtime | frozen+real RAG | target/live | pass |
| Fallback/deferred register | yes | none | explicit no LLM | none | none | none | pass |
| Binary closeout | map waits all children | complete/blocked | complete/blocked | complete/blocked | complete/blocked | complete/blocked | pass |

## 3. Interaction and ownership audit

- `FinalUserTurn` remains the authoritative speech output and carries existing call/turn/generation identity.
- `SemanticTurnParser` owns only interpretation of final text plus `DialogueExpectation`; it cannot mutate FSM or SIP.
- `DialogueFSM` remains the sole owner of semantic call state, pending transfer/reconfirmation and irreversible actions.
- `ConversationPipeline`/`CallComposition` materialize direct typed methods; no delivery facade, text Event Bus payload or
  new queue is introduced.
- Raw user text is written once to `ContextStore`; derived spans are diagnostics/data-plane content, not duplicate turns.
- Retrieval owner remains authoritative for `KnowledgeContext.sufficient`; prompt/LLM cannot create model-only answers.
- Compound-positive owner decision is materialized: answer content, ask transfer confirmation again, transfer only after
  a new pure confirmation. `clarify`/barge-in retain pending intent; reject/BYE/transfer/close clear it.

## 4. Dependency and delegation audit

Execution graph is valid:

```text
015-I
  ├── 015-A ── 015-B ──┐
  └── 015-C ────────────┼── 015-D
Plan-014 closeout ──────┘
```

- `015-I` is the first executable child and must publish the actual contract revision.
- `015-A` and `015-C` may run in parallel only after I because their code write-sets do not overlap.
- Shared config/report/docs changes are serialized by the main executor.
- `015-B` consumes the accepted A contract; `015-D` consumes B/C and cannot run before Plan-014 live closeout.
- A/C subagent plans contain write-set, protected files, stop conditions, runtime/tests and handoff requirements.
- GPU/real-provider final evidence and live SIP gate remain main-executor work.

## 5. Findings and corrective pass

The first formal pass found and corrected:

1. Map-015 said four acceptance boundaries while materializing five child plans; corrected to five.
2. The post-freeze corrective-only rule from `roadmap.md` §13.5 was not explicitly copied into the map/child plans;
   materialized in all applicable files.
3. Several child plans relied on the parent map instead of explicitly materializing applicable requirements,
   technical, documentation and APG rules; self-contained rule tables were completed.
4. `015-I` did not explicitly state the empty fallback/deferred register; `none` is now recorded.

No unresolved category-4 architecture gap or owner-review question remains.

## 6. Mechanical checks

Commands:

```text
python tools/check_document_registry.py
python tools/check_task_backlog.py
```

Observed results:

```text
document registry audit: actual=96 registry_rows=96 registry_unique=96 missing=0 extra=0 duplicate_paths=0
document registry audit: PASS
task backlog audit: rows=19 unique_ids=19
task backlog audit: PASS
```

Relative links in `Map-015`, child plans and `ADR-005` were checked against the filesystem: broken links `0`.

The worktree contains pre-existing and current uncommitted work from earlier maps. Map-015 plans explicitly preserve
unrelated changes and restrict every child to its own write-set.

## 7. Execution reconciliation

- `015-I` опубликовал accepted revision `semantic-turn-I1`;
- `015-A`/`015-B` materialized typed parser и ordered FSM/pipeline routing;
- `015-C` закрыл frozen RAG suite `12/12`;
- dependency Plan-014 закрыта registered run `r8`;
- `015-D/live-v7` прошёл три обязательных registered сценария, включая barge-in, reconfirmation, single offer и
  explicit transfer;
- category-1 дефект explicit request при pending confirmation исправлен в parser и подтверждён regression/live gate;
- полный host gate: CPython 3.14.7t, GIL off, `284 passed, 2 skipped`;
- architecture, ТЗ, roadmap, registry и backlog синхронизированы; blockers и deferred mandatory evidence отсутствуют.

## 8. Gate decision

Planning и execution APG пройдены. Все обязательные child plans закрыты только как полностью выполненные; partial или
foundation claim не использован. Map-015 имеет статус `complete`.
