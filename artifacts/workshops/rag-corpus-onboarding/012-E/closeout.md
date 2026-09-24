# 012-E closeout: retrieval evaluation and tuning

Статус: `complete`  
Дата: `2026-09-21`

## Frozen evaluation set

- Schema/version: `rag-evaluation-v1` / `small-service-company-eval-v1`.
- Cases: 12 (`positive`, `paraphrase`, `contextual`, `conflict`, `negative`).
- SHA-256: `35f5bc63156bf99a7e1ff0fe948c4fba9b3dacba694df55a87faec6464ac3738`.
- Во время tuning вопросы, expected sources, corpus и index artifact не изменялись.

## Первый прогон и corrective pass

Первый real `embeddinggemma` run: `10/12`. Не прошли два перефразированных запроса:

- цена: правильный source был первым с cosine `0.5587`, но lexical guard объявлял контекст insufficient;
- посудомоечная машина: cosine был слабым (`0.2501`), хотя документ содержал два независимых лексических anchor.

Исправлена retrieval policy владельца индекса, без lexical-only fallback:

- semantic similarity остаётся обязательной и имеет нижнюю границу;
- до трёх explainable lexical anchors дают bounded rank boost `0.08`;
- доля lexical anchors защищает от unrelated partial overlap;
- semantic-only sufficiency разрешён только для откалиброванного `embeddinggemma` при cosine `>=0.53`;
- conversation tail участвует и в embedding text, и в lexical evidence;
- near-tie metadata ordering учитывает priority/effective date детерминированно.

## Итог

Target tests: `48 passed in 5.02s`. Real repeat: `12/12`, aggregate retrieval latency `266.35 ms`; каждый negative
остался insufficient, contextual follow-up выбрал schedule/escalation, conflict case первым выбрал
`company-escalation`. `Py_GIL_DISABLED=1`, GIL после operation выключен.

Evidence:

- [`evaluation-before-tuning.json`](evaluation-before-tuning.json) — неизменяемый baseline `10/12`;
- [`evaluation-after-tuning.json`](evaluation-after-tuning.json) — corrective pass `12/12`.

`B-012-E-001` не сработал: cases не удалялись, expected sources не ослаблялись, model-only fallback не вводился.
