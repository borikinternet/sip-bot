# 021-E execution gate: browser → mod_callcenter → one bot

Status: `in_progress`; local page and direct mirrored FreeSWITCH SIP/RTP/WSS configuration pass, registered phone/browser
queue → bot → RAG gate is not yet claimed.

This pass did not claim a registered end-to-end result. The following local prerequisites are now evidenced:

- Ubuntu WSL Ollama `0.33.1` with both required models and a real metadata/index build;
- Debian WSL FreeSWITCH `1.11.3`, internal SIP/WS/WSS bindings and `mod_callcenter` queues;
- an in-WSL SIP-over-WSS upgrade returning HTTP `101` with the `sip` subprotocol.

Raw prerequisite evidence is in [`live-wsl-freeswitch-20260923.md`](live-wsl-freeswitch-20260923.md) and
[`../B/live-ollama-20260923.md`](../B/live-ollama-20260923.md).

The remaining conditions are:

1. execute a browser/phone call to `sip:7100@192.168.1.74` through `mod_callcenter`;
2. correlate the caller ID with the PJSUA2 `NormalizedSipEvent`, load a custom artifact before bot-leg `200 OK`, and
   prove the Василиса topic greeting;
3. run the baseline plus two sequential custom-corpus calls and record terminal cleanup.

The current local QR URL and SIP configuration are already staged in `demo-web/frontend/demo-config.js`; the QR can be
replaced later when the final conference hostname is supplied.

Promotion command from the project root after those inputs are available:

```powershell
$env:PYTHONPATH = "src;demo-web"
.venv\Scripts\python.exe -m pytest -q demo-web/tests tests/unit/test_incoming_answer_readiness.py tests/unit/test_sip_media.py
# then run the target CPython 3.14.7t live runner and the registered browser gate
```

Required evidence for promotion:

- caller leg `200 OK` and `moh-sound` while waiting in `mod_callcenter`;
- bot leg `180`, caller-ID correlation, selected-index load, then `200` within 15 seconds;
- baseline call plus two sequential custom corpora with no cross-session leakage;
- terminal cleanup, report/media counters and zero runtime errors/drops;
- QR decode and browser WSS/ICE/DTLS-SRTP evidence.

No isolated mock/direct SIP call is treated as a substitute for this gate. The direct mirrored path is configured with
the same LAN address for signaling and RTP, but Windows still needs the elevated Hyper-V inbound rule before the phone
can be used as the registered external device. The self-signed certificate is still a local-demo limitation.
