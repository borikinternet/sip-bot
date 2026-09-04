# 002-F closeout

Статус изолированного execution scope: `prepared and verified`; formal plan closeout остаётся `in_progress` до
main-only проверки реальной embedding-модели и последующей propagation в Map-002-I/002-G. Это не blocker отсутствия
Ollama/GPU для изолированной части F, а явно отложенный execution gate по заданной границе работ.

## Выполнено

- создан bounded append-only text-only `ContextStore` с `ContextSnapshot` и JSONL persistence;
- добавлен curated Russian natural-science corpus из трёх источников русскоязычной Википедии с `source_id`, URL,
  CC BY-SA 4.0 и attribution;
- добавлены deterministic chunks и pure-Python compact local index с cosine similarity и JSON serialization;
- добавлен typed `EmbeddingProvider` seam и `DeterministicEmbeddingBackend` только для fixture/evidence;
- реализован versioned `KnowledgeQueryBuilder`: полный вопрос для embedding, bounded context, diagnostic terms/phrases,
  сохранение отрицаний, чисел, units, formulas, scientific/unknown tokens; authoritative text не меняется;
- реализован `SkillPromptManager` с versioned skill/template/profile, delimiters, diagnostics и typed `LlmRequest`;
- обязательный RAG path enforced: source-aware context с hits/scores/source IDs/sufficiency; insufficient path —
  `unknown_answer` и `offer_transfer`, без model-only pass и без автоматического lexical fallback;
- user final text/RAG payload не публикуются в control Event Bus и не передаются через F как control events.

## Изменённые файлы

- `src/sip_bot/context/__init__.py`, `contracts.py`, `store.py`;
- `src/sip_bot/retrieval/__init__.py`, `contracts.py`, `index.py`, `query_builder.py`;
- `src/sip_bot/prompt/__init__.py`, `manager.py`;
- `config/constants.py` — только F query/index constants;
- `docs/knowledge-base.md`;
- `data/knowledge/corpus/manifest.json`, `physics-rayleigh.md`, `astronomy-mars.md`, `chemistry-water.md`;
- `tests/unit/test_context_retrieval_prompt.py`;
- `tests/contract/test_f_retrieval_prompt_contracts.py`;
- evidence files в этом каталоге.

## Evidence

- targeted F: `9 passed` (после main corrective pass для protected scientific tokens);
- host unit + contract regression: `73 passed`;
- compileall: exit `0`;
- host F imports: exit `0`;
- target `CPython 3.14.7t`: import and query operation exit `0`, `gil_enabled=false`;
- target optional capability path: `razdel=true`, `pymorphy3=true`; probe сохраняет `H2O` и `10^3`;
- deterministic fake index: 6 chunks, SHA-256 указан в `retrieval-fixture.json`;
- positive fixture возвращает `wiki-physics-rayleigh` с score `0.644514` и sufficient=true;
- negative fixture возвращает sufficient=false и `unknown_answer/offer_transfer`;
- no heavy GPU inference, Ollama model download/runtime probe или длительные embedding operations.

## Main acceptance/corrective pass

После приёма isolated результата main executor установил `razdel` и `pymorphy3` в target no-GIL runtime и обнаружил,
что обычное разбиение `razdel` дробит научные токены `H2O` и `10^3`. В `query_builder.py` добавлена защищённая ветка
для специальных токенов; authoritative text и остальные правила query policy не изменены. Target no-GIL operation probe,
targeted F tests и полный host unit/contract regression повторно прошли.

## Документальный audit

`python tools/check_task_backlog.py` завершился с exit `0`. `python tools/check_document_registry.py` после создания
`docs/knowledge-base.md` обнаружил `missing: knowledge-base.md` и завершился с exit `1`. Добавление строки в registry
не выполнено намеренно: текущий утверждённый F write-set разрешает `docs/knowledge-base.md`, но запрещает
`docs/document-registry.md`. Это передано main executor как обязательная синхронизация до formal closeout; кодовый F
scope от этого не блокируется.

## Следующий gate

Main executor должен через `002-G` подключить реальный typed embedding provider, выполнить offline index/query probe на
выбранной модели, зафиксировать model/index version и latency, затем выполнить propagation checkpoint в Map-002-I.
При ошибке provider не включать lexical fallback автоматически; действовать по уже принятому owner decision и APG gap
protocol.
