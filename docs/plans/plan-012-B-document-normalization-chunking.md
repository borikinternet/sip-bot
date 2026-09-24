# План 012-B: детерминированная нормализация и chunking

Уровень: `child plan`  
Идентификатор: `012-B`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Зависимость: `012-A complete`  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-B/`

## Цель и результат

Преобразовать validated Markdown documents в воспроизводимую typed последовательность `CorpusChunk` и отчёт ingestion,
не меняя embedding/search/runtime.

## Материализованные правила

- Используется только schema revision, переданная 012-A; новый manifest contract не вводится.
- Нормализация переводит line endings, удаляет BOM/trailing whitespace и схлопывает лишние пустые строки, но не
  перефразирует текст.
- Semantic boundary MVP: Markdown headings и paragraphs; длинные блоки детерминированно делятся по предложениям с
  фиксированным лимитом символов, короткие соседние блоки не смешивают sources.
- `chunk_id` зависит от stable source ID, ordinal и content hash; одинаковый package даёт byte-identical result/order.
- Ошибки/пустые документы отражаются typed report и не скрываются.

## Source-map/write-set

Разрешено: `src/sip_bot/retrieval/corpus.py`, `contracts.py` только для переданного report/chunk contract,
`src/sip_bot/retrieval/index.py` только compatibility wrapper `load_corpus`, `tests/unit/test_rag_chunking.py`,
собственный evidence и этот plan.

Protected: corpus manifests/documents, LLM/Ollama, runtime/constants, query/search semantics и SIP/media.

## Slices и typed handoff

1. `B1`: `CorpusNormalizer.normalize(document) -> str`.
2. `B2`: `CorpusChunker.chunk(document) -> tuple[CorpusChunk, ...]`.
3. `B3`: `CorpusPackage.ingest() -> CorpusIngestionResult` with accepted/skipped/errors.
4. `B4`: deterministic tests and serialized chunk manifest/hash for both corpora.
5. `B5`: closeout publishes exact chunk schema/revision/counts to 012-C.

## Blocker/test/fallback

| ID | Trigger | Status |
|---|---|---|
| `B-012-B-001` | Existing consumer cannot accept propagated typed chunks without protected semantic change | `none until triggered` |

Acceptance: repeated ingestion byte-identical, source boundaries preserved, IDs stable after path relocation, long text
bounded, errors visible. No parser library, NLP/LLM chunker or silent compatibility path is introduced. If delegated,
agent follows the exact write-set; main executor verifies diff/tests/evidence and performs binary closeout.

## Execution closeout — 2026-09-21

`markdown-semantic-v1` реализован и передан в 012-C: science/workshop дают соответственно 6/12 stable chunks;
content hashes зафиксированы. После двух category-1 corrective passes targeted+regression lane: `31 passed`.
Открытых blocker нет. Evidence: [`012-B/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-B/closeout.md).
