# 021-C: caller ID, call-scoped RAG load и readiness

Уровень: `child plan` · Родитель: [`Map-021`](plan-021-web-rag-conference-demo.md)
Статус: `in_progress`
Evidence root: `artifacts/implementation/021-web-rag-sip-demo/C/`

## Цель и граница

Протянуть caller ID из SIP URI user-part через PJSUA2 в нормализованное call-start событие, выбрать по нему prepared RAG, загрузить index в
единственную bot call-сессию между `180 Ringing` и `200 OK`, сформировать topic-aware greeting Василисы и очистить
call-scoped artifact после terminal event.

Очередь `mod_callcenter` и browser WSS конфигурация не изменяются этим child plan. В текущем dialplan caller leg уже
получает `200 OK` перед `callcenter` и слышит queue `moh-sound`; `180` этого плана относится только к bot agent leg.

## Source-map, owner и write-set

Owners: `SipMediaAdapter` — protocol/caller extraction; `IncomingCallReadinessGate` — admission/load; `CallOwners` /
`ConversationPipeline` — per-call retrieval/greeting. Write-set: narrow typed fields/methods in existing modules, tests,
new registry adapter and evidence root. No global active-index mutation and no second bot instance.

## Acceptance

- live incoming event exposes the normalized SIP URI user-part used by browser session;
- bot agent-leg `180` is emitted before selected index load;
- agent-leg `200` is emitted only after index load/self-check or explicit approved baseline fallback, with a `15 s` bound;
- timeout does not send agent-leg `200` with the wrong custom corpus; it follows the existing explicit failure/retry path;
- matching caller gets correct source-aware RAG and topic greeting;
- missing/stale caller mapping uses baseline RAG and does not use stale metadata;
- active artifact survives web heartbeat loss until SIP terminal event;
- terminal cleanup is idempotent;
- two sequential calls prove no cross-session leakage.

## Blocker register

| ID | Trigger | What blocks | Status |
|---|---|---|---|
| B-021-C-1 | caller ID not exposed by PJSUA2 binding | routing/live gate | `resolved in adapter contract; registered trace pending` |
| B-021-C-2 | load time exceeds agreed admission bound | agent-leg `200 OK` path | `implemented with 15 s timeout; target trace pending` |
| B-021-C-3 | Map-020 browser caller ID contract absent | full browser gate | `local WSL A/B available; URI correlation pending in 021-E` |

## Test/evidence и closeout

Contract tests cover caller propagation, `180 → prepare → 200/503`, terminal cleanup, baseline fallback and the stable
single-index handle; the focused selector is green (`19 passed` in the existing SIP/readiness lane). The live
no-GIL/FreeSWITCH trace remains deferred to 021-E. Evidence is in [`C/closeout.md`](../../artifacts/implementation/021-web-rag-sip-demo/C/closeout.md).
