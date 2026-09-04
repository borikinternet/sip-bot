# Plan-002-J: transfer, report и сквозная интеграция

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-03`  
Статус исполнения: `complete` — J1–J3, J4 component/composition lanes, full fresh live SIP/RTP scenario matrix и
J5 closeout приняты главным executor.  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Собрать последний интеграционный срез карты 4: локальный fake operator через approved `001-S`, безопасный transfer,
текстовый context/report closeout и чистый сквозной demo-flow. Демонстрация должна покрыть обычный ответ с RAG,
контекстный follow-up, barge-in, unknown-answer с предложением оператора, подтверждённый transfer и итоговый текстовый
отчёт без записи аудио проектом.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Transfer, context, report and no recording are MVP boundaries | Full demo matrix includes all mandatory scenarios | Clean-start integration | Any mandatory scenario missing |
| [`roadmap.md`](../roadmap.md) | Demo-ready by 20 September, report 25 September | Integration/evidence gate has early boundary and reserve | Calendar evidence | Demo first works only after boundary |
| [`architecture.md`](../architecture.md) | Transfer is FSM→SIP/fake operator; report consumes context | No direct LLM SIP access, no audio recording | Architecture audit | Model initiates transfer |
| [`technical-specification.md`](../technical-specification.md) | Context is available during the call and report is produced at close | Report built from text/context snapshot | Context/report lifecycle tests | Context is unavailable or mandatory report is missing |
| [`plan-001-S-voip-test-stand.md`](plan-001-S-voip-test-stand.md) | Approved local Baresip peer/fake operator | Use existing stand, no real PBX | Transfer smoke | New external operator service |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | Transfer/report cycles and channel lifecycle explicit | Integration honors close/cancel/re-entry | Map-I closeout | New edge absent from map |
| [`plan-002-I.0-call-session-orchestration-and-state.md`](plan-002-I.0-call-session-orchestration-and-state.md) | Existing Dispatcher/DialogueFSM plus CallSession composition are separated | J4 consumes only the accepted I.0 composition contract | I.0 execution/closeout + Map-I propagation | I.0 execution/closeout remains open |

## 3. Граница задачи

**Цель:** transfer orchestration with fake operator, context/report finalization, clean-start end-to-end harness and
map-level evidence.

**Входит:** user-confirmed operator offer, FSM→SIP transfer command, fake operator result, terminal/transfer cleanup,
context snapshot/report builder, scenario fixtures, full PCMU SIP flow and evidence package.

**Не входит:** real PBX/operator integration, audio recording, production deployment, load testing, new model/backend,
new SIP/RTP stack or changing component ownership.

**Protected baseline:** `001-S` local stand, one conversation, PCMU, RAG source-aware answer, direct data plane,
Dispatcher/FSM action validation, TTS cancellation and text-only report.

**Предположения:** A–H are individually accepted/closed with current Map-I contract revisions; I.0 owns the new
call-session composition gap; J is the only plan that may claim map-level end-to-end evidence after I.0 closeout.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Transfer | `src/sip_bot/transfer/` | Stand evidence only | Typed transfer command/result over SIP boundary | App orchestration absent | Implement owner service |
| Report | `src/sip_bot/report/` | No app report | Markdown report from text/context/events | No builder | Implement deterministic builder |
| Integration harness | `tests/integration/`, `tests/scenarios/` | Deterministic harness and clean-start component runner exist; live runtime wiring absent | One live SIP call through the accepted AI path | Existing consumer input methods are not invoked by the application loop | Execute approved successor `002-I.1` before full J4 |
| Evidence | `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/` | Absent | Full traces and closeout index | No map evidence | Create at execution |
| Docs | Map-I, parent map, registry/backlog | Plans only | Actual contract/status sync | Evidence absent | Update only after facts |

Допустимый write-set: `src/sip_bot/transfer/`, `src/sip_bot/report/`, integration/scenario tests, demo-run scripts,
own evidence root and synchronized status entries. Не менять requirements/architecture/technical-specification/ADR и
исполненные `001-*` молча.

### 4.1. Execution handoff и разграничение работ

Детерминированные J1–J3 slices исполняются субагентом в указанном write-set. Ему разрешены typed transfer/report
owners, fake-operator fixtures, scenario harness без запуска native inference, unit/contract tests и собственный evidence
root `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/`. Общие документы-владельцы, Map-I, parent map,
registry, backlog и итоговый статус изменяет главный executor после проверки diff и результатов.

Субагенту запрещены heavy GPU inference, запуск Ollama/XTTS/ASR, реальный SIP/RTP smoke, изменение модели или patch
baseline, изменение ownership/contract revision, скрытый fallback и ослабление assertions. Если нужен новый boundary,
owner decision или изменение write-set, он фиксирует gap и останавливает зависимый slice. Lock-файл пакетного менеджера
не считается немедленным blocker: повторить попытку после случайной задержки и сообщить устойчивый сбой только после
повторных попыток.

Обязательный handoff субагента: changed files, diff summary, commands/runtime/exit codes, targeted и regression tests,
evidence, pre-existing/out-of-scope findings, открытые blockers и следующий main-only gate. Отчёт субагента не считается
самостоятельным closeout: главный executor принимает его только после фактической проверки.

Исторический main-only J4 preflight показал, что разрешённый write-set не содержал production-level call-session
orchestration. `B-002-J-005` снят отдельным I.0. После I.0 clean-start runner подтвердил component/composition
lanes, но аудит J4 обнаружил следующий category-4 gap: application runtime не
вызывает существующие typed input methods, связывающие `SipMediaAdapter` с
speech pipeline и paced playback. Он зарегистрирован как `B-002-J-006`; новый
semantic component, delivery-owner, API или скрытый fallback до owner review
не вводятся. Подробности — в
[`j4-integration-gap.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-integration-gap.md).

## 5. Interaction topology и propagation контрактов

`N9 → N1 → N16` carries validated transfer command and SIP/fake-operator result; `N16 → N1/N9` returns protocol and
application events. `N10 → N17` provides context snapshot/terminal outcome; `N9 → N17` sends report command. J consumes
the direct media/text channels established by A–H but does not route their payload through Dispatcher.

Transfer is allowed only after explicit user confirmation or an explicit user request. When transfer starts, active LLM/TTS
operations and playback are closed/cancelled, the old conversation state is terminal for bot handling, and SIP result is
recorded. Normal hangup and transfer both finalize a text-only report exactly once; repeated terminal events are idempotent.

## 6. Audit владельца поведения и парадигмы реализации

FSM owns transfer authorization and terminal transition; SIP/media adapter owns protocol execution; fake operator adapter
owns stand interaction; context store owns persisted turns; report builder owns Markdown rendering. The integration harness
orchestrates tests but does not become a production component or bypass owners. Pure report formatting may be a function;
transfer state mutation cannot be a free helper.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Какой операторский контур? | Только local fake operator from `001-S` | No real PBX/contact-center integration | `resolved` |
| Когда разрешён transfer? | Explicit user request or positive confirmation after unknown-answer | LLM suggestion is validated by FSM | `resolved` |
| Что записывается в report? | Text turns, state/decision/context/RAG source trace and outcomes; no audio | Report is reproducible and text-only | `resolved` |
| Что является map-level pass? | Clean-start full demo matrix with source-aware RAG and unknown-answer/transfer | Unit-only evidence is insufficient | `resolved` |
| Какой recovery после failed transfer? | Зафиксировать failure и вернуть/завершить разговор по политике FSM; скрытый альтернативный оператор запрещён, а изменение политики проходит APG gap/owner review только при фактической необходимости | Не вводить новый recovery path молча; заранее утверждённое правило не является открытым вопросом | `resolved: APG fallback/gap rule; review only if triggered` |
| Кто владеет сквозным call-session orchestration? | `Dispatcher` владеет control ordering и active-session slot; отдельный `CallSession` — per-call composition/lifecycle; `DialogueFSM` сохраняет semantic ownership | Детальная typed composition передана в I.0; runtime wiring existing input methods выполняется в `002-I.1`, новый process не вводится | `resolved: owner decision 2026-09-03` |
| Нужен ли обязательный `state.json`? | Нет; такого требования нет. `report.md` — единственный обязательный итоговый артефакт; `conversation.jsonl` может быть внутренним журналом | I.0 проверяет только context/report lifecycle и не добавляет schema/checkpoint/restore для `state.json` | `resolved: owner clarification 2026-09-03` |

## 8. Process invariant audit

- J is the only end-to-end claim point and depends on closed upstream contracts.
- Clean-start runs use reproducible commands and fresh call/context/evidence directories.
- Test harness does not introduce hidden fallback or bypass FSM/SIP owners.
- Report contains actual statuses, pre-existing failures and out-of-scope findings.
- Deadline gate is 20 September; remaining days are rehearsal/reserve, not permission to expand scope.

## 9. Architecture invariant audit

- Transfer commands originate from FSM, not directly from LLM.
- SIP protocol reaction remains local to adapter; report does not block call close.
- No audio recording is created.
- Context/RAG source IDs are preserved into report evidence.
- Barge-in, close, stale result and re-entry behavior are tested in the full path.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| J1 | Connect transfer command/result with `001-S` fake operator | Positive confirmation completes local transfer; failure is typed | SIP result cannot map to FSM |
| J2 | Implement context/report closeout | Normal and transfer terminal paths create one text report | Duplicate/missing report or audio file |
| J3 | Build scenario matrix and clean-start harness | Deterministic fixtures and clean-start setup are reproducible | Scenario depends on dirty state |
| J4 | Run end-to-end evidence and latency/VRAM collection | One live SIP call proves source-aware answer, follow-up, barge-in, unknown-answer/transfer, paced PCMU playback and report | `pass`: `j4-full-live-20260904-r20` |
| J5 | Map closeout and handoff to next supermap card | Residual gaps/backlog/evidence index complete | `pass`: Map-I, parent map, registry and backlog synchronized |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-J-001` | весь plan | Child plan не прошёл owner review/closeout | End-to-end execution | project owner | APG and upstream closeouts | `resolved: owner review and J1–J5 closeout` |
| `B-002-J-002` | J1 | `001-S` transfer contract or SIP result mismatch | Transfer demo | project owner + media owner | `deterministic-results.json`, `001-S` stand evidence | `resolved: typed/fake boundary and live SIP-backed transfer accepted in r20` |
| `B-002-J-003` | J2–J4 | Missing source-aware RAG, context lifecycle or report | Map-002 closeout and report | project owner | `deterministic-results.json`, `j4-preflight.md` | `resolved: deterministic and full live evidence` |
| `B-002-J-004` | J3–J4 | Clean-start scenario cannot reproduce full flow by 20 Sep | Demo readiness | project owner | [`j4-full-live-20260904-r20`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-full-live-20260904-r20/j4-full-live.json) | `resolved: 6/6 checks, exit code 0` |
| `B-002-J-005` | J4 | Approved J write-set had no production call-session orchestration owner | J4 full demo and Map-002 closeout | project owner | [`j4-preflight.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-preflight.md), Map-I revision 15 | `resolved: I.0 complete and composition evidence accepted 2026-09-03` |
| `B-002-J-006` | J4 | Existing typed input methods are not invoked by runtime wiring from live SIP ingress through speech/AI to paced TTS PCM egress | Full J4 acceptance, J5 and Map-002 closeout | project owner | [`j4-integration-gap.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-integration-gap.md), `002-I.1` evidence, J4 evidence | `resolved: base path r4 and corrective full matrix r20` |

## 12. Test plan и evidence

- transfer on explicit request and on positive confirmation after unknown-answer;
- transfer failure, remote hangup, normal hangup and repeated terminal event;
- text context file during call and one final `report.md` for normal/transfer close;
- clean-start scenario matrix: RAG answer with source IDs, follow-up context, barge-in, unknown-answer and transfer;
- full PCMU SIP/RTP run through `001-S`, including protocol events applicable to the integrated path;
- stale LLM/TTS result after barge-in/close is not audible or actionable;
- final-turn→retrieval→LLM first result/complete and first audible response timings, VRAM/model/runtime metadata;
- evidence index links every scenario to commands, logs, exit codes and contract revision.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Local fake operator | No real PBX/operator is in project scope | Demonstrates typed transfer boundary only | `001-S` and J | `approved scope boundary` |
| Small curated corpus/index | Deadline-critical RAG demonstration | Must retain source-aware retrieval and unknown negative case | F/J/report | `approved scope boundary` |
| Production hardening/load/MOS campaign | Outside MVP deadline | Handoff to next map/backlog | Map-002 closeout | `out of scope` |
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete`. J1–J3 deterministic implementation, I.0 composition, I.1 live wiring, J4 full live
scenario matrix и J5 document/map closeout приняты главным executor.

Главное evidence — [`j4-full-live-20260904-r20`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-full-live-20260904-r20/j4-full-live.json): один чистый Baresip-вызов
прошёл SIP/RTP PCMU/8000/mono, два связанных вопроса, RAG/source IDs, barge-in с остановкой старого playback,
unknown-answer с предложением оператора, `Да.` → `user_confirmed` → SIP transfer `100/200` и итоговый
`report.md`. Все `scenario_checks` имеют значение `true`, `errors=[]`, no-GIL runtime подтверждён.

J5 закрыт синхронизацией `Map-002-I` (revision 21), parent Map-002, J4/I.1 evidence, document registry и task
backlog. Остаточные production hardening, нагрузка/MOS и качество TTS остаются явно переданными в карту 5/backlog;
они не маскируются под обязательные J4 blockers.

После красного диагностического r19 в пределах speech-ingress scope выполнен corrective pass: общий префикс соседних
partial ASR-гипотез не фиксируется без явного `stable_prefix` от backend. Targeted/target regression и r20 full live
gate прошли; r19 сохранён отдельно как raw failure evidence.
