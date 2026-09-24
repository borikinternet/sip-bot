# План 012-A: контракт corpus package и синтетический корпус

Уровень: `child plan`  
Идентификатор: `012-A`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Предшественник: [`012-I`](plan-012-I-rag-lifecycle-boundary-map.md)  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-A/`

## Цель и граница

Ввести versioned typed contract входного корпуса, строгий validator и синтетический русскоязычный corpus небольшой
сервисной компании. Входной формат — UTF-8 Markdown + JSON manifest; PDF/DOCX/HTML/OCR не входят.

## Материализованные правила и owner decisions

- Corpus/index/search остаются capability `Context/KB Manager`; CLI позднейших планов вызывает её методы.
- Каждый source обязан иметь stable `source_id`, file, title, URL/origin, license, attribution, owner, version,
  effective date, priority, topics и audiences. Path traversal, duplicate IDs/files, пустые документы и unknown fields
  не принимаются молча.
- Существующий science corpus остаётся regression fixture и переводится на тот же schema без изменения содержания.
- Workshop corpus синтетический, публикуемый вместе с исходниками; он содержит услуги, режим работы, цены/условия,
  процедуру заявки, исключения и escalation contacts.
- Invalid source не пропускается по умолчанию: validation возвращает machine-readable error и build не начинается.
- Новый parser/backend/model/fallback не выбирается в этом плане.

## Source-map и write-set

Разрешено: `src/sip_bot/retrieval/contracts.py`, новый `src/sip_bot/retrieval/corpus.py`,
`src/sip_bot/retrieval/__init__.py`, `data/knowledge/corpus/manifest.json`,
`config/workshops/rag/corpus/**`, `tests/unit/test_rag_corpus.py`, собственный evidence и этот plan.

Protected: `index.py`, Ollama/LLM files, runtime/config constants, conversation pipeline, SIP/media/speech, existing
document text in science Markdown files.

## Implementation slices

1. `A1`: typed `CorpusManifest`, enriched `CorpusSource`, `CorpusDocument` и `CorpusValidationReport`.
2. `A2`: strict UTF-8 JSON/Markdown validator with path confinement and deterministic ordering.
3. `A3`: migrate science manifest to schema v1 without content change.
4. `A4`: create synthetic workshop package and validate license/provenance.
5. `A5`: unit tests, evidence and binary closeout; publish contract revision to 012-B.

## Blockers, tests и acceptance

| ID | Trigger | Status |
|---|---|---|
| `B-012-A-001` | Source/license/version/priority cannot be validated unambiguously | `none until triggered` |

Tests cover valid packages, malformed JSON/UTF-8, missing/unknown fields, duplicate IDs/files, absolute/traversal path,
empty document, stable order and both checked-in packages. Acceptance requires no silent skip and no changes outside
write-set. Red results in scope receive corrective pass; final status only `complete` or concrete `blocked`.

## Delegation/evidence/closeout

If delegated, the agent may change only this write-set, may not alter schema/model decisions, and must return files,
diff, exact commands/exit codes and blockers. Main executor reruns tests and synchronizes owner docs/registry later.
Evidence root contains validation reports, hashes, commands and closeout.

## Execution closeout — 2026-09-21

Введён contract `rag-corpus-v1`, strict fail-closed validator, schema-v1 migration science corpus и синтетический
CC0 workshop corpus из шести документов. Target regression: `22 passed`, no-GIL подтверждён. Открытых blocker и
fallback нет. Evidence и точный handoff: [`012-A/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-A/closeout.md).
