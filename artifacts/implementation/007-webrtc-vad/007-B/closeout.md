# 007-B — closeout

Статус: `complete`

Дата: `2026-09-13`

## Что принято

`007-A` предоставил exact patched `webrtcvad-wheels 2.0.14` binding, прошедший target и combined no-GIL
import/operation/concurrency gate. В application configuration добавлен явный `VAD_MODE=2`, а
`RuntimeConfig.from_constants()` теперь предоставляет его как typed snapshot.

Существующая boundary не менялась:

```text
PcmFrame
  → VadProcessor.process(frame)
  → WebRtcVadCandidate.is_speech(pcm_s16le, negotiated_sample_rate_hz)
  → VadDecision
  → TurnDetector.consume(decision)
```

Новые owners, очереди, event-bus audio paths, conversion helpers и fallback не добавлялись.

## Evidence

- Host regression: `136 passed, 2 skipped`.
- Target CPython `3.14.7t`: `18 passed, 2 skipped`.
- Python compile check: pass.
- New boundary test confirms `VAD_MODE=2`, `WebRtcVadCandidate` source identity and negotiated rates `8000`/`16000`.
- Exact binding/no-GIL evidence: [`../007-A/closeout.md`](../007-A/closeout.md).

## Blockers

Нет. Ошибок contract/lifecycle или необходимости менять Map-I не обнаружено.

## Handoff

`007-C` может выполнять live source audit и clean-start Baresip gate. Только `007-C` меняет live tool selection;
deterministic amplitude fixtures остаются тестовыми doubles.
