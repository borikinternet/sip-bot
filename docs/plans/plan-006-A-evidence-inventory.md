# Plan 006-A: inventory evidence и traceability

Уровень: `child plan`  
Идентификатор: `006-A`  
Статус owner review: `accepted — scope inherited from Map-006, 2026-09-04`  
Статус исполнения: `complete`  
Родитель: [`plan-006-report-and-demo-preparation.md`](plan-006-report-and-demo-preparation.md)

## Цель

Собрать компактный индекс источников для доклада: требования, архитектурные решения, фактические кандидаты/runtime,
сценарии и финальные результаты Map-005. Индекс не копирует нормативные документы и не создаёт новые claims.

## Materialized APG rules

- Один факт имеет владельца; в производном индексе остаётся краткое утверждение и ссылка на source document/evidence.
- Числовой результат указывается с точным evidence path, run id и статусом проверки.
- `r7` является финальным Map-005 rehearsal evidence; r5/r6 остаются историческими corrective attempts.
- Недостающее evidence помечается `not demonstrated`, а не заменяется предположением.
- Write-set: только `artifacts/report-preparation-20260904/source-index.md` и собственный closeout.

## Scope и проверки

Включить REQ, architecture/TЗ claims, component/model/runtime facts, scenario matrix, latency/VRAM/warmup, recording,
licensing source links и list of known limitations. Проверить существование всех локальных paths, согласованность r7
JSON/closeout и отсутствие conflicting values. Новый GPU run не нужен.

## Blockers

`B-006-A-001`: category-4 только если обязательный claim нельзя сопоставить ни с одним действующим источником и его
нельзя честно пометить как limitation. На начало исполнения blocker отсутствует.

## Acceptance/closeout

`source-index.md` содержит таблицу `claim → owner/source → evidence → status`, ссылки и отдельные списки limitations и
not-demonstrated properties. После этого план получает `complete`.

Фактический closeout: [`006-A-closeout.md`](../../artifacts/report-preparation-20260904/006-A-closeout.md).
