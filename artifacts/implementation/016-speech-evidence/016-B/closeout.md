# 016-B closeout

Статус: `complete`

- Robust near-end reference: confirmed percentile window; first peak-only implementation rejected during corrective pass.
- Problem call: accepted VAD frames `847 → 494`, hard endpoints `12 → 4`.
- Controlled Map-008 corpus: expected `3`, observed `3`.
- Runtime barge-in: weak typed decision suppressed; qualified near-end speech preserved.
- AEC/media reference: not introduced; blocker not triggered.

Evidence: `problem-call-vad-replay.json`, `controlled-corpus-replay.json`.
