# Plan-008-C: application/live validation калиброванного VAD

Уровень: `child plan`  
Статус owner review: `accepted by explicit execution instruction`  
Статус исполнения: `complete`  
Родительская карта: [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md)  
Предшественник: [`plan-008-B-vad-turn-detector-calibration.md`](plan-008-B-vad-turn-detector-calibration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21  
Evidence root: `artifacts/implementation/008-vad-turn-calibration/008-C/`

## 1. Цель и границы

Проверить, что выбранные в `008-A/B` mode и endpoint parameters действительно проходят существующий application/live
path, не меняя typed boundary и не превращая ASR в VAD oracle.

Входит:

- source audit live construction;
- применение evidence-based `VAD_MODE`/endpoint constants в существующем runtime;
- clean-start application/live validation с negotiated PCMU profile;
- проверка VAD trace, endpoint events, ASR fan-out, close/stale behavior;
- optional offline/full-flow ASR diagnostic и сохранение limitations.

Не входит: новая SIP/media архитектура, новый VAD/TurnDetector component, production noise campaign и изменение
Map-I без отдельного propagation/review.

## Применимые документы и извлечённые правила

Применяются parent Map-008, Map-007, Map-I revision 21, `architecture.md`, `technical-specification.md` и
`development-guidelines.md`. В этой границе materialized rules — сохранение typed speech path, отсутствие live
fallback, main-executor ownership финального gate и запрет использовать ASR как VAD oracle.

## Граница задачи

Входит только применение и проверка решения A/B в существующем application/live path, downstream diagnostic и
evidence. Не входят новый production component, новая SIP/media topology, изменение Map-I без propagation/review и
production quality campaign.

## 2. Материализованные правила

| Правило | Применение | Проверка/stop condition |
|---|---|---|
| Existing `PcmFrame → VadProcessor → VadDecision → TurnDetector` | Live path использует ту же typed chain | Contract/source audit; mismatch blocks |
| WebRTC live, amplitude только deterministic test double | Не допускать fallback после неудачного запуска | Live source audit; live amplitude is blocker |
| SIP/media callback не ждёт ASR/LLM/TTS | Калибровка не добавляет blocking dependency | Live counters and protocol regression |
| ASR is downstream diagnostic | Проверять text integrity после endpointing, не менять VAD labels | Dependency audit; circular use blocks |
| Final live gate выполняет main executor | GPU/live resource и acceptance не передаются неподтверждённому handoff | Exact command/exit code |

## 3. Source-map и write-set

| Область | Файл | Действие | Write-set |
|---|---|---|---|
| I1/J4 construction | `tools/live_i1_gate.py`, `tools/j4_full_live_gate.py` | Подставить selected configuration и добавить только relevant assertions | VAD/endpoint construction and evidence assertions |
| Runtime config | `config/constants.py`, `src/sip_bot/config.py` | Синхронизировать selected mode/endpoint values | Existing config symbols only |
| Tests | Existing targeted/integration suites | Проверить selected application composition | Related tests only |
| Evidence | `artifacts/implementation/008-vad-turn-calibration/008-C/` | Save commands, manifests, raw logs and closeout | Own root |

Protected: ASR/LLM/TTS logic, SIP/media adapter, Map-I contracts, Map-007 historical evidence and unrelated docs.

## Owner-review решения

| Вопрос | Решение | Статус |
|---|---|---|
| Можно ли переоткрыть algorithm selection? | Нет; C проверяет выбранную конфигурацию WebRTC VAD | `resolved by Map-007/Map-008` |
| Можно ли использовать ASR для изменения VAD labels? | Нет; ASR только downstream diagnostic | `resolved by Map-008` |
| Кто запускает live gate? | Main executor, последовательно после A/B evidence | `resolved by development-guidelines` |

Новых открытых owner-review вопросов в пределах C нет.

## 4. Acceptance

`008-C` принимается, если:

- live construction использует selected `WebRtcVadCandidate`, а не `_AmplitudeVad`;
- negotiated media profile зафиксирован и совместим с VAD frames;
- VAD/endpoint trace соответствует calibrated expectations в пределах заявленных ограничений;
- ASR fan-out и downstream text diagnostic не показывают contract regression;
- close/cancel/stale path остаётся корректным;
- relevant host/target regression и live command имеют raw output/exit code;
- report/runbook/architecture/TЗ/registry/backlog синхронизированы;
- результат не заявляет production noise/recall quality.

## 5. Blocker register

| ID | Триггер | Статус |
|---|---|---|
| `B-008-C-001` | Selected configuration не воспроизводится на existing application/live boundary | `none until triggered` |
| `B-008-C-002` | Требуется новый media/audio edge, boundary change или новый VAD owner | `none until triggered` |
| `B-008-C-003` | Обязательное target/live evidence невозможно получить из-за внешнего стенда/ресурса | `none until triggered` |

Красный application test в утверждённом write-set исправляется corrective pass. Новый owner/boundary/fallback — blocker
и owner review.

## 6. Handoff и closeout

Closeout передаёт Map-008 фактический selected configuration, live manifest, endpoint/VAD trace, regression,
downstream ASR diagnostic, limitations и следующий workshop step. `complete` возможен только после полного map gate;
partial/foundation status запрещён.

## 7. Interaction topology и propagation contracts

Проверяется существующее application/live propagation:

```text
PJMEDIA/adapter → PcmFrame
PcmFrame → VadProcessor.process(frame)
VadProcessor → VadDecision
VadDecision → TurnDetector.consume(decision)
TurnDetector → EndpointEvent / FinalUserTurn
```

Точные consumer methods — `VadProcessor.process(frame)` и `TurnDetector.consume(decision)`. PCM не передаётся через
Dispatcher/Event Bus; compact control events остаются control plane. Изменение output type или нового edge — blocker
до propagation/review.

## 8. Audit владельца поведения и парадигмы реализации

`008-C` не становится владельцем VAD или endpoint state. Он только применяет решение A/B в уже существующих
construction points и проверяет live evidence. Main executor владеет финальным live gate; ASR остаётся downstream
diagnostic и не изменяет VAD labels.

## 9. Process invariant audit

| Правило | Применение | Evidence |
|---|---|---|
| Final live gate — main executor | GPU/resource/live acceptance не делегируется без проверки | Exact command and exit code |
| No silent fallback | Live construction must be WebRTC; amplitude only test double | Source audit |
| Corrective pass | Красный application test исправляется и повторяется | Raw rerun evidence |
| Typed/direct data plane | Existing methods/edges preserved | Contract and source audit |
| Binary closeout | C complete только после полного evidence | Closeout audit |

## 10. Architecture invariant audit

| Инвариант | Проверка |
|---|---|
| Negotiated PCMU profile supplies valid VAD frame | Live media manifest |
| `PcmFrame → VadDecision → EndpointEvent` unchanged | Propagation/contract tests |
| SIP callback does not wait for ASR/LLM/TTS | Live counters and protocol regression |
| close/cancel/stale generation stays safe | Existing runtime tests and live trace |

## 11. Implementation slices

| Срез | Действие | Acceptance | Stop condition |
|---|---|---|---|
| `C1` | Проверить B handoff и source construction | Selected mode/config found in live tool | Missing/contradictory B evidence |
| `C2` | Выполнить application targeted/target tests | Contract and regression pass | Contract mismatch |
| `C3` | Выполнить clean-start I1/J4 validation | Live WebRTC, media and endpoint evidence | External stand/resource blocker |
| `C4` | Optional ASR diagnostic and closeout | Downstream quality recorded without circular label | ASR ownership/boundary change |
| `C5` | Sync docs/registry/backlog and handoff | All evidence and limitations linked | Open category-4 gap |

## 12. Test plan и evidence

Target host/target regression uses the commands and executables selected by the accepted B handoff. Live command template:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && <combined-free-threaded-python> tools/live_i1_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-C/i1-YYYYMMDD-rN --timeout 240'
```

For complete scenario validation use the existing `j4_full_live_gate.py` with a new output root. Expected evidence is
JSON/live manifest with executable/GIL, candidate/mode, negotiated media profile, VAD decisions, endpoint trace, ASR
fan-out, close/stale status, errors, commands and exit code. Any deferred check must include `evidence_id`, owner,
command and promotion condition.

## 13. Fallback/deferred register

| Вариант | Статус |
|---|---|
| `_AmplitudeVad` in live path | forbidden |
| ASR as VAD oracle | forbidden; diagnostic only |
| New audio edge/component | deferred to separate map/review |
| Production noise/precision/recall claim | out of scope |

## 14. Execution report и closeout

Closeout обязан перечислить source audit, changed files/symbols, B handoff, commands/exit codes, live manifest,
regression, optional ASR diagnostic, recording ownership, pre-existing/out-of-scope/deferred findings и следующий
workshop step. C закрывается только `complete` или `blocked` по фактическому evidence.
