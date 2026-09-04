# 001-E blocker register

Дата: `2026-08-27`  
Статус: `Map-001 complete; no unresolved blocker in E scope; integration deferred to Map-002`

| ID | Trigger | Что блокируется | Evidence / decision | Status |
|---|---|---|---|---|
| `B-001E-001` | A–D closeout/evidence missing, overwritten or conflicting | E и M-G4 | `001-E/evidence-index.md`, child closeouts and D input index; all required roots present | `resolved` |
| `B-001E-002` | M-G2/M-G3 lack closure conditions or owner decision | M-G4 | [`map-gates.md`](map-gates.md), A/B/C/D closeouts; M-G2/M-G3 explicitly closed | `resolved` |
| `B-001E-003` | Full application contour lacks integrated runtime evidence | Feasibility completeness / map-ready status | Component baselines exist, but VAD/RAG/channels/context/report/full call are explicit deferred records; this is outside E feasibility/handoff scope and registered in Map-002 | `resolved by explicit out-of-scope hand-off` |
| `B-001E-004` | D map violates process/thread/control/data ownership | M-G4 and next implementation | D matrix/map preserve Dispatcher control-plane ownership, direct payload and C3 owner-approved isolation | `resolved for map synthesis` |
| `B-001E-005` | Deferred record lacks `evidence_id/task/scope/owner/gap/promotion` | Closeout trust | D and E deferred records contain required fields; see [closeout](closeout.md) | `resolved` |
| `B-001E-006` | Fallback/simplification lacks owner, scope or corrective path | Closeout and dependent plan | Scope-freeze and E fallback register contain approved cuts; no new fallback added | `resolved` |
| `B-001E-007` | New adapter/facade/IPC/architecture boundary discovered | Dependent slice | No new boundary was introduced; existing C3 HTTP IPC is the accepted boundary | `not triggered` |
| `B-001E-008` | No separately reviewed next plan with acceptance/evidence root | M-G4 hand-off and child execution | [`next-plan-approval.md`](next-plan-approval.md) records owner approval of Map-002 and Map-002-I on `2026-09-02` | `resolved 2026-09-02` |
| `B-001E-009` | Closeout claim lacks command/version/exit code/raw output or audit result | Feasibility trust | E index links commands and raw outputs; registry/backlog/diff audits executed after synchronization | `resolved` |
| `B-001E-010` | Deadline missed without owner scope/status decision | Map status | Current execution date `2026-08-27`, conference date `2026-09-25`; no missed deadline | `not triggered` |

## Residual deferred records

| evidence_id | task | scope | owner | gap | promotion |
|---|---|---|---|---|---|
| `DEFER-001E-INTEGRATION-001` | `TASK-001 / plan-002` | Сквозной SIP/RTP, protocol-event reactions (BYE как minimum example, плюс применимые CANCEL, OPTIONS, re-INVITE/UPDATE и RTP/media failure), PCMU, answer, report и single-call flow | Owner следующего plan + project owner | Feasibility evidence не является реализацией/demo evidence | Approved plan-002, deterministic stand smoke, saved logs and exit codes |
| `DEFER-001E-CHANNEL-001` | `TASK-001 / plan-002` | Stale producer, close/re-close, generations, direct audio/text channels | Channel owner + project owner | D map не заменяет application state-machine/channel tests | Contract tests и SIP/RTP scenario с channel IDs |
| `DEFER-001E-LATENCY-001` | `TASK-001 / plan-002` | E2E turn latency и component breakdown | Answer-path owner + project owner | C3/C4 timings не являются полным call-path measurement | Deterministic stand, timestamp schema, raw latency report |
| `DEFER-001D-SPEECH-001` | `TASK-001 / speech pipeline` | VAD, Transcript Assembler, Turn Detector | Next implementation owner | No runtime evidence | Speech pipeline plan and endpointing tests |
| `DEFER-001D-RAG-001` | `TASK-001 / knowledge path` | Curated natural-science KB and retrieval | Knowledge-path owner | No selected runtime/index evidence | Local KB fixture, index build and retrieval evidence |

Deferred означает отсутствие результата до promotion; это не `skip`, `xfail` и не скрытый `pass`.
