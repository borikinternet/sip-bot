# 021-C execution report: caller ID and pre-answer RAG readiness

Status: `in_progress`; local contract is implemented, registered no-GIL/FreeSWITCH trace remains deferred.

Implemented:

- `caller_id_from_sip_uri()` extracts `sip:`/`sips:` URI user-part from PJSUA2 `remoteUri`;
- `NormalizedSipEvent.caller_id` and `as_dict()` preserve the routing key;
- `IncomingCallReadinessGate` accepts optional call preparation and cleanup hooks;
- the hook is run off-loop with a strict `15 s` bound after the adapter's `180` and before `200`;
- preparation failure produces explicit `503` and cannot silently use a custom index;
- baseline sessions have an explicit baseline registry record; missing/stale custom records use the approved baseline fallback;
- terminal SIP events restore the stable baseline index and remove custom artifacts idempotently;
- live runner `tools/run_live_bot.py` sets the topic-aware female greeting: `Здравствуйте! Я Василиса...`.

Commands/results:

```text
$env:PYTHONPATH='src;demo-web'; .venv\Scripts\python.exe -m pytest -q tests/unit/test_incoming_answer_readiness.py tests/unit/test_sip_media.py
19 passed in 0.55s
```

The exact agent-leg event timestamps and target CPython `3.14.7t` run must be promoted with the registered
FreeSWITCH gate after the final WSS deployment is available.
