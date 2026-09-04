# Plan-002-H execution closeout

Дата: `2026-09-03`

Статус: `complete` — deterministic implementation, XTTS/GPU, cancellation и SIP/RTP barge-in gates завершены
`2026-09-03`.

## APG acceptance

- owner review и Map-I revision 8 приняты до closeout;
- write-set соблюдён: изменены только `src/sip_bot/tts/`, `src/sip_bot/playback/`, H tests и этот evidence root;
- typed boundaries, owner separation, direct data plane, bounded storage, cancellation, stale policy и per-call ptime
  явно реализованы и покрыты тестами;
- целевой CPython 3.14.7t import/no-GIL probe прошёл: `_is_gil_enabled()` был `False` до и после импорта TTS/playback;
- regression: `87 passed`; compileall: exit `0`.
- H-GPU-001: реальный XTTS-v2 operation прошёл на C4 patched no-GIL runtime; первый PCM и completion latency
  сохранены в [`operation.json`](operation.json), аудиорезультат — [`tts-sample.wav`](tts-sample.wav).
- H-GPU-001 cancellation: generator close после первого PCM chunk прошёл, stale output не принят; независимый
  native cancellation token отсутствует и не заявляется.
- H-RTP-001: реальный `PlaybackChannel → PcmAudioBridge/PJMEDIA → PCMU/RTP → 001-S` прошёл; per-call profile,
  RTP counters, inbound continuation, barge-in и stale suppression сохранены в [`rtp-barge-in.json`](rtp-barge-in.json).

## Открытые блокеры и deferred evidence

| ID | Причина | Требуемое доказательство | Владелец | Promotion condition | Статус |
|---|---|---|---|---|---|
| `B-002-H-003` | Реальный playback/barge-in boundary ещё не проверен | C4 XTTS operation + `001-S` RTP/PCMU playback и barge-in | main executor | оба main-only gates зелёные | `resolved — H-GPU-001 и H-RTP-001 pass` |
| `DEFER-002-H-GPU-001` | Heavy XTTS запуск запрещён для deterministic executor | first PCM, complete, no-GIL after CUDA/model load, candidate cancel | main executor | H-GPU-001 evidence | `promoted — operation.json/cancellation.json` |
| `DEFER-002-H-RTP-001` | RTP smoke требует общего SIP/RTP стенда | SDP-derived profile, PCMU counters, stale audio/barge-in trace | main executor | H-RTP-001 evidence | `promoted — rtp-barge-in.json` |

Никаких fallback, намеренных упрощений или изменений C4 source/patches не внесено. H не закрывает полный J
scenario harness: его ответственность начинается после этого upstream closeout.

Следующий шаг: обновить Map-I propagation checkpoint H, parent map, registry и открыть approved plan J.
