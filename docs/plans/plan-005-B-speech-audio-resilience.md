# Plan 005-B: устойчивость audio/speech-контура

Уровень: `child plan`  
Идентификатор: `005-B`  
Статус owner review: `accepted — owner review принят 2026-09-04`  
Статус исполнения: `complete`  
Родительская карта: [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md)  
Дата подготовки: `2026-09-04`

## 1. Цель и проверяемый результат

Проверить speech ingress от `PcmFrame` до authoritative `FinalUserTurn`: fan-out не блокирует независимых потребителей,
ASR chunks формируются по negotiated profile и timer, VAD/endpointing различают речь и паузу, partial revisions не
накапливают мусор, hard endpoint создаёт ровно один финальный ход, а stale/cancelled results не продолжают разговор.

Минимальный результат: для одного call scope есть воспроизводимая speech boundary matrix с PCMU-derived PCM profile,
VAD transitions, 300/500 ms endpoint evidence, пустыми/длинными ходами, возобновлением речи, partial correction,
explicit/absent stable prefix и cancellation/stale policy.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Русский потоковый ASR, один разговор, перебивание и контекст; обязательный результат — текстовый ход | Не менять язык, scope и authoritative final semantics | Speech integration tests | Другой scope или финализация без evidence |
| [`architecture.md`](../architecture.md) | PCM fan-out направляет один вход в VAD, turn detector и ASR accumulator; payload не проходит через Dispatcher | Consumer-ы независимы и получают typed `PcmFrame` напрямую | Fan-out/backpressure tests | Dispatcher становится audio transit |
| [`technical-specification.md`](../technical-specification.md) | Per-call SDP/profile; PCMU→PCM S16LE; soft/hard endpoint и partial ASR; stable prefix только из backend field | Размеры/частоты/таймеры извлекаются из call profile, не из global defaults | Profile, timing и revision evidence | Format mismatch или inferred stability |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Map-I rev21 содержит `PcmFrame → fan-out → VAD/ASR chunker`, `AsrHypothesis → TranscriptAssembler → FinalUserTurn` | Актуальные typed inputs и cancellation/stale rules не переопределяются | Propagation/source audit | Consumer не принимает фактический output |
| [`plan-002-C-audio-boundary-buffering.md`](plan-002-C-audio-boundary-buffering.md), [`plan-002-D-speech-ingress.md`](plan-002-D-speech-ingress.md) | Закрытые owners и contracts являются baseline; corrective changes только по доказанному gap | Не переоткрывать закрытые решения и не копировать их как новые questions | Regression/contract rerun | Требуется protected-baseline change |
| [`development-guidelines.md`](../development-guidelines.md) | Узкий typed-first slice, owner behavior, bounded queues, corrective pass и binary closeout | Исправлять только speech/media boundary scope, красные тесты не маскировать | APG/test audit | Category 4 gap или неполное evidence |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan обязан иметь source-map, topology, audits, blockers, evidence и closeout | Этот документ самодостаточен; execution только после review | Structural APG audit | Обязательный блок отсутствует |

Ранее принятые решения о 500 ms hard endpoint, direct data plane, one final authoritative turn, explicit backend
stable prefix и no-GIL target не являются открытыми owner questions.

## 3. Граница задачи

**Входит:**

- bounded `PcmFanOut` с независимыми VAD и ASR subscriptions;
- `AsrChunker` с per-call profile, target chunk, timer flush, hard-endpoint flush, close/cancel и overflow evidence;
- VAD/Turn Detector transitions для речи, пауз, soft endpoint, hard endpoint и resume;
- `TranscriptAssembler`/`SpeechIngress` для replacement partials, explicit stable prefix, finalization и stale/cancel;
- deterministic tests и target speech checks на approved ASR path;
- corrective fixes в `src/sip_bot/media/` и `src/sip_bot/speech/`, если ошибка принадлежит этому write-set.

**Не входит:** SIP transaction behavior, new VAD/ASR candidate, semantic turn detector, LLM/RAG, TTS, Dispatcher/FSM
semantics, изменение Map-I, второй вызов и аудиозапись в runtime бота. Live Baresip recording принадлежит A/D evidence.

**Protected baseline:** Map-I revision 21, closed C/D plans, `PcmFrame`, `AsrAudioChunk`, `AsrHypothesis`,
`TranscriptUpdate`, `FinalUserTurn`, approved faster-whisper candidate и per-call negotiated profile.

**Предположения:** target runtime — CPython 3.14.7t Ubuntu/WSL; GPU-heavy ASR operation запускает только main executor
и только последовательно после review. Deterministic preparation может идти независимо от A.

## 4. Source-map и write-set

| Область | Файл/символ | Текущее состояние | Действие | Write-set |
|---|---|---|---|---|
| Fan-out/chunker | `src/sip_bot/media/fanout.py`, `asr_chunker.py` | Existing bounded typed boundaries | Исправлять только category 1 defects | Existing symbols in these files |
| Speech ingress | `src/sip_bot/speech/ingress.py`, `endpointing.py`, `transcript_assembler.py`, `vad.py` | Existing VAD/endpoint/revision lifecycle | Проверка и corrective fixes | Existing symbols in these files |
| ASR adapter | `src/sip_bot/speech/asr_adapter.py` | Approved streaming/cancel candidate | Только evidence-driven fix; model/provider не менять | Existing symbols only |
| Tests | `tests/unit/test_map005_speech_resilience.py`, `tests/integration/test_map005_speech_resilience.py` | Нет | Создать matrix tests | New files |
| Target probe | `tools/map005_speech_probe.py` | Нет | Узкий PCMU-derived ASR boundary smoke до `FinalUserTurn` | New file |
| Evidence | `artifacts/implementation/002-system-testing-and-demo-readiness/005-B/` | Нет | Hypotheses, endpoint/revision/chunker outputs | Own evidence root only |

Запрещено менять `runtime_wiring.py`, `conversation_pipeline.py`, `config/constants.py`, `tests/integration/conftest.py`,
закрытые tests/plans/evidence и shared registry/backlog. Если нужен другой файл, это gap до изменения.

## 5. Interaction topology и propagation

```text
SipMediaAdapter.next_ingress_frame()
  → PcmFrame
  → PcmFanOut.publish()
      ├→ PcmFanOutSubscription("vad") → VadProcessor.process()
      │                                  → VadDecision → TurnDetector.consume()
      └→ PcmFanOutSubscription("asr_input_accumulator") → AsrChunker.push()/on_timer()
                                                           → AsrAudioChunk → StreamingAsrAdapter.stream()
                                                           → AsrHypothesis → SpeechIngress.accept_hypothesis()
                                                                                   → TranscriptAssembler
                                                                                   → FinalUserTurn
```

Материализация каждого edge — typed input method получателя. Между потоками используется только bounded thread-safe
queue; в одном main `asyncio` loop допускается прямой вызов/локальный queue. VAD overflow не должен блокировать ASR,
ASR stale result не должен порождать финальный ход, а cancellation закрывает текущий scope и не затрагивает новый.
Фактический profile, размеры, units, close/error и consumer acceptance фиксируются в evidence.

## 6. Audit владельца поведения и парадигмы реализации

`PcmFanOut` владеет bounded fan-out lifecycle; `AsrChunker` владеет сборкой media frames в ASR chunks и timer; `VadProcessor`
и `TurnDetector` владеют speech classification/endpoint transitions; `TranscriptAssembler` владеет revision lifecycle;
`SpeechIngress` владеет связкой endpoint + hypothesis и выдачей final turn. Эти owners уже существуют. Тесты не вводят
новый delivery-owner, transcript store или semantic detector.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Нужно ли менять endpoint baseline? | Нет, 250–300 ms soft и около 500 ms hard остаются конфигурационным baseline | Проверяем фактическую реализацию и evidence | `resolved by requirements/technical-specification` |
| Можно ли выводить stable prefix из совпадения гипотез? | Нет, только explicit backend stable prefix | Early common-prefix regression остаётся запрещённым | `resolved by prior corrective decision` |
| Принят ли этот child plan к execution? | Групповой owner review child plans `005-A`–`005-D` принят 2026-09-04 | Отдельное согласование этого файла не является дополнительным gate | `resolved by grouped owner review` |

Новых предметных owner decisions нет; повторное обсуждение закрытых C/D contracts не требуется.

## 8. Process invariant audit

| Инвариант | Materialized action | Evidence |
|---|---|---|
| Narrow/bounded | Каждый consumer имеет bounded subscription/overflow policy | Fan-out/chunker counters |
| Typed-first | Используются `PcmFrame`, `AsrAudioChunk`, `AsrHypothesis`, `FinalUserTurn` | Contract tests |
| Direct data plane | PCM и текстовые revisions не идут через Dispatcher | Topology/source audit |
| Cycles/cancellation | Resume cancels speculative state; close/cancel suppresses stale result | State trace |
| Corrective pass | Category 1/2 исправляется и rerun-ится targeted+regression+contract | Raw/rerun evidence |
| Binary closeout | Только `complete` или concrete `blocked` | Closeout/register |

## 9. Architecture invariant audit

- Для каждого звонка профиль берётся из negotiated SDP/словарей; hardcoded 8 kHz/ptime применяется только если это
  уже фактический профиль текущего вызова.
- VAD, turn detector и ASR accumulator получают независимые данные; медленный consumer не останавливает остальных.
- Финальный `FinalUserTurn` создаётся после authoritative hard endpoint, а partial/stale revisions не становятся ответом.
- Возобновление речи отменяет speculative path, но продолжает текущий turn.
- Native ASR/no-GIL и approved process boundaries не меняются.

## 10. Implementation slices

### B1 — contract and fan-out/chunker tests

Проверить actual frame bytes/profile, независимость subscriptions, target chunk/timer flush, overflow, close/cancel и
hard-endpoint flush. Acceptance: frame ownership, units и bounded behavior доказаны.

### B2 — VAD/endpoint/revision matrix

Проверить speech/pause/resume, soft/hard endpoint 300/500 ms, empty/long turns, replacement partials, explicit stable
prefix и отсутствие inferred prefix. Acceptance: один authoritative final turn на ход, без contradictory-prefix defect.

### B3 — target ASR and stale/cancel

После deterministic pass главный executor последовательно запускает target ASR operation, cancellation, stale result и
real PCMU-derived path. Acceptance: target evidence содержит runtime/model/command/timings и не выдаёт skipped за pass.

### B4 — corrective pass/propagation handoff

При красном результате классифицировать 1–4, исправить только write-set, повторить targeted/regression/contract,
сохранить evidence и передать в Map-005. Изменение downstream contract останавливает plan как gap.

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец | Evidence/condition promotion | Статус |
|---|---|---|---|---|---|---|
| `B-005-B-001` | весь plan | Child owner review не пройден | Любая реализация/execution | project owner | Этот файл и review message | `resolved 2026-09-04` |
| `B-005-B-002` | B1/B2 | Фактический output не принимается существующим consumer или нужен новый boundary | Affected propagation и integration | project owner | APG gap + Map-I revision if required | `none until triggered` |
| `B-005-B-003` | B3 | Target ASR/GPU недоступен или operation не завершается | Target claim, не deterministic preparation | main executor/project owner | Raw runtime output, retry after external condition | `none until triggered` |
| `B-005-B-004` | B1–B4 | Mandatory red remains category 4 after corrective pass | Affected acceptance/map closeout | project owner | Raw output + attempts + promotion condition | `none until triggered` |

Недостаток диска <20 ГБ проверяется перед target run; lock-файлы зависимостей не эскалируются после одной попытки,
а повторяются с задержкой согласно guidelines.

## 12. Test plan и evidence

```text
Target runtime: /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
Deterministic: python -m pytest -q tests/unit/test_map005_speech_resilience.py tests/integration/test_map005_speech_resilience.py
Target ASR library/cancellation: `tools/asr_primary_probe.py` with the approved patched runtime
Target application boundary: `python tools/map005_speech_probe.py --fixture <fixture> --model-path <model> --output <json>`
Regression: python -m pytest -q tests/unit tests/contract tests/integration
```

Evidence: profile/units, per-consumer queue counters, VAD decisions, endpoint events/timestamps, all hypothesis
revisions, stable-prefix source, final turns, cancellation/stale outcomes, target runtime/model, stdout/stderr и exit
codes. Deferred target evidence имеет stable ID, owner и condition promotion.

## 13. Fallback/deferred register

| Что | Причина | Ограничение | Promotion | Статус |
|---|---|---|---|---|
| Deterministic ASR/VAD backend | Проверка lifecycle без GPU | Не выдаётся за real ASR quality | Target ASR run | `allowed for preparation` |
| Common-prefix stability inference | Исторический дефект | Запрещено | Explicit backend field only | `forbidden` |
| Новый ASR/VAD candidate | Не нужен для текущего baseline | Только отдельный owner decision/plan | New feasibility gate | `none` |

## 14. Execution report и closeout

Execution date: `2026-09-04`.

Фактический diff ограничен unit/integration tests, target boundary probe и собственным evidence root; existing speech,
ASR/media owners и typed contracts не изменялись.

Acceptance:

- B1/B2 deterministic matrix: `9 passed` на target CPython 3.14.7t;
- approved faster-whisper streaming probe: `status=pass`, partial results на 1/2/3/4 s и authoritative final,
  model load `9.365 s`, final inference `0.350 s`, GIL disabled до/после operation;
- approved cancellation probe: `status=pass`, generator close observed, `post_close_items=0`,
  `stale_result_accepted=false`, GIL disabled;
- прикладной PCMU-derived probe: `status=pass`, 253 negotiated 20-ms frames прошли
  `PCMU payload → decode_pcmu_frame → PcmFrame`, затем через `AsrChunker` и real `FasterWhisperC2Backend`;
- прикладная speech boundary matrix дала 300-ms soft и 500-ms authoritative hard endpoint, три ASR hypotheses и
  ровно один `FinalUserTurn` (`Увидимся!`); этот smoke подтверждает границу и lifecycle, а не качество конкретной
  fixture-фразы;
- target regression `tests/unit tests/contract tests/integration`: `141 passed, 2 skipped`;
- red runner results классифицированы как category 2/3 и исправлены до повторного pass: сначала не был подхвачен
  CUDA library path, затем в новом probe были исправлены `-I` import path и JSON serialization; product source defect
  не обнаружен, fallback не добавлялся.

Ограничение evidence: cancellation real backend подтверждён на уровне faster-whisper generator close; независимого
native cancellation token у faster-whisper 1.2.1 нет. Live SIP/RTP уже покрыт `005-A`; этот child не выдаёт fixture
smoke за live call.

Команды и evidence: [`commands.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-B/commands.md),
[`target-20260904-r2`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-B/target-20260904-r2/),
[`target-20260904-r4`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-B/target-20260904-r4/),
[`closeout.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-B/closeout.md).

`005-B` закрыт статусом `complete`: весь scope доказан собственным evidence, category-4 blocker отсутствует. Следующий
разрешённый переход — `005-C`; Map-005 остаётся `in_progress`.
