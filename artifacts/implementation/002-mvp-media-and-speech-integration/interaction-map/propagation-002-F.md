# Propagation checkpoint 002-F

Дата: `2026-09-03`  
Статус: `accepted for deterministic scope; real embedding probe pending`  
Источник: `plan-002-F-skill-prompt-context.md`  
Следующие consumers: `002-G`, `002-J`

## Фактические output-контракты F

- `ContextStore` / `ContextSnapshot` / `ContextTurn` — bounded text-only persistence;
- `KnowledgeQuery` — полный normalized query для semantic embedding плюс диагностические
  `lexical_terms`/`phrases`;
- `EmbeddingRequest` / `EmbeddingResponse` / `EmbeddingProvider` — typed seam, через который F требует embedding
  operation, но не вызывает Ollama;
- `KnowledgeHit` / `KnowledgeContext` — source ID, chunk ID, score, threshold, top-k, sufficiency, index version и
  embedding model;
- `SkillSpec` / `PromptSpec` / `GenerationProfile` / `PromptDiagnostics` / `LlmRequest` — versioned prompt boundary.

## Boundary rules

`FinalUserTurn` — authoritative direct data-plane input F. Exact user text сохраняется в `LlmRequest.final_user_text`
и не заменяется списком ключевых слов. Нормализованные формы используются только как query metadata. Большие text/RAG
payloads не публикуются в process-local control Event Bus.

`ContextStore` сохраняет один разговор в `data/dialogues/<call_id>/conversation.jsonl`; audio не принимается и не
сохраняется. Insufficient context формирует явный `unknown_answer`/`offer_transfer` path, model-only answer не считается
успешным обязательным RAG path.

## Evidence и ограничения

- targeted F: `9 passed`;
- host unit/contract regression после propagation: `73 passed`;
- compileall: `exit 0`;
- CPython `3.14.7t`: import/query operation evidence, `gil_enabled=false`, `razdel=true`, `pymorphy3=true`;
- corrective protected-token probe сохраняет `H2O` и `10^3`;
- deterministic fake index: 6 chunks, positive source-aware hit, negative insufficient-context fixture;
- Ollama/реальная embedding-модель и heavy GPU inference не запускались.

Следующий обязательный шаг `002-G`: реализовать typed transport к существующей Ollama HTTP boundary и sequentially
выполнить main-only embedding probe. До этого F не получает formal `complete`.
