# Propagation checkpoint 002-G

Дата: `2026-09-03`  
Статус: `accepted; real provider evidence pass`  
Источник: `plan-002-G-llm-facade.md`  
Следующие consumers: `002-H`, `002-J`

## Фактические output-контракты G

- `LlmStreamEvent` — typed stream lifecycle/delta/decision/cancel/error с operation/call/turn identity;
- `InferenceStatus` и `CancelRequest` — lifecycle/cancellation boundary;
- `StructuredDecision` — небольшой результат для control plane, который проходит FSM/action validation;
- `EmbeddingResponse` — результат отдельной embedding operation для F/RAG;
- `LatencyTrace` — final user turn → request → first usable output → final result/cancel.

## Реальный provider evidence

G facade через существующий локальный Ollama 0.33.1 проверен на:

- `embeddinggemma:latest` (768 dimensions): индекс из 6 chunks, positive query с
  `wiki-physics-rayleigh`, negative query с `sufficient=false` и `unknown_answer/offer_transfer`;
- `c3-qwen35-9b-q4km:latest` (Qwen3.5-9B Q4_K_M): source-aware structured `answer`;
- `think=false`, `temperature=0.1`, `num_predict=96`: `282.8241 ms` от final user turn до first usable output,
  `1230.582814 ms` до final result.

Полные digests, VRAM sample, scores и checksum индекса находятся в
[`real-provider-probe.json`](../002-G/real-provider-probe.json).

## Boundary rules и ограничения

G принимает только typed `LlmRequest`/`EmbeddingRequest`, скрывает Ollama JSON/HTTP от consumers и не переносит prompt,
RAG fragments или stream payload через control Event Bus. В H передаётся approved text stream с cancellation/stale
policy; в J — decision, diagnostics и latency evidence. Server-side cancellation acknowledgement Ollama не заявляется;
client-side close и stale-result suppression доказаны deterministic tests.
