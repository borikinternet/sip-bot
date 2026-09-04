# 002-D closeout

Дата: `2026-09-03`  
Execution status: `complete`  
Owner review: `accepted — 2026-09-03`  
Heavy GPU inference: `not run`

## Scope result

Плановый scope выполнен в пределах speech ingress:

1. D1 — immutable typed contracts для `VadDecision`, endpoint events, `AsrAudioChunk`, `AsrHypothesis`,
   `TranscriptUpdate` и `FinalUserTurn` с lifecycle scope.
2. D2 — `WebRtcVadCandidate` с lazy native import, WebRTC frame validation и `VadProcessor`; deterministic backend
   использован для operation evidence без установки/загрузки native/GPU зависимости.
3. D3 — `TurnDetector` с явным state machine, `300 ms` soft endpoint, `500 ms` hard endpoint, resume и
   minimum-speech policy.
4. D4 — `StreamingAsrAdapter`, generation/cancellation suppression и `TranscriptAssembler` со stable-prefix,
   revision replacement и обязательной hard-boundary finalization.
5. D5 — локальный composition boundary `SpeechIngress`; authoritative final payload появляется только у hard
   endpoint и не выдаётся через Dispatcher.

## Actual changed files

```text
src/sip_bot/speech/__init__.py
src/sip_bot/speech/contracts.py
src/sip_bot/speech/vad.py
src/sip_bot/speech/endpointing.py
src/sip_bot/speech/asr_adapter.py
src/sip_bot/speech/transcript_assembler.py
src/sip_bot/speech/ingress.py
tests/unit/test_speech_ingress.py
tests/contract/test_speech_contracts.py
artifacts/implementation/002-mvp-media-and-speech-integration/002-D/*
```

## Commands and results

Полный журнал команд, stdout/stderr и exit codes находится в [`commands.md`](commands.md). Ключевые результаты:

| Command lane | Exit | Result |
|---|---:|---|
| host speech unit/contract | `0` | `11 passed in 0.04s` |
| target speech unit/contract, free-threaded CPython | `0` | `11 passed in 0.42s` |
| target speech compileall | `0` | no output |
| target import/no-GIL | `0` | `Py_GIL_DISABLED=1`, GIL false before/after |
| target controlled concurrency | `0` | four independent results, GIL false |
| document registry audit | `0` | `36/36`, PASS |
| task backlog audit | `0` | `6/6`, PASS |
| full host regression | `1` | 3 pre-existing `DialogueFSM` failures; no speech failure |

## APG §5.8B classification

- Исправлены локальные ошибки первого targeted run: тест ошибочно считал 30 ms недопустимым VAD frame, а Assembler
  ошибочно применял minimum stable-prefix length к явно переданному stable prefix.
- Исправлен синтаксически некорректный ручной concurrency one-liner; повторная команда прошла.
- Первый target `-I` pytest collection не увидел project-root `config/` через существующий unit `conftest.py`. Общий
  launcher менять запрещено; повторный target запуск выполнил тот же код через явный `sys.path` bootstrap и прошёл.
- Ни один из этих результатов не является external/API blocker. Blocker register для локального implementation slice:
  `none`.

## Pre-existing and out-of-scope

- Full host regression содержит pre-existing ошибки `DialogueFSM` в `tests/unit/test_dialogue_fsm.py`; файлы находятся
  вне write-set и не менялись.
- Native WebRTC VAD и heavy faster-whisper inference не запускались по явному ограничению execution. Это не скрыто как
  native operation pass: deterministic candidate operation подтверждает только application contract. Реальный native
  import/operation остаётся отдельным controlled runtime task.
- `002-C`, Dispatcher/FSM, Map-I, родительская карта, registry и backlog не менялись.

## Contract handoff

### Input contract revision

Работа выполнена на входной [`Map-002-I revision 4`](../../../../docs/plans/plan-002-I-boundary-interaction-map.md),
с propagated output от `002-B` и `002-C`:

- `PcmFrame`: per-call `profile`, `call_id`, `channel_id`, `generation`, sequence и monotonic timestamp от media
  boundary;
- `AsrAudioChunk`: bounded mono PCM S16LE chunk от audio accumulator/chunker; `002-C` передал этот тип как accepted
  upstream contract и отдельный input boundary.

Локальные speech-типы ниже являются результатом реализации `002-D` и остаются candidate types до следующего
propagation checkpoint. Они не заменяют revision 4 и не объявляются authoritative для соседних планов этим closeout.

### Actual output types

- `VadDecision` — `PcmFrame → VadProcessor`; frame-level `is_speech`, sequence/timestamp, duration и исходный lifecycle
  scope.
- `EndpointEvent` — `VadDecision → TurnDetector`; `speech_started`, `pause_candidate`, `soft_endpoint`,
  `speech_resumed`, `hard_endpoint`, `turn_id`, silence duration и authority flag.
- `AsrHypothesis` — `AsrAudioChunk → StreamingAsrAdapter`; revisioned text, optional stable prefix, candidate final
  flag, timestamp и lifecycle scope.
- `TranscriptUpdate` — `AsrHypothesis → TranscriptAssembler`; current text, stable prefix, unstable suffix, revision
  и explicit authority/boundary marker.
- `FinalUserTurn` — `hard_endpoint + assembled transcript → downstream dialogue boundary`; non-empty final text,
  `turn_id`, revision и authoritative `hard_endpoint`.

### Required propagation checkpoint I1–I2

Главному исполнителю после проверки этого результата необходимо выполнить следующий propagation cycle:

1. `I1`: сверить фактические поля этих output-типов с Map-I revision 4 и проверить, что названия/семантика не
   конфликтуют с уже принятыми `PcmFrame`/`AsrAudioChunk`.
2. `I2`: передать входные fixtures и contract assertions потребителям `002-E` и `002-F`: `EndpointEvent` как
   control-plane lifecycle input для Dispatcher/FSM и `FinalUserTurn` как direct text input для Skill & Prompt/RAG.
3. Отдельно передать `AsrHypothesis`/`TranscriptUpdate` только тем downstream owners, которым нужны speculative
   partial/stable observations; они не получают права менять FSM или разрешать TTS.
4. Зафиксировать новую revision Map-I и consumer contract tests. Если при сверке изменится тип/authority/lifecycle,
   этот child plan получает corrective pass и текущие локальные names нельзя использовать как accepted replacement.

- VAD consumes `PcmFrame` напрямую и emits `VadDecision` с исходным `call_id/channel_id/generation`.
- Turn Detector consumes ordered `VadDecision` and emits endpoint control events; `hard_endpoint` is authoritative.
- ASR consumes `AsrAudioChunk` and emits revisioned `AsrHypothesis`; cancellation and generation checks suppress stale
  output.
- Assembler accepts revisions as data-plane snapshots and emits one authoritative `FinalUserTurn` only at hard endpoint.
- `FinalUserTurn` is the downstream boundary payload; speech code does not call SIP, Dispatcher, FSM, LLM or TTS.

## Main-executor acceptance and propagation

`2026-09-03` main executor принял closeout, выполнил I1–I2 и закрыл найденный
contract gap. Входной `AsrAudioChunk` теперь единственный — тип из
`sip_bot.media.asr_chunker`; дублирующий speech-local тип удалён. Добавлен
`tests/contract/test_boundary_propagation.py`, а текущий unit/contract run дал
`64 passed`, `compileall` прошёл.

`FinalUserTurn` передан напрямую в Skill & Prompt Manager и в прямой вход FSM;
через control bus идут только lifecycle/speech events. Map-I обновлена до
revision 5, evidence propagation находится в interaction-map root.
Плановый статус после этой проверки: `complete`.
