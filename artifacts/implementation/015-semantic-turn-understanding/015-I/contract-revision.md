# Semantic-turn contract revision `semantic-turn-I1`

Дата аудита: `2026-09-22`  
Результат: `accepted`  
Блокеры: `none`

## Фактический baseline

- `SpeechIngress.take_final_turn()` выдаёт immutable `FinalUserTurn` с `call_id`, `channel_id`, `generation`,
  `turn_id`, `revision`, timestamp и authoritative `HARD_ENDPOINT`.
- `RuntimeWiring` вызывает `ConversationPipeline.submit_final_turn()` в основном loop.
- Pipeline заранее кладёт whole turn в cache по предполагаемому следующему `operation_id` и вызывает
  `CallComposition.accept_final_turn()`.
- Composition под одним `SessionLease` один раз вызывает `ContextStore.append_user(...)`, затем передаёт тот же
  `FinalUserTurn` в `DialogueFSM.handle(...)`.
- FSM при `AWAITING_TRANSFER_CONFIRMATION` классифицирует всю строку exact-match методами `_is_positive()` /
  `_is_negative()` и всегда завершает обработку события. Поэтому управляющий prefix и содержательный residual не
  могут быть применены последовательно.
- Для обычного хода FSM синхронно увеличивает `operation_id`, переходит в `THINKING` и выпускает компактный
  `START_INFERENCE`; observer Pipeline запускает worker. Payload в Dispatcher не попадает.

## Принятая revision

### Producer contracts

- `DialogueExpectation(kind, target)` — immutable read-only snapshot ожидания FSM. `kind`: `none` либо
  `transfer_confirmation`; `target` допустим только для подтверждения перевода.
- `SourceSpan(start, end)` — полуинтервал исходного текста; непустой, в пределах `FinalUserTurn.text`.
- Variant acts: `ConfirmPendingAct`, `RejectPendingAct`, `KnowledgeRequestAct(content)`,
  `TransferRequestAct(target=None)`. Каждый act несёт source span; content не переписывает raw turn.
- `SemanticTurn(source, expectation, acts, parser_version, diagnostics)` — immutable payload. `source` является
  исходным `FinalUserTurn`; acts непусты, упорядочены, не перекрываются и принадлежат source text.

### Exact consumer methods

| Edge | Метод | Execution context |
|---|---|---|
| FSM → parser | `DialogueFSM.current_expectation() -> DialogueExpectation` | main loop, read-only |
| Final text → parser | `SemanticTurnParser.parse(turn, expectation) -> SemanticTurn` | main loop, direct |
| Runtime → pipeline | `ConversationPipeline.submit_semantic_turn(turn) -> bool` | main loop, direct |
| Pipeline → composition | `CallComposition.accept_semantic_turn(turn) -> bool` | main loop, direct |
| Composition → context | `ContextStore.append_user(source.turn_id, source.text, revision=...)` ровно один раз | main loop |
| Composition → FSM | `DialogueFSM.handle(act)` последовательно | main loop |
| Knowledge act → worker | Pipeline cache по фактически выпущенному `START_INFERENCE.operation_id` | direct payload + compact control |
| Static re-confirmation | `PLAY_TRANSFER_CONFIRMATION`; Pipeline подставляет config text и использует существующий TTS path | control + direct TTS |

`RuntimeWiring` остаётся точкой materialization: получает `FinalUserTurn`, читает expectation, парсит один раз и
передаёт `SemanticTurn` в Pipeline. Старый authoritative `FinalUserTurn → FSM` path после propagation удаляется.

## Ordering и lifecycle

- Composition сначала валидирует `SessionLease`, затем сохраняет raw turn один раз, затем применяет acts по порядку.
- `RejectPendingAct` завершает pending transfer; следующий `KnowledgeRequestAct` того же turn запускает inference.
- Pure `ConfirmPendingAct` запускает transfer. Confirm + content только помечает pending reconfirmation, затем запускает
  inference. После `answer` playback FSM выпускает static re-confirmation; после `offer_transfer` отдельный повтор не
  создаётся.
- `clarify` и barge-in сохраняют pending reconfirmation. Reject, successful transfer, BYE/terminal/call close очищают.
- Между acts проверяется текущий call/session state; terminal transition прекращает iteration.
- Existing call generation, operation ID, cancellation и stale-result checks остаются authoritative. Semantic parser
  stateless и не вводит queue/thread/process lifecycle.

## Error policy

- Invalid contract/parser output — synchronous implementation error; никакого raw-turn fallback.
- Неоднозначный confirmation text не создаёт critical confirm/reject act: весь текст остаётся
  `KnowledgeRequestAct`.
- Parser не исполняет SIP, retrieval или LLM. FSM не получает full `SemanticTurn` через Dispatcher/Event Bus.
- Новый delivery owner, IPC, queue или изменение `FinalUserTurn` identity не нужны.

## Propagation checklist

- `015-A`: реализовать contracts/parser и corpus tests по этой revision.
- `015-C`: может исполняться независимо после freeze evaluation; semantic contracts не меняет.
- `015-B`: материализовать exact methods, удалить legacy raw-turn path, добавить semantic trace/re-confirmation.
- `015-D`: проверить ordering, no-duplicate context, stale/cancel/BYE и registered live flow.

## Проверенные blockers

- `B-015-I-001`: не сработал — новый delivery/orchestration owner не требуется.
- `B-015-I-002`: не сработал — acts упорядочиваются синхронно в существующем main loop.
- `B-015-I-003`: не сработал — protected `FinalUserTurn` identity сохраняется без изменений.

