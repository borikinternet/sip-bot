# C2 blocker register — GPU execution

| ID | Slice | Status | Evidence | Blocking effect | Owner decision needed |
|---|---|---|---|---|---|
| `C2-B-004` | C2-S1–C2-S4 | **resolved for tested path; patch mandatory** | `import-no-gil-before-patch.json`, `import-no-gil.json`, `patch-build.md`, `operation.json`, `partial-final.json`, `cancellation.json` | Unpatched `_ext` enabled GIL; exact patched binding preserved GIL-disabled state through model load, operation, streaming and close probe | Do not replace the patched binding with an unpatched wheel; future native/library change reopens this blocker |
| `C2-B-003` | C2-S2 | **mitigated for fixture materialization** | `fixture.md` | Clip hash/format/duration are known; production PCMU/RTP conversion remains outside preparation | Parent reviews fixture provenance and uses the recorded conversion path |
| `C2-B-005` | C2-S2/C2-S3 | **resolved** | `operation.json`, `partial-final.json` | One-shot result and bounded-prefix partial/final observations are present; authoritative final is non-empty | Future quality/latency work is outside this child closeout |
| `C2-B-006` | C2-S3 | **resolved with explicit limitation** | `cancellation.json`, `closeout.md` | Generator close and closed-channel stale suppression pass; candidate has no independent native cancellation token, so hard immediate kernel interruption is not claimed | Preserve the MVP “take away the pipe” semantics; reopen only if hard native cancellation becomes a requirement |
| `C2-B-009` | C2-S4 | **resolved** | `runtime-manifest.json`, `commands-and-versions.txt`, `operation.json`, `partial-final.json`, `cancellation.json` | Candidate, runtime, commands, operation records and statuses are recorded | Future reruns must preserve the same evidence fields |

No fallback candidate was inspected or selected. No `PYTHON_GIL=0` override is accepted as a blocker resolution.

## Non-blocking provenance gap

| ID | Scope | Status | Evidence | Effect | Owner decision |
|---|---|---|---|---|---|
| `C2-GAP-001` | Offline Russian fixture | open, non-blocking for GPU smoke | `fixture.md` | The public mirror is Common Voice 26.0 under a repository alias containing `25-0`; strict 25.0 provenance is not claimed | Accept the CC0 26.0 fixture for smoke, or provide an owner-approved 25.0 asset before final C2 decision |
