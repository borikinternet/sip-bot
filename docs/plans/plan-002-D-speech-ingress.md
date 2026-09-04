# Plan-002-D: speech ingress

Уровень: `child plan`  
Статус owner review: `accepted` — 2026-09-03  
Статус исполнения: `complete` — implementation и propagation закрыты `2026-09-03`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Собрать речевой ingress из VAD, Turn Detector/endpointing, Streaming ASR и Transcript Assembler. На входе — независимые
PCM-потоки и ASR chunks от `002-C`; на выходе — один authoritative final user turn, partial/stable text events,
speech lifecycle и отменяемые stale results. Speech ingress не принимает SIP-решений и не запускает TTS.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Нужны VAD, границы реплики и streaming ASR на русском | Проверяются partial/final и один финальный ход | Offline speech fixtures + ASR smoke | Нет authoritative final turn |
| [`architecture.md`](../architecture.md) | VAD, endpointing и assembler — разные owners | Нельзя сливать их в один скрытый helper | Ownership/contract audit | Один компонент меняет чужое состояние |
| [`technical-specification.md`](../technical-specification.md) | Soft endpoint ~250–300 ms, hard endpoint ~500 ms — config candidates | Pause/resume/finalization наблюдаемы | Endpoint timing tests | Порог добавлен поверх бюджета или hard endpoint не закрывает ход |
| [`plan-001-C2-asr-primary.md`](plan-001-C2-asr-primary.md) | faster-whisper/CTranslate2 tested baseline и partial/final/cancel | Application adapter использует принятый ASR candidate | ASR import/operation evidence | Runtime/patch mismatch |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `N3→N5/N4`, `N5→N6`, `N6/N7→N8`, `N8→N9/N10a` | Actual fields propagate through Map-I | Contract revision | Downstream receives stale/ambiguous event |

## 3. Граница задачи

**Цель:** speech lifecycle, VAD, endpointing, ASR adapter и transcript assembly.

**Входит:** покадровый VAD decision, `speech_started`, pause candidate, soft/hard endpoint, `speech_resumed`, streaming
partial/final hypotheses, stable-prefix handling, finalization and cancellation.

**Не входит:** PCMU decode/fan-out/chunking (`002-C`), SIP protocol reaction (`002-B`), Dialogue FSM (`002-E`), RAG/LLM,
TTS/playback и transfer.

**Protected baseline:** Russian speech, `001-C2` ASR candidate, no-GIL main/process rule, fixed endpointing heuristic,
only authoritative final ASR can change FSM, one conversation.

**Предположения:** `002-C` предоставляет bounded PCM/ASR channels; ASR heavy inference is executed by the main process
only after owner-approved runtime and GPU scheduling, not from RTP/VAD callback.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| VAD | `src/sip_bot/speech/vad.py` | Отсутствует | Frame-level speech decisions | VAD candidate не зафиксирован | Реализовать adapter contract и проверенный candidate |
| Endpointing | `src/sip_bot/speech/endpointing.py` | Отсутствует | Soft/hard/resume events | Нет state machine | Создать owner object |
| ASR adapter | `src/sip_bot/speech/asr_adapter.py` | Feasibility only | Streaming partial/final/cancel mapping | Application boundary отсутствует | Обернуть C2 candidate |
| Transcript Assembler | `src/sip_bot/speech/transcript_assembler.py` | Отсутствует | Stable prefix + authoritative final text | Revision policy не реализована | Создать stateful assembler |
| Tests | `tests/unit/test_speech_ingress.py`, `tests/contract/test_speech_contracts.py` | Отсутствуют | Deterministic VAD/endpoint/assembler + ASR adapter tests | Нет fixtures | Создать synthetic hypotheses/audio |
| Evidence | `artifacts/.../002-D/` | Отсутствует | Timing and revision evidence | Нет application evidence | Создать при execution |

Допустимый write-set: `src/sip_bot/speech/`, speech unit/contract tests и собственный evidence root. Изменения в
`002-C`, Dispatcher/FSM и model runtime запрещены; фактические contract changes идут через Map-I. После propagation
`AsrAudioChunk` из `sip_bot.media.asr_chunker` является общим authoritative типом C→D; дублирующий speech-local тип
удалён, а совместимость подтверждена `tests/contract/test_boundary_propagation.py`.

## 5. Interaction topology и propagation контрактов

`N3 → N5` передаёт `PcmFrame` напрямую в VAD; `N3 → N4 → N7` передаёт ASR audio; `N5 → N6` передаёт VAD decisions;
`N6 → N8` передаёт endpoint events, а `N7 → N8` — ASR hypotheses. `N8 → N9` публикует только control event, а
`N8 → N10a` — final text data-plane payload. `speech_started` во время playback может участвовать в barge-in cycle,
но отдельного скрытого «детектора перебиваний» в этом plan нет: speech lifecycle и состояние playback сопоставляются
в Dispatcher.

Soft endpoint может открыть speculative подготовку, но `speech_resumed` закрывает её; hard endpoint финализирует ход.
`completion_hint` от LLM остаётся advisory и не заменяет VAD/endpointing.

## 6. Audit владельца поведения и парадигмы реализации

VAD владеет классификацией frame; endpointing — последовательностью решений и таймерами; ASR adapter — mapping inference
stream; Transcript Assembler — revision/stable-prefix/finalization. Stateful semantics реализуются owner-объектами с
scoped channel и cancellation; pure text normalization допустима только без изменения lifecycle или FSM.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Какой VAD-кандидат использовать? | WebRTC VAD как первый локальный open-source candidate; проверить import/operation/no-GIL до RTP path | При провале не включать автоматический fallback, а остановить slice на owner review | `resolved: owner review accepted 2026-09-02` |
| Нужен ли semantic turn detector? | Нет; применяются VAD и фиксированный soft/hard endpoint | Семантическое дробление и отдельная модель не входят в MVP | `resolved` |
| Какие endpoint пороги? | Ориентировочно soft 250–300 ms, hard 500 ms, значения — конфигурационные | Проверяется timing и resume behavior | `resolved` |
| Что имеет право менять FSM? | Только authoritative final ASR turn через Dispatcher | Partial и speculative results не меняют FSM/TTS | `resolved` |

## 8. Process invariant audit

- VAD, endpointing, ASR и assembler не скрываются в одном компоненте.
- GPU inference и native import checks не выполняются из media callback.
- Deterministic fixtures и real ASR smoke различаются; deferred probe не считается pass.
- Команды: `python -m pytest -q tests/unit tests/contract`; GPU smoke запускает основной исполнитель отдельно.
- Каждый фактический output передаётся в Map-I и downstream tests.

## 9. Architecture invariant audit

- Speech data plane не проходит через Dispatcher.
- `N6→N8` означает endpoint event, а не отдельный barge-in detector.
- Hard endpoint создаёт один финальный user turn; stale ASR revisions не накапливаются.
- Возобновление речи до hard endpoint отменяет speculative work и продолжает текущий turn.
- Speech events не инициируют SIP action напрямую.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| D1 | Зафиксировать speech contracts и deterministic fixtures | Frame decision, endpoint events и hypothesis schema проходят contract tests | Map-I mismatch |
| D2 | Проверить и подключить VAD candidate | Candidate produces reproducible decisions in approved runtime | Native/GIL issue or quality result unexplained |
| D3 | Реализовать endpoint state machine | Soft/hard/resume timings and re-entry tests pass | Ambiguous pause/close semantics |
| D4 | Подключить ASR adapter and assembler | Partial revisions converge to one final turn; cancel works | Stale result reaches FSM |
| D5 | Pass final speech contracts to E/F | E receives control event, F receives final text | Downstream fields not stable |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-D-001` | весь plan | Child plan не прошёл owner review | Speech implementation | project owner | APG review | `resolved — owner review accepted 2026-09-03` |
| `B-002-D-002` | D2 | VAD candidate не проходит no-GIL/import или operation evidence | VAD/RTP integration | project owner | [`vad-candidate.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-D/vad-candidate.json) | `resolved — deterministic operation/target import evidence; native operation deferred by approved scope` |
| `B-002-D-003` | D3–D4 | Endpoint/ASR revision semantics не позволяют получить один final turn | Dispatcher/F/RAG downstream | speech owner | [`endpointing.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-D/endpointing.json), [`transcript-revisions.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-D/transcript-revisions.json) и 64 unit/contract tests | `resolved — one authoritative hard-endpoint final turn` |

## 12. Test plan и evidence

- deterministic VAD frames with speech/noise/silence transitions;
- soft endpoint, resume before hard endpoint, hard endpoint and timer boundary tests;
- partial ASR revision replacement and stable-prefix tests;
- ASR cancellation/close and stale hypothesis suppression;
- Russian offline fixture and one approved C2 runtime/GPU smoke;
- integration with `002-C` bounded channels and `002-E` event stub;
- evidence includes timestamps, endpoint thresholds, hypotheses, final text, cancellation reason and exit code.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Semantic turn detector omitted | Deadline-critical MVP uses fixed endpointing | Does not remove finalization/barge-in tests | Map-002 and later map | `approved scope cut` |
| Alternate VAD/process isolation | Only if primary candidate fails native gate | Requires explicit owner decision and evidence | New decision or corrective plan | `deferred unless triggered` |

## 14. Execution report и closeout

Текущий статус: `complete; owner review accepted; implementation/evidence and main propagation closed 2026-09-03`.
`002-C` передаёт D общий `media.AsrAudioChunk`; D передаёт `EndpointEvent`/`SpeechEvent` в control plane, а
authoritative `speech.FinalUserTurn` — напрямую в `002-F` и в прямой вход FSM. Map-I revision 5 и propagation evidence
зафиксированы в [`propagation-002-D.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-D.md).
