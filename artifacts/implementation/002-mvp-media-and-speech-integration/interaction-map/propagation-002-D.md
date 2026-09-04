# Map-002-I propagation: 002-D

Дата: `2026-09-03`  
Входная ревизия: `Map-002-I revision 5`  
Результат: `accepted by main executor; propagated into revision 5`

## Проверенный output

`002-D` передал следующие typed boundaries:

- `VadDecision` — frame-level data с lifecycle scope, sequence/timestamp,
  duration и decision;
- `EndpointEvent` — speech lifecycle и endpoint events; только
  authoritative `hard_endpoint` завершает ход;
- `AsrHypothesis` и `TranscriptUpdate` — speculative revision snapshots;
- `FinalUserTurn` — единственный authoritative final text payload.

`FinalUserTurn` содержит `call_id`, `channel_id`, `generation`, `turn_id`,
text, revision, finalization timestamp и обязательную
`EndpointEventKind.HARD_ENDPOINT` boundary.

## Проверка propagation

`FinalUserTurn` передаётся напрямую в Skill & Prompt Manager и в прямой typed
вход FSM. В Event Bus отправляется только небольшое `SpeechEvent`/lifecycle
наблюдение; contract test доказывает, что `FinalUserTurn` отвергается bus как
data-plane payload.

Target speech unit/contract, no-GIL import/concurrency и host tests из D
приняты. Native WebRTC operation и heavy faster-whisper inference не
объявляются пройденными в рамках этого checkpoint-а.

## Downstream handoff

- `002-E`: `SpeechEvent` для lifecycle/barge-in и `FinalUserTurn` через прямой
  data-plane вход FSM;
- `002-F`: `FinalUserTurn` плюс bounded context input;
- partial/stable observations остаются non-authoritative и не запускают FSM/TTS.
