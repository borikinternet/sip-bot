# Локальная база знаний MVP

Статус: `active workshop baseline`

Активный корпус: `small-service-company-demo-v1`

Regression-корпус: `ru-natural-science-demo-v1`

Назначение: обязательный source-aware RAG answer path и воспроизводимый мастер-класс по смене массива документов.

## Корпусы и лицензии

Активный workshop corpus находится в [`../config/workshops/rag/corpus/`](../config/workshops/rag/corpus/). Это
синтетический CC0-1.0 комплект документов условной компании «СервисПлюс»: услуги, график, цены и условия, процедура
заявки, исключения и эскалация. `manifest.json` задаёт стабильные `source_id`, origin, license, attribution, owner,
version, effective date, priority, topics и audiences. Персональных и коммерческих данных в корпусе нет.

Исходный science corpus сохранён в [`../data/knowledge/corpus/`](../data/knowledge/corpus/) как regression fixture. Он
содержит компактные фрагменты русскоязычной Википедии по рассеянию Рэлея, Марсу и воде под CC BY-SA 4.0 с URL и
атрибуцией в manifest. После активации workshop corpus его `wiki-*` источники не должны попадать в live answer path.

## Воспроизводимый lifecycle

Первый workflow принимает UTF-8 Markdown и versioned JSON manifest. `CorpusPackage` строго валидирует package, после
чего `CorpusNormalizer` и `CorpusChunker` детерминированно формируют semantic chunks со stable content-derived IDs.
PDF/DOCX/HTML/OCR в этот baseline не входят: такие документы заранее приводятся к Markdown.

Offline builder вызывает `embeddinggemma` только через typed `LLM Facade`, создаёт `rag-index-v1`, проверяет candidate
повторной загрузкой и публикует готовый файл атомарным `os.replace`. Неудачная сборка не изменяет предыдущий index.
Опубликованные artifacts:

- `data/knowledge/index/small-service-company-v1.json`: `12 × 768`, embedding model `embeddinggemma`, SHA-256
  `9a2e0937cf2bcf3a2533b4762410490c0e40420f64a29483cf2e487b56d2b579`;
- `data/knowledge/index/natural-science-v1.json`: `6 × 768`, regression/rollback artifact, SHA-256
  `1752266eae9fd351fea4a870ece36e3754ca96924e38d5604c88a88a4c1dd811`.

Runtime загружает уже построенный index и проверяет schema, index/corpus version, chunking policy, corpus hash,
embedding model, dimension, item count, payload checksum и vectors. На startup/call path весь corpus повторно не
векторизуется: readiness выполняет только один query embedding для warm query.

## Retrieval и контекст разговора

`KnowledgeQueryBuilder` сохраняет точный распознанный текст как authoritative payload, а для поиска создаёт
нормализованные леммы/термины. Контекст предыдущих ходов добавляется только для зависимых реплик: явной анафоры,
короткого conjunction-led follow-up и короткого эллиптического вопроса «сколько…?». Новый самостоятельный вопрос и
однословный ASR-фрагмент не наследуют старую тему автоматически.

`LocalKnowledgeIndex` выполняет cosine retrieval с ограниченным lexical rank boost; lexical signal не является
fallback без embeddings. Результат — typed `KnowledgeContext` с source/chunk IDs, scores, `top_k`, threshold и
`sufficient`. Immutable evaluation suite содержит 12 positive, paraphrase, contextual, conflict и negative cases;
активный baseline проходит `12/12`.

## RAG-инвариант

Ответ считается подтверждённым базой только при `KnowledgeContext.sufficient == true` и наличии переданных в
`LlmRequest` фрагментов с source IDs. Если relevance ниже порога, низкорелевантные hits остаются в диагностике, но не
подаются LLM как знания: prompt разрешает только `offer_transfer` и требует сообщить о недостатке знаний и спросить о
подключении оператора. Model-only ответ не считается успешным RAG-result.

## Воспроизведение

Полный процесс подготовки, проверки, активации, rollback и зарегистрированного SIP-звонка описан в
[`workshops/rag-corpus-onboarding-runbook.md`](workshops/rag-corpus-onboarding-runbook.md). Фактическое evidence Map-012
хранится в `artifacts/workshops/rag-corpus-onboarding/`; финальный accepted live run — `012-F/live-r5/`.

Compact JSON index и linear in-memory search достаточны только для текущего небольшого корпуса и одного бота. External
vector DB, hot reload во время звонка, incremental indexing, document ACL, multi-tenant corpus и автоматические
PDF/DOCX/OCR importers требуют отдельных карт и evidence.
