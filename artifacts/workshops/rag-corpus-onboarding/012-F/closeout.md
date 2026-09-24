# 012-F closeout: workshop runbook and registered live gate

Статус: `complete`

Дата: `2026-09-21`

Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-F/`

## Результат

- Опубликован self-contained `docs/workshops/rag-corpus-onboarding-runbook.md`.
- Clean repeat: strict validation PASS; build `12 × 768`; artifact SHA-256
  `9a2e0937cf2bcf3a2533b4762410490c0e40420f64a29483cf2e487b56d2b579`; evaluation `12/12`.
- Runtime probe: prebuilt workshop index загружен, `corpus_embedding=0`, `warm_query_embedding=1`.
- Финальный registered FreeSWITCH run: `live-r5/rag-workshop-full-live.json`, status `pass`.
- Независимый context-free review после corrective pass: `PASS`, blockers отсутствуют.

## Финальный live evidence

- Evidence ID: `E-002-J4-FULL-LIVE-20260921T183117Z`.
- Runtime: CPython 3.14.7 free-threaded, `gil_enabled=false`.
- Readiness: `21732.495 ms`; RAG index load `8.513 ms`, corpus embeddings `0`.
- Все `rag_workshop.checks` true: positive source, live follow-up, old-science insufficient, корректный unknown-answer,
  отсутствие `wiki-*` leakage и workshop sources в report.
- Все scenario checks true: follow-up, barge-in, unknown/offer, transfer, operator result, report, RTP и stereo.
- RTP: answered-call window `74217.920 ms`, negotiated `ptime=20 ms`, expected/egress/peer `3711/3711/3711`, loss,
  underruns, callback errors и drops равны нулю.
- Stereo: `live-r5/recordings/conversation-stereo.wav`, `74.217875 s`, SHA-256
  `2cb8cffb7f1cfccfdd5204b6e05bc3d23fd36c3938b47159f388b0fc18bfe916`.
- Report: `live-r5/reports/call-in-0/report.md`; итог `transfer_completed`, `operator_connected`.

## Corrective history

| Run | Красный результат | Классификация и исправление |
|---|---|---|
| `live-r1` | История заражала новый вопрос; teardown frame считался PCM; ±1 RTP packet отклонялся | Implementation/test defects: selective context, ignore non-audio PJMEDIA callback, approved frame tolerance |
| `live-r2` | Однословное `Голубое` ошибочно наследовало историю | Удалён безусловный short-fragment context; реальный probe подтвердил `sufficient=false` |
| `live-r3` | FSM offer/transfer прошёл, но текст LLM содержал ложный совет про газ | Независимый review выявил false positive; insufficient hits изолированы от prompt, добавлена semantic text assertion |
| `live-r4` | ASR потерял «А ночью», и `Сколько будет стоить?` не получило контекст | Добавлено узкое правило elliptical `сколько...?`; gate теперь требует sufficient pricing follow-up |
| `live-r5` | Нет | Финальный PASS по расширенному gate |

Raw красные artifacts сохранены; вопросы evaluation, expected sources и acceptance не удалялись и не ослаблялись.

## Проверки

- Targeted prompt/retrieval/LLM/pipeline regression: `27 passed` после последней corrective revision.
- Frozen real evaluation после retrieval correction: `12/12`.
- Independent review: `41 deterministic tests passed` и статическая проверка всех CLI/compose/scripts.
- Финальный общий regression и document/backlog checks зафиксированы в map-level closeout.

## Process/architecture audit

- Offline build и online load/query разделены; corpus re-embedding на startup/call path отсутствует.
- Typed boundaries, единственный `LLM Facade`, Dispatcher/FSM и SIP/media protected baseline сохранены.
- Новый delivery owner, vector DB, hot reload, OCR/importer, CPU/model fallback не добавлялись.
- Blocker register: `none`; `B-012-F-001` снят clean repeat, `live-r5` и независимым PASS.
