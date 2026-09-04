# Карта 5: системное тестирование, исправления и готовность демонстратора

Уровень документа: `map`  
Идентификатор: `Map-005`  
Статус: `complete — A–E и map-level corrective evidence закрыты 2026-09-04`  
Дата подготовки: `2026-09-04`  
Родитель: [`roadmap.md`](../roadmap.md)  
Предшественник: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)

## 1. Цель и проверяемый результат

Карта 5 должна превратить доказанный картой 4 сквозной baseline в воспроизводимо проверенный демонстратор к
`2026-09-20`, оставив два дня перед докладом под freeze, rehearsal и только критические исправления. Карта не добавляет
новую прикладную функциональность: она проверяет существующий SIP→RTP→speech→RAG/LLM→TTS→RTP путь, исправляет дефекты
в утверждённых границах и подготавливает evidence для доклада `2026-09-25`.

Результат карты:

- системная матрица SIP/media, audio/speech, AI/RAG, TTS, FSM, lifecycle/report и runtime проверена по актуальным
  контрактам `Map-002-I revision 21`;
- каждый красный результат сохранён, классифицирован по APG 6.1 и либо исправлен с corrective pass, либо оформлен
  конкретным deferred/gap с owner и условием promotion;
- проверены фактические latency/VRAM/warmup/resource observations, включая время от окончания речи пользователя до
  первого полезного TTS PCM-фрагмента;
- чистый demo-run, итоговый `report.md`, инструкции запуска и requirement→evidence matrix доступны для rehearsal;
- `005-D` подтвердил clean-start full flow, Baresip `enc`/`dec` recording и stereo derivative, но прослушивание r7
  выявило потерю большей части TTS-ответов, не отражённую в `egress_underruns`;
- corrective child plan `005-E` выполнен: dynamic bounded TTS accumulation buffer, frame pacing,
  lifecycle/overflow tests и target live gate r10 закрыли найденную потерю PCM;
- карта не объявляет проект production-ready и не маскирует ограничения текущего MVP.

Карточка 4 уже закрыта: главным baseline является
[`j4-full-live-20260904-r20`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-full-live-20260904-r20/j4-full-live.json), а
не старые r1–r19 диагностические прогоны. R19 сохранён как raw failure evidence и показывает исправленный дефект
Transcript Assembler; он не считается acceptance.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на Map-005 | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Один русский SIP-разговор, локальные ASR/LLM/TTS/RAG, перебивание, контекст, transfer и текстовый `report.md`; runtime бота не пишет аудио, но Baresip test peer пишет live/rehearsal-запись | Матрица должна проверять обязательный demo-flow, полную запись в evidence и отсутствие bot-side recording; PBX и production retention не добавляются | Requirement→evidence matrix, clean-start run и Baresip recording artifacts | Обязательный сценарий или запись стенда не проходит |
| [`architecture.md`](../architecture.md) | Dispatcher/FSM владеют control plane; media и крупные text payload идут по direct data plane; существующие owners не дублируются | Тесты и исправления вызывают существующие typed input methods и не вводят delivery-owner | Architecture audit и boundary tests | Требуется новый semantic owner или boundary |
| [`technical-specification.md`](../technical-specification.md) | PCMU/per-call media profile, 20 ms baseline ptime, 8→16 kHz ASR boundary, RAG, prompt/profile constants, warmup и min 20 GB free-space guard | Проверяются negotiated profile, conversions, warmup/readiness и operational prerequisites | Runtime/evidence metadata | Несогласованный формат, cold path или недостаток диска |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `Map-002-I revision 21` — authoritative topology, typed edges, cycles и propagation history | Map-005 не переоткрывает закрытые edges; любое изменение contract сначала переводится в APG gap | Contract registry/revision audit | Boundary change без owner review |
| [`development-guidelines.md`](../development-guidelines.md) | Узкий slice, typed-first, owner behavior, no silent scope/fallback, обязательные tests, corrective pass и binary closeout | Карта порождает отдельные child plans; красный тест сначала исправляется в текущем write-set | APG audit, targeted/regression/contract reruns | Category 4 gap или нет обязательного evidence |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Для карты нужны source-map, child graph, owner review, blocker register, test/evidence plan, fallback/deferred и closeout | Owner review карты и групповой owner review `005-A`–`005-D` приняты; corrective `005-E` добавлен по APG после явного audio review; execution идёт по зависимостям | Map gate and registry audit | Не пройден owner review карты или групповой child gate |
| [`ADR-001`](../decisions/ADR-001-llm-and-dialogue-manager.md), [`ADR-003`](../decisions/ADR-003-free-threaded-python.md), [`ADR-004`](../decisions/ADR-004-control-plane-event-bus.md) | LLM не управляет SIP напрямую; target — CPython 3.14.7t; control event bus не переносит data payload | Проверяется action validation/FSM, `gil_enabled=false`, loop/queue policy и запрет прямого SIP из модели | Target runtime and contract tests | Нарушен accepted ADR или нужен новый вариант |

## 3. Граница карты

**Входит:**

- системная проверка уже материализованных SIP/RTP, PCMU, media, VAD, endpointing, ASR, Transcript Assembler, FSM,
  RAG/prompt/LLM, TTS/playback, barge-in, transfer и report boundaries;
- protocol-event tests во время долгих фаз ASR/LLM/TTS: `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume,
  RTP timeout/media failure и повторное закрытие ресурсов;
- проверка частичных ASR-исправлений, пустого/длинного хода, stale result, cancellation и multi-turn context;
- latency/VRAM/warmup evidence и проверка воспроизводимости на target no-GIL runtime;
- исправления ошибок в текущих owners и тестовых harnesses без изменения утверждённых typed contracts;
- проверка полной записи live/rehearsal на стороне Baresip и подготовка channel-separated stereo evidence;
- подготовка clean-start rehearsal, requirement matrix, report/evidence index и freeze checklist.

**Не входит:** PBX, bot-side/production recording и retention аудио, второй параллельный разговор, новая модель/новый inference runtime без
отдельного решения, production HA/observability/security, semantic turn detector, полноценный MOS/load campaign и
новый fallback только ради прохождения теста.

**Protected baseline:** `Map-002-I revision 21`, существующие `Dispatcher`, `DialogueFSM`, `CallSession`, прямые
data-plane edges, control-only event bus, PJSUA2/PJMEDIA compatibility patches, CPython 3.14.7t,
`config/constants.py`, mandatory local RAG, pre-call warmup и единственный обязательный внешний артефакт звонка
`report.md`. Отдельный обязательный `state.json` отсутствует в требованиях и в эту карту не добавляется.

**Предположения:** GPU доступна главному executor-у для последовательных inference gates; перед тяжёлым прогоном
проверяется свободное место не менее 20 ГБ; `/mnt/c` и WSL paths доступны; локальные Baresip peers из `001-S` доступны.

## 4. Source-map и write-set карты

| Область | Источник/файл | Текущее состояние | Целевое состояние | Владелец | Допустимый write-set |
|---|---|---|---|---|---|
| SIP/media/protocol | `src/sip_bot/sip_media/`, `tests/integration/test_sip_media.py` | PCMU/live baseline pass; расширенная protocol matrix не сведена | Events during inference, media failure и idempotent close имеют evidence | SIP/media owners | Только исправления существующих adapter methods и tests; без нового SIP owner |
| Audio/speech | `src/sip_bot/media/`, `src/sip_bot/speech/`, speech tests | Live r20 pass; r19 выявил и r20 закрыл early-prefix defect | Gaps, silence/resume, long/empty/stale paths проверены | media/speech owners | Existing modules, fixtures, tests и собственный evidence root |
| FSM/control | `src/sip_bot/control/`, `src/sip_bot/runtime_wiring.py`, FSM tests | Core lifecycle/barge/transfer pass | Protocol/application races и forbidden actions проверены | Dispatcher/FSM owners | Existing owners/tests; control payload types не менять без gap |
| Answer/RAG/LLM | `src/sip_bot/context/`, `src/sip_bot/llm/`, `src/sip_bot/prompt/`, `config/constants.py` | Source-aware RAG и Qwen3.5-9B path pass; ADR-002 ждёт benchmark | Source IDs, unknown policy, cancellation, latency, VRAM и prompt/profile evidence | context/prompt/LLM owners | Existing facade/RAG/prompt/config symbols and tests; no new model/provider silently |
| TTS/playback | `src/sip_bot/tts/`, `src/sip_bot/playback/`, scoped output methods in `src/sip_bot/sip_media/media_port.py` and `src/sip_bot/runtime_wiring.py` | r7 source-selection/tail race corrected, но audio review found mid-stream PCM loss: fixed-capacity output buffer can reject a whole chunk and caller does not make that rejection visible | `005-E` checks dynamic current occupancy with bounded high-water/backpressure, exact byte/frame accounting, completion/drain, cancellation/stale policy, audible full output and underrun interpretation | TTS/playback owners | Existing buffering/pacer/adapters/tests; no alternate TTS fallback, signal or new delivery owner |
| Runtime/resources | `src/sip_bot/runtime*`, `tools/`, WSL target | Warmup is mandatory; target no-GIL pass | Clean-start, 20 GB guard, warmup/readiness, process/GIL/VRAM observations reproducible | main executor | Existing tools and new map evidence; no runtime baseline replacement |
| Documentation/evidence | `docs/`, `artifacts/implementation/002-system-testing-and-demo-readiness/` | Map-005 child and corrective evidence executed; r7 historical, r10 accepted | Child closeouts, requirement matrix, rehearsal package and final handoff | main executor | Map-005 docs, evidence root, downstream Map-006 refresh; registry/backlog sequentially |

Protected from direct child-plan modification: `requirements.md`, accepted ADRs, closed `001-*`, closed Map-002 child
plans, `Map-002-I` contract history and other child write-sets. Если исправление реально требует их изменения, работа
останавливается и оформляется APG gap.

## 5. Interaction topology и propagation boundary

Карта 5 использует `Map-002-I revision 21` как единственную authoritative interaction map. Новых runtime-рёбер карта не
создаёт. Проверяемый baseline остаётся:

```text
SipMediaAdapter
  → PcmFrame / direct audio fan-out
  → VAD + TurnDetector + ASR chunk boundary
  → AsrHypothesis → TranscriptAssembler
  → authoritative FinalUserTurn
  → Context/RAG + Skill & Prompt Manager
  → typed LlmRequest → LLM Facade/Ollama IPC
  → typed answer stream → TTS buffer/framer/pacer
  → PlaybackChannel → SipMediaAdapter

SIP protocol/application events ⇄ Dispatcher + DialogueFSM + CallSession
barge-in/cancel/close/stale-result cycles ⇄ existing owners
transfer result ⇄ FSM/SIP fake operator
terminal lifecycle → ContextStore → report.md
```

Материализация in-process edge остаётся вызовом typed input-метода consumer; между потоками допускается только bounded
thread-safe queue, а `asyncio.Queue` используется только внутри основного loop. Большой payload не проходит через
Dispatcher/Event Bus. Для каждого child plan в source-map указываются exact input method, loop/thread/process context,
close/cancel и stale policy.

Если тест или исправление показывает, что фактический output не принимается текущим consumer, сначала фиксируется
contract mismatch. Нельзя прятать его новым adapter/facade/delivery owner: при изменении boundary требуется новая
propagation revision и owner review.

## 6. Audit владельца поведения и парадигмы реализации

Map-005 не назначает нового владельца поведения. Существующие owners сохраняются:

- SIP/media adapter — протокольные ответы, negotiated media и media lifecycle;
- PCM/media boundary — conversion, fan-out, buffering, framing и pacing;
- VAD/Turn Detector/Transcript Assembler/ASR — speech classification, endpointing, revision lifecycle и final turn;
- Dispatcher/DialogueFSM/CallSession — control ordering, semantic state, action validation, per-call lifecycle;
- Context/RAG и Skill & Prompt Manager — context, corpus/index, retrieval sufficiency, prompt/profile;
- LLM Facade — Ollama HTTP IPC и typed stream/status/decision;
- TTS/playback — audio generation, cancellation и media-clock output;
- transfer/report — typed operator result и единственный обязательный `report.md`.

Тестовый harness только вызывает эти owners и собирает evidence. Исправление в owner-модуле допустимо лишь для поведения,
которое уже принадлежит ему. Процедурная orchestration/map-level evidence не превращается в новый компонент.

## 7. Owner-review решения

| Вопрос | Предлагаемое решение | Последствие | Статус |
|---|---|---|---|
| Можно ли считать ненулевой PJMEDIA `egress_underruns` самостоятельным провалом? | Да, после разделения источников: в `IDLE`/`CANCELLED`/`CLOSED` media boundary выбирает источник намеренной тишины; в `PLAYING` читает только TTS-буфер. После штатного completion применяется `DRAINING`: он дочитывает media-egress buffer и только затем выбирает idle silence. Пустой TTS-буфер во время `PLAYING` считается `egress_underrun`; ожидание первого кадра учитывается отдельно как `tts_startup_wait` | Тишина не заполняет bounded TTS-буфер и не конкурирует с полезными кадрами; fallback нулевого кадра в PJMEDIA сохраняется только как аварийная страховка. Дополнительно проверяются `callback_errors`, dropped frames и RTP evidence | `resolved by owner decision 2026-09-04; corrective pass 2026-09-04` |
| Допустимы ли deterministic/injected protocol tests там, где Baresip не даёт воспроизводимый внешний stimulus? | Да, при явной маркировке уровня evidence; обязательные live SIP/RTP claims остаются только за live evidence, deterministic test не выдаётся за live | A проверяет protocol reaction/latency локально, D отдельно указывает coverage gap | `resolved by existing APG test/evidence rules` |
| Какой inference candidate использовать в primary map-5 gate? | Qwen3.5-9B остаётся единственным primary; другие кандидаты проверяются только если primary не закрывает agreed latency/VRAM/quality gate | Не возникает параллельного GPU benchmark и молчаливой смены модели; ADR-002 обновляется по фактическому benchmark | `resolved by prior owner decision` |
| Нужно ли добавлять отдельный snapshot/state artifact? | Нет; `report.md` — единственный обязательный итоговый artifact, `conversation.jsonl` — внутренний журнал по текущему lifecycle | Map-005 проверяет lifecycle/report, но не создаёт `state.json` | `resolved by owner clarification` |

Вопрос интерпретации `egress_underruns` разрешён: child plan проверяет раздельные режимы
намеренной тишины, `PREROLL`, `PLAYING` и `DRAINING`, а также отсутствие конкуренции тишины с TTS-буфером. Owner review карты и
групповой child gate пройдены; отдельное согласование каждого child plan не является остановкой execution. Это решение
само по себе не объявляет child plans исполненными.

## 8. Process invariant audit

| Инвариант | Применимость и materialized действие | Evidence |
|---|---|---|
| Узкий slice и запрет silent scope | Карта декомпозируется на A–E; corrective E добавлен после явного audio review и имеет собственный source-map/write-set | Map gate, child plans |
| Typed-first/owner behavior | Тесты используют существующие typed contracts; raw dict допускается только на внешнем Ollama/fixture glue boundary | Contract tests, source audit |
| Propagation и cycles | Revision 21 является входом; при фактическом изменении output/consumer — stop, gap и новая revision | Map-I audit, child evidence |
| Параллельность | A/B deterministic preparation могут идти параллельно при disjoint write-set; C GPU и final D gate — main-only sequential | Child handoff и commands |
| Runtime/no-GIL | Main target — CPython 3.14.7t; import/operation/concurrency/GIL evidence запускается в target; host-only pass не заменяет target | Target JSON/log |
| Warmup | До SIP admission в каждом heavy gate последовательно выполняются RAG, LLM, ASR и TTS real operations | Warmup report |
| Corrective pass | Красный результат сохраняется, классифицируется, исправляется в scope и проверяется targeted + regression + contract; category 4 не обходится | Raw output, corrective report |
| No silent fallback/упрощение | Карта не заменяет RAG model-only ответом, не ослабляет assertions и не добавляет альтернативный TTS/LLM путь без review | Fallback register, diff audit |
| Binary closeout | Child закрывается только `complete` или `blocked`; карта закрывается только после всех child closeouts и map-level gates. Закрытые A–D не делают карту complete, пока E не закрыт | Closeout, registry, backlog |
| Документальная синхронизация | После каждого изменения Markdown пересчитываются registry и backlog; общий registry/backlog изменяет main executor | Audit commands |

## 9. Architecture invariant audit

- SIP protocol responses remain local to `SipMediaAdapter` and do not wait for Dispatcher, ASR, LLM, TTS or report.
- Dispatcher/Event Bus carries only compact control-plane events; audio, `FinalUserTurn` and other large data-plane payloads
  remain direct typed calls/queues.
- Only authoritative hard-endpoint `FinalUserTurn` changes FSM and starts authoritative answer/TTS; speculative/stale
  results cannot transfer, hang up or become audible.
- Barge-in closes old TTS/playback generation while ingress remains available; terminal/transfer cycles are idempotent.
- RAG source IDs and unknown-answer policy remain observable; a model-only answer cannot close the source-aware claim.
- Prompt/profile versions and current constants remain the same on benchmark and demo path.
- Target runtime remains `CPython 3.14.7t`, `gil_enabled=false`; approved process isolation/HTTP IPC is not replaced.
- One call only, no bot-created runtime audio recording, Baresip test recording only in evidence, text-only `report.md`, no `state.json` requirement.

## 10. Карта дочерних планов и порядок исполнения

Исходный срез 5 является картой, а не узким планом: он содержит независимые protocol, speech, AI/resource и rehearsal
acceptance boundaries, разные write-set и последовательные GPU gates. После пользовательского audio review к карте
добавлен corrective child plan `005-E`; это отдельный узкий plan-file внутри Map-005, а не новая подчинённая карта.
Групповой owner review `005-A`–`005-D` принят 2026-09-04, а подход `005-E` принят явным указанием владельца в тот
же день, поэтому отдельное согласование каждого файла не является дополнительным execution gate.

| ID | Child plan-файл | Узкая цель | Зависимости | Допустимый параллелизм | Минимальный результат | Owner review |
|---|---|---|---|---|---|---|
| `005-A` | `plan-005-A-protocol-media-failure-matrix.md` | SIP/media protocol reactions, RTP/media failures, idempotent close и raw Baresip recording evidence | Map-005, Map-I rev21, 001-S | deterministic preparation параллельно B; live peer checks main/stand sequential | Evidence для применимых `BYE/CANCEL/OPTIONS/re-INVITE/UPDATE/hold/resume/RTP failure` и raw `enc/dec` recording | `complete 2026-09-04` |
| `005-B` | `plan-005-B-speech-audio-resilience.md` | PCMU/audio gaps, VAD/endpointing, ASR revisions, empty/long turn, stale/cancel | Map-005, Map-I rev21, closed C/D | deterministic preparation параллельно A; target ASR main-only | No contradictory-prefix regression, one final turn, stale suppression и speech boundary matrix | `complete 2026-09-04` |
| `005-C` | `plan-005-C-ai-quality-latency-resources.md` | RAG/LLM/TTS quality, latency, warmup, VRAM и paced output/source selection | Map-005, closed F/G/H/J, primary Qwen3.5-9B | Только main executor sequential по GPU; no parallel model runs | Source-aware answer, unknown case, first-output timings, VRAM/warmup, TTS quality and clean underrun evidence | `complete 2026-09-04` |
| `005-D` | `plan-005-D-rehearsal-evidence-closeout.md` | Clean-start rehearsal, Baresip stereo recording, requirement matrix, report/evidence packaging и freeze | A–C closeouts and map gate | Documentation preparation may follow A–C; final gate sequential | Reproducible demo package к 20 Sep, full stereo call artifact and report/evidence index | `complete 2026-09-04` |
| `005-E` | `plan-005-E-tts-playback-integrity-corrective.md` | Исправить mid-stream потерю TTS PCM: dynamic bounded accumulation, frame pacing, lifecycle/overflow tests и новый r10 | r7 audio review; существующие TTS/playback contracts; A–D evidence остаётся историческим | E1–E3 deterministic preparation может идти параллельно при disjoint write-set; E4 main executor sequential/GPU-only | Полный слышимый TTS output, объяснимые byte/frame counters, target regression и новый Baresip stereo r10 | `complete 2026-09-04` |

Общие документы, registry, backlog, ADR-002 и финальный integration gate изменяются только главным executor-ом и
последовательно. Зависимости A/B → C → D остаются обязательными; `005-E` продолжил Map-005 после r7 и закрыл
map-level closeout. Downstream Map-006 использует r10 как upstream TTS baseline и закрыт текущим corrective target r6.

## 11. Blocker register карты

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-005-001` | Map-005 | Owner review карты не пройден | Создание/исполнение child plans | project owner | Этот документ и review package | `resolved 2026-09-04` |
| `B-005-002` | A–E | Исправление требует нового/изменённого typed boundary, runtime, owner или fallback | Зависимый child и affected propagation | project owner | APG gap record, новая Map-I revision/ADR при необходимости | `none until triggered` |
| `B-005-003` | C | GPU занята/недоступна или warmup не завершает реальную операцию | Main AI/resource gate и claims о latency/VRAM | project owner/main executor | Raw runtime output, retry after external condition changes | `none until triggered` |
| `B-005-004` | A–D | Свободный диск Windows или WSL ниже 20 ГБ | Heavy tests, model/cache/evidence execution | project owner | Explicit free-space check before run | `none until triggered` |
| `B-005-005` | A–D | Обязательный тест красный после corrective pass и классифицирован как category 4 | Зависимый acceptance и closeout карты | project owner | Raw output, correction attempts, gap/owner decision | `none until triggered` |
| `B-005-006` | E | Dynamic TTS fix требует межкомпонентного сигнала, нового delivery owner, изменения typed boundary или truly unbounded storage | E2 и Map-005 closeout | project owner | `005-E` APG gap и affected propagation evidence | `resolved — no trigger; existing boundary retained` |

Красный результат категории 1/2 в утверждённом write-set не является blocker: сначала выполняется corrective pass и
повторяются затронутые проверки. Category 3 фиксируется как pre-existing/out-of-scope с evidence. Только доказанный
category 4 переводится в открытый blocker с owner и condition promotion.

## 12. Test plan и evidence

| Группа | Обязательная проверка | Уровень | Evidence |
|---|---|---|---|
| Protocol | SIP answer/normal close, `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume, RTP/media failure, repeated close во время ASR/LLM/TTS | deterministic + live где поддерживает стенд | peer logs, adapter events, timestamps, exit codes |
| Audio/speech | PCMU/profile, frame loss/overflow, VAD transitions, 300/500 ms endpoint, resume, empty/long turn, partial correction, explicit/absent stable prefix, stale/cancel | unit/contract/target/live relevant | hypotheses, endpoint events, counters, final turns |
| Answer/RAG | context continuation, source IDs, positive retrieval, negative unknown policy, prompt/profile versions, structured decision и cancellation | deterministic + one sequential real primary | request diagnostics, index/query trace, LLM latency/VRAM |
| TTS/playback | warmup, first useful PCM, arbitrary chunk boundaries, dynamic accumulation, exact byte/frame accounting, bounded high-water/backpressure, completion/drain, pacing, barge-in cancellation, stale frames, full audible output и underrun interpretation | deterministic + target/live | PCM/WAV listening artifact, raw/stereo recording, accepted/emitted/discarded counters, frame stats, trace |
| FSM/lifecycle | forbidden model actions, protocol-vs-transfer race, terminal idempotence, report once, no `state.json` claim | unit/contract/integration | state trace, report, negative assertions |
| Runtime | CPython 3.14.7t, no-GIL before/after imports and controlled smoke, warmup, 20 GB guard, fresh process | target | runtime JSON, command/version/stdout/stderr/exit code |
| Rehearsal | clean-start one-call demo, required flow, report and evidence links | main-only sequential | rehearsal package and requirement matrix |

### 12.1. Полная запись разговора на стороне Baresip

Для каждого live SIP/RTP-прогона и итоговой rehearsal-записи тестовый peer Baresip должен включать модуль `sndfile` и
сохранять полную запись от начала media-сеанса до его завершения в собственный каталог артефактов:

- исходные дорожки Baresip сохраняются без удаления и без перезаписи;
- `enc` и `dec` явно маркируются относительно роли peer-а: для пользовательского peer-а это соответственно
  `user_to_bot` и `bot_to_user`;
- если конкретная версия/сборка Baresip умеет сформировать один корректный stereo WAV с разными направлениями,
  сохраняется такой файл и проверяется соответствие каналов;
- штатный documented path `sndfile`, который создаёт отдельные WAV-файлы `enc` и `dec`, считается достаточным
  источником: harness обязательно формирует удобный stereo derivative (`left=user_to_bot`, `right=bot_to_user`),
  сохраняя исходные файлы как первичные evidence;
- несовпадение длительностей, пропуски начала/конца, ошибки записи и невозможность однозначно определить mapping
  каналов фиксируются в evidence и не скрываются обработкой;
- запись выполняет Baresip test peer, а не runtime бота; в `data/dialogues/<call_id>/` аудиофайлы не добавляются.

Для deterministic unit/contract-тестов запись не обязательна. Для live и rehearsal обязательны исходные
`enc`/`dec` WAV, корректный stereo derivative, manifest с версией/config Baresip и
результат проверки channel mapping. Документированный Baresip `sndfile` module описан в
[`Using Baresip: Module sndfile`](https://github.com/baresip/baresip/wiki/Using-Baresip%3A-Module-sndfile).

Latency measurement uses the project’s user-facing end-to-end turn metric: from actual end of user speech to first useful
audible TTS PCM. Component timings (endpointing, ASR, retrieval, LLM, TTS and media) diagnose the result; the accepted
RTP budget remains 30 ms and the 200–500 ms comfort range is an orientation, not a licence to hide a larger total.
Warmup time is reported separately and must not be charged to the live call after readiness.

For every deferred evidence item record: stable `evidence_id`, owner, accepting document, exact required proof, explicit
command, raw output/exit code and promotion condition. A skipped test is not a pass.

## 13. Calendar gates

| Дата | Gate | Результат | Что блокирует продолжение |
|---|---|---|---|
| `2026-09-04` | Map-005 owner review | Scope, child graph, `egress_underruns` interpretation, recording requirement и protected baseline согласованы | Child-plan execution |
| `2026-09-04–05` | TTS playback corrective preparation | `005-E` E1–E3 preparation, targeted/contract tests и ready-to-run r10 command | E4 live acceptance и Map-005 closeout |
| `2026-09-05` | Child-plan/APG gate | A–D self-contained plans созданы, reviewed и имеют disjoint write-set; `005-E` подготовлен по corrective APG path | Исполнение child |
| `2026-09-06–10` | Speech/protocol robustness | A/B required deterministic/target checks и corrective passes | Answer/interaction gate |
| `2026-09-11–15` | Answer/resource quality | C source-aware RAG, LLM/TTS, warmup, latency/VRAM и TTS observations | Integration gate |
| `2026-09-16–18` | Interaction/failure gate | A–C protocol, barge-in, cancellation, transfer, report/failure checks | Rehearsal |
| `2026-09-19–20` | Clean-start/evidence gate | D rehearsal package, requirement matrix, report и known limitations | Code/demo freeze |
| `2026-09-06` | TTS live recheck | Main-executor clean-start r10, full Baresip recording и audio completeness review: pass | Map-006 downstream refresh |
| `2026-09-21` | Freeze | Baseline и докладные evidence заморожены | Новая функция без owner review |

## 14. Fallback и deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Existing one-call scope | Project MVP explicitly supports one conversation | Не выдаётся за scalability | requirements/roadmap and Map-002 closeout | `approved scope boundary` |
| Curated Russian natural-science KB | Deadline-critical source-aware demo | Retrieval и unknown-answer остаются обязательными | F/J/005-C | `approved scope boundary` |
| Local fake operator/Baresip stand | PBX/operator infrastructure вне проекта | Только typed transfer demonstration | 001-S/J/005-A/D | `approved scope boundary` |
| Warmup before admission | Prevents cold model load on critical call path | Не обещает постоянную VRAM residency | runtime/005-C | `target invariant` |
| Production load/MOS/HA/security/production recording/retention | Вне MVP и текущего срока | Не называть выполненным | roadmap/backlog | `out_of_scope` |
| New fallback/compatibility bridge | Не нужен для текущей карты | Запрещён без APG gap + owner review | none | `none` |

## 15. Критерии закрытия карты и следующий переход

Map-005 получает `complete` только если:

- owner review карты и групповой owner review child plans пройдены, все child plans имеют только `complete` или конкретный `blocked`;
- обязательные protocol/speech/answer/TTS/FSM/report/runtime gates закрыты собственным evidence;
- каждый красный результат имеет raw output, классификацию, corrective pass или зарегистрированный category-4 blocker;
- full clean-start demo и rehearsal воспроизводимы, а requirement→evidence matrix доступна;
- latency/VRAM/warmup observations, TTS quality/underrun limitation и known gaps честно описаны;
- `report.md` создаётся ровно по terminal lifecycle, runtime бота аудиозапись не создаёт, а Baresip test recording
  сохраняется только в evidence; `state.json` не добавляется;
- `docs/document-registry.md`, `docs/task-backlog.md`, roadmap, ADR-002 при необходимости и evidence index синхронизированы;
- code/demo freeze handoff подготовлен к `2026-09-21`; технический freeze package готов досрочно, после календарного
  freeze следующий переход — подготовка доклада и демонстрация.

### Фактический execution handoff — 2026-09-04

`005-A`–`005-D` имеют собственные binary `complete` closeout. Пользовательское прослушивание финальной stereo-записи
r7 выявило mid-stream потерю большей части TTS-ответов. В частности, наличие `egress_underruns=0` не доказывало
полноту payload: текущий fixed-capacity output buffer мог отклонить chunk до доставки в PJMEDIA, а этот отказ не был
отражён в acceptance counters.

Это наблюдение относится к существующему TTS/playback write-set и не вводит новый signal, delivery owner, process или
typed boundary. По APG был открыт `005-E` с четырьмя узкими срезами: E1 evidence/owner audit, E2 dynamic bounded
accumulation и framing, E3 lifecycle/overflow/contract tests, E4 main-executor clean-start r10. Исторический r7 не
перезаписывается; r10 стал новым acceptance evidence полноты TTS.

`005-E` закрыт: E1–E3 прошли focused/host/target tests, E4 main-executor clean-start r10 прошёл полный SIP/RTP
сценарий, все 7/7 checks, Baresip stereo recording и audio audit. Финальные counters: `accepted_chunks=48`,
`accepted_bytes=679084`, `emitted_frames=1845`, `dropped_overflow_bytes=0`, `buffered_bytes=0`, `pending_frames=0`,
`egress_underruns=0`, `egress_dropped_overflow=0`, `callback_errors=0`; `dropped_tail_bytes=88982` относится к явной
отмене старого поколения при barge-in.

Поэтому Map-005 имеет статус `complete`; Map-006 завершил технический downstream refresh по r10. Отдельное
согласование `005-E` не являлось дополнительным execution gate: подход был принят явным
указанием владельца, а открытого category-4 blocker-а нет.
