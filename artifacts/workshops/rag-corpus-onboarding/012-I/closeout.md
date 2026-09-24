# 012-I closeout: RAG lifecycle boundary

Статус: `complete`  
Дата: `2026-09-21`  
Contract revision: `rag-lifecycle-v1`

## Фактический аудит

- `CorpusSource`, `CorpusChunk`, `EmbeddingRequest/Response`, `KnowledgeHit` и `KnowledgeContext` находятся в
  `src/sip_bot/retrieval/contracts.py`.
- `load_corpus`, `LocalKnowledgeIndex.build/query/save/replace_from` находятся в
  `src/sip_bot/retrieval/index.py`; production `load()` отсутствует.
- Единственный production HTTP-владелец `/api/embed` — `LlmFacade.embed()` → `OllamaHttpClient.embed()`.
- `ConversationPipeline` вызывает `KnowledgeQueryBuilder.build()` и `LocalKnowledgeIndex.query()`, передаёт готовый
  `KnowledgeContext` в `SkillPromptManager.prepare_for_turn()` и в отчёт.
- Live runners `live_i1_gate.py` и `j4_full_live_gate.py` сейчас строят corpus embeddings в readiness; это подтверждённый
  gap 012-C/012-D.
- Сохранённый science index имеет 6 chunks и vectors dimension 768, но не содержит schema/corpus/checksum/chunking
  metadata и не загружается runtime.

## Закреплённые edges

Offline: package validation → typed documents/chunks → `EmbeddingProvider.embed()` → completed index → atomic artifact.

Runtime: index artifact → `LocalKnowledgeIndex.load()` → readiness warm query → immutable index snapshot → per-turn
query embedding/search → `KnowledgeContext` → prompt/report.

Payload передаётся прямыми typed method calls. Dispatcher/Event Bus остаётся control-only. Новый delivery owner,
queue, external vector store, direct Ollama CLI path и hot reload не требуются.

## Evidence и итог

Выполнены source/consumer/owner/topology audits; protected production files в 012-I не менялись. Новых owner-review
вопросов и blocker нет. Revision `rag-lifecycle-v1` разрешает начало `012-A`; дальнейшая authoritative propagation
выполняется строго A → B → C → D → E → F с corrective возвратом фактическому owner.

