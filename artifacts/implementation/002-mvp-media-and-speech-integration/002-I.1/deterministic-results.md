# 002-I.1 — deterministic checkpoint

## Исполнение

| Gate | Команда/окружение | Результат |
|---|---|---|
| Host regression | `python -m pytest -q` | `113 passed, 3 skipped in 0.60s` |
| Host syntax | `python -m compileall -q src/sip_bot tests` | pass |
| Document registry | `python tools/check_document_registry.py` | `actual=40 registry_rows=40 registry_unique=40 missing=0 extra=0 duplicate_paths=0`; PASS |
| Task backlog | `python tools/check_task_backlog.py` | `rows=7 unique_ids=7`; PASS |
| Diff hygiene | `git diff --check` | pass |
| Target runtime wiring | CPython `3.14.7t`, Ubuntu 24.04/WSL2, `tests/integration/test_runtime_wiring.py` + `test_sip_media.py` | `7 passed in 8.02s` |
| Target imports | CPython `3.14.7t`, combined XTTS/C2 site-packages | `pjsua2`, `faster_whisper`, `torch`, `TTS` imported; CUDA available; `_is_gil_enabled() == False` |

## Материализованные границы

Детерминированный runtime test подтверждает следующие вызовы уже существующих owners:

```text
SipMediaAdapter.next_ingress_frame()
  → PcmFanOut.publish(PcmFrame)
  → SpeechIngress.process_frame(PcmFrame)
  → AsrChunker.push(PcmFrame)
  → bounded queue.Queue → StreamingAsrAdapter.stream(...)
  → SpeechIngress.accept_hypothesis(AsrHypothesis)
  → ConversationPipeline.submit_final_turn(FinalUserTurn)
  → LocalKnowledgeIndex / SkillPromptManager / LlmFacade
  → TtsOutputBuffer.push(TtsPcmChunk)
  → MediaPacer / PlaybackChannel.pump()
  → SipMediaAdapter.enqueue_egress_frame(PcmFrame)
```

`test_protocol_terminal_event_does_not_wait_for_asr_worker` отдельно удерживает ASR worker в backend call и
показывает, что `REMOTE_HANGUP`/`BYE` обрабатывается основным asyncio loop с bounded timeout; stale ASR result после
закрытия не становится новым ходом.

## Реальный AI composition probe

После первого прогона с ошибкой `LLM operation failed: timeout` был установлен конкретный operational cause:
первый Ollama-запрос закрывался на 30-секундном фасадном лимите во время cold load Qwen3.5-9B. После отдельного
прогрева модели запросом с лимитом 180 секунд повторный probe завершился `status=pass`:

- target runtime: `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`;
- Python: `3.14.7 free-threading build`;
- `gil_enabled=false`;
- ASR: `faster-whisper-large-v3`, реальные partial hypotheses и hard endpoint;
- RAG: реальный `embeddinggemma`, локальный natural-science corpus;
- LLM: реальный Ollama `c3-qwen35-9b-q4km:latest`;
- TTS: реальный XTTS-v2, 115200 bytes PCM16/8 kHz/mono;
- `pipeline_errors=[]`;
- итоговый report и TTS WAV сохранены в `real-ai-warm/`.

Офлайн fixture распозналась как `Продолжение следует...`, поэтому RAG корректно признал контекст недостаточным,
LLM предложила оператора, а probe проверил ветку подтверждения transfer. Это не ошибка wiring; качество fixture
для требуемого natural-science вопроса следует проверять отдельным ASR/data-quality gate.

Повторный запуск после освобождения GPU также завершился `status=pass` без ошибок pipeline:

- output: `002-I.1/real-ai-retry/real-media-composition.json`;
- target runtime: CPython `3.14.7t`, `gil_enabled=false`;
- ASR/LLM/RAG/TTS: реальные модели; TTS — `108544` bytes PCM16/8 kHz/mono;
- `elapsed_from_media_start_ms=72563.658`;
- SHA-256 повторного TTS WAV: `08c067c2bd9211441c633fa7401514e298ca528ed04c9929227d1c59e420904b`.

Повтор подтверждает, что предыдущий timeout был operational cold-load эффектом, а не воспроизводимым
дефектом композиции. Как и первый успешный probe, он не заменяет свежий live SIP/RTP gate.

## Оставшийся gate

На момент подготовки этого deterministic checkpoint `I1-8` ещё не был закрыт: fresh Baresip call с фактическим
`SipMediaAdapter` не прошёл полный `SIP/RTP → ASR → RAG/LLM → TTS → SIP/RTP` в едином запуске. Это историческое
состояние superseded fresh live evidence `live-gate-20260903-r4`, которое доказало базовый path и перевело
`B-002-I-006`/`B-002-J-006` в `resolved`; сам plan остаётся `in_progress` из-за отдельной scenario matrix.

## Текущий superseding live checkpoint

`live-gate-20260903-r4/live-i1-gate.json` имеет `status=pass`: pre-call warmup завершён до admission peer, затем
реальный SIP/RTP вызов прошёл через negotiated PCMU/8000 media, runtime wiring, ASR, source-aware RAG/LLM, paced
TTS и обратный RTP. Ошибок pipeline/wiring нет; полный вопрос сохранён в context trace, создан обязательный
`report.md`. Оставшийся acceptance — protocol interruption, barge-in, follow-up, transfer/unknown-answer и полный
J4/J5 closeout.
