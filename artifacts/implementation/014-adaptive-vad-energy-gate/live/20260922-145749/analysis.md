# Live corrective run `20260922-145749`

Статус: `fail; corrective evidence`

## Вход

- call id: `call-in-0-7dbbb397dc594123a71558c6189e0cb1`;
- FreeSWITCH stereo recording: `conversation-stereo.wav`;
- SHA-256 recording: `d3fdfa6d8d4ac16e0e486f9a13ad98ca3445f0bd42e0c2fa3364dcfa299648a0`;
- формат: stereo PCM S16LE, 8 kHz, `65.1 s`;
- caller transcript diagnostic: `Почему небо голубое? Нет. А какого цвета Марс? А что такое рассеяние реле? Ау! Раз, раз, раз.`;
- bot transcript diagnostic: greeting, первый science answer, unknown-answer/transfer offer, Mars answer и оборванный хвост.

## VAD evidence

Configured WebRTC mode 2 + energy gate:

- frames: `3255`;
- raw WebRTC speech: `1275`;
- accepted after energy gate: `517`;
- rejected low-energy: `758`;
- final noise floor: `-81.487 dBFS`;
- final threshold: `-42.0 dBFS`;
- smoothed accepted speech level: `-20.821 dBFS`;
- replay authoritative turns: `7`.

Длинные accepted ranges совпадают с фактическими пользовательскими репликами. Короткие участки `20–40 ms` не прошли
`min_speech_ms` и не стали authoritative turns. Следовательно, обнаруженное завершение call-loop нельзя объяснить одним
ложным VAD barge-in.

## Обнаруженный boundary defect

В `14:58:35 UTC` call-loop завершился исключением:

```text
TranscriptContractError: endpoint belongs to another transcript scope
```

При отстающем ASR несколько реальных hard endpoints успели возникнуть до обработки worker results. Старый
`SpeechIngress` имел единственный `_pending_endpoint`, а `AsrAudioChunk`/`AsrHypothesis` не несли `turn_id`.
Следующий endpoint перезаписывал предыдущий; дополнительно assembler следующего хода создавался арифметически как
`previous + 1`, хотя TurnDetector корректно пропускает номера коротких неqualified bursts. В этом звонке authoritative
turn ids имели пропуски (`1, 2, 3, 4, 7, 8, 10`), поэтому предположение о последовательной нумерации было неверным.

## Corrective decision

- `TurnDetector` остаётся единственным владельцем `turn_id`;
- ASR accumulator открывается только после `SPEECH_STARTED`; pre-roll кадров сохраняется до `min_speech_ms`, а
  неqualified burst отбрасывается;
- фактический `turn_id` переносится в `AsrAudioChunk` и `AsrHypothesis`;
- `SpeechIngress` хранит assembler и pending endpoint по `turn_id`, не вычисляет следующий id самостоятельно;
- новый компонент, IPC или delivery owner не вводится.

Повторный live run обязателен; этот artifact не является closeout.
