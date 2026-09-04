# Plan 005-D: clean-start rehearsal и evidence closeout

Уровень: `child plan`  
Идентификатор: `005-D`  
Статус owner review: `accepted — owner review принят 2026-09-04`  
Статус исполнения: `complete — clean-start rehearsal и evidence closeout завершены 2026-09-04`  
Родительская карта: [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md)  
Дата подготовки: `2026-09-04`

## 1. Цель и проверяемый результат

Провести после закрытия `005-A`–`005-C` один воспроизводимый clean-start rehearsal полного демонстрационного сценария
и собрать финальный evidence package к `2026-09-20`: SIP answer, русский RAG-ответ, follow-up, barge-in,
unknown-answer/offer-transfer, подтверждённый transfer на fake operator, terminal close, `report.md` и полная запись
обеих сторон разговора со стороны Baresip.

Этот plan не добавляет прикладную функцию и не исправляет owners молча. Он проверяет уже закрытые boundaries, запускает
только согласованные gates и оформляет artifact package для доклада.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на этот plan | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Один русский SIP-разговор, RAG, context, barge-in, transfer и итоговый report; runtime бота не пишет аудио, test peer может писать | Rehearsal один; report обязателен; полная Baresip recording обязательна | Clean-start matrix и artifacts; raw tracks и explicit stereo alignment | Mandatory flow/recording/report missing |
| [`roadmap.md`](../roadmap.md) | Demo-ready к 20 Sep, затем freeze и доклад 25 Sep | Финальный запуск не оставляет неразрешённых обязательных claims | Calendar/freeze checklist | Deadline gate не закрыт |
| [`architecture.md`](../architecture.md) | Dispatcher/FSM control-only; direct audio/text data plane; existing owners | Rehearsal не создаёт orchestration owner и не меняет contracts | Architecture audit | Новый runtime edge/owner |
| [`technical-specification.md`](../technical-specification.md) | Warmup до SIP admission, PCMU per-call, report lifecycle, Baresip evidence отдельно от dialogue state | Clean-start запускается только после readiness; WAV не попадает в `data/dialogues` | Runtime/report/artifact audit | Cold model path или wrong artifact placement |
| [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md) | Map-level matrix, source selection, Baresip recording contract, child dependency order | D consumes A–C closeouts и does final sequential gate | Dependency/requirement matrix | Upstream child not complete/blocked with promotion |
| [`plan-001-S-voip-test-stand.md`](plan-001-S-voip-test-stand.md) | Approved Baresip peer/fake operator | Использовать копию approved config; historical no-recording run не переписывать | Peer manifest | Stand contract differs |
| [`development-guidelines.md`](../development-guidelines.md) | Evidence reproducible, deferred explicit, no silent simplification, binary closeout, shared docs sequentially | Только main executor меняет registry/backlog/roadmap; красные claims классифицируются | APG and closeout audit | Unclassified red or partial closeout |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan has source-map, write-set, topology, blockers, tests, fallback and closeout | D is self-contained and cannot close Map-005 alone | Structural audit | Required block missing |

Закрытые планы и старые r1–r20 evidence не переписываются. Этот rehearsal создаёт новый собственный evidence root и
может ссылаться на r20 только как на predecessor baseline.

## 3. Граница задачи

**Входит:**

- clean-start readiness/warmup guard, один sequential full demo call и terminal cleanup;
- requirement→evidence matrix и freeze checklist;
- Baresip `sndfile` recording полного media-сеанса на test peer;
- сохранение raw `enc`/`dec` WAV, manifest и построение проверенного stereo derivative:
  `left=user_to_bot`, `right=bot_to_user`;
- ручная проверка stereo artifact и пригодности обеих сторон для прослушивания;
- итоговый `report.md`, evidence index, commands/runtime/model/config metadata и known limitations;
- corrective fix только если он принадлежит D-owned harness/artifact packaging write-set.

**Не входит:** изменение application owners, SIP/RTP/AI contracts, новая модель/provider/codec, PBX, production
recording/retention, второй вызов, изменение `report.md` semantics, silent skip/xfail и изменение закрытых планов.

**Protected baseline:** `Map-002-I rev21`, completed `002-*`, approved local Baresip peer/fake operator, Qwen3.5-9B,
CPython 3.14.7t/no-GIL, `config/constants.py`, report lifecycle и 20 GB guard.

**Предположения:** A–C имеют собственные binary closeouts либо concrete blockers с condition promotion; GPU warmup
уже доказан; output root новый/пустой; artifact path доступен и не смешивается с историческими runs.

## 4. Source-map и write-set

| Область | Файл/символ | Текущее состояние | Действие | Write-set |
|---|---|---|---|---|
| Rehearsal runner | `tools/map005_rehearsal_gate.py` | Нет | Создать main-only full scenario runner с Baresip recording | Новый файл |
| Recording merge | `tools/map005_stereo_recording.py` | Нет | Создать PCM16 mono `enc`/`dec` validator и stereo builder с явным выравниванием хвостом тишины | Новый файл |
| Artifact tests | `tests/unit/test_map005_recording.py`, `tests/integration/test_map005_rehearsal.py` | Нет | Validate metadata/mapping/cleanup/requirements | Новые файлы |
| Evidence | `artifacts/implementation/002-system-testing-and-demo-readiness/005-D/` | Нет | New rehearsal root, logs, raw WAV, stereo WAV, manifests, report/index | Own root only |
| Docs handoff | `artifacts/.../005-D/closeout.md`, `requirement-matrix.md`, `freeze-checklist.md` | Нет | Создать execution package | Own evidence root only |

Запрещено менять `tools/j4_full_live_gate.py`, `tools/live_i1_gate.py`, `tests/integration/conftest.py`, production
`src/`, `config/constants.py`, closed plan/evidence и общие `docs/*`. Главный executor после closeout отдельно
синхронизирует registry/backlog/roadmap.

## 5. Interaction topology и propagation

```text
approved Baresip peer ⇄ SIP/RTP ⇄ existing application runtime
existing runtime → Context/RAG/LLM/TTS/playback → existing report lifecycle
Baresip sndfile enc/dec → raw recording artifacts
raw enc/dec → map005_stereo_recording.py → stereo derivative + manifest
all typed/control/media/runtime evidence → requirement matrix → closeout package
```

D не меняет существующие typed edges. Запись находится на peer-side boundary; stereo builder работает только после
закрытия файлов и не является частью live media path. Он не изменяет исходные PCM-дорожки, а создаёт производный
artifact с проверенной длительностью, sample rate, channel count, mapping и hashes. Если `enc` и `dec` имеют разную
длину из-за различного времени закрытия media-пайплайнов, более короткая дорожка дополняется только в конце нулевыми
PCM-кадрами; число таких кадров и политика выравнивания обязательно записываются в manifest.

## 6. Audit владельца поведения и парадигмы реализации

Репетиционный runner владеет только сценарием запуска и сбором evidence. Baresip владеет peer-side recording. Stereo
builder владеет преобразованием двух уже закрытых mono WAV в один stereo WAV. Report builder владеет единственным
обязательным текстовым `report.md`. Ни один из этих объектов не получает право менять SIP/FSM/AI semantics.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Можно ли писать audio для rehearsal? | Да, только Baresip test peer, raw files в evidence; application runtime не пишет | Recording requirement обязательна для live/rehearsal | `resolved by owner decision 2026-09-04` |
| Как получить stereo, если `sndfile` даёт два WAV? | Сохранить raw `enc`/`dec` и собрать производный WAV с явным `left/right` mapping; разную длину выровнять только явным trailing-silence padding | Не скрывать source files; missing track/metadata/mapping остаются red, padding отражается в manifest | `resolved by Map-005` |
| Может ли D изменить production runner/closed J4? | Нет; создаётся отдельный Map-005 runner | Исторические результаты сохраняются неизменными | `resolved by APG protected baseline` |
| Принят ли этот child plan к execution? | Групповой owner review child plans `005-A`–`005-D` принят 2026-09-04 | Отдельное согласование этого файла не является дополнительным gate; execution начинается после A–C | `resolved by grouped owner review` |

Новых предметных решений нет; последний пункт — обязательный child-plan APG gate.

## 8. Process invariant audit

| Инвариант | Materialized action | Evidence |
|---|---|---|
| Narrow/no silent scope | Только rehearsal и artifact packaging; production code не меняется; `noVad` применяется лишь in-memory в D runner для явных idle RTP frames | Source-map/diff и runtime override metadata |
| Typed/owner | Runner вызывает existing application boundaries; builder owns only closed WAV conversion | Contract/source audit |
| Sequential shared resources | One clean-start call, one GPU execution path, final docs sync main-only | Commands/timeline |
| Full evidence | Raw output, versions, commands, exit codes, logs, report, WAV manifest | Evidence index |
| No silent simplification | Missing path, partial recording, wrong mapping or skipped scenario is red/deferred, not pass; trailing padding допустим только с явной записью в manifest | Matrix/closeout |
| Binary closeout | D is `complete` only after all scope; otherwise concrete `blocked` | Closeout/register |

## 9. Architecture invariant audit

- Clean-start вызывает approved owners и не добавляет new delivery/orchestration component в application runtime.
- Control plane остаётся Dispatcher/FSM-owned; audio payload и recording не проходят через Dispatcher.
- Warmup выполняется до call admission; warmup time отдельно от live turn latency.
- Stereo derivative строится после Baresip capture и не изменяет SIP/media data plane.
- Отчёт создаётся ровно один раз по terminal lifecycle; отсутствие Baresip recording не маскируется отсутствием
  application recording.
- Один звонок, PCMU/profile, RAG, barge-in, transfer и report claims имеют соответствующее evidence.

## 10. Implementation slices

### D1 — harness/artifact preparation

Создать runner, per-run Baresip config с `sndfile`, stereo builder, unit tests и manifest schema. Проверить, что raw
recording path не пересекается с `data/dialogues` и closed J4 tools.

### D2 — preflight and clean-start rehearsal

Проверить target executable, no-GIL state, free space ≥20 GB, model/RAG/TTS warmup/readiness, Baresip version/config и
пустой output root. Запустить один clean-start full flow sequentially; сохранить event traces/logs/exit codes/report.

### D3 — recording and stereo listening artifact

Дождаться полного закрытия peer recordings, проверить `enc`/`dec` WAV metadata/hashes/durations, построить stereo
derivative, проверить channel mapping (`left=user_to_bot`, `right=bot_to_user`) и вручную прослушать обе стороны.
Если источники не выровнены, сохранить raw evidence и классифицировать результат, не исправляя его паддингом молча.

### D4 — requirement matrix/freeze/closeout

Сопоставить каждый обязательный requirement с evidence, зафиксировать latency/VRAM/warmup/known limitations, commands,
versions, report and audio links, затем подготовить freeze package. Любой красный результат классифицировать 1–4 и
повторить только допустимый corrective pass.

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец | Evidence/condition promotion | Статус |
|---|---|---|---|---|---|---|
| `B-005-D-001` | весь plan | Child owner review не пройден | Любая реализация/rehearsal | project owner | Этот файл и review message | `resolved 2026-09-04` |
| `B-005-D-002` | D2 | A–C не имеют complete/eligible blocked closeout или contract handoff | Full rehearsal | main executor/project owner | Child closeouts и promotion conditions | `none until triggered` |
| `B-005-D-003` | D2 | Warmup/readiness, disk guard, Baresip peer или GPU path не готов | Clean-start claim | main executor/project owner | Raw preflight; retry after external condition | `none until triggered` |
| `B-005-D-004` | D3 | Нет полного `enc`/`dec`, mapping не доказан, metadata некорректна или alignment не зафиксирован явно | Recording requirement | project owner/main executor | Raw files/logs, corrective pass or category-4 decision | `none until triggered` |
| `B-005-D-005` | D2–D4 | Mandatory scenario red after corrective pass / report missing | Map closeout | project owner | Raw output, attempts, promotion condition | `none until triggered` |
| `B-005-D-006` | D4 | Нельзя доказать requirement→evidence mapping к freeze | Rehearsal/Map-005 closeout | project owner | Matrix gap record and promotion condition | `none until triggered` |

Низкое место и занятая GPU не являются окончательными blocker-ами без повторной проверки после изменения внешнего
состояния. Ошибка записи/runner category 1/2 исправляется в write-set до регистрации category 4.

## 12. Test plan и evidence

```text
Target runtime: /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
Recording unit: python -m pytest -q tests/unit/test_map005_recording.py
Rehearsal: python tools/map005_rehearsal_gate.py --output-root <new-005-D-root>
Stereo builder: python tools/map005_stereo_recording.py --enc <enc.wav> --dec <dec.wav> --output <stereo.wav>
Regression: python -m pytest -q tests/unit tests/contract tests/integration
```

Evidence root содержит preflight, Baresip config/version, peer/operator logs, SIP/RTP traces, full report, raw `enc`/`dec`
WAV, stereo WAV, hashes, sample rate/channels/duration, channel mapping, requirement matrix, freeze checklist, commands,
stdout/stderr и exit codes. Все paths relative to the new root or absolute target paths are recorded.

## 13. Fallback/deferred register

| Что | Причина | Ограничение | Promotion | Статус |
|---|---|---|---|---|
| Existing J4 runner as historical reference | Предыдущий baseline | Не выдаётся за recording-enabled rehearsal | New D runner | `reference only` |
| Separate `enc`/`dec` instead of native Baresip stereo | `sndfile` documented path | Raw files сохраняются; stereo derivative обязателен; unequal tail is explicitly padded and recorded in manifest | Mapping/alignment validation | `approved path` |
| Missing external stimulus | Baresip limitation | Deterministic evidence marked separately; no live claim | Applicable live run | `deferred only if triggered` |
| New provider/codec/recording service | Не нужен | Запрещён без APG gap/owner review | New plan/ADR | `none` |

## 14. Execution report и closeout

### Фактический execution report — 2026-09-04

`005-D` выполнен главным executor-ом на Ubuntu 24.04/WSL2, target CPython `3.14.7t`,
`gil_enabled=false`. В финальном runner-е применён только in-memory override `pjsua2.EpConfig().medConfig.noVad=True`:
он заставляет PJMEDIA передавать явные idle PCMU/RTP-кадры для корректной временной оси decode recording; application
source, closed J4 и production configuration не изменялись.

Перед финальным прогоном был выполнен corrective pass в existing TTS/media owner: штатное завершение playback теперь
переходит через typed `DRAINING`, чтобы последний кадр из media-egress buffer не создавал ложный `PLAYING` underrun.
После изменений были повторены targeted/contract/regression tests и новый clean-start run.

Changed files: `src/sip_bot/sip_media/media_port.py`, `src/sip_bot/runtime_wiring.py`,
`tests/unit/test_map005_ai_playback.py`, `tests/contract/test_map005_ai_playback.py`,
`tools/map005_rehearsal_gate.py`, `tools/map005_stereo_recording.py`,
`tests/unit/test_map005_recording.py`, `tests/integration/test_map005_rehearsal.py`. Evidence сохранён в
[`target-20260904-r7`](../../artifacts/implementation/002-system-testing-and-demo-readiness/005-D/target-20260904-r7/). Ранний r5
сохранён как raw evidence, r6 — как не принятый corrective run с нестабильным внешним операторским peer.

Target test results:

- `tests/unit/test_map005_ai_playback.py` + source-mode contract + recording/rehearsal tests: `7 passed` targeted;
- full target regression `tests/unit tests/contract tests/integration`: `151 passed, 2 skipped in 9.50s`;
- J4 full live scenario inside D: `pass`, 6/6 scenario checks, 6 user turns, 4 assistant turns, 5 RAG contexts,
  follow-up, barge-in, unknown-answer/offer-transfer, fake-operator transfer and terminal report;
- SIP/RTP: PCMU/8000/mono, ptime 20 ms, peer packets transmit `4913`, receive `5089`;
- application media stats: ingress/egress `5089` frames, drops `0`, `egress_underruns=0`,
  `tts_startup_wait=209`, `intentional_silence_frames=4564`, `source_mode_transitions=19`, `callback_errors=0`;
- warmup completed before SIP admission in `44487.720 ms`; live call elapsed `102833.821 ms`.

Recording evidence:

- raw `enc` (`user_to_bot`): `98.26 s`, SHA-256
  `8f120f6a94987b8a4e95cb54f205018bfadba537c678d5335b19f21114317d0b`;
- raw `dec` (`bot_to_user`): `101.68 s`, SHA-256
  `cb8b36ebd0cefd51016c9bed95ee2d5fed782d5f06b1b7b9ff086c9b969cdc31`;
- stereo derivative: 2-channel PCM16/8000 Hz, `101.68 s`, SHA-256
  `505cefb6b67f2c9de664b4af85b6860d211086d5ec314abd100cf3b6e1a003de`;
- alignment policy: left channel received explicit `27360` zero PCM frames (`3.42 s`) at the end; raw tracks remain
  preserved and the policy is recorded in `recording-manifest.json`.

Corrective attempts `r1`–`r4` are retained. `r1` fixed a runner monkeypatch recursion, `r2` fixed missing target
`LD_LIBRARY_PATH`/result handling, `r3` exposed that default PJMEDIA idle suppression produces an unusable sparse
decode timeline, and `r4` exposed a nondeterministic late ASR final after transfer. These were category-1/2 harness or
execution findings; after the in-scope corrective runner change, `r5` passed without suppressing application errors.

Known limitation is retained, not hidden: the overall final-phrase-to-first-PCM latency remains above the 200–500 ms
comfort orientation in `005-C` evidence. No category-4 blocker or new owner-review question remains for this plan.

`005-D` receives binary status `complete`; partial/foundation/arch-ready statuses are not used.

`005-D` получает `complete` только при полном rehearsal/evidence scope. Если upstream blocker категории 4 не снят,
статус только `blocked` с concrete condition promotion; partial/foundation/arch-ready статусы запрещены.
