# Plan 005-C: качество AI-контура, latency, warmup и paced playback

Уровень: `child plan`  
Идентификатор: `005-C`  
Статус owner review: `accepted — owner review принят 2026-09-04`  
Статус исполнения: `complete`  
Родительская карта: [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md)  
Дата подготовки: `2026-09-04`

## 1. Цель и проверяемый результат

Проверить на целевом runtime основной AI-путь: source-aware RAG → Skill & Prompt Manager → typed `LlmRequest` →
LLM Facade/Ollama IPC → structured answer stream/decision → XTTS PCM → paced playback. Зафиксировать реальное время
от получения финальной пользовательской фразы до результата LLM, до первого пригодного PCM и до завершения TTS,
а также warmup, VRAM, cancellation и качество ответа.

Отдельно материализовать согласованное разделение источников исходящего media: PJMEDIA запрашивает кадры по такту,
TTS выдаёт порциями, поэтому existing media/playback owner выбирает `TTS` или `silence` без заполнения TTS-буфера
бесконечной тишиной. `egress_underruns` считается только при пустом TTS-буфере в `PLAYING`; `IDLE`/`PREROLL`/
`CANCELLED`/`CLOSED` имеют отдельные intentional/startup counters.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | RAG обязателен, ответ на русском, контекст сохраняется, unknown-answer ведёт к offer/transfer; один звонок | Model-only ответ не принимается; сохраняются structured decisions и context | Positive/negative RAG и multi-turn test | Нет source-aware evidence или unsafe action |
| [`architecture.md`](../architecture.md) | Context/RAG/Prompt, LLM Facade и TTS/playback — разные owners; payload direct, control через Dispatcher | Не вводить delivery-owner; LLM не получает SIP API | Ownership/topology audit | LLM вызывает SIP или крупный payload идёт через bus |
| [`technical-specification.md`](../technical-specification.md) | `LlmRequest` version/profile, local Ollama HTTP IPC, warmup до SIP admission, PCMU boundary; media output тактовый | Warmup использует реальный typed path; playback source selection не блокирует callback | Warmup/latency/VRAM/source-mode evidence | Cold path, wrong profile или blocking callback |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Map-I rev21: `FinalUserTurn → context/RAG/prompt → LlmRequest → Facade → answer stream → TTS → playback → SIP` | Все existing typed input methods и generation/stale policies сохраняются | Propagation/source audit | Нужна незапланированная boundary revision |
| [`ADR-001-llm-and-dialogue-manager.md`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM возвращает structured decision; SIP actions выполняет FSM/adapter | Проверять forbidden raw model actions и decision validation | Negative action tests | Модель напрямую управляет SIP |
| [`ADR-002-llm-model-selection.md`](../decisions/ADR-002-llm-model-selection.md) | Qwen3.5-9B — единственный primary; альтернативы только после провала gate | GPU run только main executor sequential; benchmark evidence обновляет ADR при необходимости | Real Ollama latency/VRAM | Молчаливая смена модели или параллельный GPU run |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Target — CPython 3.14.7t/no-GIL; process-isolated Ollama HTTP IPC принят | Не возвращать GIL-enabled runtime и не менять process boundary | Target runtime/GIL evidence | Native/import/runtime incompatibility без approved path |
| [`development-guidelines.md`](../development-guidelines.md) | Narrow typed slice, owner behavior, no silent fallback, warmup, corrective pass, binary closeout | AI/TTS changes только в write-set, красный gate исправляется и rerun-ится | APG + targeted/regression/contract | Category 4 gap или неполное evidence |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan самодостаточен: source-map, topology, audits, blockers, tests, fallback/deferred, closeout | GPU execution начинается только после owner review | Structural APG audit | Обязательный блок отсутствует |

Повторно не обсуждаются: обязательность RAG, primary Qwen3.5-9B, HTTP IPC, один звонок, warmup, no-GIL runtime,
30 ms RTP budget и отсутствие bot-side recording. Они являются protected baseline.

## 3. Граница задачи

**Входит:**

- positive/negative source-aware RAG, source IDs/scores и unknown-answer policy;
- prompt/skill/profile version evidence, exact final user phrase и context continuation;
- deterministic LLM Facade structured stream/decision/cancel checks и один последовательный real Qwen3.5-9B gate;
- измерение LLM latency именно от handoff финальной фразы до формирования валидного результата;
- XTTS warmup, first useful PCM, tokenizer-length observation, cancellation и PCMU-compatible PCM path;
- source selection в существующих playback/media owners с режимами `IDLE`, `PREROLL`, `PLAYING`, `DRAINING`, `CANCELLED`, `CLOSED`;
- counters `tts_startup_wait`, `intentional_silence_frames`, clean `egress_underruns`, dropped/callback errors;
- deterministic/target/live relevant tests и corrective fixes в перечисленном write-set.

**Не входит:** новая LLM/TTS/RAG модель без owner decision, обучение/fine-tuning, изменение Ollama IPC protocol,
новый standalone delivery-owner, изменение Dispatcher/FSM semantics, PBX, bot-side call recording, второй звонок,
production QoS/MOS/load/HA и обход no-GIL.

**Protected baseline:** `Map-002-I revision 21`, closed F/G/H/J plans, Qwen3.5-9B primary, Ollama HTTP process,
XTTS-v2, existing `LlmRequest`/`TtsPcmChunk`/`PcmFrame` contracts, `config/constants.py`, report lifecycle.

**Предположения:** GPU доступна только главному executor-у; перед каждым тяжелым запуском проверяются 20 ГБ free
space и отсутствие чужого GPU workload. Warmup выполняется до SIP admission и не считается live-call latency.

## 4. Source-map и write-set

| Область | Файл/символ | Текущее состояние | Действие | Write-set |
|---|---|---|---|---|
| RAG/prompt | `src/sip_bot/retrieval/`, `src/sip_bot/prompt/` | Closed source-aware baseline | Только evidence-driven corrective fix | Existing symbols only |
| LLM facade | `src/sip_bot/llm/`, `src/sip_bot/conversation_pipeline.py` | Closed typed Ollama facade/pipeline | Не менять protocol; исправлять только proven gate defect | Existing symbols only |
| TTS buffer/pacer | `src/sip_bot/tts/output_buffer.py`, `media_pacer.py` | Chunk aggregation/pacing exists | Add/test source lifecycle coordination if needed | Existing symbols + tests |
| Playback | `src/sip_bot/playback/channel.py`, `contracts.py` | Generation/cancel lifecycle exists | Mark start/complete/cancel source transitions | Existing symbols + tests |
| SIP media egress | `src/sip_bot/sip_media/media_port.py` и scoped delegator в `src/sip_bot/sip_media/adapter.py` | Empty buffer currently falls back to silence and counts all empties | Add typed source-mode selection; keep callback short; expose it through the existing adapter owner | Only egress/source-mode symbols and one typed delegator |
| Runtime lifecycle | Scoped playback hooks in `src/sip_bot/runtime_wiring.py` | TTS chunks are pumped from main loop | Switch source mode on existing playback lifecycle | Only `_on_tts_chunk`, `_pump_playback`, cancel/close hooks |
| Tests | `tests/unit/test_map005_ai_playback.py`, `tests/contract/test_map005_ai_playback.py`, `tests/integration/test_map005_ai_gate.py` | Нет | Deterministic contract/latency/source tests | New files |
| Target probe/evidence | `tools/map005_ai_gate.py`, `artifacts/implementation/002-system-testing-and-demo-readiness/005-C/` | Нет | Sequential warmup/real AI gate and evidence | New tool + own evidence root |

Запрещено менять `config/constants.py`, closed J4 tools, Map-I, ADR-001/003, чужие tests/evidence и registry/backlog.
В `sip_media/adapter.py` разрешён только typed delegator source-mode, принадлежащий тому же существующему media
owner; новые protocol/data boundaries и прочие изменения adapter scope запрещены. Изменение публичного contract за
пределами существующих owners останавливает plan как APG gap.

## 5. Interaction topology и propagation

```text
FinalUserTurn
  → Context/RAG + SkillPromptManager
  → typed LlmRequest
  → LlmFacade → Ollama HTTP process
  → typed answer stream / StructuredDecision
  → ApprovedTextChunk → TTS stream
  → TtsOutputBuffer → MediaPacer → PlaybackChannel
  → SipMediaAdapter.enqueue_egress_frame → PcmAudioBridge

Playback lifecycle control
  → existing media owner source mode: IDLE / PREROLL / PLAYING / DRAINING / CANCELLED / CLOSED
PJMEDIA onFrameRequested (negotiated ptime)
  → selected TTS source or silence source
  → PCMU/RTP
```

Тишина не является отдельным бесконечным producer-ом TTS-буфера. Режим выбирается existing playback/media owner;
между потоками применяются только разрешённые bounded thread-safe queues, а media callback не ждёт TTS/LLM.
`PREROLL` измеряется отдельно до первого фактически отправленного полезного TTS frame. После перехода в `PLAYING`
пустой TTS buffer — `egress_underrun`; после штатного completion playback проходит через `DRAINING`, который дочитывает
уже поставленные media-кадры и затем переключается на намеренную тишину; cancel/close выбирают намеренную тишину сразу.

## 6. Audit владельца поведения и парадигмы реализации

RAG/prompt owner владеет достаточностью контекста и версионированием prompt; `LlmFacade` — transport/inference stream
и typed result; TTS adapter — генерацией; `TtsOutputBuffer`/`MediaPacer`/`PlaybackChannel` — frame ordering, pacing,
generation и cancellation; `PcmAudioBridge` — negotiated media output и source selection непосредственно перед media
callback. `CallRuntimeWiring` только применяет уже существующие lifecycle transitions. Новый универсальный delivery или
orchestration owner не создаётся.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Как трактовать `egress_underruns`? | Считать только пустой TTS-буфер в `PLAYING`; intentional silence и startup ожидание отделить | Нужны source-mode counters и tests | `resolved by owner decision 2026-09-04` |
| Где размещать переключатель TTS/silence? | В существующей media/playback boundary; не заполнять TTS-buffer бесконечной тишиной и не вводить delivery-owner | Допустим scoped method/class внутри existing owner | `resolved by owner decision 2026-09-04` |
| Какая LLM primary? | Qwen3.5-9B; альтернативы только после провала primary gate | Только sequential main GPU execution | `resolved by ADR-002/owner decision` |
| Принят ли этот child plan к execution? | Групповой owner review child plans `005-A`–`005-D` принят 2026-09-04 | Отдельное согласование этого файла не является дополнительным gate; execution начинается после A/B | `resolved by grouped owner review` |

Новых предметных вопросов нет; последний пункт — процедурный APG gate.

## 8. Process invariant audit

| Инвариант | Materialized action | Evidence |
|---|---|---|
| Narrow/typed/owner | Changes limited to existing AI/TTS/media owners and typed contracts | Source-map/diff audit |
| Direct data plane | LLM text stream and PCM bypass Dispatcher; only control lifecycle is routed | Topology/contract tests |
| Bounded/non-blocking | TTS output and media callback never wait for inference; buffers bounded | Timing/queue tests |
| Warmup | RAG/embed, LLM chat, ASR dependency and TTS real output run before call admission | Warmup report |
| Single GPU executor | Real Qwen/XTTS run sequentially by main executor | Command/GPU evidence |
| No silent fallback | No alternate model/provider/codec or weakened assertion | Fallback register/diff |
| Corrective pass | Red category 1/2 is fixed and targeted+regression+contract rerun | Raw/rerun evidence |
| Binary closeout | Only `complete` or concrete `blocked` | Closeout/register |

## 9. Architecture invariant audit

- `FinalUserTurn` remains the only authoritative input for final LLM decision; speculative data cannot become audible or
  invoke SIP actions.
- RAG context, source IDs, prompt/profile versions and unknown-answer policy remain observable.
- `LlmFacade` exposes typed request/stream/status/decision and hides Ollama API from consumers.
- TTS chunks are aggregated/framed/paced before direct media egress; arbitrary chunk size is not treated as media ptime.
- Source selection preserves negotiated per-call profile and sends zero-filled frames only in intentional silence or as
  last-resort callback safety fallback.
- During `PLAYING`, a missing TTS frame is counted and not silently reclassified as intentional silence.
- Barge-in/cancel closes old generation, suppresses stale frames and leaves ingress available.

## 10. Implementation slices

### C1 — deterministic answer/RAG/LLM gate

Run existing contract fixtures for positive retrieval, source IDs, negative unknown answer, context continuation,
prompt/profile version, structured decision and cancellation. Acceptance: no model-only answer is accepted as source-aware,
no forbidden SIP action is accepted, exact final phrase and LLM handoff timestamps are recorded.

### C2 — main-executor real AI/resource gate

Run mandatory pre-call warmup and one sequential Qwen3.5-9B/Ollama operation. Measure time from final phrase handoff to
first useful/valid LLM result and completion; capture VRAM, runtime, model, config, stdout/stderr and exit code. No
parallel GPU inference. Failure is retried after external resource change before classification.

### C3 — deterministic TTS source-selection gate

Implement and test `IDLE`/`PREROLL`/`PLAYING`/`DRAINING`/`CANCELLED`/`CLOSED` source selection, TTS chunk bursts, empty buffer,
completion, barge-in and stale generation. Acceptance: intended silence does not increment `egress_underruns`; empty
TTS buffer in `PLAYING` does; TTS frames never compete with an infinite silence queue; callback remains non-blocking.

### C4 — main-executor TTS/live relevant gate

Run XTTS warmup and one sequential real output, measure first PCM and pacing, inspect tokenizer limit behavior, then run
the relevant clean live path after C3. Acceptance: source counters, media stats, first useful PCM, cancellation and RTP
evidence are consistent. `callback_errors`, dropped frames or audible gap require corrective handling.

### C5 — corrective pass and handoff

Classify all red results 1–4. Fix category 1/2 only in write-set and repeat targeted/regression/contract tests. A new
boundary, owner, model/provider, runtime or protected-baseline change becomes category 4 blocker; no fallback is added.

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец | Evidence/condition promotion | Статус |
|---|---|---|---|---|---|---|
| `B-005-C-001` | весь plan | Child owner review не пройден | Любая реализация/GPU execution | project owner | Этот файл и review message | `resolved 2026-09-04` |
| `B-005-C-002` | C3 | Source selection требует boundary/owner за пределами write-set | Playback/media implementation и downstream gate | project owner | APG gap + map/ADR review | `none until triggered` |
| `B-005-C-003` | C2/C4 | GPU занята/недоступна, warmup не завершает real operation или <20 ГБ | Real AI claims | main executor/project owner | Raw output; retry after external state change | `none until triggered` |
| `B-005-C-004` | C1–C4 | Mandatory red remains category 4 after corrective pass | Affected acceptance/map closeout | project owner | Raw output, attempts, promotion condition | `none until triggered` |
| `B-005-C-005` | C2/C4 | Primary model fails agreed latency/VRAM/quality gate | Real primary claim and model decision | project owner | ADR-002 update and separately reviewed candidate plan | `none until triggered` |

Lock-файл пакетного менеджера не является немедленным blocker: подготовка повторяется после случайной задержки.
Нельзя объявлять target inference пройденным по одному import или skipped test.

## 12. Test plan и evidence

```text
Target runtime: /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
Deterministic: python -m pytest -q tests/unit/test_map005_ai_playback.py tests/contract/test_map005_ai_playback.py
Target/main-only: python tools/map005_ai_gate.py --evidence-root <new-005-C-root>
Regression: python -m pytest -q tests/unit tests/contract tests/integration
```

Evidence обязан содержать RAG corpus/index/query/source IDs/scores, prompt/profile version, exact final phrase,
LLM request/response timestamps, first useful/valid/completed timings, model/runtime/GPU/VRAM, warmup stages, TTS
chunks/frames, source modes/counters, media stats, cancellation/stale outcomes, commands, stdout/stderr и exit codes.
Ошибки и skipped cases сохраняются отдельно и не превращаются в pass.

## 13. Fallback/deferred register

| Что | Причина | Ограничение | Promotion | Статус |
|---|---|---|---|---|
| Deterministic LLM/TTS doubles | Проверка typed lifecycle без GPU | Не выдаются за quality/latency model evidence | Sequential target run | `allowed for preparation` |
| Qwen3.5-4B/Qwen3 baseline | Только fallback candidate при провале primary | Не запускаются автоматически и не параллельно | Owner review + ADR-002 | `deferred` |
| Silence fallback in PJMEDIA callback | Последняя real-time safety net | Не скрывает `PLAYING` underrun counter | C3 acceptance | `required safety behavior` |
| New provider/codec/process bridge | Не нужен | Запрещён без APG gap/review | New plan/ADR | `none` |

## 14. Execution report и closeout

Execution date: `2026-09-04`.

Фактический write-set: typed source-mode implementation in the existing `PcmAudioBridge` and its one existing-owner
adapter delegator, lifecycle hooks in `CallRuntimeWiring`, three new deterministic tests and the new main-executor
AI-gate/evidence root. New delivery owner, Dispatcher payload path, model/provider fallback and protected baseline
changes не вводились.

Acceptance:

- C1/C3 deterministic source lifecycle: `7 passed` на target CPython `3.14.7t`; `IDLE`, `PREROLL`, `PLAYING`,
  `DRAINING`, `CANCELLED`, `CLOSED`, bounded TTS framing, stale generation и barge-in lifecycle проверены;
- source accounting разделён: intentional silence и `tts_startup_wait` не увеличивают `egress_underruns`, а пустой
  TTS source в `PLAYING` увеличивает только `egress_underruns`;
- C2/C4 main target gate: `map005-c-ai-gate.json` имеет `status=pass`, выполнен на CPython `3.14.7t` с
  `gil_enabled=false`, Qwen3.5-9B Q4_K_M через Ollama `0.33.1`, без fallback;
- real positive RAG вернул `sufficient=true` и source `wiki-physics-rayleigh`; real negative RAG вернул
  `sufficient=false`, prompt разрешил только `offer_transfer`;
- LLM timing от authoritative final phrase: first useful output `488.600 ms`, valid structured result
  `1518.092 ms`; первый XTTS PCM — `263.917 ms` от TTS start и `1785.090 ms` от финальной фразы; XTTS completion
  `2587.321 ms`, 11 chunks, PCMU-compatible `8 kHz/mono/S16LE` WAV сохранён;
- warmup embedding index `6943.350 ms`, LLM warmup `10484.631 ms`, TTS warmup `508.794 ms`; warmup завершён до
  измеряемого хода и исключён из его latency;
- target regression после corrective pass: `147 passed, 2 skipped`;
- clean live-path после source-mode corrective pass: `status=pass`, все `6/6` J4 scenarios, PCMU/8000/mono RTP,
  `callback_errors=0`, dropped/stale=0, `egress_underruns=0`, `tts_startup_wait=132`,
  `intentional_silence_frames=4629`, `source_mode_transitions=16`;
- дополнительный corrective pass после D-r5 выявил финальную гонку между закрытием TTS и дочитыванием media-egress;
  добавлен typed `DRAINING` в существующий media owner, stale/closed TTS chunk больше не возвращает источник в
  `PREROLL`, deterministic/contract/regression checks повторены, а финальный D-r7 подтвердил
  `egress_underruns=0` на полном Baresip rehearsal;
- cancellation/stale policy подтверждена existing accepted `002-H` evidence и deterministic C tests; независимого
  native cancellation token у XTTS не заявляется;
- initial source-mode implementation parse defect был исправлен до тестового gate; category-1/2 corrective pass
  завершён, fallback и category-4 blocker не возникли.

Latency observation: measured end-to-end segment from final phrase to first PCM is above the project comfort target
of `200–500 ms`. This plan records the decomposition and does not reclassify the result as a pass for the overall
user metric; the measurement is transferred to `005-D` rehearsal evidence and future prompt/model optimization.

Evidence and commands: [`commands.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-C/commands.md),
[`target-20260904-r1`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-C/target-20260904-r1/),
[`target-live-20260904-r1`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-C/target-live-20260904-r1/),
[`closeout.md`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-C/closeout.md).

`005-C` закрыт статусом `complete`: весь execution scope и обязательные evidence сохранены, category-4 blocker
отсутствует. Следующий разрешённый child — `005-D` после live-path check и синхронизации Map-005.
