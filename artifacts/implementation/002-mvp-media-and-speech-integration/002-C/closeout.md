# Plan-002-C closeout

Уровень: `child plan`

Статус исполнения: `complete` — 2026-09-03.

Owner review: `accepted` — 2026-09-03. Owner authorization на execution получена до начала implementation stage.

## Проверенный результат

Реализован полный scope среза C:

Входной контракт: `Map-002-I revision 4`, полученный от `002-B` handoff 2026-09-03. Эта ревизия использовалась как
входная baseline; локальные типы и наблюдения этого child plan не объявляются authoritative для соседних планов и не
изменяют Map-002-I.

- PCMU ↔ PCM S16LE conversion по фактическому per-call `NegotiatedMediaProfile`;
- `PcmFrame` сохраняет `call_id`, `channel_id`, `generation`, `sequence`, `timestamp_ns` и profile;
- frame-size проверяется относительно negotiated `ptime`, sample rate и channel count;
- специализированный `PcmFanOut` создаёт независимые bounded channels для `vad` и `asr_input_accumulator`;
- медленный или закрытый consumer не блокирует остальные, stale generation и overflow наблюдаемы через результат и
  counters;
- `AsrChunker` собирает целевые 1000 ms chunks, разрезает границы media frames без потери alignment и поддерживает
  timer, manual, hard-endpoint, graceful-close, cancel и non-blocking overflow semantics;
- cancel очищает pending/current generation data, close идемпотентен и оставляет уже queued chunks drainable;
- target C4 подтверждён на живом вызове approved Baresip peer: 100 PCM frames, два независимых потребителя и два
  target chunks по 1 секунде.

## Фактические output-типы и границы propagation

Локально получены и проверены следующие типы:

- входной per-call `NegotiatedMediaProfile` и `PcmFrame` из `sip_bot.sip_media.models` — фактический профиль PCMU,
  payload type 0, 8000 Hz, mono, 20 ms, 160 samples, 320 PCM S16LE bytes;
- `PcmFanOutSubscription` и `PublishResult` — специализированный bounded direct data-plane fan-out для независимых
  потребителей `vad` и `asr_input_accumulator`;
- `AsrAudioChunk` — PCM S16LE chunk с `call_id`, `channel_id`, `generation`, `sequence`, `timestamp_ns`, profile,
  `flush_reason` и `is_final`;
- `FlushReason` — `target`, `timer`, `hard_endpoint`, `manual`, `close`.

Эти output-типы являются результатом реализации и evidence `002-C`, но остаются кандидатами до propagation checkpoint
главного исполнителя. Для `I1–I2` требуют сверки и передачи следующие потребители/границы:

- `N3 → N5` / VAD: `PcmFrame`, generation/stale policy, bounded subscription и close semantics;
- `N3 → N4` / ASR input accumulator: `PcmFrame`, capacity/overflow semantics и порядок frames;
- `N4 → N7` / ASR: `AsrAudioChunk`, target/timer/flush/cancel semantics, `flush_reason` и `is_final`;
- downstream contract fixtures и собственный source-map `002-D`.

Propagation `I1–I2`, изменение Map-002-I и promotion output-типа в authoritative contract относятся к главному
исполнителю и выполняются отдельно. Если при этой сверке изменится boundary-контракт, `002-C` должен пройти corrective
pass; текущий closeout не трактует live C4 как закрытие downstream boundary.

## Изменённые файлы в разрешённом write-set

- `src/sip_bot/media/__init__.py`
- `src/sip_bot/media/codec.py`
- `src/sip_bot/media/types.py`
- `src/sip_bot/media/fanout.py`
- `src/sip_bot/media/asr_chunker.py`
- `tests/unit/test_audio_boundaries.py`
- `tests/contract/test_audio_contracts.py`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/contract-snapshot.json`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/commands.md`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/evidence-index.md`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/target_pcm_boundary_probe.py`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/target-tests.stdout.log`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/target-tests.stderr.log`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/c4-target.stdout.log`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/c4-target.stderr.log`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/c4-target.json`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/c4.peer.log`

Обязательное execution-control изменение в самом plan-file: owner review accepted и execution in_progress были
зафиксированы перед кодом; итоговый closeout обновляется там же до `complete`. Другие общие документы, `Map-002-I`,
родительская карта, registry и backlog не изменялись.

## Test/evidence results

| Lane | Command/result |
|---|---|
| Baseline | `21 passed` |
| Targeted host | `15 passed` |
| Full host unit/contract | `57 passed` |
| Host compile | `exit 0` |
| Target no-GIL import | CPython 3.14.7t, `Py_GIL_DISABLED=1`, GIL before/after media import `False`, `exit 0` |
| Target deterministic | `15 passed`, `exit 0` |
| Target live C4 | `pass`, 100 live PCM frames, fan-out 100/100, 2 chunks, `exit 0` |
| Heavy GPU inference | не запускался, `not applicable` для C |

## Blocker register

- `B-002-C-001`: resolved — owner review accepted 2026-09-03.
- `B-002-C-002`: resolved — 002-B handoff and authoritative media profile available.
- `B-002-C-003`: resolved — bounded overflow/close/cancel rules покрыты deterministic tests и live C4 evidence.

Open blockers: `none`.

## APG §5.8B audit

Были два красных результата, оба классифицированы как ошибки invocation/fixture-окружения, исправлены и повторно
запущены. Локальный кодовый дефект blocker-ом не объявлялся. После corrective passes targeted, regression,
contract, runtime и target handoff checks зелёные. Субагент не использовался; implementation и final verification
выполнены основным executor в текущем workspace.

## Out-of-scope и deferred

- SIP adapter, speech/ASR implementation, VAD, Dispatcher/FSM, Map-002-I и родительские документы не изменялись.
- GPU inference, model loading и real ASR не входят в C и не запускались.
- Запись аудио не выполняется.
- Fallback и намеренные упрощения: `none`.

## Следующий шаг

Передать в `002-D` фактические `PcmFrame`/`AsrAudioChunk` поля, профиль per-call, capacities и timer/flush/overflow/
close/cancel semantics. Execution `002-D` начинается только после его собственного owner review.
