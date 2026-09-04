# APG-аудит Map-005

Дата: `2026-09-04`

## Объём проверки

Проверены:

- [`docs/architectural-planning-gate.md`](../../../docs/architectural-planning-gate.md);
- [`docs/development-guidelines.md`](../../../docs/development-guidelines.md);
- [`docs/roadmap.md`](../../../docs/roadmap.md);
- [`docs/requirements.md`](../../../docs/requirements.md);
- [`docs/architecture.md`](../../../docs/architecture.md);
- [`docs/technical-specification.md`](../../../docs/technical-specification.md);
- [`docs/plans/plan-005-system-testing-and-demo-readiness.md`](../../../docs/plans/plan-005-system-testing-and-demo-readiness.md);
- child plans `005-A`–`005-E`;
- [`docs/document-registry.md`](../../../docs/document-registry.md) и [`docs/task-backlog.md`](../../../docs/task-backlog.md).

Проверка начата как audit документа-карты перед началом исполнения child plans. После принятия группового owner review
`2026-09-04` в этот же audit последовательно добавлены результаты исполнения `005-A`–`005-D`. Пользовательское
прослушивание r7 после closeout выявило mid-stream потерю большей части TTS output, поэтому ниже добавлено текущее
corrective состояние `005-E`; исторические записи о r7 не перезаписываются.

## Результаты применения APG

### 1. Классификация и декомпозиция

`Map-005` подтверждена как `map`, а не узкий child plan: она содержит независимые
acceptance boundary — protocol/media, speech/audio, AI/resource, rehearsal/evidence и corrective TTS/playback — с
разными владельцами, write-set и зависимостями. Созданы self-contained child plans:

| Child | Назначение | Write-set | Зависимость/режим |
|---|---|---|---|
| `005-A` | SIP/media protocol и failure matrix | `sip_media/adapter.py` только protocol-методы, собственные tests/tool/evidence | Deterministic preparation может идти параллельно B; live gate — main executor |
| `005-B` | audio/speech resilience | `media/` и `speech/`, собственные tests/evidence | Deterministic preparation может идти параллельно A; target ASR — main executor |
| `005-C` | RAG/LLM/TTS/resource/playback gate | `tts/`, `playback/`, `media_port.py`, scoped `runtime_wiring.py`, собственные tests/tool/evidence | GPU/TTS gate — последовательно main executor |
| `005-D` | clean-start rehearsal и closeout | собственные tools/tests/evidence; production `src/` защищён | Только после A–C closeout |
| `005-E` | corrective TTS/playback integrity | существующие `tts/`, `playback/`, scoped media/wiring methods и собственные tests/evidence | После r7 audio review; E4 main executor sequential |

Пересечение A/C по `sip_media/adapter.py` устранено в ходе APG-аудита: C больше не имеет
этот файл в write-set. Общие документы, registry, backlog, конфигурация и существующие
закрытые gates защищены от child-plan изменений.

### 2. Материализованные правила и ранее принятые решения

В карту и child plans явно перенесены применимые правила:

- typed-first и existing-owner: новый delivery owner или скрывающий adapter не добавляется;
- control plane через Dispatcher/Event Bus, крупные audio/text payloads — по прямым typed edges;
- между потоками только bounded thread-safe queue, `asyncio.Queue` только в основном loop;
- SIP-ответы выполняются локально у `SipMediaAdapter` и не ожидают AI/Dispatcher;
- `Map-002-I revision 21` — authoritative topology и propagation baseline;
- `Qwen3.5-9B` — единственный primary AI candidate, GPU-пробы выполняет main executor;
- warmup до SIP admission, свободный диск не менее 20 ГБ, no-GIL target `CPython 3.14.7t`;
- `report.md` — единственный обязательный итоговый артефакт; отдельный `state.json` не требуется;
- runtime бота не пишет аудио, запись полной стороны разговора выполняется Baresip test peer;
- для recording evidence сохраняются raw `enc`/`dec`, а stereo derivative строится отдельным harness;
- `egress_underruns` считается только для пустого TTS-источника в `PLAYING`; intentional silence и startup wait отделены;
- динамический TTS accumulation означает переменную occupancy bounded receiver-owned buffer, а не fixed response-sized
  buffer и не truly unbounded storage; normal payload не может молча теряться при `push()`.

### 3. APG structural checks

Каждый child plan содержит необходимые APG-разделы:

- применимые документы и материализованные правила;
- границу, source-map и disjoint write-set;
- interaction topology и propagation;
- audit владельца поведения и парадигмы исполнения;
- owner-review decisions;
- process/architecture invariant audit;
- implementation slices;
- blocker register;
- test plan/evidence;
- fallback/deferred register;
- binary execution report/closeout.

Все ссылки на child plans существуют. Запущены проверки:

```text
python tools/check_document_registry.py
document registry audit: actual=45 registry_rows=45 registry_unique=45 missing=0 extra=0 duplicate_paths=0
document registry audit: PASS

python tools/check_task_backlog.py
task backlog audit: rows=8 unique_ids=8
task backlog audit: PASS
```

### 4. Статусы после аудита и исполнения

- `Map-005`: `complete`; A–D и corrective `005-E` закрыты, r10 принят как TTS acceptance evidence;
- `B-005-001` карты: `resolved`;
- `005-A`: `complete` по собственному deterministic/live evidence `2026-09-04`;
- `005-B`: `complete`; deterministic, target ASR/stale/cancel и PCMU-derived application path passed;
- `005-C`: `complete`; real RAG/LLM/XTTS, source-mode live path и regression закрыты собственным evidence;
- `005-D`: `complete`; clean-start r7, J4 `pass`, 6/6 checks, Baresip raw/stereo recording, report и requirement matrix;
- `TASK-008`: `done`; A–E и map-level acceptance закрыты по r10;
- child code/evidence/GPU execution: `005-A`–`005-D` выполнены по APG; тяжелые target-прогоны запускал main executor.

## Снятие owner-review gate и переход к execution

Owner review `005-A`–`005-D` принят групповой фиксацией владельца `2026-09-04`; соответствующие
процессные blockers `B-005-A-001`/`B-005-B-001`/`B-005-C-001`/`B-005-D-001` сняты.

Предыдущее согласование Map-005 не заменяло этот gate; групповой owner review снял его для всех `005-A`–`005-D`,
отдельное согласование каждого child plan не требуется.

Исполнение шло с A/B: deterministic-подготовка могла идти параллельно, live/target прогоны выполнены главным
executor-ом последовательно; `005-A`–`005-D` закрыты. Отдельное согласование каждого child plan не было дополнительным
gate после принятия группового owner review; execution продолжался до полного map-level closeout.

### 5. Execution update — 005-B

`005-B` закрыт `complete` после main-executor проверки: target deterministic matrix `9 passed`; faster-whisper
streaming и generator-close cancellation — `pass`; узкий application probe подтвердил
`PCMU → decode_pcmu_frame → PcmFrame → AsrChunker → FasterWhisperC2Backend → FinalUserTurn`; full target regression
`141 passed, 2 skipped`. Все промежуточные красные результаты были category 2/3, получили corrective retry и не
превратились в blocker. Evidence и команды находятся в `005-B/commands.md`, `target-20260904-r2/` и
`target-20260904-r4/`; closeout — `005-B/closeout.md`.

### 6. Execution update — 005-C

`005-C` закрыт `complete`. В существующих media/playback owners реализованы typed `EgressSourceMode` и lifecycle
переключение `IDLE/PREROLL/PLAYING/DRAINING/CANCELLED/CLOSED`; live J4 после изменения подтвердил
`egress_underruns=0`, `tts_startup_wait=132`, `intentional_silence_frames=4629`, `source_mode_transitions=16`,
`callback_errors=0`, dropped/stale=0. Main AI gate подтвердил positive/negative source-aware RAG,
Qwen3.5-9B/Ollama и XTTS output на no-GIL runtime; target regression — `147 passed, 2 skipped`.

Latency observation сохранён как ограничение качества, а не скрыт: final phrase→first useful LLM `488.600 ms`,
final phrase→first PCM `1785.090 ms`, поэтому overall `200–500 ms` target не объявлен достигнутым.
Evidence и команды находятся в `005-C/commands.md`, `005-C/target-20260904-r1`, `005-C/target-live-20260904-r1`;
closeout — `005-C/closeout.md`.

### 7. Execution update — 005-D

`005-D` закрыт `complete` после main-executor clean-start rehearsal на target CPython `3.14.7t`,
`gil_enabled=false`. Промежуточный r5 выявил один tail underrun, поэтому выполнен corrective pass в существующем
TTS/media owner: добавлен typed `DRAINING`, а stale/closed TTS chunk больше не возвращает источник в `PREROLL`.
Финальный [`target-20260904-r7`](005-D/target-20260904-r7/) подтвердил J4 `pass`, 6/6 checks,
6 пользовательских ходов, 4 ответа, follow-up, barge-in, unknown-answer/transfer, fake operator transfer и terminal
report. SIP/RTP — PCMU/8000/mono, ptime 20 ms, peer packets `4913/5089`; media drops `0`, callback errors `0`,
`egress_underruns=0`, `tts_startup_wait=209`, `intentional_silence_frames=4564`, `source_mode_transitions=19`.

На peer-side Baresip `sndfile` сохранены raw `enc`/`dec`. Stereo artifact имеет mapping
`left=user_to_bot`, `right=bot_to_user`, 2 channels/PCM16/8000 Hz и duration `101.68 s`; `27360` нулевых кадров,
добавленных в конец более короткого `enc`, явно записаны в manifest. Target source-mode/recording/rehearsal tests: `7 passed`;
full target regression после corrective pass: `151 passed, 2 skipped in 9.50s`. Ранние r1–r6 сохранены как raw corrective
evidence; r6 не принят из-за незавершившегося внешнего operator peer, category-4 blocker не зарегистрирован. Closeout:
`005-D/closeout.md`.

### 8. Финальный APG/map-level check

Все child plans `005-A`–`005-D` имеют binary `complete`, собственные evidence и closeout. Map-level matrix покрывает
SIP/RTP, speech/ASR, RAG/LLM/TTS, FSM, barge-in, transfer, report, runtime/no-GIL и Baresip recording. Общее latency
ограничение из `005-C` сохранено как known limitation: final phrase→first PCM выше ориентира 200–500 ms; это не выдано
за достигнутый target и не является category-4 blocker для принятого MVP.

### 9. Execution update — corrective pass и финальная проверка

Причина r5 `egress_underruns=1` классифицирована как category-2 race в уже разрешённой source-selection boundary:
последний TTS frame покидал прикладной playback buffer раньше, чем PJMEDIA дочитывал media-egress buffer. Это не требовало
нового владельца, нового межпроцессного протокола или owner review. В существующий owner добавлен режим `DRAINING`; в нём
media callback дочитывает queued кадры, а первый пустой запрос переводит источник в `IDLE` и учитывается как intentional
silence. Stale/closed TTS chunks не меняют source mode.

После corrective pass выполнены:

`target source-mode/recording/rehearsal tests: 7 passed`; `target full regression: 151 passed, 2 skipped in 9.50s`;
`final clean-start D rehearsal: pass, 6/6 checks, egress_underruns=0`.

Финальный evidence root — `005-D/target-20260904-r7/`. После синхронизации выполнены:

`document registry audit: actual=49 registry_rows=49 registry_unique=49 missing=0 extra=0 duplicate_paths=0`
`document registry audit: PASS`
`task backlog audit: rows=9 unique_ids=9`
`task backlog audit: PASS`.

## 10. Post-closeout corrective update — 005-E

### 10.1. Наблюдение и классификация

Пользовательское прослушивание
[`conversation-stereo.wav`](005-D/target-20260904-r7/recordings/conversation-stereo.wav) показало, что в каждом
ответе слышен только короткий фрагмент, после которого полезный TTS в основном сменяется тишиной. Это противоречит
ожидаемой полноте ответа, даже если технические counters r7 показывают `egress_underruns=0`. Текущая диагностика
указывает на уже существующий fixed-capacity `TtsOutputBuffer`: chunk мог быть отклонён до PJMEDIA, а результат
`push()` не превращался в обязательную observable ошибку.

Классификация: category 1 implementation defect в существующем TTS/playback write-set. Нового межкомпонентного
сигнала, delivery owner, процесса, typed boundary или Map-I revision не требуется. Поэтому это не owner-review blocker;
исправление должно быть выполнено corrective pass с targeted, contract и regression reruns.

### 10.2. APG-решение и новый execution path

В Map-005 был добавлен self-contained child plan
[`plan-005-E-tts-playback-integrity-corrective.md`](../../../docs/plans/plan-005-E-tts-playback-integrity-corrective.md)
с четырьмя узкими срезами:

1. `E1` — immutable r7 evidence, byte/frame accounting и audit существующего owner/boundary;
2. `E2` — dynamic bounded accumulation в существующем `TtsOutputBuffer`/`MediaPacer`, один negotiated frame на media tick;
3. `E3` — lifecycle, completion/drain, cancel/barge-in, stale, overflow/backpressure и contract/regression tests;
4. `E4` — единственный main-executor clean-start target live gate с новым r10 evidence root и полной Baresip stereo записью.

Внутренняя materialization остаётся методом receiver-а: `TtsPcmChunk → TtsOutputBuffer → PcmFrame → PlaybackChannel`.
Межкомпонентный signal и передача PCM через Dispatcher/Event Bus не добавляются. «Динамический» буфер остаётся bounded;
если окажется невозможным реализовать явный high-water/backpressure/error policy, это будет отдельный category-4 APG gap.

### 10.3. Текущее состояние зависимых документов

- `005-E` имеет binary статус `complete`; отдельный owner review не требовался по явному решению владельца;
- Map-005 имеет статус `complete`: E1–E4 и map-level acceptance закрыты по target r10;
- `TASK-008` имеет статус `done`;
- Map-006 и его report/demo artifacts закрыты техническим refresh по принятому r10 evidence;
- закрытые планы `005-C`/`005-D` и исторические r7 artifacts не изменяются.

Открытого category-4 blocker-а после исполнения `005-E` нет. Исполнение останавливается только при срабатывании
blocker register `B-005-E-001`/`B-005-E-002`/`B-005-E-005` либо при другом доказанном APG gap.

### 10.4. Финальный corrective closeout — r10

`E1`–`E3` прошли focused, host и target regression tests; `E4` выполнен главным executor-ом на target CPython
`3.14.7t` с `gil_enabled=false`. Clean-start r10 прошёл полный SIP/RTP сценарий, все `7/7` checks и Baresip
stereo recording. Зафиксировано: `accepted_chunks=48`, `accepted_bytes=679084`, `emitted_frames=1845`,
`dropped_overflow_bytes=0`, `buffered_bytes=0`, `pending_frames=0`, `egress_underruns=0`,
`egress_dropped_overflow=0`, `callback_errors=0`; `dropped_tail_bytes=88982` относится к явной отмене старого
поколения при barge-in. Audio audit r10 не обнаружил прежних многосекундных TTS-провалов.

`Map-005` и `005-E` закрыты. Исторические r7 artifacts не перезаписываются; downstream Map-006 завершил
технический refresh source-index, runbook, report claims и closeout по r10. Отдельные редактура, лицензирование и
публикация остаются за пределами технического closeout.
