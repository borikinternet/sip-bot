# 007-C — команды и результаты

Дата исполнения: `2026-09-13`  
Target environment: Ubuntu 24.04/WSL2, free-threaded CPython `3.14.7t`, локальный Baresip peer и fake operator.

## I1: короткий live gate

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/live_i1_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/007-webrtc-vad/007-C/r5/i1-live-20260913-r1 --timeout 240'
```

Exit code: `0`; manifest: [`live-i1-gate.json`](r5/i1-live-20260913-r1/live-i1-gate.json), `status=pass`.
Peer/RTP/PCMU established, `WebRtcVadCandidate`, mode `2`, `1869` VAD decisions, `3738` fan-out frames, `0` ASR
drops and `0` wiring errors. This short run has `16` egress underruns and is not the evidence for full playback
integrity; the full J4 run below has `0`.

## J4: полный live gate

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/j4_full_live_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/007-webrtc-vad/007-C/j4-full-live-20260913-r3 --timeout-s 240 --post-report-grace-s 3'
```

Exit code: `0`; manifest: [`j4-full-live.json`](j4-full-live-20260913-r3/j4-full-live.json), `status=pass`.
Все 6 обязательных scenario checks истинны: follow-up, barge-in, unknown-answer/offer, transfer, operator result и
report. Зафиксированы `3910` ingress frames, `7820` fan-out frames, `20` ASR chunks, `0` ASR drops, `7` final turns,
`0` errors, `1652` emitted TTS frames и `0` egress underruns.

## Corrective rerun

J4 `r1` первоначально получил два поздних `ConversationPipeline rejected FinalUserTurn` после terminal. Это исправлено
stale guard-ом в существующем `runtime_wiring` owner; J4 `r3` — повтор после исправления. Красный результат не был
заменён старым evidence или deterministic fake.

## Target regression

Перед финальным closeout выполнены:

- host targeted/contract suite из `007-B`: `136 passed, 2 skipped`, exit code `0`;
- target free-threaded application/speech suite: `67 passed, 2 skipped`, exit code `0`;
- corrective host tests: `25 passed, 2 skipped`, exit code `0`;
- corrective target free-threaded tests: `67 passed, 2 skipped`, exit code `0`;
- `py_compile` для live tools/config/runtime files: exit code `0`.

Доказательство no-GIL native binding находится в [`007-A c4 manifest`](../007-A/c4-runtime/webrtc-vad-runtime.json).
