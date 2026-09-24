# Plan-016-A: ASR speech evidence и rejected-turn semantics

Уровень: `child plan`  
Статус: `complete`  
Зависимость: `016-I complete / speech-evidence-I1`

## 1. Цель

Сохранить model evidence `faster-whisper`, не допускать authoritative текста для доказанной не-речи и корректно
освобождать matching turn scope.

## 2. Материализованные правила

| Источник | Правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| `016-I` | Consumer принимает `AsrSpeechEvidence`; rejected final закрывает scope | Реализовать exact revision | contract/unit | Raw mapping или leaked endpoint |
| `development-guidelines.md` §2 | Структурированные данные typed от границы | dataclass/enum, validation, reason code | contract tests | Text-only production result |
| `development-guidelines.md` §6 | Test-first и corrective pass | Сначала красные model-double/rejection tests | captured pytest | Mandatory red остаётся |
| `technical-specification.md` | Параметры в constants | Threshold/tolerance через `RuntimeConfig` | config tests | Hidden threshold |
| `ADR-003` | Target native operation с GIL off | Production model probe после host tests | target evidence | GIL/runtime mismatch |

## 3. Source-map/write-set

Разрешено: `config/constants.py`, `src/sip_bot/config.py`, `src/sip_bot/speech/contracts.py`,
`src/sip_bot/speech/asr_adapter.py`, `src/sip_bot/speech/ingress.py`, exports, соответствующие contract/unit/integration
tests, `artifacts/implementation/016-speech-evidence/016-A/`.

Защищено: VAD/barge policy (`016-B`), SIP/RAG/LLM/TTS, закрытые plan/report artifacts.

## 4. Implementation slices

1. Красные tests для real segment metadata, `no_speech` partial/final и следующего independent turn.
2. Typed `AsrSpeechEvidence` и propagation через coercion/adapter.
3. Production backend aggregation: минимум `no_speech_prob` по сегментам как conservative speech evidence;
   остальные fields diagnostic. Threshold — конфигурационный `0.60` initial baseline.
4. `SpeechIngress` игнорирует rejected partial; rejected final удаляет matching assembler/endpoint state.
5. Runtime stats различают rejected evidence и stale revision.

Text blacklist и условие по конкретной строке запрещены.

## 5. Acceptance

- ложные короткие model outputs с `no_speech_prob >= threshold` не дают `FinalUserTurn`;
- реальная речь с low no-speech probability финализируется как прежде;
- rejected final после ранее принятого partial отменяет весь matching turn;
- следующий turn не загрязнён;
- affected tests зелёные; target operation сохраняет GIL off.

## 6. Blocker register

| ID | Триггер | Статус |
|---|---|---|
| `B-016-A-001` | Принятая production версия не предоставляет segment evidence | `none until triggered` |
| `B-016-A-002` | Порог не разделяет controlled speech/non-speech corpus | `none until triggered; evidence required` |

## 7. Execution closeout 2026-09-22

Реализованы immutable `AsrSpeechEvidence`/`AsrSpeechDecision`, propagation через backend/coercion/hypothesis и
атомарный rejected-final path в `SpeechIngress`. Runtime statistics различают model rejection и stale revision.
Threshold `0.60` и timeline tolerance `500 ms` находятся в `config/constants.py`.

Production replay на target 3.14t принял четыре реальные реплики с `no_speech_prob=0.004…0.480` и отверг три точных
ложных интервала с `0.883…0.941`; строка `Продолжение следует...` не использовалась как условие. У всех трёх ложных
результатов model segment заканчивался на `29.98 s` при входе `0.32…0.74 s`, что сохранено как diagnostic, но решение
принималось по no-speech evidence. GIL после model operation остался выключен.

Evidence: `artifacts/implementation/016-speech-evidence/016-A/problem-call-speech-evidence.json`. Blockers не
сработали; plan закрыт `complete`.
