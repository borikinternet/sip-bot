# Corrective Map-016: speech evidence и устойчивый barge-in

Уровень: `map`  
Статус: `complete`  
Owner review: `accepted by owner instruction "исправляй", 2026-09-22`

## 1. Цель и проверяемый результат

Исправить воспроизведённый дефект зарегистрированного звонка: слабый акустический возврат и фон не должны отменять
воспроизведение, создавать authoritative user turns и превращаться `faster-whisper` в текст вроде
`Продолжение следует...`. Настоящая речь пользователя, включая barge-in, должна сохраняться.

Карта закрывается только после deterministic replay исходного звонка, regression/target-runtime gate и
зарегистрированного SIP-прогона. Простое изменение одного dBFS-порога без ASR evidence и сквозной проверки не является
выполнением.

## 2. Фактический дефект

- запись `20260922-184910` дала 12 VAD/endpointing turns вместо четырёх содержательных пользовательских реплик;
- около `6.76 s` принятой входной «речи» совпало с TTS playback, ещё около `1.76 s` попало в его 300-ms tail;
- настоящие реплики имели приблизительно `-12.5…-17.4 dBFS`, ложные участки — `-28.4…-46.1 dBFS`;
- существующий energy gate вычислял `speech_level_dbfs`, но порог строил только из `minimum_dbfs=-42` и noise floor;
- production `faster-whisper` дал реальным ходам `no_speech_prob <= 0.024`, ложным — `>= 0.787`, однако backend
  выбрасывал эти признаки и передавал только текст;
- `SPEECH_STARTED` во время playback немедленно превращался в `BARGE_IN`, до появления ASR evidence.

Исходное evidence: `artifacts/diagnostics/latest-live-call-20260922-184910/`.

## 3. Извлечение правил

| Источник | Материализованное правило | Влияние | Проверка | Stop condition |
|---|---|---|---|---|
| `requirements.md` | Перебивание прекращает речь бота, но фон не является пользовательским запросом | Сохраняется настоящий barge-in; ложный не допускается | replay + registered call | Реальная речь теряется либо echo отменяет playback |
| `architecture.md` | VAD, TurnDetector, ASR и TranscriptAssembler имеют разные ownership; payload идёт прямыми методами | Новая evidence boundary проходит producer-first без delivery owner | `016-I`, contract tests | Требуется новый orchestration owner |
| `technical-specification.md` | Параметры VAD/ASR конфигурационные; authoritative final создаётся после hard endpoint | Порог и ASR gate находятся в `config/constants.py`; rejected final закрывает turn scope без текста | config/contract tests | Незавершённый pending endpoint или скрытый default |
| `development-guidelines.md` §2–§3 | Typed-first и итеративная propagation `I0–I5` | Сначала `016-I`, затем producer/consumer plans | dependency graph | Интеграция раньше принятой revision |
| `development-guidelines.md` §6 | Красный test текущего scope исправляется; обязательный gate не компенсируется | Исходный звонок становится immutable regression input | raw evidence + повтор | Лишь соседние тесты зелёные |
| `development-guidelines.md` §7 | Упрощение и скрытый fallback запрещены | Не заменять WebRTC VAD амплитудным и не фильтровать конкретную фразу | source audit | Text blacklist или test-only path |
| `ADR-003` | Native operation проверяется в free-threaded target runtime | WebRTC/faster-whisper operation gate сохраняет GIL off | target command/evidence | GIL включился или runtime другой |
| `architectural-planning-gate.md` | Изменение structured contracts/user flow требует map, child plans, blockers и closeout | Эта карта и четыре child plans | APG audit | Открытый category-4 gap |

## 4. Граница задачи

```text
Входит:
  typed ASR speech evidence и явное rejected-final завершение turn scope;
  configurable no-speech threshold и ASR diagnostics;
  использование per-call near-end speech reference в energy gate;
  более строгая barge-in qualification на уже доступных frame diagnostics;
  replay проблемной записи, controlled corpus, target/no-GIL и registered SIP proof.

Не входит:
  acoustic echo cancellation, новая media reference edge или suppression model;
  замена WebRTC VAD/faster-whisper/TurnDetector;
  blacklist конкретных ASR-фраз;
  изменение ASR audio accumulation topology;
  обучение/дообучение модели и production-wide acoustic evaluation.

Protected baseline:
  один звонок; WebRTC VAD mode 2; hard endpoint 520 ms;
  Dispatcher/FSM control ownership; прямой audio/text data plane;
  free-threaded CPython target; текущие SIP/RAG/LLM/TTS contracts.

Рабочее дерево:
  содержит принятые результаты предыдущих карт; unrelated changes сохраняются.
```

Если двухуровневый gate не отделяет акустический возврат от тихой реальной речи, AEC/media-reference edge считается
новым category-4 gap и требует отдельного owner review; молчаливо добавлять его запрещено.

## 5. Interaction topology и contract revision

```text
PCM frame
  ├─> WebRTC VAD ─> AdaptiveEnergyGate ─> VadDecision
  │                                          │
  │                                          ├─> TurnDetector ─> EndpointEvent
  │                                          └─> runtime barge-in qualification
  └─> ASR accumulator ─> FasterWhisperC2Backend ─> AsrHypothesis[AsrSpeechEvidence]
                                                           │
                                                           └─> SpeechIngress
                                                                 ├─ accepted -> TranscriptAssembler -> FinalUserTurn
                                                                 └─ rejected final -> discard scoped turn
```

Baseline: `speech-evidence-I0-candidate`. Authoritative revision появляется только после `016-I`.

## 6. Child plans и порядок

| Plan | Scope | Зависимость | Evidence root | Статус |
|---|---|---|---|---|
| [`016-I`](plan-016-I-speech-evidence-boundary-map.md) | Типы, exact methods, rejection lifecycle, barge-in cycle | map review | `artifacts/implementation/016-speech-evidence/016-I/` | `complete; speech-evidence-I1` |
| [`016-A`](plan-016-A-asr-speech-evidence-gate.md) | faster-whisper evidence и rejected-turn semantics | `016-I complete` | `.../016-A/` | `complete; production evidence` |
| [`016-B`](plan-016-B-near-end-vad-and-barge-in.md) | near-end reference и barge-in threshold | `016-I complete`; после A для integration | `.../016-B/` | `complete; recorded/corpus replay` |
| [`016-C`](plan-016-C-recorded-and-registered-live-gate.md) | problem replay, regression, target and registered closeout | `016-A`, `016-B` complete | `.../016-C/` | `complete; registered-live-r3` |

```text
016-I ──> 016-A ──> 016-B ──> 016-C ──> map closeout
```

Последовательность намеренная: оба code plans меняют speech contracts/config/runtime integration и не имеют безопасно
непересекающегося write-set.

## 7. Owner review

| Вопрос | Решение | Статус |
|---|---|---|
| Исправлять только VAD или также ASR hallucination boundary | Оба слоя: VAD защищает realtime barge-in, ASR evidence защищает authoritative text | `resolved by defect analysis and owner instruction` |
| Добавлять AEC/media reference сейчас | Нет; только если принятый двухуровневый gate доказанно недостаточен | `resolved; out of current scope` |
| Подгонять параметры под один WAV | Нет; исходный WAV — обязательная regression, дополнительно controlled corpus и scaled/noise cases | `resolved by prior owner requirement` |

Открытых owner-review вопросов нет.

## 8. Map-level blocker register

| ID | Триггер | Что блокируется | Owner | Evidence | Статус |
|---|---|---|---|---|---|
| `B-016-001` | ASR backend не предоставляет `no_speech_prob`/segment diagnostics в принятой версии | A/C | project owner | target operation output | `not triggered; evidence available` |
| `B-016-002` | Echo и тихая речь неразделимы без playback reference/AEC | B/C | project owner | multi-level replay + registered call | `not triggered; two-level gate passed` |
| `B-016-003` | Target GPU/SIP stand недоступен после corrective retry | C | project owner | raw commands/output | `not triggered; registered r3 passed` |

## 9. Acceptance и closeout

- нет hardcoded text blacklist и amplitude-VAD fallback;
- typed evidence доходит от backend до `SpeechIngress`, rejected final освобождает assembler/pending endpoint;
- replay проблемной записи не создаёт hallucinated final turns; настоящий content сохраняется;
- during-playback echo не вызывает `BARGE_IN`, реальный high-energy barge-in вызывает;
- Map-008 controlled corpus и affected regressions зелёные;
- target CPython 3.14t показывает GIL off после WebRTC/faster-whisper operations;
- зарегистрированный FreeSWITCH звонок создаёт корректный отчёт/запись без ложных ходов;
- документы-владельцы, registry/backlog и execution closeout синхронизированы.

Карта получает `complete` только после `complete` всех child plans. `Foundation complete` и частичное закрытие запрещены.

## 10. Closeout

Карта закрыта 22 сентября 2026 года. Исходная запись после нового VAD policy даёт четыре содержательных хода вместо
12, а три точных ложных интервала отклоняются model evidence без blacklist текста. Host regression прошла
`291 passed, 6 skipped`, target CPython 3.14.7t — `294 passed, 3 skipped` при выключенном GIL.

Registered FreeSWITCH gate `016-C/registered-live-r3` завершился `pass`: четыре пользовательских хода, source-aware
ответы, настоящий `barge_in`, подтверждённый transfer, `2792/2792` исходящих media frames, ноль underrun/drop/runtime
errors, итоговый отчёт и стереозапись. AEC/media-reference edge не понадобился; блокеры карты не сработали.

Execution closeout: `artifacts/implementation/016-speech-evidence/closeout.md`.
