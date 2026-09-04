# Plan 006-B: воспроизводимый demo runbook

Уровень: `child plan`  
Идентификатор: `006-B`  
Статус owner review: `accepted — scope inherited from Map-006, 2026-09-04`  
Статус исполнения: `complete`  
Родитель: [`plan-006-report-and-demo-preparation.md`](plan-006-report-and-demo-preparation.md)

## Цель

Описать повторяемый запуск демонстратора: preflight Windows/WSL, target no-GIL runtime, модели и RAG warmup,
локальный Baresip peer/fake operator, clean-start SIP/RTP scenario и проверку текстовых/аудио артефактов.

## Materialized APG rules

- Runbook использует только существующие commands/evidence; новые способы запуска и fallback не вводятся.
- Warmup RAG/LLM/ASR/TTS выполняется до SIP admission; warmup не выдаётся за latency результата звонка.
- GPU-heavy запуск выполняется одним main executor; перед ним проверяются свободные 20 ГБ и отсутствие чужой нагрузки.
- Runtime target — CPython 3.14.7t с `gil_enabled=false`; host Python используется только для document audits.
- Audio payload не проходит через Dispatcher; запись выполняет Baresip peer, runtime бота не пишет аудио.
- Write-set: только `artifacts/report-preparation-20260904/demo-runbook.md` и собственный closeout.

## Scope и проверки

Зафиксировать prerequisites, exact commands, ожидаемые evidence/status, demo-flow из r7, cleanup, troubleshooting для
занятой GPU/диска и правило не принимать старый run за финальный. Проверить команды по существующим `commands.md` и
финальному r7 package. Запускать новый GPU gate не требуется.

## Blockers

`B-006-B-001`: category-4, если воспроизводимый runbook невозможно составить из имеющихся exact commands и evidence.
На начало исполнения blocker отсутствует.

## Acceptance/closeout

`demo-runbook.md` позволяет подготовить clean-start rehearsal без неявных defaults и содержит ссылки на final r7
artifacts, known limitations и post-run cleanup. После этого план получает `complete`.

Фактический closeout: [`006-B-closeout.md`](../../artifacts/report-preparation-20260904/006-B-closeout.md).
