# 002-D speech ingress — execution evidence

Дата исполнения: `2026-09-03`  
План: [`docs/plans/plan-002-D-speech-ingress.md`](../../../../docs/plans/plan-002-D-speech-ingress.md)  
Статус реализации: `complete`  
Heavy GPU inference: `не запускался`

Срез реализован в разрешённых областях: `src/sip_bot/speech/`, speech unit/contract tests и этот evidence root.
Общие документы, Map-002-I, родительская карта, registry и backlog после получения дополнительного ограничения не
изменялись.

## Результат

- WebRTC VAD boundary реализован с lazy import и deterministic backend injection для тестов.
- Turn Detector реализован как отдельный stateful owner: `speech_started`, `pause_candidate`, `soft_endpoint`,
  `speech_resumed`, authoritative `hard_endpoint`.
- Soft/hard policy проверена на `300 ms`/`500 ms`; resume до hard endpoint отменяет speculative endpoint.
- ASR adapter предоставляет lifecycle-safe streaming boundary для принятого C2 faster-whisper/CTranslate2 baseline.
  Backend и model import lazy; тесты используют deterministic backend без GPU.
- Transcript Assembler заменяет revision целиком, принимает stable prefix только из явного backend metadata, отбрасывает stale revision и выдаёт
  authoritative `FinalUserTurn` только после hard endpoint.
- Cancellation закрывает активную ASR operation; поздние результаты старой operation/generation не выдаются.
- Все значения speech boundary несут `call_id`, `channel_id` и `generation`.

Входная contract revision: `Map-002-I rev4`, propagated `PcmFrame` от `002-B` и bounded `AsrAudioChunk` от `002-C`.

Corrective evidence `transcript-stability-corrective-20260904.md` фиксирует устранение найденной в live r19 ошибки:
случайный общий префикс соседних ASR-гипотез больше не фиксируется как stable.
Фактические output-типы этого среза — `VadDecision`, `EndpointEvent`, `AsrHypothesis`, `TranscriptUpdate` и
`FinalUserTurn`; до checkpoints `I1–I2` они являются локальными candidate outputs, а не authoritative контрактами
для `002-E`/`002-F`.

## Acceptance

| Slice | Result | Evidence |
|---|---|---|
| D1 | `pass` | `contract-manifest.json`, `tests/contract/test_speech_contracts.py` |
| D2 | `pass` для deterministic WebRTC VAD candidate contract; native package не импортировался | `vad-candidate.json`, `target-runtime-import.stdout.log` |
| D3 | `pass` | `endpointing.json` |
| D4 | `pass` | `transcript-revisions.json`, `cancellation-stale.json` |
| D5 | `pass` на локальном speech boundary; downstream files не изменялись | `contract-manifest.json` |

## Test summary

- Speech-specific host: `11 passed in 0.04s`.
- Speech-specific target: `11 passed in 0.42s` на CPython `3.14.7` free-threaded.
- Target compileall: exit `0`.
- Target no-GIL import: `Py_GIL_DISABLED=1`, GIL `false` до и после импорта `sip_bot.speech`.
- Target controlled concurrency: 4 независимых assembler operations, `Py_GIL_DISABLED=1`, GIL `false`.
- Full host regression: `54 passed, 3 failed`; failures pre-existing в `DialogueFSM`, перечислены в
  `pre-existing-host-regression.md`.

## Next step

Передать фактические speech contracts главному исполнителю для последовательного обновления Map-I и downstream
child plans. Для этого нужны checkpoints `I1` (сверка фактических полей) и `I2` (consumer fixtures/contract tests для
`002-E` и `002-F`). Эта синхронизация намеренно не выполнена здесь из-за дополнительного запрета на изменение общих
файлов.
