# Plan-007-B: подключение WebRTC VAD к application speech boundary

Уровень: `child plan`  
Статус owner review: `accepted — inherited from Map-007 owner approval, 2026-09-13; no additional owner question`  
Статус исполнения: `complete — explicit VAD_MODE=2 is part of RuntimeConfig; existing typed boundary tests pass, 2026-09-13`  
Родительская карта: [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md)  
Предшественник: [`plan-007-A-webrtc-vad-runtime-gate.md`](plan-007-A-webrtc-vad-runtime-gate.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21  
Evidence root: `artifacts/implementation/007-webrtc-vad/007-B/`

## 1. Цель и результат

Подключить прошедший `007-A` WebRTC binding к существующей application composition, сохранив разделение owners и
typed propagation `PcmFrame → VadProcessor.process(frame) → VadDecision → TurnDetector.consume(decision)`. Режим
WebRTC VAD должен быть явным значением `RuntimeConfig.vad_mode`, полученным из `config.constants.VAD_MODE`; скрытый
amplitude threshold не участвует в WebRTC path.

Результат — targeted code/contract evidence, показывающий, что один call generation может использовать
`WebRtcVadCandidate` с конфигурационным mode, а `VadDecision`, endpoint events, close/cancel и ASR fan-out не изменились.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на `007-B` | Проверка | Stop condition |
|---|---|---|---|---|
| [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md) | Live path переходит на WebRTC; deterministic amplitude остаётся только test double; новые owners/edges запрещены | Менять только candidate construction и необходимые tests/config | Source/diff audit + targeted tests | Появился fallback/delivery owner |
| [`plan-007-A-webrtc-vad-runtime-gate.md`](plan-007-A-webrtc-vad-runtime-gate.md) | Использовать только exact binding, прошедший target no-GIL/operation gate | B не запускается до A complete | A closeout manifest | A blocked или evidence неполно |
| [`architecture.md`](../architecture.md) | VAD классифицирует frame, Turn Detector владеет endpointing; PCM data plane не проходит через Dispatcher | Не переносить state/timing в adapter и не менять bus | Ownership/forbidden-path tests | Boundary/owner change |
| [`technical-specification.md`](../technical-specification.md) | mono PCM S16LE, negotiated per-call media profile, VAD/endpoint params — config constants | Construction принимает фактический `PcmFrame.profile`; mode не является скрытым произвольным default | Config/profile assertions | Нужна неописанная conversion |
| [`development-guidelines.md`](../development-guidelines.md) §2–§3 | Typed-first, direct materialization и exact consumer input method; inter-thread only bounded thread-safe queue | Сохранить `VadProcessor.process` и `TurnDetector.consume`; не вводить queue/manager без необходимости | Contract/architecture audit | Actual output rejected |
| [`development-guidelines.md`](../development-guidelines.md) §6–§8 | Targeted/regression/corrective pass; binary child closeout; no silent simplification | Реальный код и tests должны быть зелёными до C | Raw results and closeout | Category-4 gap or incomplete acceptance |

## 3. Граница задачи

**Входит:** construction `WebRtcVadCandidate`, явный `VAD_MODE`, application unit/contract tests,
call-generation lifecycle test, endpoint regression и propagation evidence.

**Не входит:** binding installation/no-GIL (A), live Baresip gates (C), новый VAD/endpoint algorithm, semantic detector,
ASR/LLM/TTS/SIP, изменение public contracts и закрытых Map-005/Map-006 evidence.

**Protected baseline:** `PcmFrame`, `VadDecision`, `EndpointEvent`, `VadProcessor`, `SpeechIngress`, `TurnDetector`,
PcmFanOut, Map-I revision 21, 300/500 ms endpointing, one conversation, no silent fallback.

## 4. Source-map и write-set

| Область | Файл | Текущее поведение | Целевое | Допустимый write-set |
|---|---|---|---|---|
| Config | `config/constants.py` | Есть amplitude threshold, нет явного WebRTC mode | Явный `VAD_MODE=2`, если construction использует config | Только VAD config constant; без изменения endpoint policy |
| Construction | `src/sip_bot/runtime_wiring.py` и/или composition entrypoints | Live tools вручную создают `VadProcessor(_AmplitudeVad())` | Реальный application construction использует `VadProcessor(WebRtcVadCandidate(mode=...))` | Только VAD construction/import и required wiring symbols |
| Candidate | `src/sip_bot/speech/vad.py` | WebRTC adapter уже существует | Используется exact binding из A; API остаётся прежним | Только compatibility fix, если A подтвердил фактическую необходимость |
| Speech tests | `tests/unit/`, `tests/integration/`, `tests/contract/` | Mostly injected fake backend | Доказан output/lifecycle with WebRTC candidate and existing fakes retained | VAD/speech targeted tests only |
| Evidence | `artifacts/implementation/007-webrtc-vad/007-B/` | Нет | Contract/source/runtime integration manifest | Own evidence root |

Не менять live tool selection — это отдельный C write-set. Общие docs/registry/backlog меняет main executor после
проверок. Protected files and unrelated worktree changes не трогать.

## 5. Interaction topology и propagation

`007-B` реализует только существующие рёбра:

```text
PcmFanOut subscription("vad")
  → SpeechIngress.process_frame(frame)
      → VadProcessor.process(frame)
          → WebRtcVadCandidate.is_speech(frame.pcm_s16le, frame.profile.sample_rate_hz)
          → VadDecision
      → TurnDetector.consume(vad_decision)
          → EndpointEvent
```

Exact consumer methods: `SpeechIngress.process_frame(PcmFrame)`, `VadProcessor.process(PcmFrame)`,
`TurnDetector.consume(VadDecision)`. Вызов in-process direct; audio не публикуется через Dispatcher. Условия close/cancel
и stale сохраняются существующими `SpeechIngress.cancel()/close()` и per-generation wiring. Новый VAD не возвращает
control command, не делает transfer и не завершает turn самостоятельно.

Если фактический binding требует иного input format, это не исправляется скрытым conversion helper: создаётся APG gap
и проверяется propagation. Ожидаемый путь — уже предоставленный 8 kHz mono PCM16 20 ms.

## 6. Audit владельца поведения и парадигмы реализации

Владелец frame classification — `VadProcessor` через injected `VadCandidate`; владелец stateful endpoint semantics —
`TurnDetector`; владелец composition — существующий `SpeechIngress`/runtime wiring. `007-B` не создаёт нового owner,
facade или delivery component. Для одного call generation candidate вызовы serial в speech consumer context.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Менять ли typed speech contracts? | Нет, если `007-A` подтвердил bool input/output; `VadDecision.confidence=None` сохраняется | Downstream code не переписывается | `resolved by Map-I` |
| Удалять ли deterministic backend? | Нет; оставить только в явно deterministic unit/contract paths | Не выдаётся за live evidence и не является runtime fallback | `resolved by Map-007` |
| Какой mode? | Начальный baseline — текущий `mode=2`; при materialization сделать `VAD_MODE=2` явным | Изменение mode требует фактического evidence | `resolved baseline` |
| Что делать при contract mismatch? | Остановить B как APG gap; не добавлять скрытый adapter/conversion | Owner review только при фактическом gap | `resolved by APG` |

Открытых owner-review вопросов нет.

## 8. Process invariant audit

| Инвариант | Действие | Evidence |
|---|---|---|
| Typed-first | Использовать существующие `PcmFrame`, `VadDecision`, `EndpointEvent` | Contract tests |
| Ownership | Не переносить endpoint state в WebRTC adapter | Ownership audit |
| Direct data plane | VAD получает frame через existing fan-out; bus не переносит audio | Fan-out test |
| Scope | Не менять ASR/endpoint policy/SIP/AI | Diff audit |
| Corrective pass | Любой red test исправляется в write-set и повторяется | Raw targeted/regression output |
| Binary closeout | B complete только при полном acceptance | Closeout |

## 9. Architecture invariant audit

- negotiated `PcmFrame.profile` используется как источник sample rate/channel/format;
- WebRTC VAD получает 10/20/30 ms mono PCM S16LE, baseline — 8 kHz/20 ms;
- frame-level decision не завершает пользовательский ход: hard endpoint остаётся у `TurnDetector`;
- `VadDecision` сохраняет call/channel/generation/sequence/timestamp;
- speech errors не откатываются к amplitude в live path;
- `PcmFanOut` и ASR consumer остаются независимыми.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| `B1` | Принять A manifest и импортировать exact candidate в application target | A evidence valid; candidate constructible | A blocked/incomplete |
| `B2` | Добавить/синхронизировать explicit mode configuration и construction | No hidden amplitude threshold; mode observable | Config boundary unexpectedly changes |
| `B3` | Проверить candidate → `VadDecision` → endpoint sequence | Existing contracts and endpoint transitions pass | Contract mismatch |
| `B4` | Проверить close/cancel/stale and fan-out independence | No cross-generation result; ASR consumer unaffected | Lifecycle/cycle gap |
| `B5` | Targeted + regression + handoff to C | All relevant tests pass and evidence complete | Mandatory red after corrective pass |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-007-B-001` | `B1` | `007-A` не имеет complete evidence или exact candidate не импортируется в application runtime | B/C | project owner | A closeout + target import | `none until triggered` |
| `B-007-B-002` | `B2–B3` | Текущий typed consumer отвергает фактический WebRTC output | Application propagation | project owner | Contract failure/source inspection | `none until triggered` |
| `B-007-B-003` | `B4` | WebRTC candidate lifecycle требует нового boundary/owner или shared instance leaks state | B closeout/C | project owner | Lifecycle test + APG gap | `none until triggered` |

Обычная ошибка реализации/test fixture исправляется в текущем write-set и не является blocker.

## 12. Test plan и evidence

Целевые проверки:

- `python -m pytest -q tests/unit/test_speech_ingress.py tests/unit/test_map005_speech_resilience.py`;
- `python -m pytest -q tests/integration/test_map005_speech_resilience.py tests/integration/test_runtime_wiring.py`;
- отдельный target-runtime test с exact `WebRtcVadCandidate` без fake backend;
- invalid sample-rate/channel/frame-size matrix;
- speech/pause/resume/hard endpoint sequence с реальными WebRTC decisions;
- cancel/close/new generation and fan-out isolation;
- `python -m compileall -q src tests config`;
- document registry/backlog checks после синхронизации main executor.

Команды, runtime, stdout/stderr, exit codes и evidence IDs сохраняются в `007-B/`. Host Python может применяться для
детерминированных тестов только как вспомогательная проверка; application evidence остаётся за target CPython 3.14t.

## 13. Fallback/deferred register

| Что введено | Ограничение | Статус |
|---|---|---|
| Injected fake/amplitude backend | Только deterministic tests; не live/runtime fallback | `allowed test double` |
| Hidden compatibility conversion | Не вводится; mismatch становится APG gap | `forbidden` |
| Process isolation | Только после отдельного owner decision/plan | `deferred unless triggered` |

## 14. Execution report и closeout

Closeout должен перечислить фактические файлы/diff, exact constructor, config value, tests/commands/exit codes, A evidence
reference, propagation result `I2`, pre-existing/out-of-scope findings и handoff в `007-C`. Статус только `complete` или
`blocked`; partial/foundation claims запрещены.
