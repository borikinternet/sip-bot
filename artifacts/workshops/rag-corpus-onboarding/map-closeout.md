# Map-012 closeout: воспроизводимая смена корпуса и RAG-мастер-класс

Статус: `complete`

Дата: `2026-09-21`

## Child plans

`012-I`, `012-A`, `012-B`, `012-C`, `012-D`, `012-E` и `012-F` закрыты собственными статусами `complete` и
closeout/evidence. Незавершённых или частично закрытых child plans нет.

## Map-level acceptance

1. Strict `rag-corpus-v1` проверяет metadata, license/provenance, encoding, paths, duplicates/conflicts и content.
2. `markdown-semantic-v1` детерминированно даёт 12 stable chunks.
3. Offline build через typed `LLM Facade` воспроизводит `rag-index-v1`; atomic failure tests сохраняют старый artifact.
4. Runtime проверяет exact compatibility и загружает index с нулём corpus embedding requests.
5. Frozen evaluation set SHA-256 `35f5bc63156bf99a7e1ff0fe948c4fba9b3dacba694df55a87faec6464ac3738`
   проходит `12/12`.
6. Registered `live-r5` использует workshop corpus, корректно ведёт positive/follow-up/unknown/transfer, не использует
   `wiki-*`, сохраняет source-aware report, continuous RTP и stereo recording.
7. Self-contained runbook прошёл независимый context-free review после фактического corrective pass.
8. `knowledge-base.md`, architecture, ТЗ, user guide, roadmap, registry и backlog синхронизированы.

## Deferred/out-of-scope

External vector DB, PDF/DOCX/HTML importer, OCR, hot reload во время звонка, incremental indexing, ACL/multi-tenant
corpus и production launcher не выдаются за выполненные. Их promotion требует отдельной карты и owner review.

## Blockers

`none`. Красные live runs были классифицированы и исправлены в утверждённом map scope; raw artifacts сохранены.

## Final checks

- Target runtime regression:
  `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q` → `241 passed, 2 skipped`, exit `0`,
  `43.93 s`.
- `python tools/check_document_registry.py` → `actual=85`, `registry_rows=85`, missing/extra/duplicates `0`, PASS.
- `python tools/check_task_backlog.py` → `rows=16`, `unique_ids=16`, PASS.
- Registered final gate: `012-F/live-r5/rag-workshop-full-live.json` → status `pass`, все workshop/scenario/RTP/
  recording checks true.
- Independent context-free review: PASS, blockers `none`.
