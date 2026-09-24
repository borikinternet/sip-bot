# Plan-016-B: near-end VAD reference и barge-in qualification

Уровень: `child plan`  
Статус: `complete`  
Зависимость: `016-I complete`; integration после `016-A`

## 1. Цель

Использовать измеряемый per-call уровень близкой речи, чтобы слабый фон/акустический возврат не создавал turns и не
отменял playback, сохранив настоящий barge-in.

## 2. Материализованные правила

| Источник | Правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| `016-I` | `VadDecision` публикует near-end/barge diagnostics | Producer/consumer exact fields | contract tests | Ad-hoc shared state |
| `architecture.md` | Energy policy принадлежит VAD; runtime только квалифицирует barge control edge | Без нового component/delivery owner | source audit | Дублирование TurnDetector/FSM |
| `development-guidelines.md` §6–§7 | Не подгонять один WAV и не вводить fallback | synthetic levels + Map-008 + problem replay | evidence | Только problem WAV зелёный |
| `technical-specification.md` | Параметры конфигурационные | near-end/general/barge margins в constants | config tests | Magic number |

## 3. Source-map/write-set

Разрешено: `config/constants.py`, `src/sip_bot/config.py`, `src/sip_bot/speech/contracts.py`,
`src/sip_bot/speech/vad.py`, `src/sip_bot/runtime_wiring.py`, VAD/runtime tests,
`tools/vad_energy_replay.py`, evidence `.../016-B/`.

Защищено: ASR evidence semantics после `016-A`, endpoint durations, SIP/RAG/LLM/TTS, closed artifacts.

## 4. Policy

- noise-floor threshold остаётся первой защитой;
- near-end reference имеет быстрый attack к более громкой подтверждённой речи и не обучается вниз на слабом echo;
- normal speech threshold учитывает configurable допустимое падение относительно reference;
- barge-in threshold строже normal threshold и применяется только к start/resume во время playback;
- пока near-end reference не получен, действуют прежние noise/minimum правила; ASR evidence остаётся downstream safety;
- analytics публикует оба порога и причины reject/qualify.

Initial values выбираются не по одному WAV: проверяются несколько speech levels, noise/echo levels, controlled Map-008
corpus и исходная запись. Изменение hard endpoint запрещено.

## 5. Acceptance

- synthetic real speech после bootstrap принимается в согласованном диапазоне громкости;
- echo минимум на configured margin ниже near-end reference не создаёт barge-in;
- energetic user speech during playback создаёт один barge-in;
- problem replay существенно сокращает ложные turns, а ASR gate устраняет оставшиеся hallucinated finals;
- Map-008 corpus не деградирует; runtime stats объясняют решения.

## 6. Blocker register

| ID | Триггер | Статус |
|---|---|---|
| `B-016-B-001` | Без playback reference нельзя сохранить quiet barge-in и отвергнуть echo | `none until triggered; category-4/AEC review` |

## 7. Execution closeout 2026-09-22

Energy gate получил устойчивый near-end reference: он формируется после `200 ms` кадров выше bootstrap `-26 dBFS`
как 70-й percentile и сглаживается, поэтому одиночный clipping spike не задаёт порог всего звонка. Normal margin
равен `12 dB`, playback barge margin — `8 dB`, bootstrap barge floor — `-26 dBFS`; все значения конфигурационные.
`VadDecision` переносит reference/threshold/qualified flag, а существующий runtime method подавляет слабый start/resume
в состоянии playback без нового канала или owner.

Problem replay уменьшил accepted frames `847 → 494` и authoritative turns `12 → 4`; четыре оставшихся хода production
ASR распознал как реальные. Controlled Map-008 corpus сохранил ровно три turns. Первый peak-based pass был отвергнут
после replay (`speech_level=-1.55 dBFS`) и заменён percentile policy; это зафиксированный corrective pass, не blocker.

Evidence: `artifacts/implementation/016-speech-evidence/016-B/problem-call-vad-replay.json` и
`controlled-corpus-replay.json`. Blocker `B-016-B-001` не сработал; AEC не добавлялся. Plan закрыт `complete`.
