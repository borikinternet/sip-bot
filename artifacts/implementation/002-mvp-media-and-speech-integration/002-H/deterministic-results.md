# 002-H deterministic implementation results

## Реализовано

- `ApprovedTextChunk` и `TtsPcmChunk` задают typed direct data-plane boundary;
- `TtsCancelRequest` является алиасом авторитетного `CancelRequest` из G и не создаёт второй cancel-контракт;
- `TtsStatus`/`TtsStatusKind` задают lifecycle TTS;
- `XttsV2Adapter` не импортирует тяжёлый XTTS при импорте пакета, принимает инжектированный C4 engine и нормализует
  его PCM16 mono к sample rate активного `NegotiatedMediaProfile`;
- `TtsOutputBuffer` принимает chunks произвольного размера, ограничивает storage, собирает полные media frames и
  дополняет успешный хвост нулевыми samples до точного `frame_bytes`;
- при cancel/close хвост и ожидающие frames не доставляются, late/stale generation chunks отбрасываются;
- `MediaPacer` использует timestamp и `frame_time_usec` из per-call profile, поэтому 20 ms не зашиты в implementation;
- `PlaybackChannel` доставляет готовые PCM frames через прямой callback, без Event Bus, и выполняет idempotent
  close/cancel/barge-in с producer cancellation и event trace.

## Покрытые поведения

Тестами проверены arbitrary chunk sizes `100 + 500 + 20`, exact 20 ms framing, 30 ms pacing, successful tail flush,
cancel tail drop, bounded overflow, stale generation, sequence/lifecycle validation, 24 kHz→8 kHz adapter normalization,
approved text-only input, cancellation before generation, close/re-close, direct egress and barge-in during active
playback. Integration test намеренно остаётся deterministic boundary test и не выдаётся за RTP evidence.

## Changed files

```text
src/sip_bot/tts/__init__.py
src/sip_bot/tts/contracts.py
src/sip_bot/tts/adapter.py
src/sip_bot/tts/output_buffer.py
src/sip_bot/tts/media_pacer.py
src/sip_bot/playback/__init__.py
src/sip_bot/playback/contracts.py
src/sip_bot/playback/channel.py
tests/unit/test_tts_output.py
tests/contract/test_playback_contract.py
tests/integration/test_barge_in.py
```

Изменения за пределами write-set не выполнялись.
