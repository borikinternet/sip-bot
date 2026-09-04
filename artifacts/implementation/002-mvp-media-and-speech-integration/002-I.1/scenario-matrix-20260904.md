# 002-I.1 / J4 — scenario matrix checkpoint

Дата checkpoint: `2026-09-04`

Этот файл фиксирует границу доказательств и итоговый clean-start acceptance gate. Исторические component/protocol
проверки сохранены; единый обязательный live-сценарий закрыт прогоном `002-J/j4-full-live-20260904-r20`.

| Сценарий | Текущая проверка | Результат | Evidence/команда |
|---|---|---|---|
| SIP/RTP → ASR → source-aware RAG/LLM → TTS → SIP/RTP | Fresh live Baresip call с PCMU/8000/mono и pre-call warmup | `pass` | `live-gate-20260903-r4/live-i1-gate.json`; полный ASR-текст, source IDs, `report.md`, `wiring errors=0` |
| Follow-up и контекст предыдущего хода | Target no-GIL integration test | `pass` | `test_pipeline_carries_previous_turn_context_into_the_next_prompt`; часть прогона `111 passed, 2 skipped` |
| Barge-in и suppression stale decision/audio | Target no-GIL integration test + SIP/playback subset | `pass` | `test_pipeline_cancels_inference_on_barge_in_without_stale_decision`, `test_barge_in.py`; subset `4 passed` |
| Unknown-answer → offer transfer → подтверждение → report | Target no-GIL integration test с fake operator | `pass` | `test_pipeline_runs_unknown_answer_confirmation_transfer_and_report` |
| Terminal protocol event while ASR is blocked | Target no-GIL runtime-wiring test | `pass` | `test_protocol_terminal_event_does_not_wait_for_asr_worker` |
| OPTIONS local reply | Target SIP/media integration test | `pass` | `test_local_call_lifecycle_and_options_reply` |
| Remote BYE / media teardown | Target SIP/media integration test | `pass` | `test_remote_bye_closes_media_without_dispatcher_wait` |
| Весь target integration subset | Target no-GIL integration suite | `pass` | `tests/integration`: `22 passed in 7.78s` |
| J4 clean-start component/composition lanes | Свежий запуск без предварительного call/evidence state | `pass` | `002-J/j4-clean-start-20260904-r4/j4-evidence.json`; target regression `exit_code=0`, real answer `exit_code=0`, real media/transfer `exit_code=0` |
| Единый clean-start live call, одновременно покрывающий follow-up, interruption, barge-in, unknown-answer/transfer и report | `pass`: 6/6 scenario checks, `errors=[]` | `pass` | `002-J/j4-full-live-20260904-r20/j4-full-live.json`; `B-002-I-007`, `B-002-J-004`, `B-002-MAP-006` resolved |

## Выполненные команды

```text
wsl -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q \
  /mnt/c/devel/sip-bot/tests/unit /mnt/c/devel/sip-bot/tests/contract \
  /mnt/c/devel/sip-bot/tests/integration/test_application_composition.py \
  /mnt/c/devel/sip-bot/tests/integration/test_runtime_wiring.py \
  /mnt/c/devel/sip-bot/tests/integration/test_conversation_pipeline.py
# 111 passed, 2 skipped in 2.40s

wsl -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q \
  /mnt/c/devel/sip-bot/tests/integration/test_sip_media.py \
  /mnt/c/devel/sip-bot/tests/integration/test_barge_in.py
# 4 passed in 7.39s
```

Target runtime: CPython `3.14.7t`, `gil_enabled=false`. Unit/integration evidence does not create an audio recording;
the only required call artifact is the text report.

## Clean-start J4 evidence

`j4-clean-start-20260904-r4` завершён со статусом `pass`. Target-регрессия: `9.134 s`; реальная answer-композиция:
`33.230 s`, RAG context sufficient, source IDs присутствуют, итоговый ответ и `report.md` сформированы, TTS WAV
сохранён как inspection artifact; реальная media/transfer-композиция: `26.015 s`, получен финальный ASR turn,
подтверждён transfer на локального оператора, сформированы `report.md` и TTS WAV, ошибок pipeline нет.

Это подтверждает отдельные component/composition lanes. Единый live SIP/RTP gate с полной матрицей дополнительно
пройден в r20; полные артефакты находятся в
`artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-clean-start-20260904-r4/`.

## Единый live gate r20

`002-J/j4-full-live-20260904-r20/j4-full-live.json` завершён с `status=pass` и exit code `0`. В одном чистом
запуске подтверждены SIP/RTP PCMU, source-aware RAG и контекстный follow-up, реальный `barge_in` с отменой playback,
unknown-answer с предложением оператора, положительное подтверждение `Да.` с typed transfer на локальный Baresip
оператор и итоговый `report.md`. Target runtime — CPython `3.14.7t`, `gil_enabled=false`; `wiring.errors=0`,
`stale_hypotheses=0`, `asr_chunks_dropped=0`, `callback_errors=0`.

При подготовке r20 устранены подтверждённые дефекты границ: ASR получает только speech-marked PCM, hard endpoint
доставляется как typed commit marker, допустимая русская ревизия `ё/е` не ломает стабильный префикс, минимальная
лексическая опора защищает unknown-answer от ложного semantic hit, а подтверждение transfer не теряет FSM state на
`speech_started`. Предел structured generation поднят с 96 до 192 токенов, поскольку предыдущий live ответ был
обрезан посреди JSON.
