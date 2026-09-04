# 002-D evidence index

| Evidence ID | Result | File | What is proven |
|---|---|---|---|
| `D-E-CONTRACT-001` | `pass` | `contract-manifest.json` | Typed speech boundary fields, owners and final-authority rule |
| `D-E-VAD-001` | `pass` | `vad-candidate.json` | WebRTC VAD candidate API and deterministic operation path |
| `D-E-ENDPOINT-001` | `pass` | `endpointing.json` | 300 ms soft / 500 ms hard, pause and resume semantics |
| `D-E-TRANSCRIPT-001` | `pass` | `transcript-revisions.json` | Revision replacement, stable prefix, stale suppression, final boundary |
| `D-E-TRANSCRIPT-002` | `pass` | `transcript-stability-corrective-20260904.md` | Early common ASR prefix is not frozen without backend stable-prefix metadata; target/live corrective rerun |
| `D-E-CANCEL-001` | `pass` | `cancellation-stale.json` | Cancellation and old-generation suppression |
| `D-E-RUNTIME-001` | `pass` | `target-runtime.json` | Target free-threaded runtime and no-GIL state |
| `D-E-TEST-001` | `pass` | `target-speech.stdout.log` | Target speech tests: 11 passed |
| `D-E-REGRESSION-001` | `pre-existing` | `pre-existing-host-regression.md` | Unrelated DialogueFSM failures in full host lane |

No audio recording, external ASR service, SIP action or Dispatcher payload was created by this slice.
