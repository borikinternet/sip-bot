# 001-S evidence index

| Evidence | Stage | Result | What it proves |
|---|---|---|---|
| `preflight.md` | S0 | pass | Environment, candidate freeze, canonical configs and expected registrar note |
| `candidate-manifest.json` | S0/S5 | pass | Baresip package/modules, DUT runtime, codec, ports and policy flags |
| `commands.md` | S0/S5 | pass | Reproduction commands, exit codes and observed acceptance facts |
| `lifecycle.json` | S1 | pass | Local SIP call establishment and cleanup |
| `pcmu.json` | S2 | pass | PCMU/8000/1 negotiation, bidirectional RTP and PJSUA2 media capture |
| `bye.json` | S3 | pass | Remote BYE and `DISCONNECTED` before local hangup |
| `transfer.json` | S4 | pass | Transfer request from PJSUA2 through Baresip to fake operator |
| `*.pjsua.json` | S1–S4 | pass | Nested PJSUA2 runtime, callback, GIL and event evidence |
| `*.peer.log` | S1–S4 | pass | Baresip signaling/media logs and RTP counters |
| `transfer.operator.log` | S4 | pass | Fake operator startup, PCMU answer and established call |
| `redaction.md` | S5 | pass | Confirmation that no credentials or audio recordings are included |
| `closeout.md` | S5 | pass | Final status, blockers and handoff to C1 |

The sibling `lifecycle-no-call-probe.json` is historical exploratory evidence and is not used for acceptance.
