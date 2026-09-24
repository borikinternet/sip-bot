# Plan 010-C: Registered live continuity gate

Уровень документа: `child plan`  
Статус: `complete`  
Родительская карта: [`plan-010-continuous-pcmu-comfort-noise.md`](plan-010-continuous-pcmu-comfort-noise.md)

## Цель и результат

Повторить approved registered full-AI scenario после `010-A` и `010-B` и доказать, что в пределах отвеченного вызова
бот на каждом negotiated media tick генерирует PCMU/RTP кадр: от `200 OK` на `INVITE` до получения `BYE`/`media_stopped`.
Raw Baresip tracks по-прежнему сохраняются, а stereo/timeline audit остаётся отдельным диагностическим результатом
и не подменяет проверку egress continuity.

## Применимые правила и границы

| Источник | Материализованное правило | Проверка | Stop |
|---|---|---|---|
| `architecture.md` | Existing SIP adapter/media path и one-call baseline сохраняются | Source/diff audit | Новый SIP/media boundary |
| `technical-specification.md` | `180 → readiness → 200`, negotiated PCMU/8000/mono и per-call ptime | Registered protocol trace | Readiness/protocol gap |
| `user-guide.md` | Live runner запускается на target free-threaded runtime, GPU готовится по runbook | Exact command/evidence | Runtime/environment blocker |
| `development-guidelines.md` | GPU/live red result требует corrective pass; closeout binary | Clean retry, regression, audio audit | Category-4 blocker |
| `010-A`, `010-B` | No-VAD/comfort source и event-window recording alignment уже закрыты | Child closeout evidence; recording audit не является RTP continuity clock | Dependency not complete |

Входит: registered FreeSWITCH/Baresip clean-start, GPU-backed full-AI scenario, PCMU/RTP event-window audit, raw
`enc`/`dec` WAV, event-window stereo/manifest с учётом start timestamps, report и документационный closeout. Stereo
duration mismatch фиксируется
как diagnostic limitation и не блокирует RTP continuity acceptance. Не входит: RFC 3389/CN, production PBX campaign,
multi-call, изменение исторических runs.

## Interaction topology

```text
registered Baresip peer ⇄ FreeSWITCH ⇄ SIP adapter/PJMEDIA
                                         ├─ ingress → existing ASR path
                                         └─ egress source → PCMU/RTP → Baresip sndfile
```

Control events по-прежнему идут через существующий Dispatcher/Event Bus; PCM и запись — напрямую. No-VAD и noise
source не добавляют control-plane message.

## Owner review

| Вопрос | Решение | Статус |
|---|---|---|
| Использовать ли новый CN SDP payload для live gate? | Нет | `resolved 2026-09-14` |
| Считать ли непрерывный PCMU/RTP обязательным acceptance? | Да | `resolved 2026-09-14` |
| Является ли новая стереозапись runtime artifact? | Нет, её по-прежнему владеет Baresip test peer | `resolved by architecture` |

## Implementation slices

| Slice | Действие | Acceptance | Stop |
|---|---|---|---|
| C1 | Clean-start registered full-AI run с актуальной конфигурацией no-VAD/comfort noise | Registration, readiness, 200, existing full scenario pass | External/runtime failure after corrective retry |
| C2 | Проверить RTP continuity по окну `200 OK(INVITE) → BYE/media_stopped` и negotiated profile | `round(window/ptime)` совпадает с egress frames; peer получает тот же объём; no underruns/errors/loss | Event window/profile unavailable or egress count gap persists |
| C3 | Сохранить raw/stereo/report и выполнить отдельный recording audit | Raw tracks и report сохранены; stereo builder выравнивает дорожки по event window и creation timestamps; recording audit не блокирует C2 | Raw tracks отсутствуют, event window недоступен или recording helper ломает обязательный evidence path |
| C4 | Run full regression, no-GIL/import evidence, registry/backlog and docs closeout | All required gates pass; statuses factual | Concrete category-4 blocker only |

## Blocker register

| ID | Триггер | Что блокируется | Evidence | Статус |
|---|---|---|---|---|
| `B-010-C-001` | GPU/runtime or registered stand unavailable after approved retries | C1/C4 | Sanitized command, stdout/stderr, exit code, environment | `none until triggered` |
| `B-010-C-002` | Baresip `enc`/`dec` recording boundary diverges at transfer teardown beyond the approved cleanup tail | Recording diagnostic only; no longer blocks Map-010 RTP continuity | [execution evidence](../../artifacts/implementation/010-continuous-pcmu-comfort-noise/010-C/execution-evidence.md), r1/r2/r3 live JSON, raw WAV and event-window audit | `superseded by event-window recording correction 2026-09-14` |
| `B-010-C-003` | Existing full-AI scenario regresses for a reason outside this write-set | Map-010 closeout | Regression diff and pre-existing classification | `none until triggered` |

## Test plan и evidence

Target command is the current registered full-AI runner from [`user-guide.md`](../user-guide.md), with a new output root
under `artifacts/implementation/010-continuous-pcmu-comfort-noise/010-C/<target>/`.

Required evidence:

- target runtime, `gil_enabled=false`, native import/runtime probe;
- registration trace and `180 → readiness → 200/503` result;
- negotiated PCMU/8000/mono, ptime, answered-call event window и frame/packet count evidence;
- `callback_errors=0`, overflow/closed drops `0`, `egress_underruns=0` for the intended scenario;
- raw Baresip `enc`/`dec`, event-window stereo WAV/manifest and report; raw duration result is diagnostic;
- full target regression and document-registry/task-backlog audits;
- explicit RTP continuity audit showing expected egress frames, peer receive count and no media errors/loss;
- explicit recording audit, which may report a Baresip teardown boundary mismatch without converting it into RTP failure.

Every red result first receives a corrective retry. No GPU test is marked deferred and simultaneously reported as pass.

## Fallback/deferred register

| Что введено | Почему | Ограничение | Статус |
|---|---|---|---|
| RFC 3389/CN | Не входит в MVP | Future map, no SDP/write-set change | `deferred` |
| `none` | — | — | — |

## Closeout

`010-C` получает `complete` только после C1–C4 и фактического evidence. После этого Map-010 синхронизирует owner
documents и получает binary map-level closeout. Неполный live run не объявляется foundation/complete.

## Execution closeout

В target `20260914-r4` C1–C4 полностью прошли. Непрерывность проверена по answered-call event window от `200 OK`
на `INVITE` до получения `BYE`, negotiated `ptime=20 ms` и согласованным adapter/peer RTP counters: окно
`125618.477 ms`, ожидалось `6281`, фактически egress `6281`, peer receive `6281`, loss `0`, underruns `0`,
callback errors `0`, egress drops `0`. Raw recording и stereo audit также прошли: gap `360 ms ≤500 ms`.

Первоначальный blocker `B-010-C-002` закрыт корректировкой критерия приёмки: длительность WAV больше не используется
как доказательство непрерывности RTP. Она остаётся отдельной диагностикой записи; в r4 она дополнительно прошла
принятый лимит. Новых блокеров нет, поэтому Plan 010-C закрыт полностью.
