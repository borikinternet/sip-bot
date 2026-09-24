# 012-D closeout: загрузка индекса и runtime readiness

Статус: `complete`  
Дата: `2026-09-21`

## Результат

- `LocalKnowledgeIndex.load()` проверяет payload checksum, schema, index/corpus versions, embedding model, dimension,
  chunking policy, corpus hash, item count и каждый vector.
- `config/constants.py` и immutable `RuntimeConfig` задают единственный active index и все expected revisions.
- J4, I1, Map-005 и composition probes загружают prebuilt artifact; вызовы `build()`/`load_corpus()` из их startup
  path удалены.
- Readiness загружает index без provider calls, затем выполняет ровно один typed warm query через `LlmFacade`.
- Существующие failure/admission tests подтверждают: ошибка warmup оставляет coordinator в `FAILED`, а incoming call
  не получает `200 OK` и завершается явным `503`.

## Проверки

Target CPython `3.14.7t`:

```text
60 passed in 5.22s
py_compile: pass
Py_GIL_DISABLED=1
gil after retrieval import=false
```

Real Ollama `0.33.1` / `embeddinggemma` probe:

```text
operation=load-prebuilt-index-and-warm-query
index=data/knowledge/index/natural-science-v1.json
artifact_sha256=1752266eae9fd351fea4a870ece36e3754ca96924e38d5604c88a88a4c1dd811
items=6; dimension=768
corpus_embedding_requests=0
warm_query_embedding_requests=1
load_ms=4.360
warm_query_ms=2485.672
sufficient=true
top_source=wiki-physics-rayleigh
```

Raw report: [`runtime-index-probe.json`](runtime-index-probe.json).

## Closeout

`B-012-D-001` не сработал: runtime не переиндексирует corpus, несовместимые artifacts fail-fast, readiness/admission
не принимает частичную готовность. Handoff 012-E: immutable evaluation выполняется на workshop artifact
`data/knowledge/index/small-service-company-v1.json`; его activation в runtime остаётся ответственностью 012-F.
