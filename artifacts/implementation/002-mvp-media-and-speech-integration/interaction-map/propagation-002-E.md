# Map-002-I propagation: 002-E

Дата: `2026-09-03`  
Входная ревизия: `Map-002-I revision 5`  
Результат: `accepted by main executor; propagated into revision 5`

## Проверенный output

`002-E` материализовал process-local control boundary:

- bounded FIFO `ControlEventBus` с несколькими подписчиками, close,
  unsubscribe и observable overflow;
- последовательный `Dispatcher`/`DialogueFSM`;
- typed `SpeechEvent`, `StructuredDecision`, `DialogueCommand`,
  `PlaybackEvent`, `TransferResult` и lifecycle envelopes;
- allowlisted semantic actions, channel generations, cancellation,
  terminal/re-entry и stale-result suppression.

Event Bus не переносит PCM, ASR/TTS streams, RAG fragments и `FinalUserTurn`.
`FinalUserTurn` — direct data-plane payload, который FSM принимает отдельным
typed входом; Event Bus получает только небольшие control/lifecycle events.

## Проверка

После main corrective pass: `64 passed` для unit/contract текущего дерева,
`compileall: PASS`. Полный importlib-прогон: 64 passed и 3 внешних SIP
failure из-за отсутствующего Windows executable `baresip`; target stand
evidence уже закрыт в `001-S`/`002-B`.

State trace подтверждает normal answer, barge-in, unknown-answer/offer-transfer,
explicit transfer, terminal, cancellation и call re-entry.

## Downstream handoff

- `002-F`: FSM-approved skill/profile и lifecycle control; final text остаётся
  direct data-plane;
- `002-G`: typed structured decision/status/cancel control и facade lifecycle;
- `002-H`: playback/channel commands и `PlaybackEvent`;
- `002-J`: transfer/report commands и `TransferResult`.
