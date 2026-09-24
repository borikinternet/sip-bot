# 021-B: подготовка и публикация session-scoped RAG

Уровень: `child plan` · Родитель: [`Map-021`](plan-021-web-rag-conference-demo.md)
Статус: `complete` для локального live Ollama/RAG path; registered 021-E gate остаётся отдельным.
Evidence root: `artifacts/implementation/021-web-rag-sip-demo/B/`

## Цель и граница

Преобразовать один загруженный `.md`/`.txt` в immutable prepared artifact: metadata, normalized document, deterministic
chunks, embeddings `embeddinggemma`, index и registry entry `caller_id → artifact`.

## Source-map, owner и write-set

Владелец: `RagPreparationCoordinator`; retrieval contracts остаются владельцами ingestion/chunk/index behavior.
Переиспользовать Map-012 `CorpusPackage`, `CorpusNormalizer`, `CorpusChunker`, `build_and_publish_index` и typed
embedding facade. Write-set: `demo-web/backend/rag*`, prompt/schema additions, focused tests and
`artifacts/implementation/021-web-rag-sip-demo/B/`.

Подготовленный manifest и index публикуются в общем локальном каталоге на одной машине/ОС. Публикация должна быть
атомарной: сначала временный каталог, self-check/loadability, затем rename/manifest commit; bot не читает незавершённый
artifact.

## Acceptance

- metadata включает title, topic, description, example questions, source hash и corpus ID;
- chat LLM используется только для bounded metadata; vectors строятся embedding path;
- partial/failed build не заменяет предыдущий ready artifact;
- publication атомарна и registry не видит неполный index;
- `rag_ready` публикуется только после self-check/loadability;
- stale waiting artifact и active artifact имеют разные cleanup rules;
- два последовательных корпуса не смешивают chunks/vectors/metadata.

## Blocker register

| ID | Trigger | What blocks | Status |
|---|---|---|---|
| B-021-B-1 | atomic shared local artifact publication not proven | 021-C integration | `resolved by temp-dir/self-check/rename tests and live published-artifact probe; separate registered call trace remains 021-E` |
| B-021-B-2 | metadata schema cannot be produced by local LLM | custom UI description | `resolved: Ollama 0.33.1, c3-qwen35-9b-q4km and embeddinggemma are live` |

## Test/evidence и closeout

Focused corpus/index tests pass (`demo-web/tests`: `7 passed`), including a loadable index, 640 KiB rejection and
call-scoped publish/release. The live typed-facade probe produced metadata and a `768`-dimension
`embeddinggemma` index with `item_count=1`; evidence is in
[`live-ollama-20260923.md`](../../artifacts/implementation/021-web-rag-sip-demo/B/live-ollama-20260923.md).
The child is complete for the local preparation/publication path. Registered browser → `mod_callcenter` → bot
correlation remains 021-E.
