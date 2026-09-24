# Map-007 / 007-C — closeout

Статус: `complete`  
Дата: `2026-09-13`  
Parent map: [`docs/plans/plan-007-webrtc-vad-migration.md`](../../../docs/plans/plan-007-webrtc-vad-migration.md)  
Plan: [`docs/plans/plan-007-C-webrtc-vad-live-gate-and-workshop-evidence.md`](../../../docs/plans/plan-007-C-webrtc-vad-live-gate-and-workshop-evidence.md)

## Итог

Фактический live/demo путь переведён с `_AmplitudeVad` на `WebRtcVadCandidate(mode=2)` на базе patched
`webrtcvad-wheels 2.0.14`. Путь остался прежним: `PcmFrame → VadProcessor → VadDecision → TurnDetector`; новый
audio delivery owner, event-bus audio path или межпроцессный audio IPC не добавлялись.

`007-C` принят только после исполнения `007-A` и `007-B`, corrective pass и проверки полного J4 gate. Child plan и
Map-007 закрыты бинарным статусом `complete`; частичный статус не использовался.

## Изменённые файлы

- `tools/live_i1_gate.py` — live I1 использует `WebRtcVadCandidate` и записывает VAD trace в manifest;
- `tools/j4_full_live_gate.py` — полный gate использует тот же candidate и trace;
- `src/sip_bot/runtime_wiring.py` — stale `FinalUserTurn` после terminal/closed generation отбрасывается до pipeline;
- `config/constants.py`, `src/sip_bot/config.py` — явный `VAD_MODE=2` в RuntimeConfig;
- `tests/unit/test_config.py`, `tests/unit/test_webrtc_vad_application_boundary.py`,
  `tests/integration/test_runtime_wiring.py` — проверяют конфигурацию, typed boundary и stale close path.

`_AmplitudeVad` сохранён только в deterministic tests/fixtures. Он не является live fallback и не используется
финальными I1/J4 gates.

## Финальные evidence

### 007-A handoff

- [`c4-runtime/webrtc-vad-runtime.json`](../007-A/c4-runtime/webrtc-vad-runtime.json) — `status=pass`;
- exact distribution: `webrtcvad-wheels 2.0.14`, MIT;
- target executable: `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python`;
- `cpython-314t-x86_64-linux-gnu`, `Py_GIL_DISABLED=1`, GIL remains disabled before import, after import,
  construction, operation and controlled concurrency;
- 12 valid combinations (`8/16/32/48 kHz × 10/20/30 ms`), 8 independent instances in concurrency,
  invalid frame/rate inputs rejected.

### I1

[`r5/i1-live-20260913-r1/live-i1-gate.json`](r5/i1-live-20260913-r1/live-i1-gate.json) имеет `status=pass`.
Зафиксировано:

- Baresip peer established, RTP ingress established, PCMU payload type `0`, `8000 Hz`, mono, negotiated `ptime=20 ms`;
- `WebRtcVadCandidate`, `mode=2`, `1869` decisions: `1832` speech и `37` silence;
- `1869` ingress frames, `3738` fan-out frames, `37` ASR chunks, `0` ASR drops, `0` wiring errors;
- soft/hard endpoint trace присутствует на `320/519 ms`; короткий I1 содержит `16` egress underruns и поэтому не
  используется как evidence отсутствия underrun в полном сценарии.

### J4 full live

[`j4-full-live-20260913-r3/j4-full-live.json`](j4-full-live-20260913-r3/j4-full-live.json) имеет `status=pass` и
`evidence_id=E-002-J4-FULL-LIVE-20260913T134124Z`.

| Проверка | Факт |
|---|---|
| Follow-up, barge-in, unknown answer/offer, transfer, operator result, report | 6/6 `true` |
| Runtime | CPython `3.14.7t`, `gil_enabled=false` |
| Media | PCMU, payload `0`, `8000 Hz`, mono, `ptime=20 ms`, `3911` ingress/egress frames |
| Fan-out/ASR | `7820` fan-out frames, `20` ASR chunks, `0` drops, `7` final turns |
| VAD | `WebRtcVadCandidate`, mode `2`, `3910` decisions, `567` speech / `3343` silence, `8000 Hz/20 ms` |
| Endpointing | `30` endpoint events, включая speech resume до hard endpoint и hard endpoints на `500–519 ms` |
| TTS/media integrity | `1652` emitted frames, `0` overflow/stale/closed/cancelled drops, `0` egress underruns |
| Errors/report | `0` runtime errors, итоговый `report.md` существует |

## Corrective pass и классификация результатов

Первый J4 `r1` выявил два поздних `ConversationPipeline rejected FinalUserTurn` после перехода в terminal. Это был
дефект stale-result guard в существующем runtime write-set, а не внешний блокер. Исправление проверяет terminal state и
валидность `SessionLease` до отправки final turn; после этого J4 `r3` прошёл без ошибок. Поздние результаты не меняют
состояние диалога и не запускают inference/TTS.

I1 `egress_underruns=16` классифицирован как свойство короткого I1 прогона с ограниченным TTS playback, а не как
WebRTC VAD failure: полный J4 на том же live path получил `0`. Вариативное число ASR final turns на fixture — quality
observation для дальнейшей настройки, не blocker Map-007.

Запись разговора не принадлежит runtime бота. В финальных J4 manifest указано `external_pbx=false`; Baresip peer и
operator используются как локальный тестовый стенд, а fixture WAV создаётся до допуска звонка и не является записью
разговора.

## Следующий шаг

Для мастер-класса использовать [`runbook.md`](runbook.md) и J4 evidence как baseline. При этом явно сообщать, что
Map-007 доказывает корректное подключение WebRTC VAD к MVP live path, но не заменяет отдельную noise/precision/recall
кампанию и не является утверждением production readiness.
