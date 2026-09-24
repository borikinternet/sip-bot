# Plan-014: адаптивный энергетический gate для WebRTC VAD

Уровень: `child plan`  
Статус owner review: `accepted by explicit owner instruction 2026-09-22`  
Статус исполнения: `complete`  
Родитель: [`roadmap.md`](../roadmap.md)  
Предшественник: [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md)  
Evidence root: `artifacts/implementation/014-adaptive-vad-energy-gate/`

## 1. Цель и проверяемый результат

Устранить ложные пользовательские ходы и `barge_in`, обнаруженные на реальном телефонном звонке: WebRTC VAD mode 2
принимал фон и слабый акустический возврат реплик бота за речь, после чего ASR галлюцинировал текст на шуме.

Проверяемый результат: существующий тракт
`PcmFrame → VadProcessor → VadDecision → TurnDetector` сохраняется, но положительное решение WebRTC VAD подтверждается
адаптивным энергетическим gate. Gate ведёт per-call оценки шумового и речевого уровней, публикует диагностические поля и
отсекает низкоэнергетические ложные решения до `TurnDetector`.

Первый live corrective run `20260922-145749` дополнительно обнаружил уже существовавший boundary-дефект: быстрые
последовательные пользовательские ходы могли опередить ASR, единственный pending endpoint перезаписывался, а
`AsrAudioChunk`/`AsrHypothesis` не несли authoritative `turn_id`. В результате endpoint одного хода применялся к
assembler другого и call-loop завершался с `endpoint belongs to another transcript scope`. Исправление обязано
протянуть фактический `TurnDetector.turn_id` через ASR boundary и хранить pending endpoint/assembler state по этому
идентификатору; это материализация уже принятого typed-boundary правила, а не новый компонент или канал.

## 2. Извлечённые правила

| Источник | Применимое правило | Влияние | Проверка / stop condition |
|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Изменение VAD/runtime-критерия требует scope, source-map, blockers, tests и closeout | Этот файл является self-contained corrective plan | Открытый boundary gap останавливает execution |
| [`development-guidelines.md`](../development-guidelines.md) | Красный тест в write-set исправляется; упрощения и скрытый fallback запрещены | Реальный красный звонок становится regression evidence | Нельзя объявить complete без replay и live evidence |
| [`architecture.md`](../architecture.md) | PCM идёт напрямую в VAD; `TurnDetector` остаётся владельцем endpointing | Gate находится внутри VAD owner, без очереди/Event Bus/Dispatcher | Новый data-plane edge запрещён |
| [`technical-specification.md`](../technical-specification.md) | Параметры MVP находятся в `config/constants.py` | Все параметры адаптации задаются константами | Скрытые literals в live construction запрещены |
| [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md) | Mode 2 доказан только controlled TTS corpus; human/noise generalization была deferred | Новое реальное evidence продвигает именно deferred scope | Историческое evidence Map-008 не переписывается |

## 3. Граница задачи

Входит:

- per-call вычисление RMS dBFS каждого mono PCM frame;
- устойчивая оценка noise floor по скользящему низкому квантилю с ограниченной скоростью роста;
- настраиваемый порог `max(minimum_dbfs, noise_floor + margin_db)`;
- подтверждение `raw WebRTC speech` энергетическим gate;
- диагностические поля решения и агрегированный snapshot;
- replay записанного звонка, unit/contract/regression и повторный live-звонок.
- исправление выявленной на live-звонке идентичности пользовательского хода на границе ASR: qualified speech frames,
  `AsrAudioChunk`, `AsrHypothesis`, endpoint и assembler связываются одним `turn_id`;
- несколько ASR-результатов и endpoints могут безопасно ожидать друг друга, не перезаписывая состояние соседнего хода.

Не входит: замена WebRTC VAD, acoustic echo canceller, новый IPC/поток, изменение алгоритма `TurnDetector`, ASR как VAD
oracle, production claim для всех микрофонов и уровней.

Protected baseline: SIP/PJMEDIA, fan-out topology, ASR/LLM/TTS, FSM semantics, Map-008 historical artifacts.

## 4. Source-map и write-set

| Область | Файлы | Действие |
|---|---|---|
| VAD owner | `src/sip_bot/speech/vad.py`, `speech/contracts.py`, `speech/__init__.py` | Adaptive gate, analytics и backward-compatible diagnostics |
| Конфигурация | `config/constants.py`, `src/sip_bot/config.py` | Явные параметры gate |
| Construction | `tools/run_live_bot.py`, `tools/live_i1_gate.py`, `tools/j4_full_live_gate.py` | Один фабричный способ построения configured processor |
| Turn-scoped ASR boundary | `src/sip_bot/media/asr_chunker.py`, `src/sip_bot/speech/contracts.py`, `src/sip_bot/speech/asr_adapter.py`, `src/sip_bot/speech/ingress.py`, `src/sip_bot/runtime_wiring.py` | Передать authoritative `turn_id`, не подавать в ASR не прошедшие `min_speech_ms` bursts, сопоставлять endpoint и assembler по ключу хода |
| Tests | `tests/unit/test_adaptive_vad_energy_gate.py`, related config/contract tests | Тишина, шум, речь, adaptation, recorded-call replay |
| Evidence/docs | собственный evidence root, architecture/ТЗ/roadmap/registry/backlog | Команды, результаты, ограничения и closeout |

## 5. Ownership и interaction audit

`AdaptiveEnergyGate` является внутренней политикой `VadProcessor`: получает тот же PCM frame и raw boolean кандидата.
Новый межкомпонентный канал не создаётся. `VadDecision.is_speech` остаётся единственным authoritative input для
`TurnDetector`; дополнительные поля только диагностические. Gate создаётся заново для каждого звонка вместе со
`SpeechIngress`, поэтому состояние уровней не протекает между звонками.

`TurnDetector` остаётся единственным владельцем нумерации хода. После `SPEECH_STARTED` runtime передаёт выданный им
`turn_id` существующему ASR accumulator; короткий raw/energy-positive burst, не достигший `min_speech_ms`, в ASR не
попадает. Accumulator только сохраняет этот ключ в `AsrAudioChunk`, ASR adapter переносит его в `AsrHypothesis`, а
`SpeechIngress` сопоставляет hypothesis и hard endpoint с assembler того же ключа. Межпоточная доставка остаётся на
существующих bounded queues, новый delivery owner не вводится.

## 6. Owner-review решения

| Вопрос | Решение | Статус |
|---|---|---|
| Нужна ли адаптивная энергетическая аналитика поверх WebRTC VAD? | Да; явно потребована owner после real-call evidence | `resolved` |
| Можно ли калибровать только по одному WAV? | Нет; WAV является regression, существующий multi-phrase corpus остаётся обязательным | `resolved by prior owner decision` |
| Меняется ли mode 2 автоматически? | Нет; сначала исправляется missing energy criterion, mode остаётся отдельной конфигурацией | `resolved` |

Открытых owner-review вопросов нет.

## 7. Implementation slices

| Срез | Действие | Acceptance | Stop condition |
|---|---|---|---|
| `014-1` | Реализовать analytics/gate и typed diagnostics | Unit/contract tests, без topology change | Требуется новый edge/owner |
| `014-2` | Подключить gate во все real WebRTC construction points | Config/source audit pass | Скрытый ungated live path |
| `014-3` | Replay problem recording и controlled corpus regression | Один осмысленный turn, шум не вызывает barge-in; corpus не деградирует | Невозможно разделить речь/шум без нового алгоритма |
| `014-4` | Развернуть на сервере и выполнить live validation | Нет ложных turns/barge-in, запись и diagnostics сохранены | Недоступен обязательный стенд |
| `014-4a` | Corrective propagation `TurnDetector.turn_id → AsrAudioChunk → AsrHypothesis → TranscriptAssembler` | Back-to-back turns при отстающем ASR не смешиваются, не перезаписывают endpoint и не завершают call-loop; неqualified bursts не загрязняют ASR | Для исправления требуется новый component/edge или смена владельца turn identity |
| `014-5` | Повторный live gate, closeout и document synchronization | Evidence и ограничения записаны | Открытый обязательный gate |

## 8. Blocker register

| ID | Триггер | Владелец | Статус |
|---|---|---|---|
| `B-014-001` | Для исправления требуется новый media edge или AEC-компонент | project owner | `none until triggered` |
| `B-014-002` | Gate ухудшает controlled corpus или отбрасывает нормальную телефонную речь | executor | `none until triggered` |
| `B-014-003` | Live стенд/GPU недоступен после corrective retries | project owner | `none until triggered` |
| `B-014-004` | Нельзя сопоставить несколько in-flight ASR turns существующими typed boundaries без нового компонента/канала | project owner | `not triggered`: prior architecture уже назначает `TurnDetector` владельцем `turn_id`, требуется propagation |

## 9. Test/evidence plan

- unit: RMS, percentile/noise-floor adaptation, threshold bounds, raw-vs-accepted counters;
- contract: существующие constructors без gate сохраняют прежнее поведение, live constructors используют gate;
- regression fixture: сохранённый stereo call, caller channel `8 kHz/mono/20 ms`, mode 2;
- controlled corpus: Map-008 multi-phrase fixture;
- target runtime: CPython 3.14t, проверка тестов и отсутствия GIL regression;
- live: новый звонок через FreeSWITCH с автоматической stereo recording и VAD summary.
- corrective concurrency: минимум три back-to-back user turns, ASR worker искусственно задержан; каждый final text
  завершается endpoint своего `turn_id`, а call-loop остаётся работоспособным;
- qualification: burst короче `min_speech_ms` не входит ни в один `AsrAudioChunk` и не меняет следующий turn prefix.

## 10. Closeout

Plan становится `complete` только после всех пяти slices, зелёного replay/live gate, синхронизации документов и
фиксации changed files/commands/results. Допустимый итог при реальном category-4 gap — только `blocked`.

### 10.1. Execution progress 2026-09-22

- `014-1`/`014-2`: реализованы и подключены во все live constructors;
- `014-3`: problem-call replay `447 raw → 94 accepted`, один authoritative turn; controlled Map-008 corpus сохранил
  три turns после corrective hysteresis;
- первый `014-4` run `20260922-145749`: energy filtering улучшено, но gate красный из-за воспроизводимого
  `TranscriptContractError`; evidence и расшифровки сохранены в собственном live artifact;
- `014-4a`: authoritative `turn_id` протянут через ASR boundary; три back-to-back turns при заблокированном worker и
  sub-`min_speech_ms` pre-roll regression проходят;
- host suite: `256 passed, 5 skipped`, один ранее существовавший stale registration-default test вне write-set;
- target CPython 3.14t subset после deployment: `66 passed`;
- `014-5`: authoritative registered repeat
  [`registered-repeat-20260922-r8`](../../artifacts/implementation/014-adaptive-vad-energy-gate/014-5/registered-repeat-20260922-r8/j4-full-live.json)
  завершён `status=pass`: пять пользовательских ходов разделены, follow-up/barge-in/unknown-answer/transfer/report
  пройдены, `asr_chunks_dropped=0`, `stale_hypotheses=0`, runtime errors отсутствуют, CPython 3.14.7t сохранил
  `gil_enabled=false`;
- все пять slices выполнены, открытых blockers и deferred mandatory evidence нет; Plan-014 закрыт `complete`.
