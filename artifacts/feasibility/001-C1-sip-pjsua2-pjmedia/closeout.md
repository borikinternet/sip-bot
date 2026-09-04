# C1 closeout — PJSUA2/PJMEDIA

Дата: `2026-08-27`  
Статус исполнения child plan: `complete`  
Candidate decision: `pass`  
Owner review перед execution: `2026-08-27`

## Result

PJSUA2/PJMEDIA `2.17` проходит C1 feasibility на CPython `3.14.7t` в Ubuntu 24.04.4 LTS / WSL2 as the primary
MVP SIP/media candidate. The candidate uses two explicit narrow patches to the generated SWIG wrapper:

1. `patches/pjsua2-free-threading.patch` declares the single-phase extension as not using the GIL at import;
2. `patches/pjsua2-free-threading-buffer.patch` prevents the wrapper from detaching the Python thread state around
   Python buffer API calls used by the media capture helper.

The second patch was required because the unmodified wrapper crashed when the no-GIL capture path called
`copy_to_bytearray`; the issue was isolated and the patched operation passes. The patch is a candidate compatibility
measure, not a blanket claim of native thread safety under arbitrary production load.

## Acceptance

| Slice | Result | Evidence |
|---|---|---|
| S0 prerequisite/manifest | `pass` | `candidate-manifest.json`, `commands.md` |
| S1 import/no-GIL/initialization | `pass with candidate patches` | `patched-import-lifecycle.json` |
| S2 minimal SIP lifecycle | `pass` | `../001-S-voip-test-stand/lifecycle.json` |
| S3 PCMU 8 kHz mono media | `pass` | `../001-S-voip-test-stand/pcmu.json` |
| S4 BYE during active busy fixture | `pass` | `../001-S-voip-test-stand/bye.json` |

The peer-dependent lanes use the separately approved `001-S` stand. C1 did not create a hidden test stand, use an
external PBX or write audio recordings.

## Protected constraints

- `Py_GIL_DISABLED=1`; `sys._is_gil_enabled()` is false before import, after import, after initialization and after
  SIP/media operation; no auto-enable warning was emitted.
- The peer negotiates `PCMU/8000/1`; Baresip logs both PCMU encoder and decoder and the PJSUA2 media capture receives
  non-zero frames.
- During the BYE scenario a 10-second bounded background-work fixture was active; the remote disconnect was observed
  before local hangup, with a measured loopback delivery interval of `0.453 ms`.
- Transfer is not part of C1's four acceptance lanes; it is independently covered by `001-S/transfer.json`.

## Blockers

Resolved:

- `C1-B-001` — accepted free-threaded runtime.
- `C1-B-002` — exact PJSIP/PJMEDIA source/build/import manifest.
- `C1-B-003` — patched binding imports and operates.
- `C1-B-004` — approved local peer supplied by `001-S`.
- `C1-B-005` — executable BYE scenario and timestamps supplied by `001-S`.
- `C1-B-006` — no-GIL state remains false through operation.

Not triggered:

- `C1-B-007` — lifecycle/cleanup evidence passes.
- `C1-B-008` — PCMU/RTP evidence passes.
- `C1-B-009` — BYE is observed during active bounded work before local close.

Open by policy:

- `C1-B-010` — no fallback, new isolation boundary, contract change or assertion weakening may be introduced without
  owner review.

## Decision and handoff

Fallback and process isolation were not started. The primary SIP/media candidate is accepted for the MVP implementation
path with the recorded patches and the stated testing limits. The decision can be consumed by `001-D`; this closeout
does not claim production readiness or complete the bot.
