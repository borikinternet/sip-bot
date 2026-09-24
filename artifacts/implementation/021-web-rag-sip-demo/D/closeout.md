# 021-D execution report: conference UI and browser SIP adapter

Status: `in_progress`; local IP/QR/UI and direct mirrored SIP/RTP/WSS configuration pass; final conference URL remains replaceable.

Implemented under `demo-web/frontend/`:

- responsive Russian-language page with current RAG description, topic and example questions;
- status-driven button gating: baseline is immediately callable, custom corpus is callable only after `rag_ready`;
- upload flow for `.md`/`.txt`/text-based `.pdf` and visible preparation/error state;
- small equal-size visual tiles for the supplied wide partner logo (`assets/partner-logo.svg`) and author photo
  (`assets/project-author.png`);
- WebSocket application ping/pong and caller-ID display;
- vendored JsSIP `3.10.0` runtime (no CDN dependency) plus an adapter using the assigned caller ID as SIP URI
  user-part, browser media constraints and remote audio;
- call lifecycle posts `/call/started` and `/call/ended`, and shows queue/connected state.

Validation:

```text
node --check demo-web/frontend/app.js
exit 0
```

The current QR tile encodes `http://192.168.1.74:8080/`; `window.DEMO_SIP_CONFIG` is populated with direct mirrored
FreeSWITCH WSS, SIP realm `192.168.1.74`, lab credentials and `7100` queue target. Evidence is in
[`live-ui-ip-20260923.md`](live-ui-ip-20260923.md). Replace the IP/asset/config when the final conference URL and
trusted certificate are supplied. No production authentication/security claim is made.
