# Plan-002-C: audio boundary buffering

Уровень: `child plan`  
Статус owner review: `accepted` — `2026-09-03`, owner authorization на execution получена.  
Статус исполнения: `complete` — 2026-09-03  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Реализовать преобразование и передачу аудио между SIP/media и речевыми компонентами: PCMU → внутренний PCM S16LE
mono 8 kHz, media frames с фактическим `ptime`, специализированный PCM fan-out и ASR input accumulator/chunker.
Результат должен собирать ориентировочный `asr_chunk_ms = 1000` по заполнению или timer policy, не задерживать VAD
ожиданием ASR chunk и корректно flush/close/cancel-ить хвост.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Audio pipeline — часть MVP; PCMU и один разговор | Форматы и bounded delivery проверяются отдельно | PCM/PCMU tests | Неизвестный format или multi-call scope |
| [`architecture.md`](../architecture.md) | Fan-out специализирован, payload идёт напрямую | VAD и ASR получают независимые каналы | Fan-out isolation test | Audio проходит через Dispatcher |
| [`technical-specification.md`](../technical-specification.md) | PCMU ↔ PCM S16LE mono 8 kHz, ptime, bounded chunks/timer | Conversion/framing ownership явен | Codec/chunker tests | Без bounded policy или скрытый timer |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `N2→N3`, `N3→N5/N4`, `N4→N7` типизируются и имеют lifecycle | Фактические поля обновляют contract registry | Map-I propagation | Candidate output не подтверждён |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Native dependencies проверяются | Audio code не добавляет неучтённый native boundary | Import evidence | GIL/native incompatibility без решения |

## 3. Граница задачи

**Цель:** media format adapter, PCM fan-out, bounded channels, ASR accumulator/chunker.

**Входит:** mu-law decode/encode, PCM frame metadata, bounded per-consumer channels, timer-driven ASR chunk, flush on
hard endpoint/close/cancel/overrun и discard policy.

**Не входит:** SIP transaction, VAD, endpointing, ASR inference, TTS playback, LLM/RAG.

**Protected baseline:** PCMU/G.711 mu-law, internal PCM S16LE mono 8 kHz, one conversation, direct data plane, no audio
recording, `001-S` and `002-B` media contract.

**Предположения:** `002-B` для каждого вызова получает `NegotiatedMediaProfile` из согласованного SDP и словарей/объектов
PJMEDIA и передаёт его C; этот handoff подтверждён `Map-002-I` revision 4 от `2026-09-03`, а до фактического SIP
прогона используются synthetic profiles.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Format adapter | `src/sip_bot/media/format_adapter.py` | Отсутствует | PCMU ↔ PCM conversion | Нет application code | Реализовать typed conversion |
| PCM frame | `src/sip_bot/media/types.py` | Отсутствует | Frame with timestamp/format/channel state | Candidate fields in Map-I | Confirm and propagate fields |
| Fan-out | `src/sip_bot/media/pcm_fanout.py` | Отсутствует | Independent bounded consumers for VAD/ASR | No backpressure policy in code | Implement specialized owner |
| ASR chunker | `src/sip_bot/media/asr_chunker.py` | Отсутствует | 1 s target + timer/flush/close | No timer lifecycle | Implement and test |
| Tests | `tests/unit/test_audio_boundaries.py`, `tests/contract/test_audio_contracts.py` | Отсутствуют | Deterministic conversion/fanout/chunker tests | No fixtures | Create synthetic PCMU/PCM fixtures |

Допустимый write-set: `src/sip_bot/media/`, audio unit/contract tests и собственный evidence root. Изменения в SIP adapter,
VAD/ASR implementations и Dispatcher запрещены; contract updates идут через `Map-002-I`.

## 5. Interaction topology и propagation контрактов

`N2 → N3` передаёт `PcmFrame`; `N3 → N5` и `N3 → N4` передают независимые bounded audio streams; `N4 → N7` передаёт
`AsrAudioChunk`. Fan-out не копирует данные через event bus и не ждёт самого медленного consumer без явной bounded
policy. При overrun фиксируется событие и применяется согласованный discard/close policy. При `hard_endpoint`, close
или cancellation accumulator выдаёт либо явно отбрасывает неполный хвост по contract rule; при barge-in старый output
не переиспользуется для нового turn.

## 6. Audit владельца поведения и парадигмы реализации

Media format adapter владеет преобразованием форматов; PCM fan-out владеет разветвлением и bounded delivery; accumulator
владеет таймером, буфером и flush semantics. Эти stateful объекты получают scoped channel/lifecycle dependencies.
Pure mu-law conversion допустима как функция без владельца состояния; она не меняет канал, FSM или generation.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Нужен ли универсальный audio bus? | Нет; fan-out — специализированный компонент единственной audio boundary | Универсальная event bus не используется для PCM payload | `resolved` |
| Какой внутренний PCM? | S16LE mono 8 kHz | ASR/VAD boundaries получают единый формат | `resolved` |
| Какой initial ASR chunk? | Около 1 s, с config/timer policy | Фактическая константа живёт в `config/constants.py` | `resolved` |
| Как обрабатывать per-call media profile? | Получать его из SDP/PJMEDIA для каждого звонка и передавать по typed boundary | `ptime`, rate, channels и frame size не являются глобальными константами; mismatch останавливает downstream integration | `resolved: owner review accepted 2026-09-02` |

## 8. Process invariant audit

- Specialized fan-out не превращается в универсальную шину сообщений.
- Очередь используется только как bounded delivery primitive; accumulator/timer/re-framer остаются отдельными owners.
- Synthetic tests отделены от RTP smoke; ни один skipped test не считается pass.
- Commands: `python -m pytest -q tests/unit tests/contract` и отдельный integration selector после появления стенда.
- После фактических fields обновляется Map-I и registry.

## 9. Architecture invariant audit

- Аудио не проходит через Dispatcher.
- VAD не ждёт заполнения ASR chunk.
- Каждый consumer имеет bounded channel и close/cancel policy.
- Старые закрытые channels не получают новые frames; stale payload discard наблюдаем.
- PCMU остаётся внешним форматом, PCM — внутренним; запись аудио не создаётся.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| C1 | Реализовать и проверить PCMU/PCM conversion | Round-trip/known vectors и format metadata pass | Несовместим sample format |
| C2 | Реализовать `PcmFrame` и specialized fan-out | VAD/ASR consumers получают свои frames без взаимного ожидания | Один consumer блокирует ingress |
| C3 | Реализовать ASR accumulator/chunker | Target/timer/short-tail flush/overrun/close tests pass | Timer or close semantics ambiguous |
| C4 | Подключить фактический B media output и передать contract revision | RTP PCMU frames доходят до C, downstream fixture updated | B output differs from candidate contract |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-C-001` | весь plan | Child plan не прошёл owner review | Audio implementation | project owner | APG review | `resolved: owner review accepted 2026-09-03` |
| `B-002-C-002` | C4 | `002-B` не подтвердил media format/ptime contract | RTP integration and D | media owner | `002-B` evidence + Map-I | `resolved: 002-B handoff and Map-I revision 4 recorded 2026-09-03` |
| `B-002-C-003` | C2–C3 | Bounded overflow/close rule не наблюдаем | VAD/ASR integration | channel owner + project owner | Overflow/close tests | `resolved: deterministic unit/contract and live C4 evidence 2026-09-03` |

## 12. Test plan и evidence

- known PCMU μ-law vectors, PCM sample width/endian/channel/rate checks;
- frame timestamp/order and ptime reconstruction;
- fan-out slow/closed consumer and bounded overflow;
- accumulator emits exactly target chunks, timer flushes, hard endpoint flushes tail;
- cancellation/close is idempotent and stale frames disappear;
- RTP PCMU loopback through `001-S` after B handoff;
- evidence stores input/output sizes, timestamps, overflow policy, close reason and exact commands.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete` — 2026-09-03.

### Фактически изменённые файлы

- `src/sip_bot/media/__init__.py`
- `src/sip_bot/media/codec.py`
- `src/sip_bot/media/types.py`
- `src/sip_bot/media/fanout.py`
- `src/sip_bot/media/asr_chunker.py`
- `tests/unit/test_audio_boundaries.py`
- `tests/contract/test_audio_contracts.py`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-C/`

### Результаты выполнения

- Host baseline до реализации: `21 passed`.
- Targeted host boundary tests: `15 passed`.
- Полный host unit/contract lane: `57 passed`.
- `python -m compileall -q src tests`: exit `0`.
- Target CPython `3.14.7t`: `Py_GIL_DISABLED=1`, GIL до и после импорта `sip_bot.media` — `False`.
- Target deterministic lane: `15 passed`, exit `0`.
- Live C4 через approved Baresip PCMU peer: `100` PCM frames получены из 002-B, `100` доставлены в VAD и `100` в
  ASR accumulator, сформированы два чанка по `1000 ms`, exit `0`.
- Heavy GPU inference и загрузка моделей не выполнялись: для этого child plan они не применимы.

### APG §5.8B и blocker register

Два первоначальных красных запуска были классифицированы как ошибки invocation/fixture-окружения, исправлены и
перезапущены; blocker по ним не регистрировался. Локальная реализация и тесты прошли corrective pass. Все blockers
`B-002-C-001`–`B-002-C-003` закрыты; открытых blockers нет. Намеренных упрощений и fallback не введено.

Evidence и команды: [evidence-index.md](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-C/evidence-index.md),
[commands.md](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-C/commands.md),
[closeout.md](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-C/closeout.md).

Следующий handoff: передать `002-D` фактические `PcmFrame` и `AsrAudioChunk` contracts, profile per-call, capacities и
timer/flush/overflow/close/cancel semantics. Входной baseline этого execution — `Map-002-I revision 4`; локальные
output-типы остаются candidate до propagation checkpoints `I1–I2` главного исполнителя и не объявляются authoritative
для `002-D` или других соседних планов. Main executor отдельно обновляет Map-002-I и передаёт следующую ревизию; при
изменении контракта выполняется corrective pass. Execution `002-D` начинается только после собственного owner review.
