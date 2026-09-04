# 005-E closeout

Статус: `complete`  
Дата: `2026-09-04`  
Исполнитель: main executor

## Результат

Исправлена потеря TTS PCM при быстром producer-е. `TtsOutputBuffer` теперь хранит сегменты в едином динамическом
bounded accumulation buffer без отдельного лимита числа pending frames. `MediaPacer` выдаёт negotiated frames по
одному и использует ограниченный lookahead, чтобы заранее заполнить прямой media egress buffer. High-water остаётся
защитным пределом; при его достижении producer получает явную `TtsOutputError`, а не silent drop.

Новые typed boundaries, межкомпонентные сигналы, delivery owner, Dispatcher/Event Bus payload и Map-I revision не
добавлялись. Старый generation при barge-in по-прежнему отменяется явно, его остаток отражён в
`dropped_tail_bytes`.

## Evidence

- E1 baseline и причина дефекта: текущий fixed pending-frame cap позволял потерять TTS chunks до PJMEDIA;
- E2 focused tests: `15 passed`;
- E3 host regression: `151 passed, 5 skipped`; target regression: `154 passed, 2 skipped`;
- E4 target live gate: [`target-20260904-r10`](target-20260904-r10/) — SIP/RTP PCMU, RAG, multi-turn, barge-in,
  unknown-answer/transfer, fake operator, report и stereo recording;
- `tts_output.dropped_overflow_bytes=0`, `buffered_bytes=0`, `pending_frames=0`;
- media `egress_underruns=0`, `egress_dropped_overflow=0`, `callback_errors=0`;
- full bot-to-user audio audit: [`audio-audit.md`](audio-audit.md), запись для прослушивания:
  [`conversation-stereo.wav`](target-20260904-r10/recordings/conversation-stereo.wav).

## Blockers

Открытых category-4 blockers нет. `dropped_tail_bytes` относится к явно отменённому старому поколению при barge-in и
не является потерей активного ответа. `egress_underruns=0` подтверждает, что после lookahead чистых underruns нет.

## Следующий шаг

Map-005 map-level gate закрыт; r10 передан в downstream Map-006, чей технический document/report refresh также
завершён. Исторические r7 artifacts не изменяются. Оставшиеся действия — содержательная редактура, лицензирование и
публикация материалов за пределами технического closeout.
