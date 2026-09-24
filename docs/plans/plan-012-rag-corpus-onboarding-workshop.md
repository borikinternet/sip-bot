# Карта 012: воспроизводимая смена корпуса и RAG-мастер-класс

Уровень: `map`  
Идентификатор: `Map-012`  
Статус: `complete 2026-09-21 — 012-I/012-A–012-F complete, map-level gates closed`  
Дата: `2026-09-21`

## 1. Цель и проверяемый результат

Превратить текущий технический RAG-прототип в воспроизводимый пользовательский процесс настройки SIP-ассистента на
другой массив документов и подготовить по этому процессу отдельный практический мастер-класс.

Проверяемый итог карты:

1. участник подготавливает новый локальный корпус по документированным правилам и получает понятный отчёт об ошибках;
2. одной опубликованной CLI-командой выполняются deterministic chunking, embeddings через существующий typed
   `LLM Facade`/Ollama и построение проверяемого локального индекса;
3. незавершённая или ошибочная сборка не повреждает предыдущий индекс, а готовый индекс публикуется атомарно;
4. application runtime загружает уже построенный индекс, проверяет schema/model/dimension/version/checksums и не
   векторизует весь корпус на критическом пути запуска или звонка;
5. положительные, отрицательные и контекстные контрольные вопросы дают ожидаемые source-aware результаты;
6. на существующем FreeSWITCH/SIP-стенде бот отвечает по новому корпусу, не отвечает по старой базе как будто она
   активна, корректно выполняет unknown-answer/offer-transfer и сохраняет источники в `report.md`;
7. опубликован self-contained runbook для исполнителя без контекста переписки и выполнен чистый повтор по нему.

Это не обучение и не fine-tuning Qwen. Веса генеративной LLM не меняются: меняются подготовленный корпус, его индекс,
retrieval-настройки и прикладной prompt/skill package.

## 2. Почему это карта, а не один срез

Работа содержит независимые acceptance boundaries: формат корпуса и его проверка, извлечение/деление текста, offline
embedding/index build, сериализация и атомарная публикация, runtime load/readiness, retrieval evaluation и полный
workshop/live scenario. Она также затрагивает несколько существующих владельцев поведения и typed edges:

```text
Corpus package
    → Context/KB Manager: validation/chunking
    → LLM Facade: embedding operation
    → LocalKnowledgeIndex: build/save/load/query
    → RuntimeReadinessCoordinator: load/warm/ready
    → SkillPromptManager: KnowledgeContext → LlmRequest
    → ConversationPipeline: source-aware answer/unknown-answer
```

По APG §0.4, §3 и §5.7C такой scope обязан быть разложен на отдельную interaction map и узкие child plans. Создание
этого файла не разрешает начинать кодирование до owner review карты, подготовки self-contained child plan-файлов и
прохождения их применимого APG.

## 3. Применимые документы и материализованные правила

| Источник | Материализованное правило | Влияние на Map-012 | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | Предметные знания подключаются через локальные документы и retrieval/RAG, а не переобучение LLM; ответ должен учитывать локальную базу | Новый corpus workflow не изменяет веса Qwen и остаётся локальным | Positive/negative/source-aware evaluation и live call | Model-only ответ выдан за подтверждённый RAG-ответ |
| [`architecture.md`](../architecture.md) §3.2–3.4 | `Context/KB Manager` владеет корпусом, chunking, metadata, индексом и поиском; `LLM Facade` владеет Ollama HTTP; `Skill & Prompt Manager` только собирает `LlmRequest`; индексация выполняется до звонка | Владение не смешивается; runtime не строит полный индекс в call path | Source/owner audit и `012-I` propagation map | Новый компонент дублирует существующего owner либо документы/векторы идут через Dispatcher/Event Bus |
| [`technical-specification.md`](../technical-specification.md) §2.4, §3 | Допустим компактный application-owned index без Chroma/Qdrant/FAISS; во время звонка создаётся только query embedding; пути и параметры живут в `config/constants.py` | Сохраняется локальный index backend и constants-based activation; external vector DB не вводится | Config, request-count и readiness tests | Startup/call повторно embedding-ит corpus или появляется второй источник конфигурации |
| [`knowledge-base.md`](../knowledge-base.md) | Corpus manifest, source IDs, лицензия, chunk IDs и source-aware result являются обязательными | Новый формат расширяет, но не теряет provenance и attribution | Corpus/index manifest audit | Нельзя восстановить источник любого hit |
| [`development-guidelines.md`](../development-guidelines.md) §1–§9 | Узкие slices, typed-first, owner behavior, iterative propagation, no silent fallback, target no-GIL, corrective pass, binary closeout и проверка работы субагента обязательны | Сначала `012-I`, затем contract propagation; каждый code/evidence slice получает свой plan и closeout | Child APG, diff/test/evidence audit | Молчаливое расширение scope, новый fallback или частичный child closeout |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) §0–§6 | Карта имеет child graph, source-map, owner review, blocker/fallback registers, test/evidence plan и map-level closeout | Этот файл остаётся planning-only до review; executable work идёт только через child plans | APG structural audit | Не согласован состав карты или отсутствует self-contained child plan |
| [`documentation-process.md`](../documentation-process.md) | Один факт имеет одного владельца; после Markdown-изменений проверяется registry, после backlog — task registry | Технический lifecycle корпуса принадлежит `knowledge-base.md`/ТЗ, инструкция — workshop runbook, статусы — roadmap/backlog/registry | `check_document_registry.py`, `check_task_backlog.py` | Дублирующиеся owner-описания или красный registry audit |
| [`licensing-policy.md`](../licensing-policy.md) | Публичный corpus и производные материалы должны иметь понятные права, attribution и ограничения распространения | Corpus validator требует source/license/attribution; workshop использует синтетические либо разрешённые документы | Manifest/licensing audit | В публикуемый corpus попал материал без зафиксированного основания использования |
| [`roadmap.md`](../roadmap.md) §13–§14 | Закрытый demo baseline не переоткрывается без причины; конференционные workshop tracks планируются отдельно | Map-012 — отдельный workshop track; SIP/media/ASR/TTS/FSM baseline меняется только при concrete gap | Protected-baseline diff audit | RAG-задача превращается в несогласованный рефакторинг закрытых speech/media plans |
| [`artifacts/report-preparation-20260904/talk-outline.md`](../../artifacts/report-preparation-20260904/talk-outline.md) §3 | Мастер-класс показывает систематизацию документов, chunking, embeddings, retrieval/metadata, prompt/skills и проверку в звонке | Содержание мастер-класса превращается в исполнимый runbook и live acceptance | `012-F` clean repeat и context-free review | Runbook показывает только готовый индекс, но не его подготовку и проверку |

## 4. Граница задачи

```text
Цель:
  Воспроизводимое onboarding нового массива документов в локальный RAG и проверенный мастер-класс.

Входит:
  versioned corpus manifest и правила систематизации документов;
  deterministic validation, normalization и semantic chunking для согласованных входных форматов;
  source/license/owner/version/effective-date/priority/topic/audience metadata;
  offline embeddings через существующий LLM Facade/Ollama boundary;
  локальный сериализованный index, load/validation и атомарная публикация;
  constants-based выбор corpus/index, startup readiness без corpus re-embedding;
  positive/negative/contextual evaluation set и retrieval diagnostics;
  prompt/skill настройка, source-aware live SIP answer и unknown-answer/transfer;
  workshop assets, evidence и self-contained runbook.

Не входит:
  fine-tuning/обучение Qwen, ASR или TTS;
  crawler полной Википедии, OCR и обработка сканов;
  production document-management system, ACL enforcement, multi-tenant knowledge bases;
  distributed vector database, кластеризация, HA, online incremental indexing;
  незаметная hot-reload замена знаний посреди активного звонка;
  изменение SIP/RTP, ASR, VAD, TTS, Dialogue FSM или transfer semantics без concrete APG gap;
  публикация реальных конфиденциальных документов компании.

Protected baseline:
  один активный звонок; локальные модели; существующий FinalUserTurn → retrieval → SkillPromptManager → LLM Facade path;
  source-aware KnowledgeContext и unknown-answer/offer-transfer;
  Ollama HTTP доступен только через LLM Facade;
  Dispatcher/Event Bus остаются control-only;
  конфигурация приложения хранится в config/constants.py;
  закрытые Map-002/005/007–010 и Map-011 не переписываются как будто они не были исполнены.

Предположения о рабочем дереве:
  Рабочее дерево содержит незакоммиченные результаты прежних карт. Исполнитель сохраняет unrelated changes,
  использует только write-set текущего child plan и не перезаписывает historical artifacts.

Зависимости и внешние сервисы:
  локальный Ollama и текущие embedding/chat models;
  target free-threaded CPython в Ubuntu 24.04/WSL2;
  существующий FreeSWITCH workshop stand и optional SIP registration baseline;
  перед heavy model/index/live gates требуется не менее 20 GiB свободного места на Windows и Linux volumes.
```

## 5. Текущее состояние и обнаруженный gap

Текущий baseline уже доказывает semantic retrieval, source IDs и unknown-answer, но не является пользовательским
onboarding workflow:

- [`data/knowledge/corpus/`](../../data/knowledge/corpus/) содержит три вручную подготовленных Markdown-файла и шесть
  chunks; manifest задаёт источник и лицензию;
- [`LocalKnowledgeIndex.build()`](../../src/sip_bot/retrieval/index.py) по одному вызывает typed embedding provider,
  хранит vectors/chunks в памяти и умеет `save()` в JSON;
- [`data/knowledge/index/embeddinggemma-v1.json`](../../data/knowledge/index/embeddinggemma-v1.json) — сохранённый
  evidence index, но у `LocalKnowledgeIndex` отсутствует production/workshop `load()`;
- live runners заново строят весь corpus index в readiness warmup; это противоречит целевому правилу «индексация заранее»
  для нового, неигрушечного массива документов;
- отдельной CLI-команды build/validate нет; failed build, model/dimension mismatch и atomic publication не оформлены;
- нет machine-readable набора контрольных вопросов с ожидаемыми sources и отдельного workshop runbook.

Map-012 устраняет именно этот gap. Она не заменяет работающий retrieval другим продуктом и не меняет LLM candidate.

## 6. Source-map и будущий write-set

| Область | Файл/компонент | Текущее поведение | Целевое поведение | Владелец/child |
|---|---|---|---|---|
| Typed contracts | `src/sip_bot/retrieval/contracts.py` | Source/chunk/hit/context содержат минимальные поля | Versioned corpus/index metadata и совместимые source-aware hits без raw dict boundary | `012-I`, `012-A` |
| Query/index | `src/sip_bot/retrieval/query_builder.py`, `index.py` | Query normalization, linear cosine, JSON save; load отсутствует | Согласованные typed inputs, deterministic build/save/load/query, schema/model/dimension checks | `012-I`, `012-C`, `012-D` |
| Corpus | `data/knowledge/corpus/**`, новый workshop corpus root | Один вручную подготовленный science corpus | Два независимо выбираемых corpus packages: regression baseline и синтетический small-company workshop corpus | `012-A`, `012-B` |
| Offline tooling | новый `tools/knowledge/**` либо согласованный единый CLI | Отсутствует | Validate → normalize/chunk → embed → verify → atomic publish; machine-readable report | `012-B`, `012-C` |
| Ollama boundary | `src/sip_bot/llm/facade.py`, `ollama_client.py` | Typed single-text embedding operation | Сохраняется единственный HTTP owner; batch добавляется только если `012-I` докажет необходимость и контракт | `012-I`, `012-C` |
| Runtime config | `config/constants.py`, `src/sip_bot/config.py` | Corpus/index paths существуют, но saved index не является runtime source | Однозначный active corpus/index file, versions и validation policy; только один config source | `012-D` |
| Readiness | `src/sip_bot/runtime_readiness.py`, runtime composition | Warmup строит index заново | Загружает и проверяет готовый index; warmup выполняет query embedding/retrieval, но не corpus embedding | `012-D` |
| Answer path | `src/sip_bot/conversation_pipeline.py`, `prompt/manager.py` | Рабочий source-aware answer path | Использует неизменный KnowledgeContext contract либо явно propagated revision; old-corpus leakage test | `012-I`, `012-D`, `012-E` |
| Evaluation | новый corpus/evaluation fixture и tests | Два ad-hoc вопроса в gates | Versioned positive/negative/contextual cases с expected source IDs и метриками | `012-E` |
| Workshop | новый `docs/workshops/rag-corpus-onboarding-runbook.md`, `config/workshops/rag/**` | Нет инструкции смены базы | Clean-start инструкция и синтетический corpus; live call через существующий FreeSWITCH | `012-F` |
| Evidence | `artifacts/workshops/rag-corpus-onboarding/012-*` | Нет | Build/load/evaluation/live logs, manifests, checksums, commands, exit codes и closeout | все child plans |
| Owner docs | `knowledge-base.md`, `technical-specification.md`, `architecture.md`, `user-guide.md` | Описан технический baseline | После evidence отражён фактический lifecycle; planning claims не выдаются за реализованные | `012-D`–`012-F` |

До создания child plans общий map write-set ограничен этим plan-file, `roadmap.md`, `task-backlog.md` и
`document-registry.md`. Точные code/test/data write-set задаются отдельно и не могут быть расширены субагентом.

## 7. Interaction topology и propagation

### 7.1. Offline build plane

```text
Corpus files + CorpusManifest
        │ validate/normalize
        ▼
Context/KB Manager ingestion input
        │ typed CorpusSource / CorpusChunk
        ▼
KnowledgeIndexBuilder
        │ EmbeddingRequest (или owner-reviewed batch contract)
        ▼
LLM Facade.embed(...) ──HTTP──> Ollama /api/embed
        │ EmbeddingResponse
        ▼
LocalKnowledgeIndex candidate
        │ validate + serialize + checksum
        ▼
temporary sibling artifact ──os.replace/atomic publish──> configured index file
        │
        └── BuildReport: accepted/skipped/error documents, chunks, model, dimension, hashes, timings
```

CLI является входным adapter к существующему `Context/KB Manager`, а не новым владельцем corpus/index semantics.
Ни CLI, ни builder не обращаются к Ollama напрямую в обход `LLM Facade`.

### 7.2. Runtime query plane

```text
Application bootstrap
    → RuntimeReadinessCoordinator
    → LocalKnowledgeIndex.load(configured_path)
    → schema/model/dimension/hash validation
    → one warm query embedding + retrieval
    → READY

FinalUserTurn
    → KnowledgeQueryBuilder.build(text, dialogue_context)
    → LLM Facade.embed(query)
    → LocalKnowledgeIndex.query(...)
    → KnowledgeContext
    → SkillPromptManager.prepare_for_turn(...)
    → LlmRequest
    → LLM Facade.start_chat(...)
```

`KnowledgeContext` передаётся напрямую как data-plane payload. Dispatcher/Event Bus получает только существующие
управляющие события и structured decision; chunks/vectors/prompt через него не проходят.

### 7.3. Failure и activation semantics

- build пишет только временный sibling artifact; publish разрешён после полной самопроверки;
- parse/embed/validation failure оставляет предыдущий index без изменений;
- runtime не принимает повреждённый, неполный или несовместимый index и остаётся `NOT_READY`;
- замена active index выполняется вне активного звонка и вступает в силу после restart/reload readiness; незаметное
  изменение knowledge snapshot посреди turn/call в scope карты не входит;
- текущий science corpus остаётся regression fixture и не смешивается с workshop corpus в одном индексе.

`012-I` обязан инвентаризировать фактические методы и типы, присвоить boundary revision и определить I1–I5 propagation
до начала code integration. Candidate names этой карты не считаются final API.

## 8. Audit владельцев поведения

| Поведение | Владелец | Обоснование и запрет дублирования |
|---|---|---|
| Corpus validation, normalization, chunking, source metadata | `Context/KB Manager` capability | Он уже владеет corpus/index/search по архитектуре; CLI только вызывает его typed input |
| Embedding HTTP transport/model call | `LLM Facade` | Только фасад знает Ollama IPC; direct `urllib`/`requests` из builder запрещены |
| Index storage, compatibility и similarity search | `LocalKnowledgeIndex`/KB capability | Хранит vectors/chunks и query invariants; readiness не реализует второй loader/search |
| Atomic filesystem publication | Index persistence method или scoped index writer внутри KB capability | Это lifecycle index artifact, не универсальный delivery component |
| Runtime readiness | `RuntimeReadinessCoordinator` | Координирует load/warm/result, но не владеет chunking и retrieval policy |
| Prompt composition и allowed actions | `SkillPromptManager` | Получает готовый `KnowledgeContext`; не выполняет vector search |
| Call state и transfer | Existing Dispatcher/Dialogue FSM | Map-012 не переносит решение о SIP-action в RAG/LLM |
| Workshop orchestration | Runbook/tooling adapter | Не становится production runtime owner и не скрывает ручные/GUI этапы |

Новый orchestration/service допускается только после `012-I`, если у него будет самостоятельный state/lifecycle.
Процедурное связывание существующих typed методов само по себе не оправдывает новый компонент.

## 9. Process invariant audit

| Инвариант | Применение | Проверка/evidence |
|---|---|---|
| Узкий slice и контролируемый write-set | Один child plan закрывает одну acceptance boundary; закрытые SIP/media/speech планы не становятся общим write-set | APG source-map каждого child, `git diff --name-only`, closeout changed-files list |
| Typed-first и iterative propagation | `012-I` фиксирует фактические types/methods; следующий child начинает integration только после предыдущего checkpoint | Boundary revision, contract fixtures/tests и I1–I5 handoff |
| Делегирование не заменяет main executor | Субагент получает self-contained plan, не принимает architecture/model/backend decisions и не запускает общую GPU без явного разрешения | Handoff audit, повтор команд главным executor |
| Красный результат требует classification/corrective pass | Implementation/test error исправляется в scope; только доказанная category 3/4 создаёт blocker | Raw output, corrective command и повтор targeted/regression/contract tests |
| Никакого молчаливого упрощения | Нельзя пропускать документ, подменять semantic retrieval lexical search, отвечать из pretraining или ослаблять expected sources | Negative/corruption/failure tests и fallback register |
| Binary child closeout | `accepted` не означает `complete`; каждый child заканчивается только полным evidence либо concrete blocker | Child closeout и map gate audit |
| Документальная синхронизация последовательна | Общие owner docs, registry/backlog/roadmap меняет главный executor после проверки результата | Registry/backlog tools и фактический owner-doc diff |

## 10. Architecture invariant audit

| Инвариант | Затронутая граница | Проверка/evidence |
|---|---|---|
| Corpus/index/search принадлежат Context/KB Manager | Offline ingestion/build и runtime retrieval | Owner audit, отсутствие второго search/index owner |
| Ollama HTTP принадлежит LLM Facade | Document/query embeddings и chat | Network-call source audit и fake/real provider contract tests |
| Индексация происходит до звонка | Readiness/runtime | Corpus embedding request count `0` на startup/call; prebuilt load и one warm query trace |
| Один call использует immutable knowledge snapshot | Activation/runtime lifecycle | Activation запрещена при active call; old/new corpus isolation test |
| KnowledgeContext остаётся source-aware | Retrieval → prompt | Hits имеют source/chunk IDs и scores; report/LLM request trace восстанавливает источник |
| Insufficient knowledge не становится model-only answer | Retrieval/prompt/FSM | Negative query допускает только unknown-answer/offer-transfer path |
| Data plane не проходит через Dispatcher/Event Bus | Chunks, vectors, KnowledgeContext, LlmRequest | Topology/source audit и control-bus rejection regression |
| Конфигурация имеет один источник | Corpus/index/model/top-k/threshold paths | Constants/config projection tests; CLI не создаёт скрытый runtime default |
| Readiness не принимает частичную готовность | Index load/warm и incoming answer | Corrupt/mismatch/provider-failure оставляют `NOT_READY` и не разрешают `200 OK` |
| Compact local index не выдаётся за production vector store | Persistence/search | Scope/runbook честно фиксируют linear local backend и scale limitation |

## 11. Owner-review вопросы

| ID | Вопрос | Рекомендация карты | Последствие | Статус |
|---|---|---|---|---|
| `OR-012-001` | Какие исходные форматы обязан принимать первый workshop workflow? | Обязательный формат — UTF-8 Markdown + versioned JSON manifest. PDF/DOCX/HTML сначала вручную приводятся к этому normalized package; OCR не входит | Даёт прозрачный и повторяемый мастер-класс без скрытого качества parser/OCR | `resolved by owner acceptance 2026-09-21` |
| `OR-012-002` | Нужна ли внешняя vector DB? | Нет. Сохранить application-owned compact index и exact cosine retrieval; Chroma/FAISS/Qdrant показать как варианты масштабирования, но не включать в executable scope | Нет нового service/native dependency; текущий typed retrieval остаётся baseline | `resolved by technical-specification unless owner changes scope` |
| `OR-012-003` | Что означает атомарная замена индекса? | Crash-safe publish готового файла и activation только вне активного звонка через restart/readiness. Hot reload во время call не реализовывать | Один call использует один immutable knowledge snapshot; нет нового control protocol | `resolved by owner acceptance 2026-09-21` |
| `OR-012-004` | Какой новый corpus использовать в мастер-классе? | Синтетический комплект документов абстрактной небольшой сервисной компании без персональных/коммерческих данных; включить услуги, расписание, цены/условия, процедуру заявки, исключения и escalation contacts | Позволяет показать metadata, противоречие/приоритет, positive/negative/follow-up и transfer | `resolved by owner acceptance 2026-09-21` |
| `OR-012-005` | Меняем ли embedding/chat model в этой карте? | Нет: `embeddinggemma` и текущий Qwen/Ollama baseline сохраняются; model comparison — отдельная карта | Результат измеряет corpus workflow, а не одновременно смену моделей | `resolved by protected baseline` |

Открытых owner-review вопросов на момент начала execution нет. Новое противоречащее evidence обрабатывается только по
APG gap protocol; уже принятые решения повторно не запрашиваются.

## 12. Дочерние планы и порядок исполнения

| Порядок | Child plan | Scope и acceptance boundary | Зависимость | Evidence root | Review status |
|---:|---|---|---|---|---|
| 1 | `plan-012-I-rag-lifecycle-boundary-map.md` | Фактические producer/consumer types и input methods; offline/runtime topology, compatibility, failure, activation и I1–I5 propagation revision | Map-012 review | `artifacts/workshops/rag-corpus-onboarding/012-I/` | `complete 2026-09-21` |
| 2 | `plan-012-A-corpus-package-contract.md` | Manifest/schema, source metadata, synthetic workshop corpus, validator и licensing checks | `012-I`; `OR-012-001/004` | `.../012-A/` | `complete 2026-09-21` |
| 3 | `plan-012-B-document-normalization-chunking.md` | Deterministic Markdown ingestion, normalization, semantic chunking, stable IDs и accepted/skipped/error report | `012-A` propagated contracts | `.../012-B/` | `complete 2026-09-21` |
| 4 | `plan-012-C-offline-index-build-publication.md` | CLI, typed embeddings, build manifest, serialization, self-check, failure preservation и atomic publish | `012-B`; actual embedding boundary from `012-I` | `.../012-C/` | `complete 2026-09-21` |
| 5 | `plan-012-D-index-load-runtime-readiness.md` | `load()`, compatibility validation, config, readiness without corpus re-embedding и source-aware runtime query | `012-C` artifact revision | `.../012-D/` | `complete 2026-09-21` |
| 6 | `plan-012-E-rag-evaluation-and-tuning.md` | Versioned questions, expected sources, positive/negative/contextual metrics, threshold/top-k/chunking evidence и latency breakdown | `012-D` | `.../012-E/` | `complete 2026-09-21` |
| 7 | `plan-012-F-workshop-runbook-and-live-gate.md` | Clean corpus replacement, build/load/warmup, FreeSWITCH live call, report/source IDs, clean repeat и context-free runbook review | `012-A`–`012-E`; Map-009/011 baselines | `.../012-F/` | `complete 2026-09-21` |

Порядок contract-authoritative execution — строго `012-I → 012-A → 012-B → 012-C → 012-D → 012-E → 012-F`.
После propagation checkpoint разрешена параллельная подготовка fixtures, документации и deterministic tests только при
непересекающихся write-set. Общие contracts, constants, corpus/index files, owner docs, registry/backlog и GPU/Ollama
resources изменяются/используются последовательно главным executor.

Красный evaluation/live результат возвращается не в универсальный «исправляющий» компонент, а владельцу фактического
дефекта, после чего повторяются все зависимые gates:

```text
012-I → 012-A → 012-B → 012-C → 012-D → 012-E → 012-F
                    ↑         ↑         ↑       │       │
                    └─────────┴─────────┴───────┘       │
                         corrective propagation          │
                    ←──────── live corrective ───────────┘
```

Изменение chunking возвращает execution в `012-B`, формата/build/persistence — в `012-C`, load/readiness/config — в
`012-D`; затем повторяются все downstream contract, evaluation и live gates. Scope такого corrective pass остаётся в
write-set исходного owner plan. Выход за него обрабатывается APG gap protocol.

## 13. Implementation slices и правила делегирования

Каждый child plan до execution получает собственные scope, write-set, protected files, target runtime, blocker
register, commands, tests, evidence и binary closeout. Материализуются следующие правила:

- субагент может реализовывать согласованный deterministic slice только внутри disjoint write-set;
- субагент не выбирает новый vector store, parser, model, metadata schema или fallback;
- shared contracts сначала меняет один owner plan и публикует propagation checkpoint;
- package-manager lock не является немедленным blocker; выполняется повтор после случайной задержки;
- real Ollama embeddings, общая GPU, final live call и clean-start acceptance исполняются главным executor;
- отчёт субагента не закрывает child plan: главный executor проверяет diff, команды, exit codes и evidence;
- красный тест внутри write-set проходит classification/corrective retry; blocker возникает только при доказанной
  категории 3/4;
- child plan закрывается только `complete` либо concrete `blocked`; partial/foundation closeout запрещён.

## 14. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец | Evidence/условие снятия | Статус |
|---|---|---|---|---|---|---|
| `B-012-MAP-001` | map gate | Карта, child graph или open owner-review решения не согласованы | Любой code execution | project owner | Owner review этого файла и ответы `OR-012-001/003/004` | `resolved 2026-09-21 by explicit execution instruction` |
| `B-012-I-001` | `012-I` | Фактический output/input contract требует изменения protected answer-path semantics или нового owner | Все зависимые child plans | project owner | Source audit, proposed revision и APG gap | `none until triggered` |
| `B-012-A-001` | `012-A` | Нельзя однозначно проверить source/license/version/priority либо corpus содержит конфликт без правила разрешения | Build и workshop claims | corpus owner/project owner | Validation report и исправленный manifest | `none until triggered` |
| `B-012-B-001` | `012-B` | Chunking недетерминирован, stable ID меняется без изменения содержания либо документ теряется без явной ошибки | Offline build и все downstream gates | Context/KB owner | Repeatable chunk manifest/hash, ingestion report и corrective pass | `none until triggered` |
| `B-012-C-001` | `012-C` | Build обращается к Ollama в обход Facade, не сохраняет предыдущий index при failure или artifact нельзя воспроизвести | Offline index acceptance | project owner | Target build/corruption/failure tests и hashes | `none until triggered` |
| `B-012-D-001` | `012-D` | Runtime продолжает corpus re-embedding, принимает incompatible index или способен отправить `200 OK` до успешного load/warm query | Runtime/live gate | project owner | Request-count, readiness и incoming-call tests | `none until triggered` |
| `B-012-E-001` | `012-E` | Evaluation tuning достигается удалением неудобных вопросов, ослаблением expected sources или model-only fallback | Quality acceptance | project owner | Immutable question-set hash, raw results и corrective pass | `none until triggered` |
| `B-012-F-001` | `012-F` | Исполнитель без контекста не может повторить build/activation/live scenario обычными опубликованными шагами | Map closeout | project owner | Context-free review, clean repeat и live artifacts | `resolved 2026-09-21 by corrected runbook, live-r5 and independent PASS` |

## 15. Test plan и evidence

### 15.1. Deterministic/unit

- manifest schema: обязательные поля, stable IDs, duplicate/conflict/path traversal, encoding и empty-document cases;
- deterministic chunk IDs/content/order при повторной сборке;
- accepted/skipped/error classification без молчаливой потери документа;
- save/load round-trip, corrupted/truncated file, model/dimension/schema mismatch;
- atomic publish: injected failure до publish оставляет старый SHA-256 и readable index;
- query result и tie ordering воспроизводимы.

### 15.2. Contract/integration

- exact typed edges из `012-I`, без raw dict на application boundaries;
- `LLM Facade` — единственный owner `/api/embed`; fake provider и real Ollama дают согласованную dimension/model metadata;
- runtime startup/load выполняет ноль corpus embedding requests; warm query выполняет только предусмотренный query path;
- `KnowledgeContext` содержит source IDs/chunk IDs/scores и корректный `sufficient`;
- insufficient/corrupt/provider-failure path не превращается в model-only answer.

### 15.3. Evaluation

- положительные вопросы по каждому типу документа с expected source IDs;
- вопросы с формулировками, отличными от текста документа;
- follow-up, использующий историю разговора;
- отрицательные и пограничные вопросы;
- конфликтующие/устаревшие документы согласно metadata priority/effective policy;
- фиксируются retrieval latency, top-k, scores, source recall/hit и false-sufficient/false-unknown observations;
- threshold/top-k/chunking меняются только по полному immutable набору, а не по одному удобному вопросу.

### 15.4. Target runtime и live

- последний стабильный free-threaded CPython `>=3.14` в Ubuntu 24.04/WSL2; GIL проверяется до/после imports и operation;
- local Ollama/embeddinggemma build и query evidence, model digest/dimension и disk/GPU observations;
- clean application start с готовым index, readiness trace и отсутствие corpus rebuild;
- registered SIP call через существующий FreeSWITCH: positive, follow-up, negative/offer-transfer, подтверждение transfer,
  `report.md` с source IDs;
- контрольный вопрос из старого science corpus не получает source-aware answer после активации workshop corpus;
- clean repeat и независимый review runbook агентом без истории.

Каждый executable child сохраняет exact command, cwd, runtime, versions, stdout/stderr, exit code, hashes и artifact
paths. Heavy GPU/Ollama и финальный live gate выполняются последовательно главным executor.

## 16. Fallback/deferred register

| Возможность | Решение в Map-012 | Причина/граница | Condition promotion | Статус |
|---|---|---|---|---|
| External vector DB: Chroma/FAISS/Qdrant | Не вводить | Compact local corpus и один bot не требуют отдельного service/native dependency | Отдельная карта при доказанном размере/latency gap | `deferred; owner review may change` |
| PDF/DOCX/HTML import | Нормализовать в Markdown до build | Parser quality не должна скрывать тему систематизации и RAG; решение зависит от `OR-012-001` | Отдельный importer child plan после формата/evidence corpus | `proposed deferred` |
| OCR/scans | Не вводить | Отдельная AI/document-processing задача | Отдельная карта и evaluation corpus | `deferred` |
| Hot reload во время активного call | Не вводить | Один call должен иметь immutable knowledge snapshot | Новый lifecycle/control contract и owner review | `deferred` |
| Incremental indexing | Не вводить | Первый workshop rebuilds небольшой index целиком offline | Corpus-size/build-time evidence показывает необходимость | `deferred` |
| Lexical-only fallback | Запрещён | Не выдавать отсутствие embedding path за semantic RAG | Только отдельный owner decision/APG gap | `forbidden` |
| Silent skip invalid documents | Запрещён | Потеря знаний должна быть видимой | Нет; исправить corpus или явно разрешить skip в manifest | `forbidden` |

Intentional simplification не считается принятой до owner review открытых вопросов. После review child plans копируют
точное решение и не переспрашивают его без нового противоречащего evidence.

## 17. Календарные gates

| Дата | Gate | Требуемый результат | Что блокирует переход |
|---|---|---|---|
| 21 сентября | Map review | Map-012, child graph и решения по formats/activation/corpus приняты | `B-012-MAP-001` |
| 21–22 сентября | Boundary + corpus gate | `012-I` и `012-A`: authoritative contracts, manifest и synthetic corpus | Нет propagated schema/types |
| 22 сентября | Ingestion/build gate | `012-B`/`012-C`: deterministic chunks, CLI, real index и atomic-failure evidence | Index нельзя повторно построить или проверить |
| 23 сентября | Runtime/evaluation gate | `012-D`/`012-E`: load/readiness без rebuild, полный question set и accepted tuning | Runtime re-embeds corpus или quality gate красный |
| 24 сентября | Workshop gate | `012-F`: clean live repeat и context-free runbook review | Новый corpus не доказан в звонке либо runbook неповторяем |
| 25 сентября | Резерв/показ | Только rehearsal и critical corrective pass; новый scope не добавляется | Нет recovery path для workshop demo |

Если мастер-класс назначен позже, порядок gates сохраняется, а даты становятся ранними target dates, не разрешением
сократить acceptance.

## 18. Map-level closeout

Map-012 получает статус `complete` только если:

1. карта и все child plans прошли применимый owner review/APG;
2. `012-I`, `012-A`–`012-F` закрыты собственным статусом `complete`, а не промежуточным claim;
3. другой corpus строится опубликованной CLI-командой, failed build не изменяет предыдущий index;
4. сохранённый index загружается и проверяется runtime без corpus re-embedding;
5. immutable evaluation set подтверждает expected sources, negative/unknown и contextual retrieval;
6. clean registered SIP call использует новый corpus и сохраняет source IDs в итоговом отчёте;
7. self-contained runbook повторён исполнителем без контекста и исправлен по результатам review;
8. `knowledge-base.md`, ТЗ/архитектура при фактическом изменении контрактов, user guide, roadmap, registry и backlog
   синхронизированы главным executor;
9. `python tools/check_document_registry.py` и `python tools/check_task_backlog.py` проходят;
10. open gaps/fallbacks не выданы за выполненную возможность.

До этого карта остаётся `proposed`, `map ready for child execution`, `in_progress` или `blocked` согласно фактическому
состоянию. Планирование карты не является execution evidence.

## 19. Фактический closeout

Карта закрыта 2026-09-21 без открытых blockers. Все child plans имеют собственные `complete` closeout. Active workshop
corpus валидируется и детерминированно превращается в `12 × 768` `rag-index-v1`; failed publish сохраняет предыдущий
artifact; runtime загружает index без corpus re-embedding; immutable evaluation проходит `12/12`.

Финальный registered `012-F/live-r5` подтвердил source-aware positive/follow-up, новую самостоятельную тему без
заражения историей, корректный insufficient/offer-transfer текст, подтверждённый transfer, report, continuous RTP и
stereo recording. Независимый context-free review после corrective pass — PASS. Owner docs, user guide, roadmap,
document registry и task backlog синхронизированы; итоговый execution report:
[`map-closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/map-closeout.md).
