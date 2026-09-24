# План 012-I: typed boundary и lifecycle локального RAG

Уровень: `child plan / interaction map`  
Идентификатор: `012-I`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-I/`

## Цель и результат

Инвентаризировать фактические producer/consumer API существующего RAG, закрепить revision целевых типов и полный
offline/runtime lifecycle до изменения кода. Результат — authoritative I0–I5 propagation map без нового владельца
доставки и без передачи data-plane payload через Dispatcher/Event Bus.

## Материализованные правила

| Источник | Правило | Применение | Stop condition |
|---|---|---|---|
| Map-012 §7–10 | KB capability владеет corpus/index/search, LLM Facade — Ollama HTTP, readiness — load/warm | Все рёбра закрепляются за существующими owners | Нужен новый owner либо меняется protected answer path |
| `development-guidelines.md` §2–4 | Typed-first, direct receiver method, I0–I5 propagation | Raw JSON допустим только внутри persistence adapter | Не удаётся выразить границу typed contract |
| `technical-specification.md` | Offline corpus embedding, runtime query embedding, constants config | Build и runtime разделены | Corpus embedding остаётся в call/startup path |
| APG §5.7A | Producer, consumer, method, lifecycle, errors и cancellation фиксируются до integration | Эта карта является prerequisite для A–F | Не закрыт consumer contract |

## Граница и write-set

Входит read-only source audit и этот plan/evidence. Не входят production code, corpus, constants и live run.

Write-set: этот файл, `artifacts/workshops/rag-corpus-onboarding/012-I/closeout.md`, статусы Map-012/registry.
Protected: весь `src/`, `config/`, `data/knowledge/`, tests и historical artifacts.

## Фактический baseline и revision `rag-lifecycle-v1`

| Edge | Producer output | Consumer input method | Plane/lifecycle | Ошибка/cancel |
|---|---|---|---|---|
| Corpus package → ingestion | `Path` к UTF-8 Markdown + JSON manifest | `CorpusPackage.load(path)` (целевой owner-method) | offline, immutable build input | validation exception; publish запрещён |
| Ingestion → chunking | `CorpusSource` + normalized text | `CorpusChunker.chunk(source, text)` | offline/direct | document classified accepted/skipped/error |
| Chunking → embeddings | `CorpusChunk` | `EmbeddingProvider.embed(EmbeddingRequest)` | offline/direct, sequential MVP | provider error aborts candidate build |
| LLM Facade → index builder | `EmbeddingResponse` | `LocalKnowledgeIndex.add/build` | offline/direct | request/model/dimension mismatch aborts |
| Builder → persistence | completed `LocalKnowledgeIndex` + `IndexManifest` | `save_atomic(path)` | offline/crash-safe publish | old file preserved before `os.replace` |
| Index file → readiness | versioned JSON artifact | `LocalKnowledgeIndex.load(path, expected=...)` | process startup/readiness | corruption/mismatch keeps NOT_READY |
| Final turn → query builder | `FinalUserTurn.text` + context | `KnowledgeQueryBuilder.build(...)` | per turn/direct worker | no fallback on invalid query |
| Query → embedding | `EmbeddingRequest` | `LlmFacade.embed(...)` | per turn/direct HTTP | failure produces insufficient/unknown path |
| Query vector → search | `EmbeddingResponse.vector` | `LocalKnowledgeIndex.query(...)` | per turn/direct | dimension mismatch is explicit error |
| Search → prompt | `KnowledgeContext` | `SkillPromptManager.prepare_for_turn(...)` | per turn/direct | insufficient permits only offer-transfer |
| Knowledge → report | `KnowledgeContext` | `CallComposition.record_rag_context(...)` | per turn/direct | source IDs remain attributable |

Persistence JSON is an internal serialization boundary, not an application `dict` boundary. CLI invokes typed owner
methods and does not call Ollama directly. There is no backpressure queue: offline operations are sequential; runtime
query runs in the already existing inference worker. Cancellation applies to active chat/TTS operations, while a
completed immutable index snapshot lives for the process lifetime.

## I0–I5 propagation

1. `I0`: topology above and candidate contracts accepted by Map-012.
2. `I1`: A publishes authoritative `CorpusManifest/CorpusSource` validation contract.
3. `I2`: B consumes that contract and publishes deterministic `CorpusChunk` sequence plus ingestion report.
4. `I3`: C consumes chunks through `EmbeddingProvider.embed`, publishes `rag-index-v1` artifact/build report.
5. `I4`: D consumes the exact artifact revision in readiness and rechecks lifecycle/failure cycles.
6. `I5`: E/F may integrate only after D proves load/query and immutable snapshot semantics.

## Owner-review, blocker и fallback

Новых owner-review вопросов нет. Map-012 owner decisions являются authoritative.

| ID | Trigger | Status |
|---|---|---|
| `B-012-I-001` | Нужен новый owner, bus/queue либо protected answer-path semantics меняются | `none until triggered` |

External vector DB, direct Ollama from CLI, raw-dict application API, hot reload during call и lexical-only fallback
запрещены этим срезом.

## Test/evidence и closeout

Проверки: source grep фактических methods/types, consumer inventory, topology audit, protected-diff audit и registry.
Closeout обязан перечислить фактические symbols, revision `rag-lifecycle-v1`, найденные gaps и разрешение начала 012-A.

## Execution closeout — 2026-09-21

Source/consumer audit подтвердил существующих owners и все рёбра `rag-lifecycle-v1`. Production code не изменялся;
новый transport/delivery owner не требуется. Подтверждены gaps: отсутствуют strict package validation, production
index load, compatibility/checksum metadata, atomic publish, CLI и evaluation set; live readiness повторно строит
corpus embeddings. Полный evidence и handoff: [`012-I/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-I/closeout.md).
Открытых blocker нет; `012-A` разрешён.
