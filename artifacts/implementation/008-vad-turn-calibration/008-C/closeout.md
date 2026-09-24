# Map-008-C execution closeout

Статус: `complete`  
Дата: `2026-09-13`  
Evidence: `i1-live-20260913-r5/live-i1-gate.json` и
`j4-full-live-20260913-r1/j4-full-live.json`

## Source и configuration audit

Проверено, что `tools/live_i1_gate.py` и `tools/j4_full_live_gate.py`
конструируют `VadProcessor(WebRtcVadCandidate(mode=constants.VAD_MODE))` и
`TurnDetector(EndpointingConfig(... constants.ENDPOINT_* ...))`.
Live path сохраняет `PcmFrame → VadDecision → TurnDetector`; амплитудный
VAD в live не используется. ASR остаётся downstream diagnostic.

В рамках clean-start harness исправлены два test-stand дефекта: I1 теперь
создаёт peer из принятого `001-S` template и изолирует его в конкретном
output root; fixture копируется в короткий `/tmp`-путь до старта Baresip.

## Regression

- host: `163 passed, 5 skipped`;
- target free-threaded: `166 passed, 2 skipped`;
- targeted calibration tests: `8 passed`.

## I1

Команда использовала C4 combined free-threaded runtime с C2 library path и
target package path:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot && /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/live_i1_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-C/i1-live-20260913-r5 --timeout-s 240'
```

I1: `pass`; WebRTC mode 2; `PCMU/8000/mono/ptime=20 ms`; `367` ingress
frames, `734` fan-out frames, `3` ASR chunks, `1` final user turn,
`0` drops/underruns/errors; RAG, LLM, TTS, FSM и итоговый report прошли.
Hard endpoint составил `539 ms` по фактическому 20-ms clock.

## J4

Команда:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot && /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/j4_full_live_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-C/j4-full-live-20260913-r1 --timeout-s 240 --post-report-grace-s 3'
```

J4: `pass`; `5` final turns, `4036` wiring ingress frames, `8072` fan-out
frames, `0` underruns/drops/errors. Проверены follow-up, barge-in,
unknown-answer/offer-transfer, transfer к fake operator и report. Все пять
hard endpoints — `520/522 ms`, WebRTC mode 2, negotiated PCMU profile.

## Corrective passes и ограничения

Ранние I1 попытки зафиксировали, но не скрыли: отсутствующий NumPy в
минимальном target executable, отсутствие CTranslate2 shared-library path,
отсутствие pjsua2 в isolated `-I` запуске, затем отсутствие peer account и
межзапусковое столкновение `peer-5080`. Это были setup/harness проблемы;
после применения штатного combined runtime, `LD_LIBRARY_PATH`/`PYTHONPATH`
и clean-start isolation I1 и J4 прошли.

ASR trace в J4 использован только downstream diagnostic; карта не заявляет
noise/recall/MOS или production generalization. Запись разговора остаётся
ответственностью Baresip test stand, не runtime.
