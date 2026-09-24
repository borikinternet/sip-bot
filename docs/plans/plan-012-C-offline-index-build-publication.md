# План 012-C: offline index build и атомарная публикация

Уровень: `child plan`  
Идентификатор: `012-C`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Зависимость: `012-B complete`  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-C/`

## Цель и результат

Предоставить опубликованную CLI-команду, которая валидирует corpus package, детерминированно получает chunks,
векторизует их только через typed `LLM Facade`, самопроверяет candidate index и crash-safe публикует его одним
`os.replace`, сохраняя предыдущий индекс при любой ошибке до publication point.

## Материализованные правила

- Ollama `/api/embed` вызывается только `LlmFacade.embed(EmbeddingRequest)`; CLI не владеет HTTP.
- MVP остаётся sequential single-request build; batch contract не добавляется без отдельного evidence/owner decision.
- Index artifact содержит schema/index/corpus/chunking/model/dimension, source metadata, hashes и build manifest.
- Временный sibling создаётся на том же filesystem; flush/fsync, load/self-check и только затем `os.replace`.
- Build failure не удаляет и не изменяет ранее опубликованный файл; fake backend не выдаётся за real workshop index.
- Тяжёлый real-Ollama gate запускает главный executor; субагенту доступна deterministic fake реализация и tests.

## Source-map/write-set

Разрешено: `src/sip_bot/retrieval/contracts.py`, `index.py`, новый persistence/build module при необходимости,
`src/sip_bot/retrieval/__init__.py`, новый `tools/knowledge/rag_index.py`, `tests/unit/test_rag_index.py`,
`tests/contract/test_rag_index_build.py`, `data/knowledge/index/*.json` только для нового опубликованного workshop
artifact, собственный evidence и этот plan.

Protected: corpus package, query/prompt semantics, runtime/constants until 012-D, LLM HTTP implementation, SIP/media.

## Slices

1. `C1`: versioned `IndexMetadata/IndexBuildReport` and serialization contract.
2. `C2`: fail-fast build checks for response identity/model/vector dimension and non-empty items.
3. `C3`: `save_atomic` with injected pre-publish failure test and load/self-check hook.
4. `C4`: CLI `validate`/`build`, JSON report, exact exit codes and safe overwrite semantics.
5. `C5`: deterministic fake build tests, then target real `embeddinggemma` build by main executor.
6. `C6`: closeout publishes artifact SHA/schema/dimension/model/corpus revision to 012-D.

## Blockers/tests/fallback

| ID | Trigger | Status |
|---|---|---|
| `B-012-C-001` | Direct Ollama bypass, non-atomic publish, irreproducible artifact or old-index corruption | `none until triggered` |

Tests include build reproducibility, response mismatch, mixed dimensions, empty index, serialization round-trip,
corruption and injected failure preserving old SHA. Real gate records target no-GIL state before/after import/operation,
Ollama/model version, dimension, timings, hashes and disk/GPU observations. No lexical/fake/model fallback.

## Delegation и closeout

Delegated deterministic work is restricted to the write-set and may not run shared GPU inference. Main executor reviews
diff, runs all tests and the real build, classifies red results, then records `complete` or concrete `blocked`.

## Execution closeout — 2026-09-21

Реализованы `rag-index-v1`, strict build checks, atomic self-checking publish, typed build report и CLI. Real
`embeddinggemma` build создал 12×768 artifact SHA-256
`9a2e0937cf2bcf3a2533b4762410490c0e40420f64a29483cf2e487b56d2b579`; deterministic lane `37 passed`.
Blocker/fallback нет. Evidence: [`012-C/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-C/closeout.md).
