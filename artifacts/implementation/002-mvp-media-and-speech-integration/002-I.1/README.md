# 002-I.1 — execution evidence и closeout

Дата checkpoint: 2026-09-03

Статус: `complete`. Базовый target/live SIP→AI→SIP gate закрыт `live-gate-20260903-r4`; полная interruption,
multi-turn, barge-in, unknown-answer/transfer и report matrix закрыта единым clean-start gate
`002-J/j4-full-live-20260904-r20`.

В checkpoint входят:

- `deterministic-results.md` — результаты host и target no-GIL deterministic gates;
- `real-ai-warm/real-media-composition.json` — реальный ASR→RAG→Ollama→XTTS composition probe без SIP/RTP
  wiring, выполненный главным executor после прогрева Ollama;
- `real-ai-warm/tts-media-composition-sample.wav` — результат TTS, предназначенный для ручного прослушивания;
- `real-ai-warm/reports/real-media-composition-call/report.md` — единственный обязательный отчёт этого probe.
- `real-ai-retry/real-media-composition.json` — повторный реальный composition probe после освобождения GPU;
- `real-ai-retry/tts-media-composition-sample.wav` — звуковой результат повторного прогона;
- `real-ai-retry/reports/real-media-composition-call/report.md` — отчёт повторного прогона.
- `live-gate-20260903-r4/live-i1-gate.json` — успешный fresh Baresip SIP/RTP gate после pre-call warmup;
- `live-gate-20260903-r4/baresip-peer.log` — raw peer log;
- `live-gate-20260903-r4/context/i1-8-live-call/conversation.jsonl` — текстовый context trace, без аудиозаписи;
- `live-gate-20260903-r4/reports/i1-8-live-call/report.md` — итоговый report live-вызова.
- `scenario-matrix-20260904.md` — текущая граница deterministic/protocol/live evidence и открытый unified-scenario gate.

- `../002-J/j4-full-live-20260904-r20/j4-full-live.json` — главный executor full live acceptance с `status=pass`.
- `../002-J/j4-full-live-20260904-r20/README.md` — команда, результаты, runtime и наблюдаемые ограничения прогона.

Запись `real-media-composition.json` с `status=pass` означает успешный composition probe с реальными AI owners,
а не самостоятельное доказательство live SIP/RTP. Live-доказательство находится в указанном full gate r20.

## Повторный реальный AI-прогон

После сообщения о возможной конкурирующей GPU-нагрузке probe был запущен повторно в том же target no-GIL
окружении. Результат: `status=pass`, `pipeline_errors=[]`, `elapsed_from_media_start_ms=72563.658`.
В прогоне реально участвовали faster-whisper-large-v3, embeddinggemma, Ollama Qwen3.5-9B и XTTS-v2;
получены ASR hypotheses, source-aware RAG result, ответ LLM, PCM16/8 kHz/mono TTS и проверка ветки
подтверждённого перевода на локального оператора. GPU-нагрузка не привела к отказу прогона.

Этот результат также не закрывает `I1-8`: входом оставался offline PCM fixture, а свежий полный SIP/RTP
путь через `SipMediaAdapter` ещё не доказан.

## Fresh live gate после исправления cold start и ASR boundary

`live-gate-20260903-r4/live-i1-gate.json` имеет `status=pass`. До запуска Baresip peer runtime последовательно
выполнил RAG embedding index, structured Ollama chat, ASR warmup на входе 8 kHz/модельном входе 16 kHz, инициализацию
XTTS, первый TTS stream chunk и подготовку offline fixture. Суммарный warmup занял `40373.688 ms`; этот расход больше
не входит в время живого разговора. От момента admission вызова до финализации report прошло `11432.893 ms`.

Вызов установил SIP/RTP с PCMU/8000/mono, получил RTP в обе стороны, передал live media через `CallRuntimeWiring`,
сформировал полный ASR-текст `Почему небо днём кажется голубым?`, source-aware RAG-контекст, ответ Ollama и paced TTS
egress. Ошибок wiring/pipeline нет; target runtime — CPython 3.14.7t, `gil_enabled=false`.

В corrective pass faster-whisper boundary стала явной: negotiated 8 kHz PCM ресемплируется в 16 kHz, а каждый partial
строится на растущем префиксе текущей реплики. Поэтому в live context сохраняется полный вопрос, а не только последний
секундный chunk. Это исправление дополнительно покрыто unit/target contract tests.

После этого corrective pass целевой no-GIL runtime повторно прошёл integration subset: `111 passed, 2 skipped` для
unit/contract/application-composition/runtime-wiring/conversation-pipeline, а отдельный SIP/media protocol subset
`test_sip_media.py` + `test_barge_in.py` прошёл `4 passed` за `7.39s`; весь `tests/integration` прошёл `22 passed`
за `7.78s`. Эти результаты закрывают заявленные
deterministic/protocol checks, но не подменяют оставшуюся live scenario matrix.

## Full clean-start acceptance gate

`002-J/j4-full-live-20260904-r20/j4-full-live.json` завершён с `status=pass`, exit code `0`, шестью из шести
обязательными scenario checks и пустым `errors`. Один live-вызов доказал SIP/RTP PCMU/8000/mono, follow-up с
контекстом, real barge-in с отменой playback, source-aware RAG, unknown-answer с предложением transfer, подтверждение
`Да.` с переходом FSM в `transferring`, SIP-backed typed transfer на локального fake operator и финальный
`report.md`. Прогон выполнен на CPython `3.14.7t`, `gil_enabled=false`; warmup всех AI owners завершён до call
admission.

Корректирующие boundary-изменения, вошедшие в acceptance: ASR принимает только speech-marked frames и hard endpoint
commit marker; допустимое `ё/е` различие не считается противоречием стабильному префиксу; lexical support guard
защищает negative RAG case; confirmation speech не сбрасывает FSM из `awaiting_transfer_confirmation`; structured
LLM generation limit увеличен до 192 токенов после зафиксированного обрезания JSON на 96.
