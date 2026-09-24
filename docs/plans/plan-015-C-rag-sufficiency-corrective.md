# Plan-015-C: доказуемая RAG sufficiency для разговорных вопросов

Уровень: `child plan`  
Статус: `complete 2026-09-22; frozen suite 12/12 pass`  
Родитель: [`Map-015`](plan-015-semantic-turn-understanding.md)  
Зависимость: `015-I complete`; может исполняться параллельно `015-A`  
Evidence root: `artifacts/implementation/015-semantic-turn-understanding/015-C/`

## 1. Цель и результат

Исправить доказанный false-insufficient: релевантный `wiki-physics-rayleigh` является top-1 и имеет score выше
`RAG_RELEVANCE_THRESHOLD`, но conversational/paraphrase query получает `sufficient=false` из-за дополнительных
неотражённых в diagnostics условий. Изменение принимается только по расширенной immutable evaluation suite, а не по
одному звонку.

## 2. Materialized rules

| Источник | Правило | Применение | Проверка / stop condition |
|---|---|---|---|
| [`requirements.md`](../requirements.md) | Answer path обязан использовать локальный source-aware RAG, а не встроенные знания модели | Corrective сохраняет sources и negative unknown path | Model-only answer — stop |
| [`technical-specification.md`](../technical-specification.md) §2.4 | Ответ разрешён только при source-aware sufficient context; negative path остаётся offer-transfer | Policy меняется без model-only answer | Negative case стал sufficient — stop/correct |
| [`architecture.md`](../architecture.md) §3.3 | Context/KB owner владеет query/index/threshold и diagnostics | Изменения локальны retrieval owner | Prompt/LLM скрыто решает sufficiency — stop |
| [`plan-012-E`](plan-012-E-rag-evaluation-and-tuning.md) | Threshold/chunking меняются только по immutable positive/negative/contextual набору | Расширить suite до corrective, затем freeze before tuning | Cases переписаны после результата — stop |
| [`development-guidelines.md`](../development-guidelines.md) §6.1 | Красный acceptance не компенсируется соседними зелёными; implementation/fixture error исправляется | Before/after raw evidence и rerun | Single-query hand tuning — stop |
| [`documentation-process.md`](../documentation-process.md) | Фактический алгоритм/threshold описываются у владельцев, не в историческом плане | После pass синхронизировать knowledge-base/ТЗ/config | Расходящиеся hidden thresholds — stop |
| [`roadmap.md`](../roadmap.md) §13.5 | После freeze только corrective mandatory demo-flow | C исправляет воспроизведённый false refusal, не расширяет corpus/domain | Новая retrieval feature/model — stop |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Model/RAG boundary change требует full tests/evidence/blockers | Frozen suite, real provider и closeout обязательны | Непроверенный threshold change — stop |

## 3. Scope, owner и write-set

Входит:

- immutable corrective cases: разговорный wrapper, короткий paraphrase, exact science question, contextual follow-up,
  unrelated/negative/ambiguous questions;
- evidence всех факторов sufficiency: semantic score, lexical support, configured/effective threshold, reason code;
- query normalization/stop-term policy и ranking/sufficiency logic по результатам suite;
- report diagnostics и contract tests;
- real embedding provider probe через существующий `LLM Facade`.

Не входит: новый corpus/chunks/index rebuild без доказанного gap, новая embedding/reranker/chat model, vector DB,
ослабление unknown-answer policy.

Допустимый write-set:

- `src/sip_bot/retrieval/query_builder.py`, `index.py`, retrieval contracts/evaluation при необходимости;
- `src/sip_bot/report/builder.py` только sufficiency diagnostics (координируется последовательно с B);
- dedicated immutable evaluation fixture/config под Map-015;
- related unit/contract/evaluation tools/tests;
- `config/constants.py` только если evidence требует изменения явного configured threshold;
- этот plan и собственный evidence.

`LocalKnowledgeIndex`/query builder остаются владельцами. Prompt/FSM/LLM facade/SIP/speech защищены. При параллельном
исполнении с A write-set не пересекается; общий report/config/docs изменяет главный executor последовательно.

### 3.1. Source-map

| Область | Текущее поведение | Целевое изменение |
|---|---|---|
| Query builder | Morphology/terms включают conversational framing | Наблюдаемые semantic/query terms без single-phrase hack |
| Local index | Hybrid rank и несколько sufficiency branches | Config/effective criteria согласованы и имеют reason code |
| Evaluation | Accepted Map-012 suite не содержит live phrasings | Новый frozen corrective suite поверх сохранённого baseline |
| Report | Показывает threshold/top-k, но не скрытые gates | Все факторы и final reason sufficiency |
| Config | `RAG_RELEVANCE_THRESHOLD` объявлен authoritative | Меняется только если full suite это докажет |

## 4. Required evaluation

До code change сохранить baseline минимум для:

- `Привет! Ты можешь сказать, какого цвета небо?` → sufficient, source Rayleigh;
- `Какого цвета небо?` → sufficient, source Rayleigh;
- `Почему небо днём голубое?` → sufficient, source Rayleigh;
- domain paraphrases из accepted science suite;
- unrelated service/business and nonsense queries → insufficient;
- context-dependent follow-up не заражает самостоятельный новый вопрос старой темой.

Target policy обязана иметь один наблюдаемый configured threshold либо явно именованные дополнительные criteria с
reason codes. Отчёт `threshold=0.35` при фактическом скрытом semantic-only `0.53` без diagnostics запрещён.

## 5. Slices и blockers

1. Freeze expanded suite и снять baseline before evidence.
2. Добавить full sufficiency diagnostics/reason codes.
3. Выполнить минимальный policy/query corrective pass.
4. Прогнать fake/unit и real `embeddinggemma` suite, affected prompt/unknown-answer regression.

| ID | Срез | Триггер | Блокируется | Владелец | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-015-C-001` | 3 | Текущий provider/index не разделяет positive/negative без reranker/model | C/D | project owner | immutable before/after matrix | `none until triggered` |
| `B-015-C-002` | 1 | Corrective cases конфликтуют с accepted corpus/source semantics | C | executor | source/corpus audit | `none until triggered` |
| `B-015-C-003` | 4 | Real provider unavailable after corrective retry | C/D | project owner | command/raw output | `none until triggered` |

### 5.1. Owner review

Открытых вопросов нет: corpus/index/model не меняются, tuning следует уже принятому Map-012 evaluation process. Если
suite потребует нового reranker/model или изменения corpus, это новый category-4 gap, а не решение C.

### 5.2. Process invariant audit

- Evaluation cases замораживаются и хэшируются до policy change; после результата не переписываются.
- C допускает параллельный субагент с A только по непересекающемуся retrieval write-set; real shared GPU и final audit
  выполняет main executor.
- Красный positive/negative acceptance исправляется, не маскируется average score или соседними cases.
- Config/report/docs меняются главным executor после проверки handoff; registry/backlog audit обязателен.

### 5.3. Architecture invariant audit

- Retrieval owner, а не prompt/answer LLM, определяет `KnowledgeContext.sufficient`.
- Semantic score остаётся обязательным; lexical-only/model-only fallback запрещён.
- `KnowledgeContext` остаётся typed source-aware boundary с hits/scores/version/reason.
- Новая модель, process или vector DB не вводятся; существующий HTTP embedding facade сохраняется.
- Insufficient context по-прежнему разрешает только unknown-answer/offer-transfer.

## 6. Test/evidence, fallback и closeout

Evidence сохраняет fixture hash, model/index/corpus versions, per-case query terms, hits/scores, all sufficiency factors,
latency, command and exit code. Target free-threaded runtime проверяется до/после imports/operation; тяжёлый shared GPU
probe запускает главный executor.

Fallback register: `none`; lexical-only answer, model-only answer, lowered assertion и special-case exact phrase
запрещены. Closeout только `complete` после всей frozen suite и regression либо `blocked` по доказанному category-4 gap.

## 7. Closeout

Immutable suite SHA-256 `0c73fb2183fdbd8653120cc8d4835d79d878e22bfea040ef54cad05efbc9f80d`:
baseline `8/12`, corrective result `12/12` на real `embeddinggemma`. Configured threshold `0.35`, corpus/index/model не
менялись; query policy стала `ru-natural-science-v2`, а все sufficiency gates получили typed diagnostics/reason code.
Target runtime сохранил disabled GIL; affected regression `23 passed`. Evidence:
[`015-C/closeout.md`](../../artifacts/implementation/015-semantic-turn-understanding/015-C/closeout.md).
