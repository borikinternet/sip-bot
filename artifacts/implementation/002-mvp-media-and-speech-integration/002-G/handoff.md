# G → main/H/J/F handoff

## Typed operations

- `LlmFacade.start_chat(LlmRequest, final_user_turn_ns)` → single-use `ChatOperation`.
- `ChatOperation` yields `LlmStreamEvent`: `started`, `delta`, `decision`, `completed`, `cancelled`, `error`.
- `InferenceStatus` reports `created`, `running`, `completed`, `cancelled`, `failed`.
- `LlmFacade.embed(EmbeddingRequest)` → `EmbeddingResponse`; this is a separate typed operation on the same HTTP
  boundary and does not own retrieval/index semantics.
- `CancelRequest` identifies `operation_id`, `call_id`, `generation` and reason.
- `LatencyTrace` records `final_user_turn_ns`, request start, first stream event, first usable output, final result and
  cancel timestamps plus derived milliseconds.

## Boundary invariants

- Only `LlmFacade` consumers need the typed application API; Ollama URLs/JSON are contained in `ollama_client.py`.
- Existing C3 process boundary is preserved: local Ollama over HTTP; no new IPC and no native inference import in the
  free-threaded controller.
- `LlmRequest` comes from F unchanged; prompt/RAG semantics remain outside G.
- Structured output is required: an invalid final JSON response produces `error/malformed_response`, never successful
  completion.
- Cancellation closes the HTTP stream and suppresses late chunks/decisions. This does not claim a separate native Ollama
  cancellation acknowledgement.
- `StructuredDecision` is returned as data; G never validates or executes SIP/FSM actions.

## Required main-only probe

Sequentially connect the real local Ollama `0.33.1` process and record actual model/runtime/VRAM metadata. Verify chat
stream, embedding request, malformed/timeout/cancel behavior, latency from final user turn to first useful/final result,
and stale-result suppression. Then propagate accepted G contracts to Map-002-I and unblock H/J. No fallback backend/model
may be introduced silently.
