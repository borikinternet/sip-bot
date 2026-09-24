# 021-B execution report: session-scoped RAG publication

Status: `complete` for the local live preparation/publication path; registered 021-E gate remains open.

Implemented `RagPreparationCoordinator`:

- validates extension, UTF-8, non-empty text and `640 KiB` limit;
- asks the existing typed chat facade for bounded title/topic/description/questions;
- reuses the existing corpus ingestion/chunking/index builder;
- uses the injected embedding facade, with production model default `embeddinggemma`;
- self-checks with `LocalKnowledgeIndex.load()` before publication;
- publishes a unique artifact directory and registry record only after atomic directory replacement;
- the bot-side `CallScopedRagController` loads that immutable artifact and restores the baseline index after release.

Commands/results:

```text
$env:PYTHONPATH='src;demo-web'; .venv\Scripts\python.exe -m pytest -q demo-web/tests
7 passed in 0.52s
```

The deterministic provider proves artifact shape, loadability, atomic publication path and call-scoped release. A
live probe also passed through the existing typed `LlmFacade`: Ollama `0.33.1` returned metadata from
`c3-qwen35-9b-q4km`, `embeddinggemma` returned `768`-dimension vectors, and the coordinator published and
self-loaded a temporary one-item index. Raw evidence is in
[`live-ollama-20260923.md`](live-ollama-20260923.md). The remaining promotion condition is the registered
browser → `mod_callcenter` → bot scenario, not the local model service.
