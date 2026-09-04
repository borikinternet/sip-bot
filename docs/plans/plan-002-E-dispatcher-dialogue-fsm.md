# Plan-002-E: Dispatcher и Dialogue FSM

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-03`  
Статус исполнения: `complete` — implementation и propagation закрыты `2026-09-03`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Создать центральный Dispatcher и Dialogue FSM, которые последовательно изменяют состояние одного разговора, принимают
нормализованные control events, управляют открытием/закрытием каналов и разрешают структурированные действия. Dispatcher
не переносит audio/text payload, не ждёт ASR/LLM/TTS и не даёт LLM прямого SIP-доступа.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Диалог должен помнить контекст, поддерживать barge-in, unknown-answer и transfer | FSM содержит состояния и transitions для всех обязательных сценариев | State-machine/integration tests | Сценарий не имеет terminal/recovery path |
| [`architecture.md`](../architecture.md) | Dispatcher владеет control plane, но не payload | Используется прямой data plane и typed control event | Architecture audit | Dispatcher проксирует аудио/крупный текст |
| [`technical-specification.md`](../technical-specification.md) | SIP replies local, config constants, cancellation and one call | FSM не ждёт protocol reply и закрывает scoped channels | Cancellation/state tests | FSM blocks local SIP reaction |
| [`ADR-001-llm-and-dialogue-manager.md`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM proposes, FSM executes | Structured decision validated before action | Decision validation | LLM emits SIP command |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Cycles, control/data planes and close semantics explicit | FSM consumes candidate contracts and returns control commands | Map-I propagation | Transition bypasses cycle register |

## 3. Граница задачи

**Цель:** main dispatcher loop, process-local control event routing, Dialogue FSM, action validation, channel commands and
cancellation orchestration.

**Входит:** event envelope/subscription delivery for control plane, call states, speech states, answer/playing/transfer
states, terminal handling, structured decision validation, channel open/close/cancel commands.

**Не входит:** SIP transaction implementation (`002-B`), PCM/audio payload, ASR/VAD, prompt/RAG, Ollama HTTP, TTS codec or
fake operator implementation.

**Protected baseline:** one Dispatcher-owned state machine, direct data plane, SIP adapter local protocol reactions,
structured LLM decisions only, one conversation, no blocking main loop.

**Предположения:** `002-A` provides runtime/lifecycle; event bus is process-local and control-only; component boundaries
remain those of Map-I.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Dispatcher | `src/sip_bot/control/dispatcher.py` | Отсутствует | Non-blocking serialized control loop | Нет runtime | Создать owner component |
| Event bus | `src/sip_bot/control/event_bus.py` | Отсутствует | Process-local control event fan-out | Scope/ordering not implemented | Create bounded control router |
| Dialogue FSM | `src/sip_bot/dialogue/fsm.py` | Отсутствует | Explicit states/transitions | No implementation | Create state machine |
| Actions | `src/sip_bot/dialogue/actions.py` | Отсутствует | Typed approved actions/commands | Decision validation absent | Implement allowlist validator |
| Tests | `tests/unit/test_dialogue_fsm.py`, `tests/contract/test_control_events.py` | Отсутствуют | State/cancel/re-entry tests | No fixtures | Create deterministic event fixtures |
| Evidence | `artifacts/.../002-E/` | Отсутствует | Transition/event logs | No app evidence | Create at execution |

Допустимый write-set: `src/sip_bot/control/`, `src/sip_bot/dialogue/`, control/FSM tests и собственный evidence root.
Изменения в data-plane owners и SIP implementation запрещены.

## 5. Interaction topology и propagation контрактов

Dispatcher принимает protocol/application events от `N1/N2/N3`, speech lifecycle event от `N8`, structured decision/status
от `N11` и playback/transfer events от `N15/N16`. Он выдаёт typed control commands: channel open/close/cancel,
approved skill/profile, playback control, SIP semantic command и report command. Audio and large text payloads bypass it.

Event bus является process-local control-plane fan-out с owner в Dispatcher; подписчики не получают доступ к payload
channels и не могут изменить FSM напрямую. `FinalUserTurn` не публикуется в bus: он передаётся в FSM прямым typed
data-plane входом, а в bus публикуется только небольшое speech lifecycle event. Terminal events and barge-in are
re-entrant: they cancel active operations, close old channels idempotently and then admit new state transitions.

## 6. Audit владельца поведения и парадигмы реализации

Dispatcher owns ordering and subscription lifecycle; FSM owns state and transition guards; action validator owns allowlist
of semantic commands. Event bus is transport/fan-out infrastructure and does not own dialogue semantics. Pure transition
predicates may be functions; any state/channel mutation remains on owner objects.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Нужна ли отдельная event bus? | Да, как process-local singleton universal control-plane component; она не передаёт PCM или крупный текст | Все control subscribers получают typed events, Dispatcher владеет semantics, payload остаётся в direct channels | `resolved: ADR-004, owner review accepted 2026-09-02` |
| Кто исполняет решение LLM? | Dispatcher/FSM после validation | LLM не вызывает SIP/transfer напрямую | `resolved` |
| Как реагировать на terminal event во время inference? | Немедленно закрыть/cancel channels, stale result отбросить | FSM не ждёт LLM/ASR/TTS | `resolved` |
| Какие дополнительные dialogue states нужны сверх demo-flow? | Использовать только состояния обязательного demo-flow; при фактической необходимости нового состояния применять APG gap/owner-review protocol | Не расширять scope молча; заранее утверждённое правило не является открытым вопросом | `resolved: APG scope/gap rule; review only if triggered` |

## 8. Process invariant audit

- Event bus is not an audio/text bus and has explicit bounded delivery/close behavior.
- Dispatcher loop contains no blocking inference or SIP wait.
- Every transition has deterministic tests and terminal/re-entry behavior.
- Commands: `python -m pytest -q tests/unit tests/contract`; integration tests use stubs before real components.
- Any new state or command is recorded in Map-I/ADR as applicable.

## 9. Architecture invariant audit

- Dispatcher owns control plane and semantic SIP actions.
- Local SIP adapter answers protocol transactions independently.
- Audio and large text payload never transit the Dispatcher/event bus.
- Closing a channel cancels active work and suppresses stale outcomes.
- Speculative results cannot change FSM, transfer or hangup.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| E1 | Define control event/command envelopes and event bus lifecycle | Subscribers receive typed events with bounded/close semantics | Payload leakage or unbounded queue |
| E2 | Implement FSM states and transition guards | Call, speech, answer, playback, unknown/transfer and terminal paths tested | Missing terminal/re-entry path |
| E3 | Implement action validation and channel orchestration | Structured decisions map only to allowlisted actions | LLM can produce arbitrary SIP action |
| E4 | Integrate deterministic upstream/downstream stubs | Final turn, barge-in, close and cancellation visible | Dispatcher blocks on component |
| E5 | Pass control contracts to F/G/H/J | Downstream plans receive actual event/command fields | Map-I revision not updated |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-E-001` | весь plan | Child plan не прошёл owner review | FSM implementation | project owner | APG review | `resolved — owner review accepted 2026-09-03` |
| `B-002-E-002` | E1 | Event bus semantics conflict with Map-I/control ownership | All control integration | project owner | [`state-trace.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-E/state-trace.json), control contract tests и `FinalUserTurn` bus-rejection test | `resolved — process-local control-only bus; direct final text path` |
| `B-002-E-003` | E2–E3 | No safe terminal/re-entry transition exists | Integration and demo-flow | project owner | [`state-trace.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-E/state-trace.json) и 64 unit/contract tests | `resolved — terminal, re-entry, barge-in и stale suppression verified` |

## 12. Test plan и evidence

- unit transition matrix for normal answer, clarification, unknown-answer, transfer and hangup;
- protocol event during AI operation: BYE, CANCEL, OPTIONS, re-INVITE/hold/resume and media failure as normalized events;
- barge-in closes playback and admits new user turn;
- event bus multi-subscriber ordering, bounded behavior, unsubscribe/close and terminal event re-entry;
- stale decision/playback outcome after close is ignored;
- evidence includes state trace, event sequence, command sequence, cancellation outcomes and exit codes.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| One Dispatcher/main loop | MVP has one conversation | Does not constrain workers/processes | Map-002 and later scaling work | `approved scope boundary` |
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete; owner review accepted; implementation/evidence and main propagation closed 2026-09-03`.
Фактический control contract и direct final-text rule переданы в Map-I revision 5; propagation evidence находится в
[`propagation-002-E.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-E.md).
