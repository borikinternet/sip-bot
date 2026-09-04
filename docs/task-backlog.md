# Backlog задач проекта

Статус: `active`

Документ учитывает работу, которая ещё не закрыта, частично выполнена, отложена или сознательно вынесена за границы
MVP. Он не заменяет [дорожную суперкарту](roadmap.md): roadmap описывает порядок программы, а backlog — конкретные
остаточные задачи и их состояние.

## Правила

- Каждая задача получает уникальный идентификатор `TASK-NNN`.
- Статус задачи отражает фактическое состояние, а не намерение.
- `Source` указывает документ или решение, из которого возникла задача.
- `Next step` должен быть конкретным; для `done` допускается ссылка на evidence.
- Закрытая задача не удаляется: её статус меняется на `done`, `superseded` или `out_of_scope`.
- Если задача требует архитектурного выбора, в `Next step` указывается новый ADR/plan-file и задача не считается выполненной.
- После изменения таблицы запускается `python tools/check_task_backlog.py`.

## Статусы и приоритеты

| Статус | Значение |
|---|---|
| `open` | Задача принята, но работа не начата. |
| `in_progress` | Работа выполняется в текущем согласованном срезе. |
| `blocked` | Работа остановлена из-за внешнего или owner-review условия. |
| `deferred` | Задача отложена до отдельного среза/решения. |
| `done` | Есть evidence закрытия. |
| `out_of_scope` | Задача сознательно не входит в MVP. |
| `superseded` | Задача заменена другим идентификатором. |

Приоритеты: `high`, `medium`, `low`.

## Реестр задач

| ID | Название | Статус | Приоритет | Source | Next step | Owner | Updated |
|---|---|---|---|---|---|---|---|
| `TASK-001` | Feasibility benchmark CPython 3.14t и выбранных SIP/ASR/LLM/TTS-кандидатов | `done` | `high` | `roadmap.md`, `ADR-003`, `plans/plan-001-deadline-feasibility.md` | Evidence закрытия: Map-001, `001-A`/`001-B`, `001-S`, `001-C1`–`001-C4`, `001-D`, `001-E`; прикладная реализация продолжается отдельной Map-002 | project owner | 2026-09-03 |
| `TASK-002` | Проверка no-GIL для критичных native-зависимостей | `done` | `high` | `ADR-003`, `tooling-notes.md`, `plans/plan-001-C1-sip-pjsua2-pjmedia.md`, `plans/plan-001-C2-asr-primary.md`, `plans/plan-001-C3-llm-primary.md`, `plans/plan-001-C4-tts-primary.md` | Evidence закрытия: C1–C4 import/operation/isolation gates и application target-runtime checks; повторять только при смене native baseline | project owner | 2026-09-03 |
| `TASK-003` | Создание локального SIP/RTP тестового стенда с PCMU и fake operator | `done` | `high` | `roadmap.md`, `architecture.md`, `plans/plan-001-C1-sip-pjsua2-pjmedia.md`, `plans/plan-001-S-voip-test-stand.md` | Evidence закрытия: `artifacts/feasibility/001-S-voip-test-stand/closeout.md`; повторять только при изменении SIP candidate | project owner | 2026-08-27 |
| `TASK-004` | Проверка запуска на native Ubuntu вне WSL2 | `out_of_scope` | `low` | `roadmap.md` | Вернуться после MVP при наличии отдельной Linux-машины или GPU-стенда | project owner | 2026-08-25 |
| `TASK-005` | Поддержка нескольких параллельных разговоров и планирование общей нагрузки | `out_of_scope` | `low` | `requirements.md`, `roadmap.md` | Не расширять MVP; оформить отдельную production roadmap при необходимости | project owner | 2026-08-25 |
| `TASK-006` | Production hardening: HA, secrets, observability и эксплуатационный runbook | `out_of_scope` | `low` | `roadmap.md`, `licensing-policy.md` | Не объявлять MVP production-ready; создать отдельную roadmap при появлении требования | project owner | 2026-08-25 |
| `TASK-007` | Сквозная call-session composition вокруг существующих Dispatcher/DialogueFSM и live SIP-to-AI driver | `done` | `high` | `plans/plan-002-I.0-call-session-orchestration-and-state.md`, `plans/plan-002-I.1-live-call-asyncio-wiring.md`, `plans/plan-002-J-transfer-report-integration.md`, `plans/plan-002-I-boundary-interaction-map.md`, `plans/plan-002-mvp-media-and-speech-integration.md` | I.0/I.1/J complete; corrective full clean-start J4 r20: SIP/RTP, follow-up, RAG, barge-in, unknown-answer/transfer и report, 6/6 checks; residual quality/production gaps переданы Map-005/backlog | project owner | 2026-09-04 |
| `TASK-008` | Системное тестирование и исправления после закрытия карты 4 | `done` | `high` | `roadmap.md`, `plans/plan-002-mvp-media-and-speech-integration.md`, `plans/plan-005-system-testing-and-demo-readiness.md`, `plans/plan-005-A-protocol-media-failure-matrix.md`, `plans/plan-005-B-speech-audio-resilience.md`, `plans/plan-005-C-ai-quality-latency-resources.md`, `plans/plan-005-D-rehearsal-evidence-closeout.md`, `plans/plan-005-E-tts-playback-integrity-corrective.md`, `docs/development-guidelines.md` | A–E и map-level acceptance complete; r10 подтвердил полный TTS output, no overflow и `egress_underruns=0`; r7 сохранён исторически | project owner | 2026-09-04 |
| `TASK-009` | Подготовка доклада и воспроизводимого демонстрационного пакета | `done` | `high` | `roadmap.md`, `plans/plan-006-report-and-demo-preparation.md`, `docs/licensing-policy.md`, `plans/plan-006-D-demo-input-timing-corrective.md` | A–D complete; target r6 дал compact fixture, 7/7 checks, stereo recording и audio audit. Редактура, project license и публикация остаются отдельными действиями | project owner | 2026-09-05 |
