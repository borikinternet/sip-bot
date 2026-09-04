# Plan-002-E closeout

Date: 2026-09-03  
Status: `complete` for the approved code/evidence scope

The initial delegated closeout intentionally left formal plan closure and
downstream I1-I2 propagation to the main executor. That propagation is now
complete and recorded in the interaction-map evidence root.

## Delivered

- Process-local `ControlEventBus` singleton with typed control-only values,
  bounded subscriber queues, FIFO fan-out, non-blocking overflow reporting,
  call-scoped close/unsubscribe and wakeable subscription shutdown.
- Non-blocking serialized `Dispatcher` with bounded ingress, explicit
  attach/pump/drain APIs, optional daemon loop, and error statistics.
- Immutable speech, finalized-turn, playback, transfer and structured-decision
  event values.
- Allowlisted `answer`, `clarify`, `offer_transfer`, `transfer` and `hangup`
  validation; arbitrary SIP actions and malformed decision fields are rejected.
- `DialogueFSM` with call open/answer/listen/think/playback/offer/confirm/
  transfer/terminal states, input/playback channel generations, idempotent
  close/cancel orchestration, barge-in, stale operation/generation guards,
  unknown-answer transfer path, decline recovery, protocol/media failure and
  new-call re-entry.

## Files touched by this slice

- `src/sip_bot/control/event_bus.py`
- `src/sip_bot/control/dispatcher.py`
- `src/sip_bot/control/__init__.py`
- `src/sip_bot/control/lifecycle.py` (public channel snapshot helper plus formatting)
- `src/sip_bot/dialogue/events.py`
- `src/sip_bot/dialogue/actions.py`
- `src/sip_bot/dialogue/fsm.py`
- `src/sip_bot/dialogue/__init__.py`
- `tests/contract/test_control_events.py`
- `tests/unit/test_dialogue_fsm.py`

## Verification

- Delegated `python -m pytest -q tests\unit tests\contract`: **59 passed**.
- Final main-executor rerun after two additional contract assertions:
  `python -m pytest -q tests\unit tests\contract`: **61 passed**.
- Targeted `compileall`: **exit 0**.
- 002-E Ruff scope: **all checks passed**.
- Delegated full importlib collection: **59 passed, 3 existing out-of-scope
  SIP integration failures** because the Windows host lacks `baresip`; no
  002-E test failed.
- Final main-executor full importlib collection: **61 passed, 3 existing
  out-of-scope SIP integration failures** for the same unavailable Windows
  `baresip` executable; no 002-E test failed.

## Handoff and findings

The actual event/command names, channel generation and cancellation rules are
captured in `state-trace.json` for downstream F/G/H/J consumers. Shared docs,
Map-002-I, parent plan, registry and backlog were not changed per the strict
delegated write-set. Existing SIP integration environment failures remain
outside this slice and require the target Linux/WSL SIP stand.

## Boundary handoff

Input contract revision: **Map-002-I revision 4**. The following output types
are factual implementation results of this slice, but remain candidates until
the main executor completes propagation checkpoints I1-I2:

| Output candidate | Immediate consumers needing I1-I2 |
|---|---|
| `SpeechEvent` and speech operation/generation metadata | 002-F and dialogue integration |
| `StructuredDecision` and `DialogueCommand(START_INFERENCE)` | 002-F/002-G |
| `DialogueCommand(APPROVE_ANSWER/OPEN_CHANNEL/CANCEL/CLOSE_CHANNEL)` and `PlaybackEvent` | 002-H |
| `DialogueCommand(TRANSFER/REPORT/HANGUP)` and `TransferResult` | 002-J and SIP control integration |
| `ControlEvent`/`NormalizedSipEvent` terminal, media and protocol signals | SIP/media adapter and parent integration |

Large text and audio payloads are deliberately excluded from the event bus.
`FinalUserTurn` is a direct data-plane payload and is rejected by the bus;
FSM receives it through its direct typed input. Any contract change discovered
during later integration requires a corrective pass for this slice.

## Main-executor acceptance and propagation

`2026-09-03` main executor accepted the delegated implementation and verified
the control-only bus against Map-I revision 5. The FSM state trace covers
normal answer, barge-in, unknown-answer/offer-transfer, explicit transfer,
terminal, cancellation and re-entry. Current unit/contract evidence is
`64 passed`; `compileall` is green. The three full-suite Windows failures are
external SIP-stand failures caused by the absent `baresip` executable and do
not fail the E slice.

The plan-level status is now formally `complete`.
