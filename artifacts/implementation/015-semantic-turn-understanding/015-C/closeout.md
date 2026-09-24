# Plan-015-C closeout

Дата: `2026-09-22`  
Статус: `complete`

Frozen suite `natural-science-map015-corrective-v1` имеет SHA-256
`0c73fb2183fdbd8653120cc8d4835d79d878e22bfea040ef54cad05efbc9f80d` и не менялась после baseline.

## Результат

- Before: `8/12`, fail (`baseline-before.json`).
- After: `12/12`, pass (`after.json`).
- Real provider: Ollama `/api/embed`, `embeddinggemma`, index
  `natural-science-embeddinggemma-v1`, corpus `ru-natural-science-demo-v1`.
- Target runtime: CPython 3.14.7t, `Py_GIL_DISABLED=1`, GIL after operation `false`.
- Affected deterministic regressions: `23 passed`.

Исправление не меняет configured threshold `0.35`, model, corpus или index. Query policy `ru-natural-science-v2`
исключает из lexical denominator разговорную рамку (`привет`, modal/request words и формы `какой`), причём работает
и без optional morphology packages. Lexical criteria считают только термы, которые реально могут участвовать в
matching. Однословный запрос ниже strong-semantic threshold остаётся insufficient. Evaluation применяет историю
диалога только при `requires_dialogue_context()`, как production pipeline, поэтому новый самостоятельный вопрос не
заражается предыдущей темой.

`KnowledgeContext.sufficiency_diagnostics` и отчёт теперь показывают reason code, configured/effective threshold,
semantic-only threshold, lexical floor, semantic score, lexical support и число query terms. Hidden gate больше нет.

Blockers `B-015-C-001`–`003` не сработали; новый reranker/model/index не нужен.

