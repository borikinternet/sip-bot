# 021-E: registered end-to-end gate web → mod_callcenter → bot

Уровень: `child plan` · Родитель: [`Map-021`](plan-021-web-rag-conference-demo.md)
Статус: `in_progress` — local page, host-to-WSL WSS bridge and browser media gate pass; queue → bot/RAG correlation remains
Evidence root: `artifacts/implementation/021-web-rag-sip-demo/E/`

## Цель и граница

Провести clean-start conference scenario после закрытия 021-A–D и local Map-020 contract: baseline call, custom corpus
upload, `rag_ready`, browser SIP call with URI user-part caller ID, FreeSWITCH `mod_callcenter` caller-leg `200` plus
hold music, bot agent-leg `180 → load → 200` within `15 s`, topic greeting, source-aware dialogue, terminal cleanup and
a second sequential corpus.

## Acceptance matrix

1. Baseline user sees questions and calls immediately.
2. Custom user sees preparing state and cannot call before index readiness.
3. Ready custom user sees updated metadata and active button.
4. FreeSWITCH owns waiting order; bot handles one call at a time.
5. Caller ID selects the correct prepared index.
6. Greeting says «Василиса» and the current topic.
7. Two sequential calls have no RAG/context leakage.
8. Closed/reloaded page removes waiting mapping; stale call uses approved baseline fallback.
9. Active call survives heartbeat loss until SIP terminal event.
10. RTP continuity, report, runtime errors, drops and underruns are clean.
11. A corpus load timeout never produces a `200 OK` with a mismatched custom corpus; the queue remains in charge of the
    existing agent failure/retry path.

## Source-map/write-set и blocker register

Write-set: only test fixtures, runner glue and `artifacts/implementation/021-web-rag-sip-demo/E/`; no new runtime behavior
may be introduced solely in the gate. Blockers are inherited from Map-021 plus:

| ID | Trigger | What blocks | Status |
|---|---|---|---|
| B-021-E-1 | 021-C/D still have deferred registered evidence | map-level gate | `open — B is complete; C/D correlation remains` |
| B-021-E-2 | browser → `mod_callcenter` → bot/RAG correlation not yet executed | live acceptance | `open — transport and page config pass; run registered queue/bot scenario` |

## Test/evidence и closeout

Run focused child selectors, full host regression, target CPython 3.14.7t/no-GIL regression where available, and the
registered FreeSWITCH gate. Save raw commands, output, exit codes, call/RAG correlation, SIP timing and artifacts. A
No registered gate was claimed in this pass: a successful local/mock call cannot replace the browser →
`mod_callcenter` → one-bot scenario. Promotion command and required evidence are in
[`E/closeout.md`](../../artifacts/implementation/021-web-rag-sip-demo/E/closeout.md).
