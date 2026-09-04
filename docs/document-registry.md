# Реестр документов проекта

Статус: `active`

Реестр содержит все Markdown-документы проекта, а не только документы, ожидающие исполнения. Он нужен одновременно
для навигации, определения владельца информации и контроля полноты документации.

Для ручного обзора документы разделены на тематические таблицы. Машинный инвариант применяется ко всем таблицам:
каждый `*.md` под каталогом `docs` должен встретиться ровно один раз.

## Инварианты и проверка

- каждый Markdown-файл под `docs` присутствует в одной и только одной таблице ниже;
- лишняя строка в реестре, пропущенный файл и дубликат являются ошибкой;
- после каждого изменения Markdown запускается:

```powershell
python tools/check_document_registry.py
```

- проверка печатает `actual`, `registry_rows`, `registry_unique`, `missing`, `extra` и `duplicate_paths`;
- дата `Checked at` обновляется при изменении назначения, статуса или состава документа; механическое добавление нового
  файла также требует добавить его в подходящую таблицу.

Статусы документа:

| Статус | Значение |
|---|---|
| `active` | Актуальный документ-источник или процессный документ. |
| `planning_only` | План/roadmap, который задаёт будущую работу. |
| `proposed` | Решение или документ ещё не утверждён владельцем. |
| `accepted` | Решение принято и действует, пока не заменено. |
| `in_progress` | Карта или supermap находится в активном execution-переходе; это не closeout child plan. |
| `complete` | Карта или child plan полностью закрыты собственным acceptance/evidence и closeout. |
| `blocked` | Исполнение остановлено по конкретному зарегистрированному блокеру; частичное выполнение не считается closeout. |
| `map ready for child execution` | Карта согласована и готова к отдельному owner review/execution child plans. |
| `superseded` | Документ заменён другим источником. |
| `retired` | Документ сохранён только как история. |

## 1. Канонические и справочные документы

Эти документы сами по себе не являются очередью реализации; они определяют требования, правила или текущую модель
проекта.

| Path | Area/owner | Classification | Status | Evidence | Next step | Checked at |
|---|---|---|---|---|---|---|
| `requirements.md` | Requirements | Постановка задачи и границы MVP | `active` | Документ содержит пользовательские сценарии и критерии готовности | Обновлять только при изменении требований владельцем | 2026-08-25 |
| `architecture.md` | Architecture | Сквозная архитектура, control/data plane и boundary-взаимодействия | `active` | Зафиксированы компоненты, ownership, process-local control event bus, direct `FinalUserTurn` data-plane path, per-call SDP/PJMEDIA media profile, endpointing, Skill & Prompt Manager, локальный RAG/embedding boundary, typed `LlmRequest`, dynamic bounded TTS accumulation/frame pacing, правило interaction map и ссылка на PJSUA2/PJMEDIA patch invariant | Синхронизировать при изменении архитектурного контракта | 2026-09-04 |
| `technical-specification.md` | Technical constraints | Техническое задание, конфигурация, boundary adapters и критерии проверки | `active` | Зафиксированы PCMU, per-call SDP/PJMEDIA media profile, latency, context, no-GIL, config constants, обязательные PJSUA2/PJMEDIA patches, audio chunking/re-framing, LLM Facade, prompt/profile, RAG baseline и 20 GB operational guard | Синхронизировать с фактическим runtime и кодом | 2026-09-04 |
| `documentation-process.md` | Documentation process | Правила владельцев информации и недублирования | `active` | Определяет распределение информации по документам, включая отдельный владелец правил разработки и подходов | Обновлять при появлении нового устойчивого владельца | 2026-09-03 |
| `development-guidelines.md` | Development process | Устойчивые правила и подходы разработки, тестирования, runtime, границ, делегирования и closeout | `active` | Выделяет правила второго типа из APG и задаёт owner/source для их materialization в plan-files | Обновлять только при изменении общих правил процесса | 2026-09-03 |
| `licensing-policy.md` | Licensing | Лицензии, публикация и демонстрационный scope | `active` | Зафиксирована прикладная лицензионная политика проекта | Обновлять при выборе компонента с новыми условиями | 2026-08-25 |
| `architectural-planning-gate.md` | Planning process | Локальный APG для отбора, materialization и проверки правил в supermap/map/child plan и отчётах | `active` | Содержит типологию документов, процедуру выбора применимых источников, обязательную структуру plan-file, owner review, gap protocol и closeout audit; устойчивые правила вынесены в `development-guidelines.md` | Поддерживать при изменении процесса планирования или способа применения правил | 2026-09-03 |
| `tooling-notes.md` | Tooling process | Адаптируемые no-GIL и document/task registry tooling-паттерны | `active` | Зафиксированы ссылки на соседние инструменты и локальные команды | Обновлять при добавлении project tools | 2026-08-25 |
| `knowledge-base.md` | Knowledge base | Curated Russian natural-science corpus, источники, лицензии/атрибуция и baseline локального RAG | `active` | F зафиксировал три source-aware источника и их materialized corpus manifest; retrieval/query/index evidence хранится в `artifacts/implementation/002-mvp-media-and-speech-integration/002-F/` | Обновлять при изменении корпуса, источников, лицензий или embedding/index baseline | 2026-09-03 |
| `task-backlog.md` | Task governance | Backlog deferred/out-of-scope задач и их состояния | `active` | Имеет стабильные `TASK-NNN`, owner/next-step поля и обязательный RAG handoff для текущей карты; `TASK-001`/`TASK-002` и J4 blocker синхронизированы с Map-001/Map-002 statuses | Синхронизировать при появлении или закрытии задачи | 2026-09-03 |
| `document-registry.md` | Documentation governance | Полный инвентарь всех Markdown-документов | `active` | Этот файл является self-entry и проверяется локальным tool | Пересчитывать после каждого изменения Markdown | 2026-09-04 |

## 2. Документы в очереди или требующие дальнейшей работы

Эта таблица предназначена для быстрого ответа на вопрос «какие документы сейчас надо исполнять или дорабатывать».
Она не заменяет task backlog: backlog фиксирует задачи, а здесь перечислены именно документы, которые являются входом
или результатом следующей работы.

| Path | Area/owner | Classification | Status | Evidence | Next step | Checked at |
|---|---|---|---|---|---|---|
| `roadmap.md` | MVP planning | Дорожная supermap и порядок карт/child plans | `in_progress` | Map-001/Map-002/Map-005/Map-006 закрыты в пределах исполненных карт; дальнейшие действия — freeze, редактура, лицензирование и публикация | Выполнить календарный code/demo freeze к 2026-09-21 и завершить отдельные publication actions | 2026-09-04 |
| `decisions/ADR-002-llm-model-selection.md` | LLM selection | Предварительный выбор LLM, ожидающий benchmark на RTX 5060 Ti | `proposed` | Shortlist, versioned prompt/profile-контракт и RAG/source-aware benchmark criteria зафиксированы, итоговая модель не утверждена | Выполнить одинаковый benchmark через Skill & Prompt Manager с локальным RAG и обновить статус ADR | 2026-09-02 |
| `plans/plan-001-deadline-feasibility.md` | Feasibility planning | Map-level декомпозиция scope freeze и child feasibility plans до 31 августа | `complete` | Map owner review принят 2026-08-26; все child plans и M-G1–M-G4 имеют evidence/closeout, следующий Map-002 reviewed 2026-09-02 | Использовать feasibility baseline в Map-002; новых feasibility-кандидатов не добавлять молча | 2026-09-03 |
| `plans/plan-001-A-environment-baseline.md` | Feasibility / environment | Child plan baseline Ubuntu/WSL2/GPU/CUDA/filesystem | `complete` | Owner review принят 2026-08-27; environment evidence и child-plan closeout подтверждены | Использовать закрытый environment baseline; source-placement probe повторить только при появлении source content | 2026-09-03 |
| `plans/plan-001-B-cpython314t-runtime.md` | Feasibility / runtime | Child plan latest stable free-threaded CPython >= 3.14 и no-GIL baseline | `complete` | Owner review принят 2026-08-27; GIL/runtime evidence и child-plan closeout подтверждены | Использовать CPython 3.14.7t в component compatibility slices | 2026-09-03 |
| `plans/plan-001-C-native-compatibility-map.md` | Feasibility / native map | Дочерняя map декомпозиции native compatibility на C1–C4 | `complete` | Map review принят 2026-08-27; C1–C4 имеют execution complete, evidence и candidate decisions; handoff в `001-D` выполнен | Использовать синхронизированный handoff; fallback не запускался | 2026-09-03 |
| `plans/plan-001-C1-sip-pjsua2-pjmedia.md` | Feasibility / SIP | Child plan PJSUA2/PJMEDIA import, lifecycle, PCMU и BYE | `complete` | Owner review принят 2026-08-27; candidate decision `pass`, patched no-GIL import/operation и peer-dependent evidence записаны | Переданный candidate decision использовать в `001-D`; fallback не запускался | 2026-09-03 |
| `plans/plan-001-S-voip-test-stand.md` | Test infrastructure | Child plan локального SIP/RTP peer, PCMU loopback, BYE и fake operator | `complete` | Owner review и stand result `pass` 2026-08-27; Baresip peer, PCMU, remote BYE и fake transfer имеют evidence | Использовать `001-S` как approved local peer; повторять только при изменении candidate/stand contract | 2026-09-03 |
| `plans/plan-001-C2-asr-primary.md` | Feasibility / ASR | Child plan streaming ASR partial/final/cancel | `complete` | Owner review и candidate decision `pass` 2026-08-27; faster-whisper 1.2.1 с patched CTranslate2 binding и closeout записаны | Переданный candidate decision и patch/cancellation limitations использовать в `001-D` | 2026-09-03 |
| `plans/plan-001-C3-llm-primary.md` | Feasibility / LLM | Child plan Qwen3.5-9B 4-bit import/inference/VRAM/cancel | `complete` | Owner review и candidate decision `pass_with_isolation` 2026-08-27; GPU evidence, HTTP IPC boundary и closeout записаны | Переданный candidate decision и HTTP IPC boundary использовать в `001-D` | 2026-09-03 |
| `plans/plan-001-C4-tts-primary.md` | Feasibility / TTS | Child plan русского TTS import/audio/cancel | `complete` | Owner review и candidate decision `pass` 2026-08-27; XTTS-v2, WAV/PCMU evidence и closeout записаны | Переданный candidate decision, patches и cancellation limitations использовать в `001-D` | 2026-09-03 |
| `plans/plan-001-D-process-boundaries.md` | Feasibility / architecture | Child plan синтеза process/thread boundaries и control/data plane | `complete` | Owner review принят 2026-08-27; synthesis result `pass`, evidence root и сводные boundaries созданы | Использовать baseline в `001-E`/Map-002; integration gaps не выдавать за pass | 2026-09-03 |
| `plans/plan-001-E-feasibility-closeout.md` | Feasibility / closeout | Child plan закрытия feasibility и допуска следующей карты | `complete` | Owner review принят 2026-08-27; next Map-002 reviewed 2026-09-02, M-G4 закрыт, final evidence package обновлён | Использовать закрытый feasibility baseline и выполнять отдельные child plans Map-002 | 2026-09-03 |
| `plans/plan-002-mvp-media-and-speech-integration.md` | MVP implementation / map | Карта 4: декомпозиция реализации основной логики и boundary-взаимодействий на child plans | `complete` | Owner review принят 2026-09-02; `002-A`–`002-H`, `002-I.0`, `002-I.1` и `002-J` complete; corrective full live gate r20 6/6, Map-I revision 21 | Перейти к карте 5 системного тестирования и исправлений | 2026-09-04 |
| `plans/plan-002-A-application-runtime-skeleton.md` | MVP implementation / child plan | Runtime/bootstrap, config constants, lifecycle и control foundation | `complete` | Owner review принят 2026-09-02; runtime/control scope полностью выполнен на target runtime, tests/evidence и audit завершены | Использовать contract revision в `002-B`; не смешивать SIP/media gap с runtime baseline | 2026-09-03 |
| `plans/plan-002-B-sip-media-adapter.md` | MVP implementation / child plan | PJSUA2/PJMEDIA application adapter, SIP/media lifecycle и protocol reactions | `complete` | Owner review принят 2026-09-02; B1–B4 pass, corrective target rerun pass, Map-I propagation checkpoint revision 4 записан 2026-09-03 | Использованный `NegotiatedMediaProfile`/`PcmFrame` contract принят следующим C и propagated through Map-I revisions 5–6; новый C1 patch/isolation decision не требуется | 2026-09-03 |
| `plans/plan-002-C-audio-boundary-buffering.md` | MVP implementation / child plan | PCMU/PCM conversion, PCM fan-out, bounded channels и ASR chunker | `complete` | Main audit и C→D propagation accepted 2026-09-03; C1–C4, target deterministic/live evidence и blocker closeout подтверждены | Использовать authoritative `media.AsrAudioChunk` в `002-D`; propagation evidence в interaction-map root | 2026-09-03 |
| `plans/plan-002-D-speech-ingress.md` | MVP implementation / child plan | VAD, endpointing, streaming ASR и Transcript Assembler | `complete` | Owner review, corrective C→D contract pass, target speech/no-GIL evidence и final-turn propagation accepted 2026-09-03 | Использовать `FinalUserTurn` напрямую в F/FSM; native ASR/VAD execution остаётся в утверждённых controlled checks | 2026-09-03 |
| `plans/plan-002-E-dispatcher-dialogue-fsm.md` | MVP implementation / child plan | Dispatcher, control event bus, Dialogue FSM и action validation | `complete` | Owner review, control-only bus contract, direct final-text correction, state trace и propagation accepted 2026-09-03 | Передать F/G/H/J typed control contracts; `FinalUserTurn` не публиковать через bus | 2026-09-03 |
| `plans/plan-002-F-skill-prompt-context.md` | MVP implementation / child plan | Skill/prompt manager, context persistence, curated KB и mandatory local RAG | `complete` | Owner review принят 2026-09-03; deterministic scope, target no-GIL optional path, real embedding index/query и positive/negative evidence приняты | Использовать закрытый RAG/prompt baseline в `002-G`/`002-J` | 2026-09-03 |
| `plans/plan-002-G-llm-facade.md` | MVP implementation / child plan | Typed LLM/embedding facade и Ollama HTTP IPC | `complete` | Owner review принят 2026-09-03; deterministic tests, corrective non-thinking config, real `/api/embed`/`/api/chat`, latency и VRAM evidence приняты | Передать typed stream/status/decision и latency evidence в `002-H`/`002-J` | 2026-09-03 |
| `plans/plan-002-H-tts-output-playback-barge-in.md` | MVP implementation / child plan | XTTS output buffering, media pacing, playback cancellation и barge-in | `complete` | Owner review принят 2026-09-03; H propagation принят в Map-I revision 8, revision 15 дополнительно фиксирует I.0 composition/J4 handoff; deterministic, XTTS/GPU, PCMU/RTP и barge-in evidence приняты | Использовать H output contract в `002-J`; повторять только при изменении media contract | 2026-09-03 |
| `plans/plan-002-J-transfer-report-integration.md` | MVP implementation / child plan | Fake operator transfer, report и сквозной demo-flow | `complete` | Owner review принят 2026-09-03; J1–J5 complete; corrective full live r20 6/6, B-002-J-004 resolved | Передать остаточные quality/production gaps в Map-005/backlog | 2026-09-04 |
| `plans/plan-002-I-boundary-interaction-map.md` | MVP implementation / interaction map | Под карта карты 4: topology взаимодействий, циклы и итерационное propagation контрактов | `complete` | Owner review принят 2026-09-02; revision 21 содержит checkpoints `002-A`–`002-H`, I.0/I.1, full live r20 и resolved blockers | Использовать принятую topology в карте 5; не переоткрывать закрытые boundaries без evidence | 2026-09-04 |
| `plans/plan-002-I.0-call-session-orchestration-and-state.md` | MVP implementation / child plan | Deterministic CallSession composition вокруг существующих Dispatcher/DialogueFSM и active-session slot | `complete` | Owner clarification и composition scope приняты 2026-09-03; deterministic I0-1…I0-5, named bindings, real ASR/LLM/XTTS composition и closeout приняты; live SIP wiring явно не входит; `state.json` не входит в требования | Использовать composition baseline в `002-I.1`/J4; не считать live edges закрытыми | 2026-09-03 |
| `plans/plan-002-I.1-live-call-asyncio-wiring.md` | MVP implementation / child plan | Live wiring существующих SIP/media/speech/AI/TTS input methods через основной asyncio loop | `complete` | APG plan и owner review приняты; I1-1…I1-8 complete, pre-call warmup, ASR 8→16 kHz/growing-prefix, corrective full live J4 r20; evidence и closeout сохранены | Использовать live wiring baseline в Map-005; повторять только при изменении contracts | 2026-09-04 |
| `plans/plan-005-system-testing-and-demo-readiness.md` | MVP system testing / map | Карта 5: системное тестирование, corrective passes и готовность demo/rehearsal | `complete` | 005-A/B/C/D и corrective 005-E закрыты; r10 подтвердил полный TTS output, `egress_underruns=0`, без overflow; r7 сохранён как historical evidence | Передать r10 downstream Map-006 и выполнить календарный code/demo freeze | 2026-09-04 |
| `plans/plan-005-A-protocol-media-failure-matrix.md` | MVP system testing / child plan | SIP/media protocol matrix, media failures, idempotent close и raw Baresip recording evidence | `complete` | Owner review принят 2026-09-04; A1 deterministic, A2/A3 live PCMU/Baresip/sndfile evidence, regression и closeout завершены | Передать protocol/media evidence в Map-005 и `005-D`; live-deferred stimuli не выдавать за pass | 2026-09-04 |
| `plans/plan-005-B-speech-audio-resilience.md` | MVP system testing / child plan | Audio fan-out, negotiated chunking, VAD/endpointing, ASR revisions и stale/cancel policy | `complete` | Owner review принят 2026-09-04; B1/B2 `9 passed`, target ASR streaming/cancel и PCMU-derived application path pass, regression `141 passed, 2 skipped`, closeout сохранён | Передать ASR/speech evidence в 005-C и Map-005 | 2026-09-04 |
| `plans/plan-005-C-ai-quality-latency-resources.md` | MVP system testing / child plan | RAG/LLM/TTS quality, latency, warmup, VRAM и paced playback/source selection | `complete` | Owner review принят 2026-09-04; deterministic, source-aware real AI, source-mode live gate, target regression и closeout завершены | Передать latency observation и source counters в 005-D; не выдавать overall target за достигнутый | 2026-09-04 |
| `plans/plan-005-D-rehearsal-evidence-closeout.md` | MVP system testing / child plan | Clean-start rehearsal, Baresip stereo recording, requirement matrix и evidence closeout | `complete` | Grouped owner review принят 2026-09-04; D r7 J4 `pass`, 6/6 checks, raw enc/dec, stereo manifest, report, source-mode corrective pass, targeted `7 passed`, full regression `151 passed, 2 skipped`; closeout сохранён как historical baseline | Использовать r7 как diagnostic evidence; полнота TTS принята последующим corrective `005-E`/r10 | 2026-09-04 |
| `plans/plan-005-E-tts-playback-integrity-corrective.md` | MVP system testing / child plan | Dynamic bounded TTS accumulation, frame pacing, lifecycle/overflow tests и target r10 corrective gate | `complete` | E1–E4 complete; r10 main-executor clean-start, full SIP/RTP scenario, stereo recording, target regression и audio audit passed; no category-4 blocker | Передать r10 downstream Map-006; historical r7 не перезаписывать | 2026-09-04 |
| `plans/plan-006-report-and-demo-preparation.md` | MVP report preparation / map | Карта 6: evidence-backed доклад и демонстрационный пакет | `complete` | 006-A/B/C и corrective 006-D закрыты; target r6 подтвердил compact fixture, 7/7 checks, stereo recording и audio audit | Содержательная редактура, project license и публикация остаются отдельными действиями | 2026-09-05 |
| `plans/plan-006-D-demo-input-timing-corrective.md` | MVP report preparation / child plan | Сокращение искусственных пауз demo input fixture без потери обязательных сценариев | `complete` | Target r6: compact fixture, полный SIP/RTP сценарий, 7/7 checks, Baresip raw/stereo recording, audio audit; `egress_underruns=0`, no overflow | Использовать target r6 в demo/report package; исторические r1–r5 не перезаписывать | 2026-09-05 |
| `plans/plan-006-A-evidence-inventory.md` | MVP report preparation / child plan | Evidence inventory и requirement/claim traceability | `complete` | Source index создан, числовые и архитектурные claims сверены с owner documents и r7 evidence | Использовать в report draft | 2026-09-04 |
| `plans/plan-006-B-demo-runbook.md` | MVP report preparation / child plan | Воспроизводимый runbook чистого запуска и демонстрации | `complete` | Exact target command, prerequisites, scenario, artifacts, cleanup и limitations зафиксированы | Использовать в rehearsal | 2026-09-04 |
| `plans/plan-006-C-conference-report-draft.md` | MVP report preparation / child plan | Русскоязычный докладный черновик и publication checklist | `complete` | Report draft и checklist созданы с traceability; latency limitation и licensing prerequisites не скрыты | Передать владельцу на редактуру | 2026-09-04 |

## 3. Принятые архитектурные решения

Эти документы не являются очередью исполнения: они фиксируют решения, которыми должны руководствоваться следующие
срезы.

| Path | Area/owner | Classification | Status | Evidence | Next step | Checked at |
|---|---|---|---|---|---|---|
| `decisions/ADR-001-llm-and-dialogue-manager.md` | Dialogue architecture | LLM не управляет SIP напрямую; решения исполняет Dialogue FSM/Dispatcher, prompt собирает отдельный manager, IPC скрывает Facade | `accepted` | Решение, три границы LLM-пути и последствия описаны в ADR | Соблюдать при реализации и пересматривать только отдельным ADR | 2026-08-29 |
| `decisions/ADR-003-free-threaded-python.md` | Python runtime | CPython 3.14.7t как baseline, process isolation для несовместимых native-компонентов | `accepted` | Проверки `Py_GIL_DISABLED`/`sys._is_gil_enabled()` и правила isolation описаны в ADR | Выполнить feasibility no-GIL checks для выбранных зависимостей | 2026-08-25 |
| `decisions/ADR-004-control-plane-event-bus.md` | Control-plane architecture | Process-local control-plane event bus | `accepted` | Зафиксированы singleton scope, control-only payload policy, Dispatcher ownership, bounded subscription lifecycle и отклонённые alternatives | Синхронизировать с фактическим event bus contract при реализации `002-E` | 2026-09-02 |

## 4. Исторические и заменённые документы

Пока таких документов нет. Таблица остаётся явной, чтобы появление исторического материала не привело к удалению
traceability.

| Path | Area/owner | Classification | Status | Evidence | Next step | Checked at |
|---|---|---|---|---|---|---|
