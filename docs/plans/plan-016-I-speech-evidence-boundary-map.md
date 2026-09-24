# Plan-016-I: boundary map speech evidence и barge-in qualification

Уровень: `child plan / interaction map`  
Статус: `complete`  
Owner review: `covered by Map-016 review`

## 1. Цель

До code integration принять producer-first revision типов и lifecycle для двух рёбер: `faster-whisper → SpeechIngress`
и `VadDecision → runtime barge-in qualification`.

## 2. Применимые правила

| Источник | Правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| `development-guidelines.md` §2–§3 | Typed producer output предшествует consumer input; cycles явны | Инвентаризировать реальные faster-whisper segment fields и VAD diagnostics | source/model probe audit | Неизвестный обязательный field/lifecycle |
| `architecture.md` | VAD/ASR/TurnDetector/assembler ownership не объединяются | Только типы и методы существующих owners | topology audit | Новый delivery owner |
| `technical-specification.md` | Final text authoritative только после hard endpoint | Rejected final завершает scope без `FinalUserTurn` | lifecycle table | Pending scope остаётся навсегда |
| `architectural-planning-gate.md` | Source-map/write-set/blockers/evidence обязательны | Разделы ниже | closeout | Непроверенная candidate revision |

## 3. Source-map и write-set

| Producer/consumer | Файл | Текущее | Целевое |
|---|---|---|---|
| faster-whisper producer | `src/sip_bot/speech/asr_adapter.py` | только concatenated text | text + typed segment/audio evidence + decision |
| ASR contract | `src/sip_bot/speech/contracts.py` | `AsrHypothesis` без speech evidence | immutable optional `AsrSpeechEvidence` |
| turn consumer | `src/sip_bot/speech/ingress.py` | любой final text может финализировать | rejected final atomically discards scoped pending state |
| VAD producer | `src/sip_bot/speech/vad.py` | noise threshold и неиспользуемый speech level | near-end reference + normal/barge thresholds in `VadDecision` |
| barge consumer | `src/sip_bot/runtime_wiring.py` | любой start/resume during playback -> barge-in | typed threshold qualification before control event |

Write-set: этот plan меняет только собственный документ и evidence source audit. Код принадлежит `016-A/B`.

## 4. Candidate contract `speech-evidence-I1`

`AsrSpeechEvidence`:

- `decision`: `speech` или `no_speech`;
- `no_speech_probability`: агрегированная conservative model probability либо `None`;
- `average_log_probability`, `compression_ratio`: diagnostics, не самостоятельный hidden threshold;
- `input_duration_ms`, `max_segment_end_ms`: проверяемая временная геометрия;
- `reason`: стабильный reason code решения.

`AsrHypothesis.evidence` опционален для test doubles/backends без evidence. Отсутствие evidence сохраняет прежнюю
семантику accepted hypothesis, но production `FasterWhisperC2Backend` обязан выдавать evidence. `no_speech` partial не
изменяет assembler. `no_speech` final удаляет только matching `turn_id` из assemblers/pending endpoints и не создаёт
`FinalUserTurn`; новый turn остаётся независимым.

`VadDecision` дополнительно публикует near-end reference и `barge_in_threshold_dbfs`. Runtime во время `playing` или
`offering_transfer` материализует `BARGE_IN` только когда текущий frame удовлетворяет этому порогу. Обычные endpoint
events вне playback остаются во владении TurnDetector.

## 5. Циклы и termination

```text
playback active -> input frame -> VAD -> SPEECH_STARTED
  -> frame >= barge threshold -> BARGE_IN -> FSM cancels playback -> listening
  -> frame <  barge threshold -> no BARGE_IN; ASR/endpoint scope later accepted or rejected

hard endpoint -> final ASR hypothesis
  -> speech -> assembler.finalize -> FinalUserTurn
  -> no_speech -> discard(turn_id) -> no text/control action
```

BYE/CANCEL/close отменяют обе ветви существующим generation/cancel contract; evidence не открывает новый цикл.

## 6. Blocker register

| ID | Триггер | Статус |
|---|---|---|
| `B-016-I-001` | Реальные segment fields отличаются от принятой версии faster-whisper | `none until triggered` |
| `B-016-I-002` | Rejected-final нельзя выразить без нового component owner | `none until triggered` |

## 7. Acceptance

- source audit подтверждает exact producer fields и consumer methods;
- принят `speech-evidence-I1` без raw dict между слоями;
- lifecycle rejected turn и barge-in cycle однозначны;
- A/B plans используют эту revision без параллельной candidate integration.

## 8. Execution closeout 2026-09-22

Source audit подтвердил оба producer/consumer ребра. `FasterWhisperC2Backend.transcribe_chunk()` получает lazy segment
objects с `text`, `no_speech_prob`, `avg_logprob`, `compression_ratio`, `start` и `end`, но до этой карты сохранял
только `text`. `StreamingAsrAdapter` уже является единственной точкой coercion в `AsrHypothesis`, а
`SpeechIngress.accept_hypothesis()` — единственным consumer перед `TranscriptAssembler`; новый facade не нужен.

`VadProcessor.process()` уже владеет RMS/noise analytics и формирует `VadDecision`. `CallRuntimeWiring._publish_speech_events()`
является существующей materialization boundary `EndpointEvent → SpeechEvent/BARGE_IN` и знает состояние playback;
отдельный control/data channel не требуется.

Принята revision `speech-evidence-I1` из §4–§5. Все обязательные поля, rejection lifecycle, циклы и direct consumer
methods определены; blockers не сработали. Evidence:
`artifacts/implementation/016-speech-evidence/016-I/source-audit.md`.
