# 012-B closeout: normalization and chunking

Статус: `complete`  
Дата: `2026-09-21`  
Chunking revision: `markdown-semantic-v1`

## Результат

- `CorpusNormalizer` канонизирует line endings, trailing whitespace и пустые строки без перефразирования.
- `CorpusChunker` переносит Markdown heading в каждый paragraph chunk, детерминированно делит длинный paragraph по
  предложениям/фиксированному лимиту и не смешивает sources.
- Stable chunk ID: `<source_id>-<ordinal>-<12 hex content hash>`; полный SHA-256 хранится в typed chunk.
- Chunk наследует source version/effective date/priority/topics/audiences.
- `ingest_corpus()` возвращает typed accepted/skipped/errors report; `load_corpus()` остаётся совместимым fail-closed
  entry point поверх нового owner.

Immutable handoff:

- science: 6 chunks, content SHA-256 `531d177f8f77611faaad32cf08c0a9b172e1f2cb2c8a0d3d26667a210f0e33ee`;
- workshop: 12 chunks, content SHA-256 `9f6c1fb70792d6a44e3c098f920bf5895b1fa03503aac13d14897ea833e707ff`.

## Corrective pass и проверки

Первый targeted run завершился collection error из-за ошибочно удалённого `re` import — category 1 implementation
error; import восстановлен. Второй run выявил date serialization regression в существующем `save()` — category 1;
effective date сериализуется ISO-строкой. После исправлений:

```text
31 passed in 3.37s
```

Проверены A/B tests, прежние retrieval/prompt contracts и conversation pipeline. Target runtime CPython 3.14.7t,
no-GIL; exit code `0`.

## Closeout

Scope выполнен полностью, blocker/fallback отсутствуют. 012-C получает 12 workshop chunks, точный policy/content hash
и существующий `EmbeddingProvider.embed` как единственную embedding boundary.

