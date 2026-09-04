# J4 full live clean-start gate — r20

Дата прогона: `2026-09-04`  
Статус: `pass`  
Evidence: [`j4-full-live.json`](j4-full-live.json)

## Команда

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/j4_full_live_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-full-live-20260904-r20 --timeout-s 240'
```

Exit code: `0`. Прогон выполнен главным executor в целевом CPython `3.14.7t`; `gil_enabled=false`.

## Что доказано одним вызовом

- Baresip установил SIP/RTP-вызов; negotiated media profile — PCMU, payload type 0, 8000 Hz, mono, `ptime=20 ms`.
- Пять пользовательских ходов прошли через live `PcmFrame → PcmFanOut → VAD/endpointing → ASR → FinalUserTurn → RAG/prompt/LLM → TTS/output/pacer/playback → SIP RTP`.
- Второй вопрос использовал контекст предыдущего хода; q3 вызвал `barge_in` и отменил предыдущий playback generation.
- Для вопроса вне curated KB модель сообщила об отсутствии подтверждённых данных и предложила оператора.
- «Да.» сохранило состояние подтверждения, вызвало `user_confirmed`, typed transfer и локальный операторский SIP `INVITE 100/200`.
- Финальный `report.md` создан; проектом аудиозапись разговора не создавалась.

Scenario checks: `6/6=true`; `wiring.errors=0`; `callback_errors=0`; `stale_hypotheses=0`; `asr_chunks_dropped=0`.

## Warmup и наблюдения

До допуска peer последовательно прогреты RAG embeddings/index, structured Ollama chat, faster-whisper с входом 8 kHz
и внутренним входом модели 16 kHz, XTTS и первый TTS PCM chunk. Warmup занял `20627.558 ms`; от admission вызова до
финального отчёта — `101087.898 ms` в полном сценарии, включая управляемые паузы fixture.

Полный прогон выполнялся после corrective pass для Transcript Assembler: без явно переданного backend-ом
`stable_prefix` сборщик больше не фиксирует общий префикс двух последовательных гипотез. Это предотвращает фиксацию
ошибочной ранней ASR-гипотезы; r19 сохранился как raw failure evidence.

В XTTS остаётся предупреждение о длине одного русского ответа относительно лимита tokenizer `182` символа; это не
нарушило acceptance и передано в следующую карту как quality/latency observation. Высокое число `egress_underruns`
(`4692`) остаётся наблюдаемым ограничением текущего paced-output стенда, не ошибкой callback или потерей RTP.
