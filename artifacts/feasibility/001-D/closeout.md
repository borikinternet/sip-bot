# 001-D execution closeout

Дата исполнения: `2026-08-27`  
Plan: `001-D`  
Статус исполнения child plan D: `complete`  
Synthesis result: `pass`  
Handoff: `ready for owner review of 001-E`

## Результат

Синтез process/thread boundaries и control/data plane выполнен на основании closeout/evidence A–C. D не запускал
runtime, не устанавливал пакеты, не менял исходный код и не переписывал child evidence.

Итоговая component matrix:

| Контур | Итог | Process decision |
|---|---|---|
| SIP/PJSUA2/PJMEDIA | `pass` в проверенном patched path | Main free-threaded CPython; application callback affinity остаётся `undecided` |
| ASR/faster-whisper | `pass` в проверенном patched path | Main free-threaded CPython; exact CTranslate2 patch обязателен |
| LLM/Qwen3.5-9B | `pass_with_isolation` | Main no-GIL HTTP controller + отдельный локальный Ollama native process |
| TTS/XTTS-v2 | `pass` в проверенном patched path | Main free-threaded CPython; exact dependency patches обязательны |

## Исполненные D-срезы

| Slice | Результат | Evidence |
|---|---|---|
| D-001 Intake и gate proof | `pass` | `input-evidence-index.md`; все A–C closeout доступны |
| D-002 Process/thread synthesis | `pass with explicit undecided` | `process-thread-boundary-matrix.md`, `baseline-register-draft.md` |
| D-003 Control/data map | `pass with deferred integration` | `control-data-plane-map.md` |
| D-004 Reconciliation/blocker review | `pass` | `unexpected-gaps.md`; no blocking unexpected architecture gap |
| D-005 Closeout/handoff | `pass` | этот файл; `001-E` — следующий plan |

## Зафиксированные архитектурные решения

1. Main process — free-threaded CPython `3.14.7t`; automatic GIL re-enable в tested main-process paths не принимается.
2. PJSUA2/PJMEDIA, faster-whisper и XTTS-v2 остаются main-process feasibility candidates только с exact recorded
   patches/build constraints.
3. C3 inference не импортируется в main process. Ollama `0.33.1` с bundled native CUDA runner работает отдельным
   локальным процессом; HTTP на `127.0.0.1` — существующий IPC и принятая boundary.
4. Dispatcher владеет control plane, Dialogue FSM, semantic action validation и lifecycle каналов.
5. RTP/PCM/ASR partial/final/answer text идут по direct data paths между владельцами; Dispatcher не является payload
   proxy.
6. Mandatory SIP protocol responses, включая `BYE`, не ждут LLM/TTS/Dispatcher; semantic disconnect передаётся событием.

## Blocker reconciliation

| ID | Итог |
|---|---|
| `B-001D-001` | Resolved: A–C closeout/evidence доступны |
| `B-001D-002` | Resolved for current inputs: required component fields присутствуют в child evidence |
| `B-001D-003` | Resolved 2026-08-27: C3 HTTP process boundary owner-approved |
| `B-001D-004` | Not triggered: новый queue/facade/IPC не создавался |
| `B-001D-005` | Deferred by scope: full integrated channel lifecycle belongs to implementation/test plan |
| `B-001D-006` | Not triggered: architecture/ADR conflict не обнаружен |
| `B-001D-007` | Resolved for D synthesis: source command/version/output paths indexed; raw commands remain in child roots |
| `B-001D-008` | Not triggered: no required contour has unresolved fail/blocked status |

## Pre-existing и out-of-scope findings

- Patched native bindings are required for the tested C1/C2/C4 paths; this is a compatibility constraint, not a silent
  simplification.
- C2, C3 и C4 не предоставляют hard native cancellation token/ack; close + stale-result suppression are the accepted
  MVP boundary observations.
- C3 timing is not a full user-perceived end-to-end latency: warm valid response `2121.229 ms`, cold first valid
  response `52716.908 ms`, with ASR/VAD/SIP/RTP/TTS excluded from that measurement.
- Concurrent GPU contention, full RAG, VAD/endpointing implementation, Transcript Assembler, direct channel runtime,
  real barge-in RTP and complete end-to-end call remain outside D.
- `GAP-001D-001` was a stale preparatory C2 manifest field; it was corrected to `operation_gate=pass` after D review.
  The authoritative operation evidence and closeout remain unambiguous.

## Deferred records

The detailed records are in `unexpected-gaps.md`: thread/task affinity, existing C3 IPC adapter contract, integrated
channel lifecycle, concurrent GPU fit, speech pipeline and RAG. Deferred records are not treated as successful tests.

## Handoff to 001-E

`001-E` may review this evidence-backed handoff. It must reconcile the baseline register, residual deferred records and
Map-001 gates; D does not close M-G4 by itself and does not authorize implementation without the next plan's review.
