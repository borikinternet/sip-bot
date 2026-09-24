# План 012-D: загрузка индекса и runtime readiness

Уровень: `child plan`  
Идентификатор: `012-D`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Зависимость: `012-C complete`  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-D/`

## Цель и результат

Сделать опубликованный index единственным runtime source для активного corpus: загрузить и проверить artifact до
готовности, выполнить только warm query embedding/retrieval и не embedding-ить corpus на startup/call path.

## Материализованные правила

- `config/constants.py` остаётся единственным источником active corpus/index/version/model policy; `RuntimeConfig`
  переносит все необходимые поля без hidden defaults.
- `LocalKnowledgeIndex.load()` проверяет schema/index/corpus/model/dimension/checksums и не обращается к provider.
- Readiness coordinator остаётся владельцем общей single-flight подготовки; loader не создаёт второй lifecycle owner.
- Existing stable index handle допускает только publication завершённого compatible snapshot до приёма звонка.
- До READY выполняется один реальный warm query через `LlmFacade`; corpus embedding request count равен нулю.
- Corrupt/mismatch/provider failure оставляет runtime NOT_READY и не разрешает incoming `200 OK`.
- Hot reload during active call не входит; activation — restart/readiness вне звонка.

## Source-map/write-set

Разрешено: `config/constants.py`, `src/sip_bot/config.py`, `src/sip_bot/retrieval/index.py`, небольшой scoped loader helper,
`tools/j4_full_live_gate.py`, `tools/live_i1_gate.py`, применимые composition probes, unit/contract/integration tests,
собственный evidence и этот plan.

Protected: corpus/index artifact contents from C, query/prompt/FSM semantics, SIP protocol/media implementation,
ASR/VAD/TTS and historical artifacts.

## Slices и propagation

1. `D1`: `LocalKnowledgeIndex.load(path, expected...)` and compatibility errors.
2. `D2`: constants/RuntimeConfig point to one active index file and carry expected revisions.
3. `D3`: live/readiness stages load/replace snapshot, then warm one query; no corpus build.
4. `D4`: request-count, corrupt/mismatch, readiness/admission and old/new isolation tests.
5. `D5`: target-runtime clean load/warm evidence and closeout to 012-E.

## Blockers/tests/fallback

| ID | Trigger | Status |
|---|---|---|
| `B-012-D-001` | Runtime re-embeds corpus, accepts incompatible index or can answer before load/warm succeeds | `none until triggered` |

Acceptance includes save/load/query equivalence, zero corpus embedding requests, exactly one warm query request,
failed load/provider keeps NOT_READY, no old science source after workshop activation, and relevant regression tests.
Rebuilding corpus during startup, direct fallback to science index and accepting an unverifiable artifact are forbidden.

## Closeout

Исполнено полностью. Runtime/live tools загружают versioned prebuilt index с проверкой corpus/index/model/dimension/
chunking/hash; readiness делает только один query embedding. Target test lane: `60 passed`; real CPython 3.14.7t probe
зафиксировал `corpus_embedding=0`, `warm_query_embedding=1`, GIL disabled и успешный source-aware retrieval.
Evidence: [`012-D/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-D/closeout.md).

## Delegation/evidence/closeout

Shared constants and live runners are changed sequentially by main executor. Heavy Ollama/live checks are main-only.
Closeout records exact files, requests, timings, target runtime/no-GIL, hashes, failures/corrective pass and binary status.
