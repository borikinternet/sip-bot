# Локальная база знаний MVP

Статус: `active baseline`  
Версия корпуса: `ru-natural-science-demo-v1`  
Назначение: демонстрация обязательного source-aware RAG answer path.

## Состав и лицензия

Корпус — небольшой воспроизводимый срез русскоязычной Википедии по естественным наукам. Исходные материалы доступны
по лицензии CC BY-SA 4.0. В `data/knowledge/corpus/manifest.json` для каждого документа зафиксированы стабильный
`source_id`, название, URL, лицензия, атрибуция и локальный файл. Локальные файлы содержат компактные тематические
фрагменты для демонстрации; они не заменяют полные статьи и не являются утверждением о полноте базы знаний.

Источники:

- [Рассеяние Рэлея](https://ru.wikipedia.org/wiki/%D0%A0%D0%B0%D1%81%D1%81%D0%B5%D1%8F%D0%BD%D0%B8%D0%B5_%D0%A0%D1%8D%D0%BB%D0%B5%D1%8F), CC BY-SA 4.0.
- [Марс](https://ru.wikipedia.org/wiki/%D0%9C%D0%B0%D1%80%D1%81), CC BY-SA 4.0.
- [Вода](https://ru.wikipedia.org/wiki/%D0%92%D0%BE%D0%B4%D0%B0), CC BY-SA 4.0.

## Воспроизводимый lifecycle

`load_corpus()` читает manifest и разбивает каждый локальный файл по пустым строкам. Идентификатор фрагмента имеет
форму `<source_id>-<ordinal>`. Offline builder передаёт каждый `CorpusChunk` в typed `EmbeddingProvider`, а
`LocalKnowledgeIndex` сохраняет компактный JSON с версиями, chunk metadata и векторами. Runtime query отдельно
векторизует `KnowledgeQuery.embedding_text`, считает cosine similarity, сортирует по score/chunk ID и возвращает
`KnowledgeContext` с `source_ids`, hits, scores, `top_k`, threshold и `sufficient`.

В F deterministic evidence используется только `DeterministicEmbeddingBackend` (fake character-ngram backend), чтобы
не скачивать и не запускать модель. Это не production semantic embedding и не lexical fallback. Реальный Ollama
`/api/embed` adapter и GPU/model probe принадлежат `002-G`/main executor. При ошибке embedding исключение не
подменяется лексическим поиском.

## RAG-инвариант

Ответ считается подтверждённым базой только если `KnowledgeContext.sufficient == true` и в запросе LLM присутствуют
исходные фрагменты, `source_id` и score. При недостаточной релевантности менеджер формирует `unknown_answer` с
разрешённым действием `offer_transfer`; model-only ответ не считается успешным RAG-result.
