# C2 evidence index

| Evidence ID | Record | Result |
|---|---|---|
| `C2-OR-001` | `candidate-freeze.md` | One primary frozen: `ASR-PRIMARY-001-faster-whisper`; no fallback |
| `C2-OR-002` | `runtime-manifest.json` | Exact candidate, model, dependencies, runtime, artifacts and licenses recorded |
| `C2-OR-003` | `import-no-gil.json`, `import-no-gil-before-patch.json` | Before patch CTranslate2 auto-enabled GIL; after local binding patch all listed imports passed |
| `C2-OR-004` | `fixture.md` | Licensed offline Russian source and materialization provenance; clip/hash recorded after extraction |
| `C2-OR-005` | `commands-and-versions.txt` | Reproduction and guarded future GPU commands recorded |
| `C2-OR-006` | `model-manifest.json` | Pinned model revision downloaded; all 7 expected files and hashes verified |
| `C2-OR-007` | `patch-build.md`, `ctranslate2-free-threading.patch` | Exact CTranslate2 source, narrow patch, build output and hashes recorded |
| `C2-OR-008` | `operation.json` | GPU one-shot on `cuda/int8_float16` passed; non-empty Russian result and GIL-disabled checkpoints recorded |
| `C2-OR-009` | `partial-final.json` | 1.0 s bounded-prefix streaming produced partial revisions and authoritative final |
| `C2-OR-010` | `cancellation.json` | Generator-close boundary passed; no stale output after close; no native cancel token available |
| `C2-BLOCKERS` | `blocker-register.md` | `C2-B-004`, `C2-B-005`, `C2-B-006`, `C2-B-009` closed for tested path; `C2-GAP-001` remains non-blocking provenance gap |
| `C2-PROBE` | `/C:/devel/sip-bot/tools/asr_primary_probe.py` | Import, one-shot operation, bounded-prefix streaming and cancellation/close evidence were executed |

The pinned model weights are materialized outside the repository and indexed by `model-manifest.json`; live
conversation audio is not present. The tested C2 path requires the exact patched binding described by
`ctranslate2-free-threading.patch` and `patch-build.md`.
