# F → main/G handoff

## Authoritative data-plane types

- `FinalUserTurn` из `sip_bot.speech.contracts` — входной authoritative final text; в Event Bus не помещается.
- `ContextSnapshot` / `ContextTurn` — bounded text-only conversation state.
- `KnowledgeQuery` — `authoritative_text`, `normalized_text`, `embedding_text`, `lexical_terms`, `phrases`,
  `policy_version`, `context_turn_ids`.
- `EmbeddingRequest` / `EmbeddingResponse` — typed seam для отдельной embedding-операции. HTTP/Ollama adapter не входит
  в F и должен быть реализован в `002-G`.
- `KnowledgeHit` — `chunk_id`, `source_id`, `text`, `score`.
- `KnowledgeContext` — `context_id`, query, hits, `sufficient`, `threshold`, `top_k`, `index_version`,
  `embedding_model`, optional failure.
- `LlmRequest` — call/turn identity, skill/template/profile/schema IDs и версии, точный `final_user_text`, rendered
  prompt, `KnowledgeContext`, authoritative mode, allowed actions и diagnostics.

## Required downstream behavior

`002-G` должен принимать только `LlmRequest`/typed embedding operation, не раскрывать Ollama API и возвращать typed
stream/status/structured decision. `002-E`/FSM получает control outcomes отдельно; большие тексты, final turn и RAG
fragments идут direct data-plane. При `KnowledgeContext.sufficient == false` F request маркируется `unknown_answer`
и разрешает только `offer_transfer`; model-only answer не является RAG pass.

## Not a blocker for isolated F

Настоящая embedding-модель, Ollama runtime и GPU probe намеренно не запускались согласно входной границе исполнения.
Deterministic fake backend доказывает схему, воспроизводимость индекса, similarity, source IDs и negative path, но не
претендует на semantic quality production embedding. Следующий main-only gate обязан проверить реальный provider и
обновить model/index metadata.
