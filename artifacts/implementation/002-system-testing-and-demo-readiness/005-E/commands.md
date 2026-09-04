# 005-E execution commands and results

Дата: `2026-09-04`  
Target: Ubuntu 24.04/WSL2, CPython `3.14.7t`, `gil_enabled=false`, RTX 5060 Ti

## E1–E3 deterministic and target checks

| Проверка | Команда | Результат |
|---|---|---|
| Focused playback tests | `python -m pytest tests/unit/test_tts_output.py tests/unit/test_map005_ai_playback.py tests/integration/test_barge_in.py -q` | `15 passed` |
| Host regression | `python -m pytest -q` | `151 passed, 5 skipped in 13.48s` |
| Target regression | `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q tests/unit tests/contract tests/integration` | `154 passed, 2 skipped in 9.46s` |
| Target runtime/live preflight | `wsl.exe -d Ubuntu-24.04 -- nvidia-smi` и target runner | RTX 5060 Ti, target free-threaded runtime, GIL disabled |

## E4 target live gate

```text
wsl.exe -d Ubuntu-24.04 -- /usr/bin/env \
  LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs \
  /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I \
  /mnt/c/devel/sip-bot/tools/map005_rehearsal_gate.py \
  --output-root /mnt/c/devel/sip-bot/artifacts/implementation/002-system-testing-and-demo-readiness/005-E/target-20260904-r10 \
  --timeout-s 240 --post-report-grace-s 3
```

Результат runner: `pass`; сценарий содержит SIP/RTP PCMU, multi-turn/RAG, barge-in, unknown-answer/transfer,
fake operator transfer, report и Baresip stereo recording.

Машиночитаемый результат: [`map005-d-rehearsal.json`](target-20260904-r10/map005-d-rehearsal.json). Runner сохраняет
historical schema `map005-d-rehearsal.v1`, но evidence принят этим plan как новый E4 root; исходные r7–r9 не
перезаписывались.

## E4 counters

| Counter | Значение | Интерпретация |
|---|---:|---|
| `tts_output.accepted_chunks` | `48` | Все принятые TTS chunks |
| `tts_output.accepted_bytes` | `679084` | Принятый полезный PCM |
| `tts_output.emitted_frames` | `1845` | Сформированные/выданные negotiated frames |
| `tts_output.emitted_bytes` | `590400` | 1845 × 320 bytes, включая padding tail |
| `tts_output.flushed_tail_frames` | `2` | Штатно дополненные последние frames |
| `tts_output.dropped_overflow_bytes` | `0` | Потери из-за high-water отсутствуют |
| `tts_output.dropped_stale_chunks` | `0` | Stale TTS chunks не пришли |
| `tts_output.dropped_cancelled_chunks` | `0` | Новые chunks после cancel не пришли |
| `tts_output.dropped_tail_bytes` | `88982` | Явно отменённый хвост старого поколения при barge-in |
| `tts_output.buffered_bytes` | `0` | После завершения playback буфер пуст |
| `tts_output.pending_frames` | `0` | После завершения playback кадров не осталось |
| `adapter_media_stats.egress_underruns` | `0` | Чистых playback underruns нет |
| `adapter_media_stats.egress_dropped_overflow` | `0` | Media egress overflow отсутствует |

`accepted_bytes - dropped_tail_bytes + tail padding = emitted_bytes`; расхождение объясняется только двумя
штатными tail frames и отменённым старым поколением, а не silent drop активного ответа.

