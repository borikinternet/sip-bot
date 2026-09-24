# 021-I closeout: web/RAG/SIP boundary

Status: `complete` for the local execution pass.

Accepted revision: `web-rag-session-I1`.

Materialized boundaries:

- WebSocket carries only compact status messages and application heartbeat;
- the same-machine shared boundary is an atomically published JSON registry plus immutable artifact directory;
- `NormalizedSipEvent.caller_id` carries the SIP URI user-part extracted by `SipMediaAdapter`;
- `IncomingCallReadinessGate` owns the `180 → preparation → 200/503` admission decision;
- the stable retrieval object is replaced sequentially, never concurrently, and is restored to baseline on terminal cleanup;
- FreeSWITCH `mod_callcenter` remains the only queue owner.

Evidence:

- `tests/unit/test_incoming_answer_readiness.py`: caller user-part, readiness ordering and cleanup contracts;
- `demo-web/backend/call_rag.py`: shared registry adapter;
- `demo-web/backend/registry.py`: session/heartbeat/artifact ownership.

The registered FreeSWITCH/browser trace is intentionally outside this local boundary closeout and remains 021-E work.
