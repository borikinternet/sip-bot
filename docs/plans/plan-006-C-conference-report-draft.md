# Plan 006-C: черновик конференционного доклада

Уровень: `child plan`  
Идентификатор: `006-C`  
Статус owner review: `accepted — scope inherited from Map-006, 2026-09-04`  
Статус исполнения: `complete`  
Родитель: [`plan-006-report-and-demo-preparation.md`](plan-006-report-and-demo-preparation.md)

## Цель

На основе `006-A` и `006-B` подготовить русскоязычный черновик доклада: задача, архитектура, технологии, RAG,
сценарии, измерения, ограничения и воспроизводимость. Материал должен быть пригоден как нейтральный outline
выступления и не зависит от ещё не заданного числа слайдов или длительности.

## Materialized APG rules

- Report — производный operational artifact и ссылается на owner documents; он не заменяет requirements, architecture,
  ТЗ, ADR или licensing policy.
- Каждый существенный claim получает ссылку на source-index/evidence; отсутствие production proof явно помечается.
- Latency `final phrase → first PCM = 1785.090 ms` показывается честно; `200–500 ms` не объявляется достигнутым.
- Обязательный RAG, source IDs, unknown-answer/transfer, barge-in, multi-turn и Baresip stereo evidence должны быть
  видны в narrative и traceability.
- Лицензии кода, моделей, corpus, voices и outputs не смешиваются; unresolved project-license choice остаётся open в
  publication checklist.
- Write-set: только `report-draft.md`, `publication-checklist.md` и собственный closeout.

## Scope и проверки

После handoff A/B собрать sections: abstract, problem/MVP boundaries, architecture, concurrency/control-vs-data plane,
ASR/LLM/RAG/TTS, demo flow, measured evidence, limitations, reproducibility, publication checklist. Проверить каждую
ссылку и согласованность числовых данных с r7/C evidence. Новые model/GPU tests не требуются.

## Blockers

`B-006-C-001`: category-4, если обязательный тезис доклада требует нового технического решения или неподтверждённого
evidence. На начало исполнения blocker отсутствует.

## Acceptance/closeout

`report-draft.md` и `publication-checklist.md` созданы на русском языке, имеют traceability через `source-index.md`,
показывают achieved/known limitations/not-demonstrated и готовы к содержательной редактуре владельцем. После этого
план получает `complete`.

Фактический closeout: [`006-C-closeout.md`](../../artifacts/report-preparation-20260904/006-C-closeout.md).
