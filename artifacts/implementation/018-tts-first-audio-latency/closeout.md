# Plan-018 closeout: XTTS first-audio latency

Статус: `complete`  
Дата: 2026-09-23  
Выбранный baseline: `TTS_STREAM_CHUNK_SIZE=5`, `TTS_STREAM_OVERLAP_WAV_LEN=1024`

## Результат sweep

Один прогретый XTTS-v2 runtime на `NVIDIA A100-SXM4-40GB`, CPython `3.14.7t`, GIL выключен. Для каждого кандидата
выполнено десять генераций: пять русских фраз, два прохода после отдельного warmup.

| Chunk size | Median first PCM | P95/max first PCM | Max full RTF | Minimum buffer before refill | Producer underruns | Clipping |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 398.059 ms | 401.991 ms | 0.533 | 443.420 ms | 0 | 0 |
| 10 | 204.681 ms | 264.605 ms | 0.575 | 210.416 ms | 0 | 0 |
| **5** | **107.277 ms** | **149.634 ms** | **0.542** | **73.305 ms** | **0** | **0** |

Все полные WAV и per-run metrics: [`sweep-r1/probe.json`](sweep-r1/probe.json). Кандидат `5` уменьшил isolated
median TTFA примерно в `3.7` раза относительно `20`, сохранил generation быстрее realtime и не вызвал starvation.

## Registered live timing

Full FreeSWITCH gate: `status=pass`; follow-up, barge-in, unknown-answer/offer-transfer, transfer, report, RTP continuity
и stereo recording прошли. Typed trace измеряет существующие owner boundaries и не участвует в управлении вызовом.

| Generation | LLM→command | Command→worker | Worker→adapter | Adapter→engine | Engine→PCM | PCM→playback | LLM→playback |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 6.940 | 0.431 | 2.463 | 192.562 | 2.784 | 1.692 | **206.873 ms** |
| 3 | 1.566 | 0.320 | 1.254 | 166.487 | 2.645 | 1.227 | **173.499 ms** |
| 4 | 4.774 | 0.695 | 0.996 | 176.862 | 2.687 | 6.960 | **192.975 ms** |
| 5 | 8.532 | 0.235 | 0.157 | 210.945 | 2.768 | 1.197 | **223.834 ms** |

Основной остаток — собственно ожидание первого engine chunk XTTS (`166.487–210.945 ms`). Остальной путь после
финального решения LLM занимает `7.012–12.889 ms`. RTP: expected/egress `6151/6151`, `egress_underruns=0`;
`dropped_overflow_bytes=0`, wiring/runtime errors `0`.

Evidence:

- [`registered-live-r1/registered-j4-full-live.json`](registered-live-r1/registered-j4-full-live.json) — исходный gate;
- [`registered-live-r1/tts-latency-audit.json`](registered-live-r1/tts-latency-audit.json) — машинная агрегация четырёх trace;
- [`registered-live-r1/recordings/conversation-stereo.wav`](registered-live-r1/recordings/conversation-stereo.wav) — stereo recording;
- [`sweep-r1/`](sweep-r1/) — WAV каждого кандидата и raw metrics.

## Проверки

```text
host full suite: 300 passed, 6 skipped
target full suite: 306 passed
registered FreeSWITCH full gate: pass
tts latency audit: pass, 4 complete ordered traces
runtime: CPython 3.14.7 free-threading, Py_GIL_DISABLED=1, gil_enabled=false
document registry audit: pass, 103/103
task backlog audit: pass, 26 unique rows
```

После финальной target regression production-like `sip-bot.service` запущен, прогрел все providers за `28.029 s`, зарегистрировал account
`1002` и объявил доступность очереди `7100`. Открытых blocker-ов Plan-018 нет.
