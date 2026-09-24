# Map-008-B execution closeout

Статус: `complete`  
Дата: `2026-09-13`  
Evidence: `r3/turn-detector-replay.json`

## Результат

Сохранённый `mode-2` VAD trace из `008-A` replay-нут через существующий
typed edge `VadDecision → TurnDetector.consume(decision)`. Новый компонент,
очередь или boundary не добавлялись; endpoint state остался у
`TurnDetector`.

Первичный baseline `hard_endpoint_ms=500` дал `4` authoritative endpoint
вместо ожидаемых `3`: пауза, размеченная как 480 ms внутри второго
semantic turn, после VAD/frame quantization достигла фактических 500 ms.
Это было исправлено корректировкой существующего endpoint policy, а не
добавлением smoother.

Проверена сетка `500/520/540/560 ms`. Минимальная проходящая настройка —
`hard_endpoint_ms=520`, при сохранении `soft_endpoint_ms=300` и
`min_speech_ms=80`.

| Проверка | Результат при 520 ms |
|---|---:|
| Authoritative hard endpoints | `3/3` |
| Hard endpoints внутри ожидаемого semantic turn | `0` |
| Internal pauses without split | `pass` |
| Soft endpoints | `4` |
| Speech resumed | `3` |
| Repeated replay deterministic | `pass` |

Команда:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/turn_detector_calibration_probe.py --trace /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/runs/mode-sweep/mode-2.json --corpus-manifest /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/corpus/manifest.json --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-B/r3'
```

Exit code: `0`; runtime: CPython `3.14.7t`, `gil_enabled=false`.

## Изменения

- `config/constants.py`: `ENDPOINT_HARD_MS=520`;
- `src/sip_bot/speech/endpointing.py`: default policy `hard_endpoint_ms=520`;
- `tools/turn_detector_calibration_probe.py`: threshold sweep, baseline
  failure retention, corrected interior split metric;
- unit tests для replay/frame/manifest helpers.

Следующий child получил selected configuration, corpus/trace hash, endpoint
trace, metrics, regression result и ограничения. `008-B` не использовал ASR
как oracle.
