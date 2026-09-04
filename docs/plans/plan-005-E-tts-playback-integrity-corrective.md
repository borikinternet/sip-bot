# План 005-E: целостность TTS-воспроизведения и корректирующий прогон

Уровень документа: `child plan`  
Идентификатор: `005-E`  
Родитель: [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md)  
Предшествующее evidence: [`target-20260904-r7`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-D/target-20260904-r7/)  
Дата подготовки: `2026-09-04`  
Статус owner review: `accepted by explicit owner instruction 2026-09-04; new separate child-plan review is not required`  
Статус исполнения: `complete — E1–E4 executed and accepted 2026-09-04`

## 1. Цель и проверяемый результат

Исправить обнаруженную при прослушивании stereo-записи r7 потерю большей части звучащего ответа TTS. В записи
есть короткий слышимый фрагмент, пауза и затем ещё один фрагмент, после чего остальная часть ответа заменяется
тишиной. При этом `egress_underruns=0`, поэтому одного этого счётчика недостаточно для обнаружения дефекта.

Целевое поведение:

- TTS может выдавать PCM chunks произвольного размера и с произвольными интервалами;
- chunks последовательно добавляются во внутренний буфер воспроизведения с переменной текущей длиной;
- PJMEDIA по каждому такту получает ровно один согласованный `PcmFrame` (`frame_bytes`/`ptime` текущего звонка);
- отсутствие нового TTS chunk в момент чтения не приводит к отбрасыванию уже принятого PCM;
- normal producer completion означает, что уже принятый PCM должен быть дочитан до конца;
- barge-in, cancellation, close и stale generation не доставляют старый PCM пользователю;
- normal overflow не скрывается молчаливым drop. При достижении защитного high-water применяются явные
  backpressure/ожидание или диагностически видимая ошибка;
- media callback остаётся коротким и неблокирующим.

Приёмочный результат — новый target live/rehearsal evidence `r10`, в котором весь обязательный TTS-ответ реально
слышен в Baresip stereo derivative, нет необъяснимых TTS-дропов, а статистика отличает потерю полезного PCM от
намеренной тишины, startup wait и аварийного underrun.

План не добавляет новый межкомпонентный сигнал, новый delivery owner, новый тип межкомпонентного payload или новую
подчинённую карту. Он исправляет существующую цепочку `TtsPcmChunk → TtsOutputBuffer → PcmFrame → PlaybackChannel`.

## 2. Применимые документы и материализованные правила

| Источник | Материализованное правило | Действие в этом плане | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | В MVP нужен полноценный ответ локального TTS в SIP-разговоре; запись выполняет Baresip test peer | Приёмка оценивает фактически слышимый ответ по peer-side stereo evidence; bot-side recording не добавляется | Прослушивание и waveform/manifest audit `r10` | Требуемый ответ не воспроизводится полностью |
| [`architecture.md`](../architecture.md) | TTS выдаёт произвольные chunks; output buffer/framer/pacer владеет преобразованием в media frames; payload идёт напрямую | Сохраняются существующие owners и typed edges; новый signal/event bus не вводится | Architecture/source audit | Нужен новый owner или boundary |
| [`technical-specification.md`](../technical-specification.md) | Между форматами и темпами нужен boundary adapter; TTS chunks агрегируются, фреймятся и paced-ятся; bounded storage обязателен | Уточняется, что variable-length — это occupancy динамического bounded буфера, а не фиксированные 50 frames и не truly unbounded storage | Unit/contract tests и config audit | Реализация требует неограниченного хранения |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `Map-002-I revision 21` — authoritative topology; in-process edge — метод receiver-а; между потоками максимум bounded thread-safe queue | TTS producer вызывает существующий typed input method receiver-а; storage и lifecycle принадлежат playback owner | Propagation audit | Меняется typed edge или propagation revision |
| [`development-guidelines.md`](../development-guidelines.md) | Typed-first, owner behavior, direct data plane, explicit lifecycle/backpressure/stale policy, no silent simplification | Исправление остаётся в write-set существующих owners; drop и слабые assertions запрещены | APG audit, targeted/regression/contract reruns | Категория 4 или обход обязательного теста |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Ошибка category 1/2 в принятом write-set исправляется corrective pass; category 4 требует owner review | Текущее наблюдение классифицируется как category 1 до доказательства архитектурного gap | Raw output, классификация, corrective report | Только подтверждённый category 4 |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Target — CPython 3.14.7t/no-GIL; native baseline не заменяется молча | Проверки выполняются на утверждённом target; GPU gate запускает main executor | Runtime metadata | Target/runtime baseline недоступен |
| [`plan-005-D-rehearsal-evidence-closeout.md`](plan-005-D-rehearsal-evidence-closeout.md) | r7 — сохранённое историческое rehearsal evidence, но запись является предметом пользовательского review | r7 не перезаписывается; r10 получает новый evidence root и проверяет полноту PCM | New recording manifest and report | Нет нового clean-start evidence |

Уже принятые решения не повторно выносятся на owner review: один звонок, PCMU, 30 ms RTP budget, no-GIL target,
основной Qwen/ASR/TTS baseline, control-only Dispatcher/Event Bus, прямой data plane, локальный RAG, отсутствие
`state.json`, Baresip-side recording и запрет silent simplification. Этот план не изменяет их.

## 3. Граница и допущения

### Входит

- диагностика текущего пути TTS output и подтверждение места потери PCM;
- изменение существующего output buffer/framer/pacer и только необходимой wiring-логики его владельца;
- динамическое накопление PCM с отдельной фреймизацией по negotiated `frame_bytes`;
- явные правила producer completion, normal drain, cancellation, barge-in, stale generation, close и overflow;
- тесты byte/frame accounting, частичных chunks, multiple chunks per frame, chunk boundary внутри frame и пустого
  буфера при активном producer;
- новый последовательный clean-start target live/rehearsal прогон с полной Baresip записью;
- синхронизация Map-005, Map-006 downstream status, registry, backlog и execution evidence.

### Не входит

- новый сигнал между компонентами, новый event bus payload, новый delivery owner или новая очередь поверх уже
  существующего receiver-owned buffer;
- изменение `TtsPcmChunk`, `PcmFrame`, `EgressSourceMode`, `PlaybackChannel`, `Dispatcher`, `DialogueFSM`,
  `CallSession`, `LlmRequest` и `Map-002-I revision 21`, если тест не докажет настоящий contract gap;
- замена TTS-модели, Ollama/LLM process, SIP-стека, PJMEDIA callback contract или Python runtime;
- truly unbounded buffer без high-water/backpressure policy;
- изменение исторических планов `005-C`/`005-D` и исторического r7 evidence;
- оптимизация latency/warmup, не связанная с целостностью доставки уже сгенерированного PCM.

### Protected baseline

Защищены `config/constants.py`, accepted ADRs, `Map-002-I revision 21`, закрытые планы `001-*`, `002-*`, `005-C`,
`005-D`, существующие typed payloads и r7 artifacts. Если изменение затрагивает защищённый контракт, план не
расширяется молча: создаётся APG gap с категорией и останавливается affected execution.

## 4. Source-map и write-set

| Область | Источник | Текущее состояние | Целевое состояние | Владелец | Допустимый write-set |
|---|---|---|---|---|---|
| PCM accumulation | `src/sip_bot/tts/output_buffer.py` | Буфер имеет фиксированную ёмкость; chunk, превышающий остаток, может быть отклонён целиком, а caller не делает обязательную проверку результата | Очередь/буфер хранит принятые PCM chunks с переменной occupancy; normal payload не теряется; overflow имеет явную backpressure/error policy | `TtsOutputBuffer` | Только существующий output buffer, его tests и собственный evidence |
| Frame pacing | `src/sip_bot/tts/media_pacer.py` | Pacer преобразует PCM в media frames; нуждается в проверке поведения при chunk/frame boundary и drain | На каждом media tick выдаётся ровно один negotiated `PcmFrame`; callback не ждёт producer и не съедает лишний PCM | `MediaPacer`/playback owner | Существующий pacer/framer и tests |
| TTS ingress wiring | `src/sip_bot/runtime_wiring.py` | `_on_tts_chunk` передаёт chunk в output buffer; факт отказа не должен теряться | Сохраняется тот же typed receiver call; result/error/backpressure observable и согласован с lifecycle | Existing runtime wiring owner | Только scoped chunk/close/cancel handling и tests |
| Media egress | `src/sip_bot/sip_media/media_port.py` | PJMEDIA читает fixed frame; source selection уже различает intentional silence и TTS path | Источник выбирается как прежде; callback читает из dynamic buffer до исчерпания, затем корректно применяет `DRAINING`/idle silence | SIP/media playback owner | Только scoped read/metrics behavior; без SIP boundary change |
| Deterministic tests | `tests/` | r7 metrics не обнаружили потерю PCM | Проверяются accounting, lifecycle, stale/cancel, overflow и отсутствие silent drop | Main executor | Existing/new focused tests under playback/TTS test scope |
| Live evidence | `artifacts/implementation/002-system-testing-and-demo-readiness/005-E/` | отсутствует | Commands, raw logs, r10 JSON, raw Baresip enc/dec, stereo, manifest, report и closeout | Main executor | Новый evidence root only |

Не входят в write-set: центральный Dispatcher, Event Bus, FSM, Context/RAG/LLM, ASR/VAD, `config/constants.py`,
закрытые планы и ранее созданные artifacts. Новый межпоточный канал не создаётся: если существующий worker находится
в другом потоке, используется его существующий bounded thread-safe receiver mechanism, а не Dispatcher.

## 5. Interaction topology и typed boundary

Authoritative topology не меняется:

```text
TTS producer
  -- TtsPcmChunk, existing typed receiver input --> TtsOutputBuffer (receiver-owned storage)
  -- internal buffer/framer method ----------------> MediaPacer
  -- PcmFrame per negotiated media tick -----------> PlaybackChannel/PJMEDIA media callback
  -- PCMU media frame -----------------------------> RTP peer
```

Входная граница — существующий typed метод output buffer/playback owner-а, принимающий `TtsPcmChunk`. Выходная
граница — существующий путь `PcmFrame` к `PlaybackChannel`/PJMEDIA. На границе выполняется преобразование размера:
произвольные TTS chunks склеиваются в текущем динамическом bounded accumulation buffer, затем извлекаются кусками
ровно `frame_bytes`; остаток сохраняется для следующего media tick.

Материализация in-process edge остаётся методом получателя. Никакой отдельный «владелец доставки» и никакой
межкомпонентный control signal не добавляются. `TtsOutputBuffer` владеет storage, accounting, backpressure/error
policy и lifecycle своего входа; `MediaPacer` владеет fixed-frame extraction/pacing; PJMEDIA callback владеет только
тактовым чтением одного кадра и не выполняет ожидание, блокирующий drain или inference.

## 6. Инварианты реализации

| Инвариант | Требование |
|---|---|
| Variable length | Текущая occupancy меняется по мере прихода и чтения chunks; размер одного TTS chunk и число chunks не должны быть заранее равны размеру ответа |
| Bounded safety | Buffer имеет явный защитный high-water; «динамический» не означает неограниченный. Нормальная запись при заполнении не превращается в silent drop |
| Exact accounting | Принятые bytes либо выдаются как `PcmFrame`, либо явно относятся к cancel/stale/close policy; каждый discard имеет причину и counter |
| Frame clock | Один media callback извлекает не более одного negotiated frame; если данных меньше frame, поведение padding/underrun явно тестируется |
| Non-blocking callback | PJMEDIA callback не ждёт TTS producer, не вызывает inference и не держит долгую lock-секцию |
| Completion/drain | После producer completion уже принятые bytes сохраняются; `DRAINING` заканчивается только после их выдачи |
| Barge-in | Cancel закрывает старое поколение и очищает/отбрасывает только его stale PCM по явной generation policy; новый ответ получает новый generation |
| Source selection | Intentional silence выбирается отдельным источником в `IDLE`/`CANCELLED`/`CLOSED`; она не записывается в TTS buffer |
| Observable failure | `dropped_overflow_bytes`, `dropped_stale_bytes`, `accepted_bytes`, `emitted_bytes`, `underruns`, `startup_wait` и source transitions не противоречат фактическому PCM |

## 7. Срезы исполнения

### E1. Evidence baseline и контракт владельца

Сохранить r7 как immutable diagnostic baseline, воспроизвести byte/frame accounting на минимальном fixture и
зафиксировать точный путь, на котором текущий `push()` допускает потерю chunk. Уточнить в тестах существующие
типизированные методы, не создавая новые boundary types.

Acceptance:

- источник observed gap и текущая причина потери имеют raw test evidence;
- подтверждено, что исправление относится к существующему `TtsOutputBuffer`/`MediaPacer` owner;
- подтверждено отсутствие необходимости в новом signal, delivery owner, process или Map-I revision;
- сделан baseline inventory counters до исправления.

Stop:

- если требуются новые typed boundary, owner, process protocol или изменение Map-I — category 4 APG gap;
- если причина полностью внешняя и не воспроизводится в текущем write-set — сохранить evidence и зарегистрировать
  category 3, не объявляя TTS pass.

### E2. Dynamic TTS output buffer и framing

Изменить существующий playback path так, чтобы chunks добавлялись в receiver-owned dynamic accumulation buffer, а
media callback извлекал `frame_bytes` по одному кадру. Буфер может быть реализован очередью PCM segments с cursor либо
эквивалентным storage; способ не фиксируется планом, пока сохраняются typed boundary и инварианты раздела 6. Для
компенсации обычного jitter основного loop `MediaPacer` использует ограниченный lookahead не более половины ptime
и 10 ms; это только предварительное заполнение direct media buffer, а не изменение media cadence.

Обязательные свойства:

- chunk меньше, равен или больше `frame_bytes` обрабатывается без потери;
- один chunk может породить несколько frames, несколько chunks — один frame;
- остаток между callbacks сохраняется;
- producer completion не очищает остаток;
- normal overflow не молча отклоняет chunk. Если нужен high-water, producer получает backpressure/явную ошибку,
  а runtime wiring её учитывает и сохраняет диагностическую причину;
- emergency silence остаётся source selection media owner-а, а не payload TTS buffer-а.

### E3. Lifecycle, cancellation и regression tests

Добавить/обновить deterministic unit, contract и target-compatible tests для:

- exact byte/frame accounting при произвольных chunk boundaries;
- быстрых chunks и медленного producer-а;
- producer completion, `DRAINING` и последнего media frame;
- barge-in/cancel, stale generation, close и повторного close;
- empty buffer в `PREROLL`, active producer в `PLAYING`, exhausted buffer после completion;
- high-water/backpressure/error path без silent drop;
- несоответствия counters и фактического PCM;
- non-blocking media callback и absence of inference call внутри callback.

После focused tests обязательны targeted playback tests, contract tests и полный доступный target regression. Красный
category 1/2 результат исправляется в этом write-set и прогоняется повторно; `skip`/`xfail` для ожидаемой ошибки не
принимается.

### E4. Main-executor target live gate и closeout

После E2/E3 главный executor последовательно выполняет новый clean-start прогон с прогретыми моделями и свободным
GPU. Для диагностических итераций использованы новые roots `r8` и `r9`; финальный output root —
`005-E/target-20260904-r10/`; r7 не перезаписывается.

Обязательное evidence:

- target runtime/no-GIL и versions/config;
- warmup/readiness отдельно от turn latency;
- фактические `TtsPcmChunk`/accepted/emitted/discarded byte/frame counters;
- полная Baresip raw `enc`/`dec` запись и stereo derivative с проверенным mapping;
- ручная проверка слышимости каждого обязательного ответа и автоматические сценарные assertions;
- report/evidence index и closeout с classification всех красных результатов.

E4 не запускается параллельно с другим GPU-heavy процессом и не делегируется субагенту. Документальная подготовка,
unit/contract fixtures и анализ E1–E3 могут выполняться параллельно только при disjoint write-set; общий registry,
backlog, Map-005 и финальный gate изменяет main executor последовательно.

## 8. Blocker register

| ID | Триггер | Действие | Статус |
|---|---|---|---|
| `B-005-E-001` | Для исправления нужен новый typed boundary, owner, process protocol, межкомпонентный signal или Map-I revision | Остановить affected slice, оформить APG gap и owner review; не скрывать gap adapter-ом | `none until triggered` |
| `B-005-E-002` | Dynamic storage нельзя реализовать с bounded high-water и явной backpressure/error policy | Не вводить truly unbounded memory; зафиксировать category 4 gap и остановить E2 | `none until triggered` |
| `B-005-E-003` | Target GPU/runtime недоступен, warmup не завершает реальную операцию или disk guard ниже 20 ГБ | Повторить после изменения внешнего условия; не выдавать target/live claim за pass | `none until triggered` |
| `B-005-E-004` | После corrective pass E4 обязательная полнота TTS остаётся красной, но причина требует только текущего owner/write-set | Продолжить corrective pass в E2/E3; это не owner-review blocker | `none until triggered` |
| `B-005-E-005` | После E2/E3/E4 остаётся category 4 gap или обязательное live evidence невозможно получить | Зарегистрировать blocker для Map-005 closeout с raw evidence и condition promotion | `none until triggered` |

`r7` и его заявленный `egress_underruns=0` не отменяют пользовательское аудио-наблюдение. До E4 это историческое
evidence полного сценария, но не acceptance полноты TTS payload. Category 1/2 дефект исправляется внутри плана;
только триггеры `B-005-E-001`, `B-005-E-002` или `B-005-E-005` требуют остановки по APG.

## 9. Test/evidence commands и критерии закрытия

Конкретные команды наследуются от утверждённых `005-C`/`005-D` runbooks и зафиксированы в
[`005-E commands`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-E/commands.md).
Выполнен следующий порядок:

```text
1. target unit tests for output buffer/framer/pacer;
2. target contract tests for TtsPcmChunk → PcmFrame → PlaybackChannel;
3. target regression after corrective pass;
4. one main-executor clean-start live/rehearsal gate with a new 005-E evidence root;
5. document registry and task backlog audits after synchronization.
```

План получает `complete` только если E1, E2, E3 и E4 имеют собственные evidence, focused/contract/regression tests
проходят, новый stereo recording содержит полный фактически слышимый TTS output, counters объяснимы, а Map-005 и
downstream Map-006 синхронизированы. Частичный результат или статус `foundation complete` не является closeout.

Если execution останавливается, closeout получает только `blocked` с конкретным blocker ID и raw evidence. Нельзя
закрыть этот план как `complete`, ссылаясь только на отсутствие `egress_underruns` или на старый r7.

## 10. Fallback/deferred register

| ID | Решение | Статус |
|---|---|---|
| `D-005-E-001` | Не заменять TTS предварительно записанной фразой, фиксированным ответным WAV или model-only shortcut | `forbidden` |
| `D-005-E-002` | Не увеличивать фиксированную ёмкость до размера «типичного ответа» как единственное исправление | `forbidden as sole fix` |
| `D-005-E-003` | Не вводить truly unbounded buffer; bounded high-water и backpressure/error должны оставаться явными | `forbidden` |
| `D-005-E-004` | Не менять TTS/LLM/SIP кандидата и не переносить PCM через Dispatcher/Event Bus | `deferred/out of scope` |

## 11. Execution report

E1–E4 выполнены главным executor-ом. Фактический результат и raw commands находятся в
[`005-E commands`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-E/commands.md),
а audio audit и файл для прослушивания — в [`005-E audio audit`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-E/audio-audit.md).

- r7 gap классифицирован как category 1 в существующем TTS/playback write-set;
- изменены `TtsOutputBuffer`, `MediaPacer`, runtime diagnostics и focused tests; новые boundary/signal/owner не добавлены;
- focused tests: `15 passed`; host regression: `151 passed, 5 skipped`; target regression: `154 passed, 2 skipped`;
- финальный target gate: [`target-20260904-r10`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-E/target-20260904-r10/);
- target runtime — CPython `3.14.7t`, `gil_enabled=false`; full scenario и Baresip stereo recording — `pass`;
- `accepted_bytes=679084`, `emitted_bytes=590400`, `dropped_overflow_bytes=0`, `dropped_tail_bytes=88982`,
  `buffered_bytes=0`, `pending_frames=0`; tail относится к barge-in generation cancellation;
- media `egress_underruns=0`, `egress_dropped_overflow=0`, `callback_errors=0`;
- plan closeout — `complete`; Map-005 map-level closeout разрешён.
