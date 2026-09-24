# Plan-007-C: WebRTC VAD live gate и evidence для мастер-классов

Уровень: `child plan`  
Статус owner review: `accepted — inherited from Map-007 owner approval, 2026-09-13; no additional owner question`  
Статус исполнения: `complete — I1/J4 live gates and evidence passed after corrective pass, 2026-09-13`  
Родительская карта: [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md)  
Предшественник: [`plan-007-B-webrtc-vad-application-integration.md`](plan-007-B-webrtc-vad-application-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21  
Evidence root: `artifacts/implementation/007-webrtc-vad/007-C/`

## 1. Цель и результат

Заменить VAD в фактическом live/demo application path на проверенный WebRTC VAD и доказать это clean-start прогоном
через утверждённый Baresip PCMU peer. Проверяются не только вызовы VAD, но и speech/pause/resume/hard endpoint,
независимость ASR fan-out, cancellation/close и отсутствие скрытого возврата к `_AmplitudeVad`.

Результат — live manifest и подготовленный для мастер-класса runbook/evidence с точным runtime, candidate, mode,
negotiated media profile, ВAD decisions, endpoint trace, SIP/RTP markers, командами и exit codes. Исторические Map-005/006
results не переписываются и не выдаются за WebRTC evidence.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на `007-C` | Проверка | Stop condition |
|---|---|---|---|---|
| [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md) | Live gate обязан использовать WebRTC; amplitude допустим только в deterministic tests; один call | Менять только VAD construction в live tools и собирать фактическое evidence | Source/live manifest audit | Live path использует amplitude или scope расширен |
| [`plan-007-B-webrtc-vad-application-integration.md`](plan-007-B-webrtc-vad-application-integration.md) | B complete и propagation `I2` обязательны до live gate | C не запускается на неподтверждённом binding/contract | B closeout reference | B incomplete или contract changed |
| [`plan-001-S-voip-test-stand.md`](plan-001-S-voip-test-stand.md) | Approved local Baresip peer, PCMU/8000/1 и fake operator доступны | Использовать существующий стенд, не создавать новый SIP component | SIP/RTP logs and manifest | Стенд недоступен |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `PcmFanOut → PcmFrame → VadProcessor → VadDecision → TurnDetector`; Dispatcher не переносит audio | Live wiring меняет только candidate selection | Boundary/forbidden-path audit | New edge/owner or stale contract |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Shared config/docs/live gate выполняются последовательно main executor; subagent output не evidence | Подготовку можно делегировать, final live run принимает main executor | Diff/evidence audit | Overlap or unverified handoff |
| [`development-guidelines.md`](../development-guidelines.md) §6–§8 | Mandatory tests, corrective pass, no silent fallback, binary closeout | Красный live acceptance исправляется, а не маскируется deterministic fixture | Raw live result + rerun | Category-4 blocker |
| [`technical-specification.md`](../technical-specification.md) | Per-call negotiated media/PCMU и fixed endpointing; no audio recording by bot | Проверить фактический profile и endpoint timing; recording остаётся Baresip responsibility | Media/VAD trace and recording manifest | Format/recording ownership mismatch |

## 3. Граница задачи

**Входит:** `tools/live_i1_gate.py`, `tools/j4_full_live_gate.py`, при необходимости реальный composition probe;
замена VAD constructor, live clean-start gate, Baresip PCMU evidence, endpoint trace, source audit, workshop runbook handoff.

**Не входит:** SIP protocol redesign, Baresip feature changes, new VAD algorithm, semantic turn detector, model warmup
изменения, ASR/LLM/TTS/RAG, recording ownership, multi-call/load campaign.

**Protected baseline:** approved Baresip peer, PJSUA2/PJMEDIA, PCMU, Map-I rev21, `PcmFrame`/`VadDecision`/endpoint
contracts, one call, existing report and recording policy.

## 4. Source-map и write-set

| Область | Файл/ресурс | Целевое действие | Допустимый write-set |
|---|---|---|---|
| Live I1 | `tools/live_i1_gate.py`, `src/sip_bot/runtime_wiring.py` | Конструировать `VadProcessor(WebRtcVadCandidate(mode=...))`; отбрасывать stale final turn после terminal/close | VAD import/construction, stale-result corrective guard and related manifest/assertions only |
| Full live | `tools/j4_full_live_gate.py` | Тот же переход для full clean-start gate | VAD construction and VAD evidence only; AI/SIP flow unchanged |
| Real composition | `tools/real_media_composition_probe.py` | Проверить, является ли это live application path; менять только если входит в target gate | VAD construction only |
| Evidence | `artifacts/implementation/007-webrtc-vad/007-C/` | Save commands, manifests, traces, recordings references and audit | Own evidence root |
| Runbook/docs | `docs/tooling-notes.md`, appropriate workshop/demo docs | Synchronize factual command and limitation after pass | Main executor sequentially |

Не менять deterministic `tools/map005_speech_probe.py` и unit fakes только ради удаления test double. Не менять общие
registry/backlog из child parallel context; main executor обновляет их после результатов.

## 5. Interaction topology и propagation

Live path остаётся:

```text
PJMEDIA PCMU/RTP
  → PcmFrame (negotiated profile)
  → PcmFanOut("vad")
  → SpeechIngress.process_frame
  → WebRtcVadCandidate/VadProcessor
  → VadDecision
  → TurnDetector
  → existing endpoint/ASR/FSM edges
```

VAD decision не публикуется через Event Bus; speech events materialize existing control edge only after endpointing.
ASR subscription получает собственные frames и не должен ждать VAD operation beyond existing bounded loop work. Protocol
events и barge-in cycles остаются владельцами existing Dispatcher/FSM and playback; C не добавляет reverse VAD edge.

## 6. Audit владельца поведения и парадигмы реализации

Child C только материализует существующую boundary в live harness. Он не владеет VAD, endpointing, SIP или аудиодоставкой.
Live gate запускается main executor-ом последовательно, потому что он использует общий SIP peer, native runtime и может
затрагивать общие GPU/model resources. Вызов WebRTC VAD не выполняется из native PJMEDIA callback напрямую.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Можно ли переписать исторические Map-005/006 gates? | Нет; создать новый WebRTC evidence root и сохранить историю | Traceability не смешивается | `resolved` |
| Можно ли оставить amplitude в live, если WebRTC уже проверен? | Нет; amplitude только deterministic test double | Live construction/source audit обязателен | `resolved` |
| Нужно ли менять endpoint thresholds? | Нет; 300/500 ms и min speech остаются protected baseline | C проверяет transitions, но не переопределяет policy | `resolved` |
| Нужен ли новый SIP/recording component? | Нет; approved Baresip stand и existing recording ownership сохраняются | Workshop evidence использует существующий стенд | `resolved` |

Открытых owner-review вопросов нет.

## 8. Process invariant audit

| Инвариант | Действие | Evidence |
|---|---|---|
| Main executor final gate | Live run и final evidence принимаются главным executor-ом | Command/output review |
| No silent fallback | Source audit ищет live `_AmplitudeVad` construction | `rg` output + manifest |
| Corrective pass | Красный live result rerun-ится после исправления | Raw rN/rN+1 evidence |
| Evidence levels | Deterministic, target operation и live SIP/RTP разделены | Manifest fields |
| Scope | Не менять SIP, AI, recording, endpoints и contracts | Diff audit |
| Closeout | Child C binary `complete`/`blocked` | Closeout and registry audit |

## 9. Architecture invariant audit

- Live input использует фактический negotiated `PcmFrame.profile`, а не глобальный sample-rate default.
- VAD получает моно PCM S16LE; baseline 8 kHz/20 ms, WebRTC legal frame durations 10/20/30 ms.
- `PcmFanOut` сохраняет независимую VAD/ASR delivery; Dispatcher не становится audio transit.
- Speech events и FSM semantics не переносятся в WebRTC adapter.
- При закрытии call generation поздние decisions/result не попадают в новый вызов.
- Baresip recording остаётся test-stand artifact и не превращается в bot-side recording.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| `C1` | Проверить B handoff и рабочее дерево | B complete, no overlapping changes | Missing handoff/contract mismatch |
| `C2` | Заменить VAD construction в live I1/full gate | Source audit finds WebRTC construction, no live amplitude | Candidate import/API error |
| `C3` | Run clean-start PCMU Baresip live gate | Speech/pause/resume/hard endpoint, ASR independence, one call | Live acceptance red after corrective pass |
| `C4` | Save manifest/trace/runbook and rerun relevant regression | Evidence reproducible and correctly levelled | Missing raw output or external stand issue |
| `C5` | Map closeout + docs/registry/backlog sync | Map-level all child complete, no blocker | Category-4 gap or incomplete child |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-007-C-001` | `C2` | Live tool still constructs amplitude or exact WebRTC candidate unavailable | Live promotion | project owner | Source audit/target command | `not triggered — live source audit passed` |
| `B-007-C-002` | `C3` | WebRTC decisions do not produce reproducible endpoint/ASR behavior on approved peer | C/map closeout | project owner | Baresip raw logs, VAD/endpoint trace | `not triggered — I1/J4 passed` |
| `B-007-C-003` | `C3–C4` | Target stand/resource prevents mandatory live evidence | Live acceptance only | project owner | Exact command, raw output, exit code, promotion condition | `not triggered — target evidence captured` |
| `B-007-C-004` | `C4` | Required workshop runbook would claim unsupported production quality | Publication handoff | project owner | Claim/evidence audit | `not triggered — limitation stated in runbook` |

Deterministic test failure и stale-result defect в пределах write-set сначала исправляются corrective pass; не
подменяются успешным старым Map-005 evidence. Late `FinalUserTurn` после terminal/closed generation считается
stale и отбрасывается до вызова pipeline.

## 12. Test plan и evidence

Перед live gate:

- `rg -n "_AmplitudeVad|WebRtcVadCandidate|VadProcessor\(" tools src tests` с классификацией каждого употребления;
- target import/operation manifest из `007-A`;
- B targeted/contract/regression tests;
- clean-start target command на утверждённом Baresip peer;
- negotiated media profile, PCMU/8000/1, actual frame durations, VAD decisions and endpoint events;
- speech before/after soft endpoint, resume before hard endpoint, hard endpoint and one authoritative final turn;
- fan-out counters proving ASR path is independent;
- close/cancel/stale generation and full relevant regression;
- Baresip recording reference if the existing live gate produces recording; bot-side recording claim не добавляется.

Evidence сохраняется с runtime/executable, exact package/model baseline (если затронуто), commands, stdout/stderr and
exit codes. Этот gate не требует нового GPU inference; если одновременно используется AI full-flow, GPU run остаётся
последовательным main-executor operation.

## 13. Fallback/deferred register

| Что введено | Ограничение | Статус |
|---|---|---|
| Existing deterministic amplitude fixture | Только deterministic tests; не live | `allowed test double` |
| New live fallback | Запрещён | `none` |
| Full quality/noise campaign | Не входит в Map-007; может быть отдельной future map | `out of scope` |

## 14. Execution report и closeout

Closeout должен указать изменённые live tool files, source audit, commands/exit codes, B handoff, live manifest,
endpoint/ASR evidence, recording ownership, regression, pre-existing/out-of-scope findings и следующий workshop step.
`complete` разрешён только после полного C scope и map-level acceptance; partial/foundation status запрещён.

Фактический closeout сохранён в [`artifacts/implementation/007-webrtc-vad/007-C/closeout.md`](../../artifacts/implementation/007-webrtc-vad/007-C/closeout.md).
Авторитетные финальные live evidence:

- [`I1 live manifest`](../../artifacts/implementation/007-webrtc-vad/007-C/r5/i1-live-20260913-r1/live-i1-gate.json) — `status=pass`,
  Baresip/PCMU/8000/mono, `WebRtcVadCandidate`, negotiated `ptime=20 ms`, `egress_underruns=16` в коротком I1 прогоне;
- [`J4 full live manifest`](../../artifacts/implementation/007-webrtc-vad/007-C/j4-full-live-20260913-r3/j4-full-live.json) — `status=pass`,
  6/6 scenario checks, `3910` ingress frames, `7820` fan-out frames, `20` ASR chunks, `0` ASR drops, `7` final turns,
  `0` errors, `0` egress underruns и WebRTC VAD trace на `8000 Hz/20 ms`.

Первый J4 прогон с двумя поздними final-turn ошибками не скрыт: он сохранён как `r1`, причина исправлена в пределах
утверждённого write-set stale guard-ом, после чего повторный r3 прошёл. Runbook для мастер-класса сохранён рядом с
closeout; он требует pre-call warmup и не обещает production noise/quality campaign.
