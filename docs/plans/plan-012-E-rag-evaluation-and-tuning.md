# План 012-E: оценка retrieval и настройка RAG

Уровень: `child plan`  
Идентификатор: `012-E`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Зависимость: `012-D complete`  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-E/`

## Цель и результат

Создать неизменяемый machine-readable набор positive, paraphrase, contextual/follow-up, negative и conflict cases;
прогнать его по реальному активному индексу и обоснованно принять либо скорректировать top-k/threshold/chunking.

## Материализованные правила

- Question set и expected source IDs фиксируются до tuning; неудобные cases не удаляются и assertions не ослабляются.
- Evaluation проверяет retrieval/source selection, а не красоту свободного LLM-ответа.
- Follow-up включает переданный conversation tail; negative case не становится model-only answer.
- Conflict/effective/priority metadata учитывается детерминированно либо выявляет concrete gap; модель не выбирает
  актуальный документ сама при отсутствии policy.
- Сохраняются raw scores, source IDs, sufficiency, latency, corpus/index/question-set hashes и aggregate metrics.

## Source-map/write-set

Разрешено: `config/workshops/rag/evaluation.json`, новый `tools/knowledge/evaluate_rag.py`, при необходимости scoped
retrieval policy в `src/sip_bot/retrieval/index.py`, `tests/unit/test_rag_evaluation.py`, constants только при evidence-
обоснованном изменении top-k/threshold, собственный evidence и этот plan.

Protected: corpus content after immutable hash, index artifact (rebuild only through C command), LLM/prompt/SIP/media.

## Slices

1. `E1`: freeze evaluation schema/questions/expected sources and hash.
2. `E2`: deterministic fake-run verifies evaluator logic.
3. `E3`: real embeddinggemma evaluation and raw score capture.
4. `E4`: one full-set tuning pass if necessary; rebuild/re-run all cases, no case deletion.
5. `E5`: latency/quality report and closeout handoff to F.

## Blockers/tests/fallback

| ID | Trigger | Status |
|---|---|---|
| `B-012-E-001` | Gate can pass only by deleting cases, weakening expected sources or enabling model-only fallback | `none until triggered` |

Acceptance requires all required source hits, all negative cases insufficient, contextual case correct, conflict policy
deterministic, raw result file and reproducible command. Main executor owns real GPU/Ollama run and final tuning decision.

## Closeout

Исполнено полностью. Неизменяемый набор из 12 cases имеет SHA-256
`35f5bc63156bf99a7e1ff0fe948c4fba9b3dacba694df55a87faec6464ac3738`. Первый real run дал `10/12`; не меняя ни
одного вопроса/expected source, retrieval получил bounded hybrid ranking (semantic score обязателен, lexical anchors
только усиливают его), model-calibrated high-confidence rule и context terms. Повтор дал `12/12`, включая negatives,
follow-up и priority conflict. Evidence: [`012-E/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-E/closeout.md).
