# 012-C closeout: offline index build and publication

Статус: `complete`  
Дата: `2026-09-21`  
Artifact schema: `rag-index-v1`

## Результат

- `LocalKnowledgeIndex.build()` fail-fast проверяет non-empty chunks, typed response, request/model identity, finite
  values и единую vector dimension.
- Artifact содержит schema, corpus/index/chunking/model metadata, dimension/item count, source metadata, chunks/vectors
  и canonical payload checksum.
- `save_atomic()` пишет temporary sibling, делает flush/fsync, загружает/self-checks candidate и только затем вызывает
  `os.replace`; pre-publish failure сохраняет старый SHA и удаляет temp.
- CLI `tools/knowledge/rag_index.py validate|build` вызывает corpus owner и `LlmFacade`; прямого Ollama HTTP из builder
  нет.
- `build_and_publish_index()` возвращает typed `IndexBuildReport`.

## Deterministic и real evidence

Target deterministic lane после corrective B handoff:

```text
37 passed in 4.42s
```

CLI validation: exit `0`, workshop package valid, 6 documents.

Real build через Ollama 0.33.1 / `embeddinggemma`:

```text
status=pass
items=12
dimension=768
elapsed_ms=2655.151
artifact=data/knowledge/index/small-service-company-v1.json
artifact_sha256=9a2e0937cf2bcf3a2533b4762410490c0e40420f64a29483cf2e487b56d2b579
size=213794 bytes
```

Для сохранения действующего science-demo baseline тем же опубликованным builder path построен второй runtime artifact:

```text
artifact=data/knowledge/index/natural-science-v1.json
items=6
dimension=768
elapsed_ms=254.386
artifact_sha256=1752266eae9fd351fea4a870ece36e3754ca96924e38d5604c88a88a4c1dd811
```

Ollama `/api/show`: `embeddinggemma`, Gemma3 300M BF16, embedding length 768. Target CPython 3.14.7t reported
`Py_GIL_DISABLED=1`, `gil=false` before import and after artifact load.

## Closeout

Scope выполнен, previous-file preservation и corruption checks зелёные, blocker/fallback отсутствуют. Handoff 012-D:
оба artifact используют одну schema/model/dimension; runtime baseline загружает science artifact, а workshop activation
в 012-F переключает constants на `small-service-company-v1.json`. Ни один runtime path не должен выполнять corpus
embedding requests.
