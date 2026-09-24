# Frozen corrective RAG suite

- Suite: `config/evaluation-map015.json`
- Evaluation version: `natural-science-map015-corrective-v1`
- SHA-256: `0c73fb2183fdbd8653120cc8d4835d79d878e22bfea040ef54cad05efbc9f80d`
- Frozen before policy changes: `2026-09-22`
- Cases: `12` (`7` positive/paraphrase/contextual, `5` negative)
- Baseline: `8/12 passed`, status `fail`
- Baseline evidence: `baseline-before.json`

Baseline failures are immutable acceptance evidence: two conversational sky phrasings were false-insufficient; the
one-word underspecified color and an explicit new topic after prior sky context were false-sufficient.

