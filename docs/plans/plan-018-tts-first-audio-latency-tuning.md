# Corrective Plan-018: настройка задержки первого аудио XTTS

Уровень: `child plan / corrective vertical slice`  
Статус: `complete`  
Owner review: `accepted by explicit owner instruction, 2026-09-23`

## 1. Цель и проверяемый результат

Сократить измеренный интервал от финального структурированного результата LLM до первого слышимого PCM-кадра,
не меняя выбранную XTTS-v2, голос, typed TTS/playback boundary или SIP/media clock. Настройка выполняется по
измерениям нескольких русских фраз, а не по одному WAV.

План считается выполненным только если:

- live-тракт предоставляет точные monotonic timestamps `LLM final decision → TTS worker → first engine chunk →
  first normalized PCM → first playback frame`;
- один прогретый XTTS runtime сравнивает `stream_chunk_size` как минимум `20`, `10` и `5` на общем наборе русских
  коротких и средних фраз;
- выбранный размер снижает time-to-first-audio относительно baseline `20`, не создаёт generation starvation,
  пропусков, overflow или `egress_underruns`;
- полные WAV каждого кандидата и machine-readable metrics сохранены для проверки качества;
- итоговое значение хранится в `config/constants.py`, проходит target CPython 3.14t/no-GIL и зарегистрированный
  FreeSWITCH live gate.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние | Проверка | Stop condition |
|---|---|---|---|---|
| `requirements.md` / `REQ-LAT-001` | Пользователь воспринимает суммарную паузу; RTP-бюджет фиксирован как 30 ms | Оптимизируется TTS TTFA, а не сеть | isolated + live timing | Для улучшения требуется смена модели/голоса |
| `architecture.md` | TTS выдаёт произвольные PCM chunks; receiver-owned bounded buffer формирует `ptime` frames; callback не ждёт producer | `stream_chunk_size` не становится media `ptime`; output/playback ownership не меняется | contract/regression/live counters | Потребовался новый delivery owner или boundary |
| `technical-specification.md` | Настраиваемые MVP-значения принадлежат набору констант | Победивший XTTS chunk size становится явной константой и typed runtime config | config tests | Скрытый tool-only default расходится с live runtime |
| `development-guidelines.md` §1, §5–§7 | Узкий срез, target no-GIL, real model latency evidence; обязательный красный результат исправляется без ослабления gate | GPU sweep и финальный live gate выполняет основной executor | commands/raw JSON/WAV/exit codes | Category-4 gap после corrective retry |
| `plan-002-H`, `plan-005-E` | Произвольный TTS chunk отделён от media frame; bounded accumulation и cancellation сохраняются | Не менять playback protocol и stale/cancel policy | existing unit/contract tests | Появился underrun/overflow/stale payload |
| `plan-017` | Endpoint latency уже закрыта; downstream TTS latency выделена отдельно | Не открывать заново VAD/TurnDetector | diff/source audit | Изменение speech endpoint policy |
| `architectural-planning-gate.md` | Corrective plan имеет scope, source-map, blocker register, evidence и бинарный closeout | Этот файл является self-contained execution plan | APG/registry/backlog audit | Открытый owner-review вопрос |

## 3. Граница задачи

```text
Входит:
  typed observability событий от LLM final decision до первого playback frame;
  воспроизводимый XTTS stream_chunk_size sweep на нескольких русских фразах;
  оценка TTFA, chunk cadence, полного generation RTF и starvation risk;
  конфигурация выбранного размера и target/live regression.

Не входит:
  смена XTTS, голоса, speaker conditioning, ASR, LLM, RAG или prompt;
  filler phrases из TASK-022;
  инкрементальная передача незавершённого LLM-текста в TTS;
  исправление содержания greeting из TASK-024;
  изменение RTP/PCMU/ptime, output-buffer capacity или Dialogue FSM semantics.
```

Protected baseline: XTTS-v2 2.0.3 / `coqui-tts 0.27.5`, существующий reference voice, 24 kHz engine output,
нормализация в negotiated 8 kHz mono S16LE, receiver-owned dynamic buffer, `ptime=20 ms`, barge-in/cancellation,
continuous PCMU и один активный звонок.

Предположение о рабочем дереве: текущие незакоммиченные изменения принадлежат ранее исполненным картам; этот срез
изменяет только явно перечисленный write-set и не откатывает чужие файлы.

## 4. Interaction topology и propagation

Ревизия существующей карты: `plan-002-I`, edges `E17–E19`; payload-типы не меняются.

```text
LlmStreamEvent(DECISION, timestamp_ns)
  -> ConversationPipeline._consume_llm_event()
  -> Dispatcher / DialogueFSM APPROVE_ANSWER
  -> ConversationPipeline._run_tts_payload()
  -> XttsV2Adapter.stream_approved_text()
  -> _RealXttsEngine.inference_stream(stream_chunk_size=N)
  -> TtsPcmChunk
  -> CallRuntimeWiring._on_tts_chunk()
  -> TtsOutputBuffer / MediaPacer
  -> PlaybackChannel.pump()
  -> SipMediaAdapter.enqueue_egress_frame()
```

Materialization рёбер остаётся вызовом typed input-метода получателя. Диагностические timestamps не идут через
Dispatcher, не управляют поведением и не становятся новым payload-каналом.

## 5. Владелец поведения и source-map

XTTS provider владеет параметром количества акустических токенов до декодирования; `XttsV2Adapter` владеет
нормализацией engine PCM; `ConversationPipeline` знает момент финального LLM decision и запуска TTS; playback owner
знает момент первого отправленного media frame. Наблюдение не переносит ownership между ними.

| Область | Разрешённые файлы | Действие |
|---|---|---|
| Config | `config/constants.py`, `src/sip_bot/config.py` | Явный XTTS stream chunk baseline |
| TTS provider/telemetry | `tools/real_composition_probe.py`, `src/sip_bot/tts/`, при необходимости узкий telemetry contract | Настраиваемый chunk size и first-chunk timestamps |
| Pipeline/playback telemetry | `src/sip_bot/conversation_pipeline.py`, `src/sip_bot/runtime_wiring.py`, существующие runtime factories | Сопоставимые monotonic stage events без изменения control/data plane |
| Sweep tool | `tools/tts_stream_latency_probe.py` | Один model load, несколько фраз/кандидатов, JSON/WAV |
| Evidence audit | `tools/tts_latency_audit.py` | Детерминированная агрегация live stage events и проверка baseline/underrun/error условий |
| Live evidence | `tools/j4_full_live_gate.py`, `tools/run_live_bot.py` | Экспорт timing evidence и использование config |
| Tests | `tests/unit/test_config.py`, `tests/unit/test_tts_output.py`, `tests/unit/test_tts_latency_audit.py`, targeted pipeline/wiring tests | Exact config, timestamp order, unchanged payload contracts |
| Owner docs | `docs/technical-specification.md`, `docs/user-guide.md` | Фактический baseline и способ настройки |
| Governance/evidence | этот plan, registry/backlog, `artifacts/implementation/018-tts-first-audio-latency/` | APG evidence и closeout |

Защищены от изменения: VAD/endpointing/ASR, LLM/RAG/prompt, Dialogue FSM semantics, SIP signaling, media codec,
closed evidence предыдущих карт и TTS model package/weights.

## 6. Owner review

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Настраивать ли XTTS first-chunk latency | Да, это принятая owner-ом подстройка | План запускается без дополнительного review | `resolved 2026-09-23` |
| Подбирать ли по одному WAV | Нет; общий набор русских фраз | Sweep не оптимизируется под одну запись | `resolved` |
| Можно ли менять модель/голос | Нет, только streaming chunk policy текущего XTTS | Candidate/voice protected | `resolved scope boundary` |
| Как выбирать победителя | Минимальный устойчивый TTFA при непрерывной generation cadence, полном PCM и зелёном live gate | Число не задаётся заранее | `resolved engineering rule` |

Открытых owner-review вопросов нет.

## 7. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| `018-1` | Добавить typed timing evidence на существующих owner boundaries | Для каждой TTS operation упорядочены пять stage timestamps; observability не влияет на routing | Требуется новый control/data channel |
| `018-2` | Реализовать и выполнить target XTTS sweep `20/10/5` на общей фразовой матрице | JSON содержит TTFA, first chunk duration, full RTF/chunk cadence; WAV сохранены; GIL off | Кандидаты нельзя сравнить в одном прогретом runtime |
| `018-3` | Выбрать и материализовать chunk size в constants/provider | Targeted tests и повторный probe подтверждают выигрыш без starvation/quality failure | Ни один кандидат не лучше baseline |
| `018-4` | Выполнить host/target regression и registered FreeSWITCH live gate | Exact live stage timings, `egress_underruns=0`, no overflow/errors, сценарий/recording pass | Общая GPU/SIP среда недоступна после retry либо live regression |
| `018-5` | Синхронизировать owner docs, registry/backlog и closeout | Audits green, binary status и evidence links | Evidence неполно |

Исполнитель: основной executor. Тяжёлый GPU sweep и live gate не делегируются. Отдельное согласование срезов не
требуется, поскольку owner явно разрешил исполнение всей настройки до результата.

## 8. Blocker register

| ID | Срез | Триггер | Что блокируется | Owner | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-018-001` | 018-2/3 | Уменьшение chunk size ухудшает full-generation cadence до starvation либо повреждает PCM | Выбор нового baseline | project owner | sweep JSON/WAV | `not triggered` |
| `B-018-002` | 018-4 | Target GPU/SIP stand недоступен после retry | Live acceptance | project owner | command/raw output | `not triggered` |
| `B-018-003` | любой | Настройка требует смены модели, boundary или protected playback policy | Implementation | project owner | gap report | `not triggered` |

## 9. Test plan и evidence

1. Unit/contract: config range; deterministic timestamp ordering; TTS chunk normalization, cancellation и playback.
2. Target runtime: CPython 3.14t, `Py_GIL_DISABLED=1`, GIL off до/после XTTS import и operation.
3. GPU sweep: один прогретый model owner; одинаковый ordered phrase set; кандидаты `20/10/5`; минимум два прохода
   после отдельного warmup; raw per-chunk monotonic timing, full PCM SHA-256 и WAV.
4. Selection gate: TTFA улучшен против `20`; full RTF оставляет playback headroom; simulated buffer не голодает после
   первого чанка; output не пуст и полностью завершается.
5. Regression: affected tests и полный target suite.
6. Registered call: FreeSWITCH, exact stage trace, complete scenario/stereo/RTP, `egress_underruns=0`, overflow/errors=0.

Ручное прослушивание WAV полезно, но не заменяет machine checks; automated checks не объявляют субъективное качество
production-grade.

## 10. Fallback/deferred register

Fallback: `none`. Запрещены test-only chunk size, сохранение скрытого `20` в live service, предварительно записанные
ответы, ослабление continuity assertions и подмена XTTS другой моделью.

Инкрементальный LLM→TTS и filler phrases остаются отдельными задачами; они не требуются для закрытия этого плана.

## 11. Execution report и closeout

Все срезы `018-1`–`018-5` выполнены без fallback и без срабатывания blocker register. Выбран
`TTS_STREAM_CHUNK_SIZE=5`, `TTS_STREAM_OVERLAP_WAV_LEN=1024` сохранён. Прогретый target sweep дал median TTFA
`398.059 / 204.681 / 107.277 ms` для `20 / 10 / 5`; full RTF всех кандидатов `<1`, underrun и clipping отсутствуют.

Registered FreeSWITCH gate прошёл полный сценарий. Для четырёх ответов `LLM final → playback first frame` составило
`206.873`, `173.499`, `192.975`, `223.834 ms`; RTP continuity `6151/6151`, `egress_underruns=0`, output overflow и
runtime errors равны нулю. Target CPython 3.14.7t сохранил `Py_GIL_DISABLED=1`/GIL off, полный target suite прошёл.
Authoritative evidence и команды собраны в
`artifacts/implementation/018-tts-first-audio-latency/closeout.md`; статус плана — `complete`.
