# 001-E execution closeout

Дата исполнения: `2026-08-27`  
Plan: `001-E`  
Статус исполнения child plan E: `complete`  
Map-001: `complete; M-G4 closed after next-plan approval`  
Handoff: `Map-002 approved; child plans require separate owner reviews`

## Result

Feasibility evidence A–D и локального VoIP stand `001-S` reconciled. Candidate baseline, map gates, blocker protocol,
deferred records и next-plan package созданы. E не запускал новые GPU probes, не устанавливал пакеты, не менял source,
runtime или config и не исполнял application integration.

E закрыт как `complete` в пределах своего feasibility/handoff scope. Полный demo-flow не входил в scope E и передан
в отдельную Map-002; следующий implementation plan получил owner approval 2026-09-02.

## E slices

| Slice | Result | Evidence |
|---|---|---|
| `E-001` Evidence intake and requirements index | `pass` | [`evidence-index.md`](evidence-index.md) |
| `E-002` Map-gate matrix | `pass; M-G4 closed 2026-09-02` | [`map-gates.md`](map-gates.md) |
| `E-003` Baseline and blocker closeout | `pass` for candidate baseline | [`baseline-register.md`](baseline-register.md), [`blocker-register.md`](blocker-register.md) |
| `E-004` Deferred/fallback/unexpected-gap review | `pass` | [`blocker-register.md`](blocker-register.md), D gaps |
| `E-005` Next-plan hand-off | `complete; owner review accepted 2026-09-02` | [`next-plan-approval.md`](next-plan-approval.md) |
| `E-006` Feasibility closeout | `complete` | this file |

## Gate result

- `M-G1` closed 2026-08-26.
- `M-G2` closed 2026-08-27: Ubuntu/WSL2 and CPython `3.14.7t` no-GIL baseline.
- `M-G3` closed 2026-08-27: C1/C2/C4 main patched paths and C3 owner-approved process isolation.
- `M-G4` closed 2026-09-02: E package is complete and the next map received its own owner review. This does not
  authorize unreviewed child plans inside Map-002.

## Final feasibility decision

| Area | Decision |
|---|---|
| Main runtime | CPython `3.14.7t` free-threaded/no-GIL |
| SIP/media | PJSUA2/PJMEDIA `2.17` with two exact generated-SWIG patches; local Baresip stand accepted |
| ASR | faster-whisper `1.2.1` + exact CTranslate2 patch; main-process candidate accepted |
| LLM | Qwen3.5-9B GGUF Q4_K_M through Ollama `0.33.1` local process and HTTP IPC; `pass_with_isolation` |
| TTS | XTTS-v2 v2.0.3 with exact no-GIL dependency patches; main-process candidate accepted |
| Control/data plane | Dispatcher owns control; audio and large text direct between channel owners |
| Protected scope | Russian, one call, PCMU/8 kHz/mono, local KB/fake operator, context/report, no audio recording |

## Residual limitations and blockers

- Full application SIP/media integration, protocol-event matrix beyond the tested BYE example, VAD, Transcript Assembler,
  fixed endpointing runtime, retrieval, context/report, real RTP barge-in and complete answer path remain deferred.
- Application callback/thread affinity remains `undecided` where child evidence did not prove it.
- C2/C3/C4 demonstrate close/stale-result semantics, not hard native cancellation acknowledgement.
- C3 warm valid response is `2121.229 ms`, cold valid response `52716.908 ms`; this is not full user-perceived E2E
  latency.
- Concurrent ASR+LLM+TTS GPU contention and production readiness were not claimed.
- `B-001E-008` resolved 2026-09-02 after owner review of Map-002 and Map-002-I. `B-001E-003` is an explicit
  out-of-scope hand-off to Map-002, not a hidden successful integration result.

## Pre-existing and out-of-scope findings

- Negative no-GIL import evidence for unpatched PJSUA2/CTranslate2 is retained; exact patches are part of the baseline.
- Optional C4 Triton/torchcodec paths remain outside the tested path because of their recorded compatibility/runtime
  limitations.
- C3 has no separate backend cancellation acknowledgement; client close and stale-result suppression are the accepted
  MVP boundary observations.
- Real PBX, audio recording, multiple calls, full Wikipedia crawler, MOS study and production hardening are out of scope.

## Execution commands and audits

E used read-only intake of the listed child closeouts/evidence and created only the reserved E artifact set. After
synchronization the following checks passed:

- `python tools/check_document_registry.py` — `actual=24 registry_rows=24 ... PASS`;
- `python tools/check_task_backlog.py` — `rows=6 unique_ids=6 ... PASS`;
- C2 `runtime-manifest.json` JSON parse and `operation_gate=pass` check — pass;
- E artifact-set existence check — 6 files present;
- `git diff --check` — pass.

## Handoff

The next action is execution of separately reviewed Map-002 child plans. Approval of Map-002 and Map-002-I is already
recorded; each implementation child plan still requires its own owner review, and `002-B` remains blocked on its
registered media gap.
