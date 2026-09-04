# 002-H main-only gate output

Дата: `2026-09-03`

## H-GPU-001

Запущен главный executor на target runtime с C4 manifest, но с отдельным H evidence root:

```text
wsl -d Ubuntu-24.04 -- /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -u /mnt/c/devel/sip-bot/tools/feasibility/tts_primary_probe.py --manifest /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-H/c4-manifest.json --stage operation --allow-tts-operation
```

Результат: exit `0`, XTTS-v2 `v2.0.3` revision `6b8036b35d787cf43d18d640587956b9db8fd1b8`, CPython `3.14.7t`,
GIL `false` до импорта и после model load/first PCM/completion, model load `8.79122045 s`, first PCM через
`821.817432 ms` после финальной фразы, completion через `1301.724865 ms`, 4 PCM chunks. H-owned
[`operation.json`](operation.json) и [`tts-sample.wav`](tts-sample.wav) содержат полные metadata и sample.

## H-GPU-001 cancellation

```text
wsl -d Ubuntu-24.04 -- /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -u /mnt/c/devel/sip-bot/tools/feasibility/tts_primary_probe.py --manifest /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-H/c4-manifest.json --stage cancellation --allow-tts-operation
```

Результат: exit `0`, first PCM получен, generator закрыт после первого chunk, post-close items `0`, stale result
не принят, GIL `false`. Native cancellation token отсутствует и не заявляется.

## H-RTP-001

Главный executor выполнил связный inline smoke на target no-GIL runtime:

```text
SipMediaAdapter/PJSUA2 + PcmAudioBridge -> PlaybackChannel -> PcmFrame -> PJMEDIA -> PCMU/RTP -> Baresip 001-S
```

Результат: exit `0`, фактический профиль из PJMEDIA — `PCMU/8000/1`, payload `0`, `ptime=20 ms`, `160 samples`,
`320 PCM bytes`; в RTP peer observed `59` transmit / `58` receive packets, `0` errors, `0` lost. Playback sent
`35` frames, после barge-in channel закрыт, stale push rejected, post-cancel frames from PlaybackChannel `0`.
Inbound media path продолжил работу: `50` ingress frames / `16000` bytes. Полная структурированная запись —
[`rtp-barge-in.json`](rtp-barge-in.json).

В данном approved `001-S` fixture фактически согласован `ptime=20 ms`; H использовал значение, полученное из
per-call `StreamInfo`/PJMEDIA, а не константу. Код boundary сохраняет произвольный negotiated `ptime` и не меняет
этот evidence под 20 ms.

## Ограничение evidence

Инлайн-runner использовал принятый H WAV sample и детерминированное 24→8 kHz mono преобразование для подачи PCM в
приложение; PCMU/G.711 и RTP packetization выполнялись PJMEDIA/Baresip. Это доказывает H playback/media boundary и
не является заменой будущему полному J scenario harness.
