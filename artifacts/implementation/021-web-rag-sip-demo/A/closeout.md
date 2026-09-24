# 021-A closeout: web session, upload and heartbeat

Status: `complete` for the local sidecar foundation; hosted URL remains deferred.

Implementation:

- `demo-web/backend/server.py`: aiohttp HTTP/static/upload/WebSocket sidecar;
- `demo-web/backend/registry.py`: volatile `session_id`, unique `caller_id`, heartbeat lease and lifecycle;
- `.md`/`.txt` UTF-8 and selectable-text `.pdf` upload with hard `640 KiB` limit;
- `rag_preparing`, `rag_ready`, `rag_failed`, `call_started`, `call_ended` status events;
- baseline mapping is published when a session is created, so baseline callers are immediately routable;
- waiting/preparing artifacts are removed after heartbeat expiry, while active-call artifacts are retained until terminal cleanup.

Commands/results:

```text
$env:PYTHONPATH='src;demo-web'; .venv\Scripts\python.exe -m pytest -q demo-web/tests
7 passed in 0.52s

$env:PYTHONPATH='src;demo-web'; .venv\Scripts\python.exe -c "import aiohttp, sys; print({'python': sys.version.split()[0], 'aiohttp': aiohttp.__version__})"
{'python': '3.14.3', 'aiohttp': '3.14.3'}
```

The final conference URL is still required before QR/hosting can be promoted to live acceptance.
