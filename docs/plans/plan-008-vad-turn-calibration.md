# Карта 8: калибровка VAD и TurnDetector для телефонных условий

Уровень документа: `map`  
Идентификатор: `Map-008`  
Статус: `complete`  
Дата подготовки: `2026-09-13`  
Родитель: [`roadmap.md`](../roadmap.md)  
Предшественник: [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21

## 1. Цель и проверяемый результат

Настроить ранее подключённый WebRTC VAD и существующую связку `VAD + TurnDetector` для условий телефонного разговора
на воспроизводимом наборе фонограмм, сгенерированных одним фиксированным голосом TTS и содержащих множество разных
фраз.

Карта должна дать два последовательно полученных результата:

1. выбранный режим WebRTC VAD (`0..3`) для телефонного PCM-тракта;
2. параметры и поведение существующего `TurnDetector`, при которых последовательность VAD-решений преобразуется в
   ожидаемые пользовательские ходы без недопустимого дробления или объединения фраз.

Проверяемый тракт калибровки:

```text
TTS phrase set + timing manifest
        → telephone-condition fixture (PCMU/8 kHz/mono/20 ms)
        → WebRTC VAD mode sweep
        → VadDecision trace
        → TurnDetector
        → EndpointEvent / FinalUserTurn expectation
```

ASR не является входом для выбора режима VAD или настройки `TurnDetector`. Его offline-результат может использоваться
только как дополнительная проверка содержательной целостности фонограммы и обнаружение проблем, которые не объясняются
VAD/endpointing.

## 2. Почему это карта, а не один plan-file

Работа содержит три разные acceptance boundaries:

1. воспроизводимый тестовый корпус, телефонная деградация и независимый покадровый sweep WebRTC VAD;
2. настройка владельца endpointing по зафиксированному VAD trace;
3. проверка выбранной конфигурации на существующей application/live boundary.

У этих границ разные владельцы, write-set, runtime и stop conditions. Поэтому карта декомпозируется на:

- [`008-A`](plan-008-A-vad-standalone-calibration.md) — корпус, phone-condition replay и standalone VAD calibration;
- [`008-B`](plan-008-B-vad-turn-detector-calibration.md) — VAD trace replay и настройка `TurnDetector`;
- [`008-C`](plan-008-C-vad-application-validation.md) — application/live validation и downstream ASR check.

На момент подготовки эти файлы были планом; execution stage завершён ниже в соответствии с APG.

## 3. Применимые документы и материализованные правила

| Источник | Точная применимая формулировка | Влияние на Map-008 | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Русский SIP-бот обслуживает один звонок, использует PCMU и локальные ASR/LLM/TTS; запись разговора не принадлежит боту | Калибровка остаётся локальной, single-call и PCMU-oriented; запись не добавляется | Requirement/evidence matrix | Появился новый пользовательский scope, запись ботом или второй звонок |
| [`architecture.md`](../architecture.md) | VAD классифицирует PCM-кадры; `TurnDetector` владеет endpoint state; `Transcript Assembler` владеет сборкой текста | A тестирует classifier отдельно, B — существующего owner endpointing; ASR не подменяет VAD | Ownership/source audit | Потребовался новый production owner или semantic endpointing |
| [`technical-specification.md`](../technical-specification.md) | Внутренний звук — mono PCM S16LE; базовый SIP media profile — PCMU, 8 kHz, а фактические `ptime`/profile negotiated per call | Fixture проходит PCMU round-trip и replay-ится кадрами 20 ms как согласованный MVP baseline; скрытый media default не меняется | Fixture manifest и media-profile evidence | Нужен новый audio format/boundary или неверен negotiated profile |
| [`development-guidelines.md`](../development-guidelines.md) §2–§3 | Typed-first, owner behavior, direct data plane, bounded storage и явные lifecycle/cancel/close | Offline harness не становится production component; существующие `PcmFrame`, `VadDecision`, `EndpointEvent` сохраняются | Typed/source-map audit и tests | Новый production edge, очередь или обход владельца |
| [`development-guidelines.md`](../development-guidelines.md) §6 | Обязательны targeted/contract/regression tests, raw output, exit codes и corrective pass | Каждый режим и каждое endpoint-решение имеют trace и повторяемую проверку; красный тест исправляется в write-set | Test/evidence package | Category-4 gap после corrective pass |
| [`development-guidelines.md`](../development-guidelines.md) §7–§8 | Молчаливое упрощение и fallback запрещены; child plan закрывается только `complete` или `blocked` | Amplitude VAD не возвращается в live; сравнение с ним возможно только как явно маркированный контрольный test double | Fallback register и closeout audit | Попытка скрыть WebRTC failure за amplitude или partial closeout |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Непересекающиеся write-set можно делегировать; общий config/docs и финальные gates синхронизирует main executor | A/B/C выполняются последовательно по evidence; независимая подготовка fixtures допустима только при disjoint write-set | Handoff/diff audit | Пересечение write-set или неподтверждённый handoff |
| [`documentation-process.md`](../documentation-process.md) | Один владелец факта, ссылки вместо дублирования, registry/backlog пересчитываются после изменения | Фактические параметры и evidence живут в Map-008/closeout, общие требования не копируются в другие owner docs | Registry/backlog check | Дублирующий или противоречащий source of truth |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Основной runtime — free-threaded CPython; native dependency проверяется фактически, GIL нельзя вернуть молча | A запускается в target `3.14.7t`; Map-007 native evidence используется как prerequisite, а не заменяется host test | Target runtime manifest | Новый native/API gap без patch или решения |
| [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md) | `WebRtcVadCandidate` — live candidate, `VAD_MODE=2` — baseline; mode можно менять только по evidence; amplitude — deterministic test double | Карта не переоткрывает выбор алгоритма, а измеряет mode и при необходимости предлагает evidence-based изменение mode | Map-007 closeout и A evidence | Требуется новый VAD algorithm, fallback или protected-boundary change |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Authoritative speech edges: `PcmFrame → VadProcessor → VadDecision → TurnDetector`; Dispatcher/Event Bus не переносят PCM | Production topology не меняется; offline replay — тестовый harness, C проверяет те же typed edges | Propagation checkpoint и source audit | Фактический тип или consumer не совпадает с Map-I |

## 4. Граница задачи

### Входит

- фиксированный голос TTS и набор разных русских фраз;
- короткие/длинные фразы, числа, имена/термины, разные фонетические составы;
- известные интервалы тишины между фразами, включая границы около 300/500 ms;
- сохранённый manifest с текстом, voice/generation parameters, offsets, PCM/WAV hashes и ожидаемой структурой ходов;
- телефонный baseline: mono PCM S16LE, PCMU encode/decode round-trip, 8 kHz, 20-ms frames;
- отдельный sweep WebRTC VAD modes `0..3` без SIP, ASR, LLM и TTS inference в цикле измерения;
- покадровые решения, ошибки классификации, onset/offset и устойчивость на всём наборе;
- replay VAD trace через существующий `TurnDetector` и настройка его endpoint policy;
- regression/application/live validation выбранной конфигурации;
- optional offline ASR как вторичная проверка содержательной целостности, не как gold label для VAD;
- evidence, closeout, registry/backlog и передача следующего шага в мастер-класс.

### Не входит

- новый VAD algorithm, neural VAD или semantic turn detector;
- обучение/дообучение TTS, ASR или WebRTC VAD;
- выбор голоса по качеству TTS, кроме фиксации одного воспроизводимого голоса для корпуса;
- обязательная ручная разметка большого корпуса человеческих записей;
- заявка на production precision/recall, MOS, шумовую кампанию или multi-speaker generalization;
- изменение `PcmFrame`, `VadDecision`, `EndpointEvent`, `FinalUserTurn` или Map-I без отдельного propagation gate;
- новый audio fan-out, event-bus audio path, IPC или production data component;
- полноценный ASR/LLM/TTS live gate как часть A/B calibration;
- запись разговора runtime-бом; fixture WAV не является записью SIP-разговора.

### Protected baseline

- Map-007 accepted WebRTC path и patched `webrtcvad-wheels 2.0.14`;
- текущий `WebRtcVadCandidate`, `VadProcessor`, `TurnDetector` и `SpeechIngress` owners;
- `PcmFrame → VadDecision → TurnDetector` и revision 21 Map-I;
- `VAD_MODE=2` как evidence-based решение Map-008;
- `ENDPOINT_SOFT_MS=300`, evidence-based `ENDPOINT_HARD_MS=520`, `MIN_SPEECH_MS=80`;
- PCMU/8 kHz/mono и per-call negotiated profile в application path;
- deterministic `_AmplitudeVad` только в существующих контрольных тестах;
- один звонок, обязательный итоговый report и отсутствие аудиозаписи со стороны runtime.

### Предположения

- XTTS может один раз создать стабильный набор фраз, после чего артефакты не перегенерируются в каждом сравнительном
  прогоне;
- генератор fixture может записать ожидаемые offsets и структуру пауз без использования ASR;
- текущий target no-GIL runtime и WebRTC binding из Map-007 доступны;
- application/live validation выполняется главным executor последовательно после A и B;
- изменение `VAD_MODE` или endpoint constants по evidence не меняет typed boundary и не требует нового owner.

## 5. Текущее состояние и gap

| Область | Состояние после Map-007 | Gap Map-008 |
|---|---|---|
| WebRTC binding | `webrtcvad-wheels 2.0.14` patched, target/combined no-GIL pass | Нет систематического сравнения modes `0..3` на множестве фраз |
| Live candidate | `WebRtcVadCandidate(mode=2)` подключён в I1/J4 | Mode 2 пока baseline, а не evidence-based calibration result |
| Fixture | Есть compact multi-turn XTTS fixture для live gate | Нет отдельного immutable corpus/manifest для VAD metrics |
| Endpointing | `TurnDetector` использует 300/520 ms и min speech 80 ms | Калибровка закрыта на controlled TTS corpus; human/noise generalization deferred |
| ASR | Работает в полном pipeline | Нельзя использовать его full-pipeline result как единственную VAD-разметку |
| Evidence | Есть live traces WebRTC | Нет независимого mode sweep и воспроизводимого VAD/endpoint scorecard |

## 6. Test-only interaction topology

Map-008 не добавляет production boundary. Для измерения создаётся только тестовый replay-контур:

```text
TTS artifacts + timing manifest
        → PhoneConditioner (test-only)
        → PcmFrame replay (test-only)
        → WebRtcVadCandidate(mode)
        → VadDecision trace
        → TurnDetector replay
        → endpoint scorecard
```

`PhoneConditioner` не является новым runtime-компонентом бота: это test helper, который фиксирует PCMU round-trip,
частоту, каналы и frame alignment. В полном application path остаются существующие edges:

```text
PcmFrame → VadProcessor → VadDecision → TurnDetector → EndpointEvent
```

ASR используется после этих этапов и не участвует в выборе VAD mode. Event Bus, Dispatcher и PCM fan-out в offline
calibration не участвуют.

### 6.1. Typed edges и propagation checkpoints

| Ребро | Output | Consumer input method | Контекст вызова | Checkpoint |
|---|---|---|---|---|
| `A.test-replay → WebRtcVadCandidate` | `bytes` mono PCM S16LE frame + `sample_rate_hz` | `WebRtcVadCandidate.is_speech(pcm_s16le, sample_rate_hz)` | Один последовательно обрабатываемый 20-ms frame после PCMU round-trip | `A1` |
| `VadProcessor → TurnDetector` | `VadDecision` | `TurnDetector.consume(decision)` | В исходном порядке кадров, с call/channel/generation scope из replay | `B1` |
| `TurnDetector → B.scorecard` | `tuple[EndpointEvent, ...]` | test observer/replay collector | После каждого `consume`; authoritative hard endpoint считается один раз | `B2` |
| `C.application → existing speech path` | existing `PcmFrame` | `VadProcessor.process(frame)` | Existing live wiring and negotiated media profile | `C1` |

Map-008 не меняет эти output-типы и не вводит отдельный delivery-owner. Изменение любого consumer method, scope или
контракта требует propagation checkpoint и нового owner review по APG.

## 7. Audit владельца поведения и парадигмы реализации

- `WebRtcVadCandidate` владеет только классификацией одного допустимого PCM frame;
- `VadProcessor` владеет преобразованием candidate result в typed `VadDecision`;
- `TurnDetector` владеет temporal endpoint state, soft/hard thresholds, pause/resume и authoritative hard endpoint;
- calibration harness владеет только fixture replay, trace и метриками; он не становится production owner и не меняет
  control plane;
- источник эталонных границ — timing manifest сборщика TTS-фактуры. ASR transcript/timestamps — вторичный diagnostic
  signal;
- если для сглаживания VAD-ошибок понадобится изменение поведения, оно остаётся в существующем `TurnDetector`, а не
  оформляется скрытым новым `VadSmoother` без отдельного boundary plan.

## 8. Source-map и write-set карты

| Область | Источник/файл | Целевое действие | Владелец | Write-set |
|---|---|---|---|---|
| Corpus/manifest | `artifacts/implementation/008-vad-turn-calibration/008-A/` | Создать TTS corpus, PCMU-conditioned fixtures и labels | `008-A` | Только собственный evidence root и test fixture tool |
| VAD probe | новый `tools/vad_calibration_probe.py` | Sweep modes, replay frames, emit raw trace/metrics | `008-A` | Новый test-only tool; production `src/` запрещён |
| VAD tests | `tests/unit/`/`tests/contract/` | Проверить frame format, mode sweep and deterministic replay | `008-A` | Новые targeted tests; исторические tests не переписывать |
| Endpointing | `src/sip_bot/speech/endpointing.py`, `config/constants.py` | Только evidence-based настройка существующего owner/constant | `008-B` | Existing endpoint symbols/constants and B evidence; no new component |
| Endpoint tests | `tests/unit/`, `tests/integration/` | Проверить split/merge/pause/resume/hard endpoint | `008-B` | Новые tests и собственный evidence; no unrelated runtime |
| Application/live validation | `tools/live_i1_gate.py`, `tools/j4_full_live_gate.py` при необходимости | Проверить selected mode and final endpoint behavior | `008-C`/main executor | Только VAD mode/endpoint construction and evidence assertions |
| ASR secondary check | Existing offline ASR tools | Сверить expected text с ASR, не использовать как VAD gold label | `008-C` | Только own evidence; no ASR boundary change |
| Architecture/TЗ | `docs/architecture.md`, `docs/technical-specification.md` | Синхронизировать только фактический selected mode/endpoint baseline | main executor | Owner sections only, after evidence |
| Registry/backlog/roadmap | `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md` | Record map/status/next step and checks | main executor | Sequential docs sync |

Protected from modification: `Map-I` contracts, Map-007 historical evidence, SIP/media owners, ASR/LLM/TTS/RAG
implementation and unrelated presentation files.

## 9. Дочерние планы, зависимости и порядок

| ID | Plan-file | Назначение | Зависимости | Исполнитель | Acceptance boundary | Статус |
|---|---|---|---|---|---|---|
| `008-A` | [`plan-008-A-vad-standalone-calibration.md`](plan-008-A-vad-standalone-calibration.md) | Corpus, PCMU conditioning, manifest and modes `0..3` | Map-007 complete | main executor; target operation принял main executor | Immutable corpus, raw masks, comparative scorecard and mode recommendation | complete |
| `008-B` | [`plan-008-B-vad-turn-detector-calibration.md`](plan-008-B-vad-turn-detector-calibration.md) | Replay selected VAD trace and configure existing endpoint owner | `008-A` evidence | sequential main executor | Expected turns, no unacceptable split/merge, endpoint metrics and config decision | complete |
| `008-C` | [`plan-008-C-vad-application-validation.md`](plan-008-C-vad-application-validation.md) | Verify selected configuration on application/live path and optional ASR diagnostic | `008-B` complete | main executor for live gate | Same typed boundary, selected VAD in live, evidence-backed downstream behavior | complete |

`008-A → 008-B → 008-C` — sequential execution order. Corpus preparation may be parallelized only with unrelated
documentation preparation and only under disjoint write-set; no child may consume unaccepted evidence from a predecessor.

## 10. Owner-review решения, уже покрытые предыдущими решениями

| Вопрос | Применимое решение | Последствие | Статус |
|---|---|---|---|
| Нужно ли снова выбирать алгоритм VAD? | Нет, WebRTC VAD принят в `002-D` и подключён Map-007 | Сравниваем только modes и endpoint behavior | `resolved by prior decision` |
| Подходит ли один голос TTS для корпуса? | Да, для воспроизводимой первичной калибровки использовать один фиксированный голос и много фраз | Не перегенерировать вход в каждом прогоне; generalization вынести отдельно | `resolved by current owner instruction` |
| Нужен ли ASR в A/B? | Нет; manifest даёт первичную разметку, ASR — только secondary diagnostic | Исключается full-pipeline circularity | `resolved by current owner instruction` |
| Можно ли изменить `VAD_MODE`? | Да, только по сохранённому evidence; mode 2 остаётся baseline до результата | Изменяется только config decision, не boundary | `resolved by Map-007` |
| Можно ли добавить новый smoother component? | Нет молча; smoothing, если потребуется, принадлежит existing `TurnDetector` либо отдельному plan/review | Не появляется скрытый delivery/behavior owner | `resolved by architecture/APG` |
| Нужно ли калибровать по human corpus сейчас? | Нет, обязательный scope — controlled TTS corpus; human/noise generalization — отдельная future map | Не выдавать baseline за production quality | `resolved scope boundary` |

Открытых owner-review вопросов на этапе подготовки карты нет. Новый вопрос появляется только при фактическом изменении
protected boundary, создании production component или необходимости новой стратегии/fallback.

## 11. Process invariant audit

| Инвариант | Действие в Map-008 | Evidence |
|---|---|---|
| Typed-first | Не менять `PcmFrame`, `VadDecision`, `EndpointEvent`; replay использует те же формы данных | Contract tests и trace schema |
| Owner behavior | VAD не владеет endpointing; harness не владеет runtime behavior | Source-map/ownership audit |
| Direct data plane | Offline PCM идёт напрямую в VAD/TurnDetector; Dispatcher/Event Bus не участвуют | Forbidden-path source audit |
| Deterministic evidence | Один сохранённый corpus/hash используется всеми mode runs | Manifest/hash and repeated replay |
| Corrective protocol | Красный test/metric сначала классифицируется и исправляется в write-set, затем rerun | Raw output, exit code, corrective evidence |
| No silent simplification | Не удалять сложные фразы/паузы после неудобного результата; corpus changes получают новый revision | Corpus manifest diff and revision |
| Delegation | A/B/C имеют disjoint write-set; общие config/docs/live gates ведёт main executor | Handoff/diff audit |
| Binary closeout | Каждый child закрывается только `complete` или `blocked`; partial/foundation запрещены | Child closeouts and map gate |
| Registry discipline | После изменения docs запускаются registry checker; после backlog — backlog checker | Checker output |

## 12. Architecture invariant audit

| Инвариант | Затронутая граница | Проверка |
|---|---|---|
| `PcmFrame → VadProcessor → VadDecision → TurnDetector` остаётся authoritative | Existing speech boundary | Contract and propagation tests |
| TurnDetector владеет temporal state и hard endpoint | `VadDecision → TurnDetector.consume` | Replay tests, endpoint trace |
| PCM не идёт через Dispatcher/Event Bus | Test replay and live path | Source audit and counters |
| Negotiated media determines profile; test baseline is explicit | PCMU/8 kHz/mono/20 ms | Fixture manifest and live media profile |
| ASR cannot change VAD/endpoint labels | Calibration stages A/B | Tool dependency audit; optional ASR marked diagnostic |
| Existing lifecycle/close/stale rules remain | C live validation | Existing regression plus close/cancel tests |

## 13. Implementation slices

| Срез | Цель | Исполнитель | Acceptance | Следующий шаг |
|---|---|---|---|---|
| `A1` | Создать immutable corpus и timing manifest | main executor; подготовка corpus может быть передана субагенту с disjoint write-set | Hashes, source text, voice/generation parameters и expected intervals сохранены | `A2` |
| `A2` | Реализовать phone-condition replay и mode sweep | main executor или субагент в write-set `008-A` | Modes `0..3`, raw masks, metrics, repeatability | `B1` |
| `B1` | Replay selected VAD decisions в `TurnDetector` | main executor | `VadDecision → consume` сохранено; split/merge/pause/resume измерены | `B2` |
| `B2` | Зафиксировать endpoint configuration и tests | main executor; test preparation may be delegated | Evidence-based constants, targeted/contract/regression pass | `C1` |
| `C1` | Проверить selected config на application/live boundary | main executor | Live WebRTC, media profile, VAD trace, ASR independence | `C2` |
| `C2` | Синхронизировать closeout и документы | main executor | Evidence index, registry/backlog/roadmap checks, no open blocker | Map closeout |

Каждый child plan имеет собственный write-set, blocker register, target runtime и closeout. Незавершённый child не может
быть выдан за выполненный map-level slice; отдельное owner review child не повторяется после группового approval, если
в child нет нового вопроса.

## 14. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-008-A-001` | `008-A` | Target WebRTC binding из Map-007 нельзя повторно использовать или фактическая operation не проходит | VAD sweep | project owner | Target raw output and prior manifest | `none until triggered` |
| `B-008-A-002` | `008-A` | Невозможно создать immutable TTS corpus/manifest с известными offsets | Standalone calibration | project owner | Generator output and manifest audit | `none until triggered` |
| `B-008-A-003` | `008-A` | Для phone-condition fixture требуется новый production audio boundary | Map-008 | project owner | Gap record per APG §6 | `none until triggered` |
| `B-008-B-001` | `008-B` | Никакой mode не даёт проверяемого trade-off без изменения protected contract | Endpoint calibration | project owner | Scorecard and replay evidence | `none until triggered` |
| `B-008-B-002` | `008-B` | Требуется новый production component/semantic endpointing вместо existing TurnDetector | B/map closeout | project owner | Ownership/boundary gap | `none until triggered` |
| `B-008-C-001` | `008-C` | Selected configuration не воспроизводится на existing application/live boundary | Application promotion | project owner | Live manifest and source audit | `none until triggered` |
| `B-008-MAP-001` | map gate | Acceptance требует VAD algorithm replacement, new IPC, protected boundary change или production-quality claim | Map closeout and dependents | project owner | Map gap record | `none until triggered` |

Красный unit/metric result в пределах approved write-set не является blocker: выполняется corrective pass. Blocker
возникает только при category-4 gap, внешней невозможности получить обязательное evidence или новом owner-review trigger.

## 15. Test plan и evidence

### 008-A

- corpus manifest с фиксированным голосом, фразами, offsets, паузами и hashes;
- PCMU round-trip и replay на `8 kHz/mono/20 ms`;
- mode sweep `0..3` на одной и той же последовательности кадров;
- raw decision masks, onset/offset и scorecard;
- repeated replay на том же hash для проверки детерминизма;
- optional ASR pass только для проверки ожидаемого текста.

Target runtime: CPython `3.14.7t`, Ubuntu 24.04/WSL2, patched WebRTC binding из Map-007. Команда и ожидаемый формат:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/vad_calibration_probe.py --corpus-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/corpus --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/runs/mode-sweep'
```

Ожидаемый результат: exit code `0`, JSON manifest со статусом, hashes, mode `0..3`, raw decisions, metrics и
runtime/GIL fields; красный результат сохраняется с exit code и corrective classification.

### 008-B

- replay каждого mode trace через `TurnDetector`;
- паузы около 300/500 ms и устойчивые паузы длиннее hard endpoint;
- speech resume до hard endpoint;
- split/merge counts, endpoint delay, turn count и authoritative events;
- targeted unit/contract/regression tests для выбранной конфигурации.

### 008-C

- source audit live construction;
- application/live gate с negotiated PCMU profile;
- проверка selected mode, endpoint trace, ASR fan-out и stale/close path;
- optional full-flow evidence с ASR как downstream diagnostic;
- raw commands, exit codes, manifest, regression и limitations.

Target runtime: existing combined free-threaded runtime used by Map-007, Ubuntu 24.04/WSL2, Baresip approved peer.
Ожидаемые команды:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && <target-python> -I -c "import pytest; raise SystemExit(pytest.main([\"-q\", \"tests/unit\", \"tests/contract\", \"tests/integration\"]))"'
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && <combined-free-threaded-python> tools/live_i1_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-C/i1-YYYYMMDD-rN --timeout 240'
```

Ожидаемый результат: exit code `0`, raw JSON/live manifest, VAD candidate/mode, negotiated media profile, endpoint
trace, ASR fan-out и errors. `<target-python>` заменяется фактическим executable в execution evidence, а не считается
заранее доказанным значением.

## 16. Fallback/deferred register

| Вариант | Разрешение | Ограничение |
|---|---|---|
| `_AmplitudeVad` | Только существующий deterministic control test | Не использовать для выбора live mode и не возвращать в live path |
| ASR-derived labels | Дополнительная weak/diagnostic annotation | Не является gold label и не участвует в A/B acceptance |
| Один фиксированный TTS voice | Разрешён для repeatable baseline | Не доказывает robustness на человеческих голосах |
| Human/noise corpus | Deferred future map | Не блокирует Map-008, если не заявлен production claim |
| Новый smoother component | Запрещён без отдельного boundary plan | Сначала проверить existing `TurnDetector` owner |

## 17. Map-level acceptance и closeout

Map-008 может получить статус `complete` только если:

1. `008-A`, `008-B`, `008-C` имеют собственные APG-compliant closeout со статусом `complete`;
2. corpus/manifest immutable и позволяет повторить все mode runs;
3. выбранный mode основан на сравнительном evidence, а не на одном WAV или субъективном прослушивании;
4. параметры `TurnDetector` проверены на разных фразах и паузах, включая границы 300/500 ms;
5. typed speech boundary и ownership не изменились без отдельного propagation/review;
6. ASR не использован как скрытая первичная разметка VAD;
7. application/live validation подтверждает selected configuration, а все красные результаты прошли corrective protocol;
8. registry, backlog, roadmap, architecture/TЗ и evidence синхронизированы;
9. closeout передаёт limitation: это controlled TTS baseline, а не production noise/recall campaign.

## 18. Следующий шаг

Map-008 полностью исполнена. Следующий шаг — использовать зафиксированные `VAD_MODE=2` и
`ENDPOINT_HARD_MS=520` в материалах мастер-класса и, при необходимости, вынести human/noise generalization в отдельную
карту без расширения текущего closeout.

## 19. Execution report и closeout (planning contract)

После исполнения Map-008 closeout обязан перечислить фактически изменённые файлы и symbols, corpus revision/hash,
команды и exit codes для A/B/C, target runtime/GIL evidence, mode scorecard, endpoint trace, application/live result,
regression, corrective passes, pre-existing failures, out-of-scope findings, deferred evidence с owner/condition
promotion, registry/backlog audit и следующий workshop step. Статус карты меняется на `complete` только после закрытия
всех child plans и map-level acceptance; при category-4 gap — только `blocked`. `partial`, `foundation` и
`arch-ready` не являются closeout-статусами.

## 20. Фактическое исполнение

Карта закрыта со статусом `complete`. Подробный execution closeout находится в
[`artifacts/implementation/008-vad-turn-calibration/closeout.md`](../../artifacts/implementation/008-vad-turn-calibration/closeout.md).

- `008-A`: mode sweep `0..3` на corpus из 729 PCMU-conditioned кадров; выбран mode 2;
- `008-B`: baseline 500 ms дал split, минимальная проходящая существующая политика — hard 520 ms;
- `008-C`: I1 и J4 live gates прошли на WebRTC mode 2; J4 подтвердил follow-up, barge-in, transfer, report и нулевые underruns;
- child closeouts: [`008-A`](../../artifacts/implementation/008-vad-turn-calibration/008-A/closeout.md),
  [`008-B`](../../artifacts/implementation/008-vad-turn-calibration/008-B/closeout.md),
  [`008-C`](../../artifacts/implementation/008-vad-turn-calibration/008-C/closeout.md).
