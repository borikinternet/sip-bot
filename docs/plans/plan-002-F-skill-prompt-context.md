# Plan-002-F: Skill & Prompt Manager, context и локальный RAG

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-03`  
Статус исполнения: `complete` — implementation, propagation и real embedding/RAG evidence закрыты `2026-09-03`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Создать application-owned контур, который принимает authoritative final user turn, сохраняет и извлекает текстовый
контекст разговора, ищет релевантные фрагменты в заранее подготовленной локальной базе знаний, выбирает разрешённый
skill/profile и собирает версионируемый typed `LlmRequest`. Результат обязан содержать source-aware `KnowledgeContext`;
ответ только из памяти модели без retrieval evidence не закрывает RAG-требование демонстрации.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Нужны локальная knowledge retrieval, контекст и ответ по естественным наукам | RAG — обязательный answer path, не optional enhancement | Source-aware demo fixture | Model-only answer выдаётся как RAG |
| [`architecture.md`](../architecture.md) | Context/KB Manager и Skill & Prompt Manager разделены от LLM Facade | Поиск и prompt policy остаются в приложении | Ownership audit | Ollama владеет corpus/prompt policy |
| [`technical-specification.md`](../technical-specification.md) | `/api/embed` — candidate, index/search app-owned, config constants | Runtime query проходит typed facade; corpus/index готовятся offline | Retrieval evidence | Direct Ollama call или скрытый index |
| [`ADR-001-llm-and-dialogue-manager.md`](../decisions/ADR-001-llm-and-dialogue-manager.md) | LLM предлагает, FSM исполняет | `LlmRequest` не даёт SIP access | Decision validation in G | Prompt manager не исполняет action |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `N8→N10a`, `N10→N10b→N11` и `B5/B6` типизированы | Context, hits, scores and sources propagate explicitly | Contract revision | Missing source/sufficiency fields |

## 3. Граница задачи

**Цель:** context store, curated corpus, chunk/index builder, local retrieval, skill/profile registry, prompt templates и
typed `LlmRequest` preparation.

**Входит:** text context file per call, corpus manifest and attribution, chunk metadata, offline embedding/index build,
runtime query embedding через `LLM Facade`, similarity/top-k/threshold, source IDs, unknown-answer decision input,
prompt version/profile and diagnostics.

**Не входит:** chat inference/HTTP transport (`002-G`), SIP/FSM action, audio, ASR, TTS, external vector database as a goal,
automatic web search, training/fine-tuning и аудиозапись.

**Protected baseline:** local curated Russian natural-science corpus, one conversation, no external runtime services,
RAG evidence separate from model pretraining, config in `config/constants.py`, source-aware context mandatory.

**Предположения:** `002-D` supplies final text; `002-E` supplies allowed skill/profile and state; `002-G` supplies typed
embedding/chat facade. GPU embedding probe is performed sequentially by the main executor.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Context store | `src/sip_bot/context/store.py` | Нет application state | Append-only turn/context snapshot file without audio | No runtime owner | Implement bounded snapshot lifecycle |
| Knowledge corpus | `docs/knowledge-base.md`, `data/knowledge/` | Source not yet formalized | Curated corpus manifest, license/attribution and chunks | Exact source set open | Create owner doc and fixtures |
| KnowledgeQueryBuilder | `src/sip_bot/retrieval/query_builder.py` | Нет query-preparation boundary | Deterministic normalized query, embedding text, lexical terms and phrases | No Russian text normalization policy | Implement and version the query policy |
| Retrieval index | `src/sip_bot/retrieval/`, `data/knowledge/index/` | No index | Compact reproducible local index | Embedding/index choice open | Build offline and query runtime |
| Skill/prompt | `src/sip_bot/prompt/` and `config/constants.py` | No application manager | Versioned templates/profiles and typed request | No schema implementation | Implement manager/validation |
| Tests | `tests/unit/test_context_retrieval_prompt.py`, `tests/contract/test_f_retrieval_prompt_contracts.py` | Отсутствуют | Context, retrieval and prompt tests | No fixtures | Create source-aware fixtures |
| Evidence | `artifacts/.../002-F/` | Отсутствует | Corpus/index/query/source trace | No RAG evidence | Create at execution |

Допустимый write-set: `src/sip_bot/context/`, `src/sip_bot/retrieval/`, `src/sip_bot/prompt/`, `config/constants.py`,
`docs/knowledge-base.md`, `data/knowledge/`, related unit/contract tests и own evidence root. Protected documents and
Ollama implementation are not edited here.

## 5. Interaction topology и propagation контрактов

`N8 → N10a` provides final user turn; `N9 → N10` provides state/turn lifecycle; `N10 → N10b` provides `KnowledgeQuery`;
`N10b → N11` requests embedding through the typed facade; `N11 → N10b` returns `EmbeddingResponse`; `N10b → N10a`
returns `KnowledgeContext`/`KnowledgeHit`; `N10 → N10a` supplies `ContextSnapshot`. Within the retrieval boundary,
`KnowledgeQueryBuilder` prepares the query deterministically: it keeps the full normalized question for semantic embedding
and produces lexical terms/phrases as explicit metadata. Prompt manager combines final text, context, source-aware hits
and FSM-approved profile into `LlmRequest`, but never calls Ollama directly.

### 5.1. Deterministic query preparation

The primary RAG query is not a list of extracted keywords. `KnowledgeQueryBuilder` produces two related representations:

1. `embedding_text`: the complete current final user turn, optionally prefixed with a bounded context window for resolving
   short follow-ups such as `«А на Марсе?»`. This is the input to `/api/embed` and retains the question's relations,
   negation and intent.
2. `lexical_terms` and `phrases`: an explainable diagnostic representation for traceability and possible explicitly
   approved hybrid ranking. It is not an automatic fallback when embedding fails.

The MVP deterministic pipeline is:

- rule-based tokenization and sentence handling with [`razdel`](https://github.com/natasha/razdel);
- Unicode normalization and case normalization without changing the authoritative user text;
- Russian lemmatization/morphological analysis with [`pymorphy3`](https://github.com/no-plagiarism/pymorphy3), subject to
  the project's no-GIL import/operation check;
- filtering only the versioned stop-word set of service words. Negations (`не`, `нет`, `без`), question qualifiers,
  numbers, units, chemical formulas, Latin scientific notation and unknown domain tokens are preserved by explicit rules;
- formation of short content n-grams/phrases from adjacent content tokens, with a maximum length fixed in configuration.

The analyzer never drops a token merely because it is absent from a general dictionary: curated-corpus vocabulary and
scientific notation are valid retrieval signals. The authoritative final user text remains intact and is passed separately
to `LlmRequest`; normalization is query metadata, not a silent rewrite of the user's words.

For a multi-turn query, the context window is bounded and versioned. The builder may include recent relevant turns or the
persisted context summary, but it does not make a second LLM call to rewrite the question in this plan. If the embedding
query cannot establish sufficient relevance, retrieval returns an explicit insufficient-context result and does not ask the
model to guess.

Offline index build is a separate lifecycle from runtime retrieval. Runtime retrieval records query, top-k, scores,
source IDs, threshold decision and index/model version. If relevance is insufficient, the result is an explicit
unknown-context outcome; prompt manager does not silently remove the context or ask the model to guess.

## 6. Audit владельца поведения и парадигмы реализации

Context store owns conversation persistence and revision; `KnowledgeQueryBuilder` owns deterministic text normalization,
lemmatization, stop-word/special-token policy, bounded context assembly and query representation versioning; retrieval owner
owns corpus/chunk/index/query/similarity and relevance; Skill & Prompt Manager owns skill/profile/template selection and
request composition. Embedding transport belongs to LLM Facade. Pure chunking/scoring functions may be stateless, but
decisions about threshold, source sufficiency or prompt policy remain on their owner objects.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Обязателен ли RAG в demo answer path? | Да; source-aware local context is required evidence | Model-only answer is a failed applicability claim | `resolved` |
| Какой corpus? | Небольшой curated-срез русскоязычной Википедии по естественным наукам с source/license/attribution в `knowledge-base.md` | Corpus считается RAG-baseline только при локальной индексации, runtime retrieval, source IDs и передаче контекста в prompt | `resolved: owner review accepted 2026-09-02` |
| Какой runtime retrieval baseline? | Ollama `/api/embed` через typed facade + компактный локальный индекс; exact model/index parameters фиксируются execution evidence | Vector DB не добавляется без необходимости; embedding failure не запускает lexical fallback автоматически | `resolved: owner review accepted 2026-09-02` |
| Что при insufficient relevance/embedding failure? | Insufficient relevance → unknown-answer/offer-transfer; embedding failure не получает автоматический lexical fallback и при фактическом trigger проходит APG gap/owner review | Failure is visible in evidence; заранее утверждённое отсутствие fallback не является открытым вопросом | `resolved: Map-002-I/technical-specification rule; review only if triggered` |
| Где prompt policy? | Versioned templates/profiles in `config/constants.py`, manager composes typed request | User text is inserted without silent semantic rewriting | `resolved` |
| Как выделять ключевые слова и строить RAG query? | Полный нормализованный вопрос используется для embedding; `razdel` + `pymorphy3` + versioned rules создают диагностические terms/phrases, сохраняя отрицания, числа, units, formulas и unknown scientific tokens | Keyword list не заменяет semantic query и не становится автоматическим fallback; policy и версия нормализации попадают в evidence | `resolved: owner review accepted 2026-09-03` |
| Нужен ли отдельный LLM query rewrite? | Нет для MVP; короткие follow-up queries получают bounded context window, а второй LLM-вызов не добавляется | Не увеличиваем latency и не вносим непроверяемую смысловую подмену; необходимость расширения проходит отдельный review | `resolved: owner review accepted 2026-09-03` |

## 8. Process invariant audit

- RAG is not equated with pretraining; every answer fixture carries source IDs and context trace.
- Corpus/index build and runtime query are separate, reproducible steps.
- The plan does not introduce a vector database for its own sake.
- No direct Ollama HTTP calls outside `002-G`; commands and model/index metadata are recorded.
- Query normalization is deterministic, versioned and separately tested; the authoritative final user text is never replaced
  by extracted keywords.
- `lexical_terms`/`phrases` are observable query metadata; embedding failure does not silently activate lexical retrieval.
- Any corpus/license/source change updates `knowledge-base.md`, registry and evidence.

## 9. Architecture invariant audit

- Final user text and large context payload use direct data-plane channels; Dispatcher sees only control events.
- `KnowledgeQueryBuilder` produces query metadata from final text plus bounded context; it does not own LLM inference or FSM
  decisions.
- `KnowledgeContext` must include source identifiers, scores and sufficiency decision.
- Insufficient context prevents a model-only authoritative answer.
- Prompt manager cannot emit SIP/transfer commands or change FSM.
- Context is persisted as text/state only; project does not record audio.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| F1 | Record corpus source/license and create deterministic chunks | Manifest, source IDs, chunk metadata and attribution reproduce | Source/license cannot support public demo |
| F2 | Implement deterministic `KnowledgeQueryBuilder` | Normalization, lemmatization, stop-word/special-token policy, bounded context query and terms/phrases fixtures pass | Query policy drops meaning-bearing tokens or rewrites authoritative text |
| F3 | Build local index using typed embedding operation | Offline index rebuild and version evidence pass | Embedding/index baseline not reproducible |
| F4 | Implement runtime query/top-k/threshold | Query returns source-aware hits or explicit insufficient result | Scores/source IDs missing |
| F5 | Implement context store and prompt/profile manager | Context continuation and versioned `LlmRequest` pass schema tests | User text silently changed or context over limit |
| F6 | Integrate with E/G deterministic stubs | Answer request contains final turn, source IDs, context and profile | Direct Ollama call or model-only path |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-F-001` | весь plan | Child plan не прошёл owner review | Context/RAG/prompt implementation | project owner | APG review | `resolved — owner review accepted 2026-09-03` |
| `B-002-F-002` | F1 | Corpus source/license/attribution не зафиксированы | Public RAG demo and report claim | project owner | `knowledge-base.md` + source evidence | `resolved — corpus manifest, source URLs, CC BY-SA 4.0 и attribution зафиксированы 2026-09-03` |
| `B-002-F-003` | F3–F4 | No reproducible embedding/index or source-aware retrieval | Answer path and M4-G3 | project owner | `002-G/real-provider-probe.json`, saved index, positive/negative runtime queries | `resolved — real embeddinggemma index/query evidence accepted 2026-09-03` |

## 12. Test plan и evidence

- corpus manifest, source links/license/attribution and stable chunk IDs;
- no-GIL/import/operation evidence for `razdel` and `pymorphy3`, plus deterministic query-policy fixtures;
- normalization, lemmatization, stop-word and special-token tests: negations, numbers, units, formulas, Latin scientific
  notation, unknown domain terms and multiword phrases;
- short follow-up query fixture proving bounded previous-turn context is included in `embedding_text` while authoritative
  final text remains unchanged;
- offline index build from clean corpus and recorded embedding model/index parameters;
- runtime query through `EmbeddingRequest`/`EmbeddingResponse`, top-k, scores, threshold and source IDs;
- positive natural-science question with source-aware context passed to LLM;
- negative question with insufficient hits producing unknown-answer path;
- context continuation across two turns and bounded snapshot persistence;
- prompt version/profile, exact user text and context trace in evidence;
- commands, stdout/stderr, exit codes, index checksum and latency measurements.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Compact local index without vector DB | Reduces MVP setup while retaining retrieval evidence | Must be reproducible, source-aware and score-bearing | F3/F4 | `approved scope boundary` |
| Lexical retrieval after embedding failure | Possible recovery path | Never automatic; extracted terms remain diagnostics unless hybrid ranking is explicitly approved | New plan/ADR if triggered | `deferred` |
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete; owner review accepted; deterministic implementation, main corrective pass, propagation и real
embedding/RAG evidence закрыты 2026-09-03`. В isolated scope выполнены F1/F2/F4/F5/F6 на deterministic backend;
target no-GIL `razdel`/`pymorphy3` path проверен с сохранением научных токенов. Затем через G facade выполнены real
index/query probes на `embeddinggemma`, включая positive source-aware и negative unknown path.

Принятый handoff передаёт `002-G` typed request requirements и embedding operation contract, `002-E` unknown/answer
control outcomes, `002-J` source trace и Map-I revision `7`. Real provider evidence находится в
`artifacts/implementation/002-mvp-media-and-speech-integration/002-G/real-provider-probe.json`; при ошибке provider
не вводился неутверждённый fallback.

`docs/knowledge-base.md` является source owner для corpus/license facts.
