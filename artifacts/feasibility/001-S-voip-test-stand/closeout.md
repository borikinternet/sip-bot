# 001-S closeout — локальный VoIP/RTP тестовый стенд

Дата: `2026-08-27`  
Статус исполнения child plan: `complete`  
Stand result: `pass`  
Owner review перед execution: `2026-08-27`

## Candidate and runtime

- Stand candidate: Baresip `1.0.0-4build14`, Ubuntu 24.04 Noble stable package.
- DUT candidate: PJSUA2/PJMEDIA `2.17` with the recorded CPython free-threading compatibility patches.
- Runtime: CPython `3.14.7t`, `Py_GIL_DISABLED=1`; PJSUA2 evidence reports GIL disabled before import, after import,
  after initialization and after each call.
- Peer: `127.0.0.1:5080`; fake operator: `127.0.0.1:5090`; codec: PCMU/8000/1.

## Acceptance

| Slice | Evidence | Result |
|---|---|---|
| S-S0 preflight/candidate freeze | `preflight.md`, `candidate-manifest.json` | `pass` |
| S-S1 lifecycle | `lifecycle.json` | `pass` |
| S-S2 PCMU/RTP | `pcmu.json` | `pass`; peer counters 201/200, DUT capture 200 frames / 64000 bytes |
| S-S3 remote BYE | `bye.json` | `pass`; remote disconnect observed while 10 s busy fixture was active and before local hangup, measured 0.453 ms in loopback |
| S-S4 fake operator/transfer | `transfer.json`, `transfer.operator.log` | `pass`; operator reports established call |
| S-S5 evidence/closeout | `evidence-index.md`, `redaction.md`, `commands.md` | `pass` |

## Blockers

- `S-B-001`: resolved — Baresip is installed and starts.
- `S-B-002`: resolved — PCMU/8000/1 and bidirectional RTP are evidenced.
- `S-B-003`: resolved — lifecycle is observable and cleans up.
- `S-B-004`: resolved — the peer can send BYE during the bounded call window.
- `S-B-005`: resolved — transfer reaches the local fake operator.
- `S-B-006`: remains `open by policy` — fallback, external PBX, recordings and production-contract changes remain
  prohibited without owner review.
- `S-B-007`: resolved — required command, version, exit-code, event and failure fields are present.

The Baresip `501 Not Implemented` self-registration response is an expected property of the direct-IP stand, not a
blocker. No fallback was started and no production architecture was changed.

## Handoff

`001-S` supplies the approved local peer and evidence required to resume `001-C1` slices S2–S4. The stand does not
prove production SIP ownership, Dispatcher behavior or the final bot transfer adapter; those remain the responsibility
of the corresponding architecture and implementation slices.
