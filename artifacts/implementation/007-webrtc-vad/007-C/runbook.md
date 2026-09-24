# WebRTC VAD — краткий runbook для мастер-класса

Этот runbook описывает воспроизводимый локальный demo-путь Map-007. Он не является production deployment guide.

## Предусловия

- Ubuntu 24.04/WSL2, свободное место не менее 20 GB;
- target/combined free-threaded CPython `3.14.7t`;
- patched `webrtcvad-wheels 2.0.14` из Map-007;
- локальные ASR/TTS/LLM/RAG зависимости и Ollama `0.33.1` с заранее прогретыми моделями;
- утверждённый Baresip peer из `001-S`; для transfer — локальный fake operator;
- GPU свободен до запуска warmup и live gate.

## Обязательный порядок

1. Проверить runtime/no-GIL manifest `007-A` и application tests `007-B`.
2. Запустить локальный Ollama и убедиться, что доступны `embeddinggemma` и выбранная LLM.
3. Выполнить pre-call warmup RAG → LLM → ASR → TTS; SIP-вызов не допускать до успешного warmup.
4. Выполнить I1 или J4 командой из [`commands.md`](commands.md), сохранив новый output root, а не перезаписывая
   исторические evidence.
5. В manifest проверить `WebRtcVadCandidate`, `mode=2`, negotiated `PCMU/8000/mono/ptime=20 ms`, VAD decisions,
   endpoint trace, ASR fan-out, `errors=0` и финальный report.
6. Для демонстрации полного сценария предъявить J4: follow-up, barge-in, unknown-answer offer, transfer к operator
   и итоговый report.

## Авторитетная команда J4

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/j4_full_live_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/007-webrtc-vad/007-C/j4-full-live-YYYYMMDD-rN --timeout-s 240 --post-report-grace-s 3'
```

Команда использует `PYTHONPATH` только для доступного target Python package set; это не меняет application boundary и
не включает GIL. Exact accepted result — [`j4-full-live-20260913-r3`](j4-full-live-20260913-r3/j4-full-live.json).

## Ограничения демонстрации

- `_AmplitudeVad` допустим только как deterministic test double;
- VAD mode `2` — зафиксированный baseline, изменение требует отдельного evidence;
- запись аудио делает Baresip/стенд, а не runtime бота;
- warmup до звонка обязателен из-за стоимости загрузки моделей и дискового I/O;
- показанный baseline не содержит полного noise/precision/recall или MOS исследования.
