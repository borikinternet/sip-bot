# 016-I source audit

Дата: 2026-09-22  
Результат: `PASS`  
Contract revision: `speech-evidence-I1`

## ASR edge

- Producer: `FasterWhisperC2Backend.transcribe_chunk()`.
- Native/model output: lazy faster-whisper segments with `text`, `no_speech_prob`, `avg_logprob`,
  `compression_ratio`, `start`, `end`.
- Existing loss: implementation consumed the iterator and retained only concatenated `text`.
- Coercion owner: `StreamingAsrAdapter.stream()` / `coerce_backend_hypothesis()`.
- Consumer: `SpeechIngress.accept_hypothesis()` followed by `TranscriptAssembler.accept()/finalize()`.
- Required rejection lifecycle: rejected partial is ignored; rejected final discards only the matching `turn_id`
  assembler and pending hard endpoint, producing no `FinalUserTurn`.

Production probe on the recorded-call turns showed real speech `no_speech_prob <= 0.024` and false acoustic/noise turns
`no_speech_prob >= 0.787`. This is evidence for the initial configurable threshold, not a claim of universal
calibration.

## VAD/barge edge

- Producer: `VadProcessor.process()` returns immutable `VadDecision`.
- Existing diagnostics: RMS dBFS, noise floor and normal speech threshold.
- Existing unused state: per-call speech level was calculated but not used to qualify turns/barge-in.
- Endpoint owner: `TurnDetector.consume()`.
- Existing barge materialization: `CallRuntimeWiring._publish_speech_events()` maps start/resume during
  `playing|offering_transfer` to `BARGE_IN`.
- Required change: producer adds near-end/barge threshold diagnostics; existing runtime method applies the threshold
  before emitting the compact control event. No new component, queue or delivery owner is needed.

## Blockers

- `B-016-I-001`: not triggered; required model fields observed.
- `B-016-I-002`: not triggered; existing scoped owners express rejection atomically.
