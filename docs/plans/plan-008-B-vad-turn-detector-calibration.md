# Plan-008-B: calibration WebRTC VAD + TurnDetector

Уровень: `child plan`  
Статус owner review: `accepted by explicit execution instruction`  
Статус исполнения: `complete`  
Родительская карта: [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md)  
Предшественник: [`plan-008-A-vad-standalone-calibration.md`](plan-008-A-vad-standalone-calibration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21  
Evidence root: `artifacts/implementation/008-vad-turn-calibration/008-B/`

## 1. Цель и границы

На corpus и VAD trace из `008-A` настроить существующий `TurnDetector`, не перенося в него VAD classifier,
Transcript Assembler или ASR.

Проверяется преобразование:

```text
VadDecision → TurnDetector.consume(decision) → EndpointEvent
```

Цель — определить mode/configuration, которые правильно обрабатывают короткие паузы, паузы около soft/hard thresholds,
возобновление речи и окончательное завершение хода. Новый `VadSmoother` не создаётся: необходимое temporal behavior
либо остаётся текущей политикой, либо изменяется в существующем `TurnDetector` в пределах этого write-set.

## Применимые документы и извлечённые правила

Применяются parent Map-008, Map-I revision 21, Map-007, `architecture.md`, `technical-specification.md` и
`development-guidelines.md`. Их operational projection зафиксирована в разделах owner-review, process/architecture
audit и test plan ниже: `VadDecision → TurnDetector.consume(decision)` сохраняется, ASR не является разметкой, а новые
owners/boundaries требуют отдельного review.

## Граница задачи

Входит только replay VAD decisions и настройка существующего `TurnDetector`/`EndpointingConfig` с tests/evidence.
Не входят изменение VAD algorithm, SIP/media, ASR/LLM/TTS, новый smoother component, новый typed edge или live gate.

## 2. Материализованные правила и ownership

| Правило | Применение | Evidence |
|---|---|---|
| `TurnDetector` владеет endpoint state | Менять только его existing behavior/config; VAD не получает endpoint ownership | Source/ownership audit |
| `VadDecision → TurnDetector` — authoritative typed edge | Replay использует реальные `VadDecision`, не ASR segments | Contract/propagation tests |
| 300/500 ms — current baseline | Проверить границы и явно зафиксировать evidence-based result; результатом стал hard 520 ms | Endpoint trace |
| ASR не участвует в A/B | Ожидаемые ходы берутся из timing manifest; ASR — после B, diagnostic | Dependency audit |
| No silent simplification | Не удалять фразы/паузы после неудобного split/merge | Corpus revision and diff |

## 3. Source-map и write-set

| Область | Файл | Действие | Write-set |
|---|---|---|---|
| Endpoint policy | `src/sip_bot/speech/endpointing.py` | При необходимости корректировать существующую политику | Existing `TurnDetector`/`EndpointingConfig` only |
| Config | `config/constants.py` | При необходимости изменить endpoint constants после evidence | Endpoint constants only; no VAD algorithm |
| Tests | `tests/unit/`, `tests/integration/`, `tests/contract/` | Replay and expected events | New/related tests only |
| Evidence | `artifacts/implementation/008-vad-turn-calibration/008-B/` | Save traces, metrics, commands and closeout | Own root |

Protected: `VadCandidate` algorithm, Map-I types, SIP/media, ASR/LLM/TTS and live tools until `008-C`.

## Owner-review решения

| Вопрос | Решение | Статус |
|---|---|---|
| Где материализуется temporal smoothing/endpoint behavior? | В существующем `TurnDetector`; новый `VadSmoother` не вводится молча | `resolved by architecture/APG` |
| Можно ли менять soft/hard constants? | Да, только после evidence и без изменения typed boundary | `resolved by Map-008` |
| Нужен ли ASR для endpoint acceptance? | Нет; A manifest и VAD trace являются первичным входом | `resolved by Map-008 owner instruction` |

Новых открытых owner-review вопросов в пределах B нет.

## 4. Тестовая методика

Для каждого candidate mode/recommended trace:

- прогнать frames в исходном порядке;
- проверить `min_speech_ms` и короткие bursts ниже минимума;
- проверить паузы меньше soft endpoint;
- проверить soft endpoint около 300 ms;
- проверить resume до hard endpoint;
- проверить hard endpoint около 500 ms и длиннее; фактическая выбранная настройка после frame-level calibration — 520 ms;
- проверить две соседние фразы с паузами, чтобы обнаружить merge/split;
- измерить число emitted authoritative events, onset/offset delay, split/merge и turn count;
- повторить replay по тому же trace для детерминизма.

В случае единичных ложных кадров сначала проверяется возможность исправления existing `TurnDetector` policy. Добавление
нового компонента, новой очереди или нового typed edge автоматически переводится в Map-008 blocker и owner review.

## 5. Acceptance и blocker register

`008-B` принимается, если выбранный trace/recommendation преобразуется в ожидаемые ходы на всём corpus, split/merge и
pause/resume измерены, параметры зафиксированы, targeted/contract/regression tests зелёные, а source-map подтверждает
отсутствие нового production owner.

| ID | Триггер | Статус |
|---|---|---|
| `B-008-B-001` | Ни один mode/configuration не даёт проверяемого trade-off без protected contract change | `none until triggered` |
| `B-008-B-002` | Требуется semantic endpointing или новый production component | `none until triggered` |

Красный тест или метрика в existing write-set сначала исправляется corrective pass. Partial/foundation closeout
запрещён.

## 6. Handoff

Closeout передаёт `008-C` selected `VAD_MODE`/endpoint constants, corpus revision/hash, endpoint trace, metrics,
commands, regression и список ограничений. `008-C` не меняет конфигурацию по устному пересказу без evidence.

## 7. Interaction topology и propagation contracts

В этом child plan проверяется существующее typed edge:

```text
VadProcessor.process(frame) → VadDecision
VadDecision → TurnDetector.consume(decision) → tuple[EndpointEvent, ...]
```

Вызов `TurnDetector.consume(decision)` выполняется для каждого упорядоченного решения с исходными
`call_id/channel_id/generation/sequence/timestamp_ns`. Нового adapter, queue или delivery-owner нет.

## 8. Audit владельца поведения и парадигмы реализации

`TurnDetector` остаётся единственным владельцем temporal endpoint state. `008-B` может изменить только
`TurnDetector`/`EndpointingConfig` behaviour и соответствующие constants по evidence; VAD classifier, ASR и
Transcript Assembler не поглощаются этим owner.

## 9. Process invariant audit

| Правило | Применение | Evidence |
|---|---|---|
| Typed-first/owner behavior | Replay использует `VadDecision`; endpoint state остаётся у `TurnDetector` | Contract/source audit |
| Direct in-process materialization | `TurnDetector.consume(decision)` — materialization edge | Replay trace |
| Corrective pass | Split/merge/error исправляется в B write-set и повторяется | Raw output/exit code |
| No silent simplification | Все фразы и паузы corpus сохраняются | Manifest revision |
| Binary closeout | Только `complete`/`blocked` | Closeout audit |

## 10. Architecture invariant audit

| Инвариант | Проверка |
|---|---|
| `VadDecision → TurnDetector.consume` не меняет contract | Contract tests and method audit |
| Soft/hard endpointing остаётся у TurnDetector | Ownership test and endpoint trace |
| Dispatcher/Event Bus/ASR не переносят calibration PCM | Forbidden-path audit |
| Close/cancel and generation scope remain valid | Existing regression and replay scopes |

## 11. Implementation slices

| Срез | Действие | Acceptance | Stop condition |
|---|---|---|---|
| `B1` | Загрузить A corpus/trace и replay decisions | Trace/hash accepted | Missing or contradictory A evidence |
| `B2` | Прогнать thresholds/pause/resume cases | Endpoint trace for each case | Новый owner/boundary required |
| `B3` | При необходимости изменить existing policy/constants | Tests and comparative metrics pass | Protected contract change |
| `B4` | Сохранить endpoint recommendation/closeout | Complete handoff to C | Mandatory evidence missing |

## 12. Test plan и evidence

Targeted host command:

```text
python -m pytest -q tests/unit tests/contract tests/integration/test_map005_speech_resilience.py
```

Target free-threaded command:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys; sys.path.insert(0, \"/mnt/c/devel/sip-bot\"); sys.path.insert(0, \"/mnt/c/devel/sip-bot/src\"); import pytest; raise SystemExit(pytest.main([\"-q\", \"tests/unit\", \"tests/contract\", \"tests/integration/test_map005_speech_resilience.py\"]))"'
```

Expected evidence: endpoint traces, split/merge/onset/offset metrics, selected constants, raw output and exit codes.
Deferred replay or live evidence must carry `evidence_id`, owner, command and promotion condition.

## 13. Fallback/deferred register

| Вариант | Статус |
|---|---|
| Existing VAD mode 2 | baseline до A evidence |
| `_AmplitudeVad` | deterministic comparison only, live fallback запрещён |
| New `VadSmoother`/semantic detector | forbidden without separate boundary plan/review |
| Human/noise generalization | deferred future map |

## 14. Execution report и closeout

Closeout обязан перечислить фактические endpoint policy changes, corpus/trace revision, commands/exit codes,
target/host regression, split/merge/pause/resume metrics, corrective passes, pre-existing/out-of-scope/deferred findings
и handoff в `008-C`. Частичный результат не закрывает B.
