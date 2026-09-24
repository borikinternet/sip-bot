# Plan-015-D closeout

Дата: `2026-09-22`  
Итог: `complete`

## Immutable input

Fixture package: [`fixtures-v5/manifest.json`](fixtures-v5/manifest.json).

| Сценарий | SHA-256 |
|---|---|
| compound negative + explicit transfer | `b41e393615f7f1269780fad7dc718a5350355f9d5d1c8691f74f0acd611560fd` |
| compound positive + barge-in + confirm | `1661827046a543a7216e87c5e27707261ef8c0f8900d22059bfc32820cbed689` |
| compound positive + unknown + single offer | `e90e4f6d2a0b6c39f0ff2d92374ed584f202bcbb71d288dbbdb041ab5832ecdb` |

## Authoritative result

Aggregate: [`live-v7/map015-semantic-live-gate.json`](live-v7/map015-semantic-live-gate.json), `status=pass`, SHA-256
`839b8b56a0658d477f2e686210cd8483f12199384e28e4f2cb9600f8e1bb6c9c`.

Первый и второй сценарии переиспользуют ранее полученные зелёные результаты только потому, что их WAV SHA-256 не
изменился; полные источники скопированы в [`live-final-components`](live-final-components/). Третий сценарий выполнен
заново после category-1 исправления parser и хранится в
[`live-v7/compound-positive-unknown-single-offer`](live-v7/compound-positive-unknown-single-offer/). Его stereo WAV
имеет SHA-256 `97babd55594408a8cd3f8059b52873f622e50852681888a72c7a181319141a27`.

Все обязательные semantic checks зелёные: ordered acts, one-write raw context, RAG diagnostics, compound negative,
compound positive/reconfirmation, barge-in, no duplicate offer, typed reject и explicit transfer. Во всех результатах
использован CPython 3.14.7t с выключенным GIL и отсутствуют runtime errors.

## Corrective history

`live-v6` доказал прикладной дефект: точный ASR final `Переведите меня на оператора.` при pending confirmation
классифицировался как `knowledge_request`. `SemanticTurnParser` исправлен: `DialogueExpectation` интерпретирует
контекстные ответы, но не подавляет self-contained `TransferRequestAct`. Добавлен regression test; локальный полный
gate после исправления: `284 passed, 2 skipped`.

Открытых blockers, owner-review вопросов и deferred mandatory evidence нет.
