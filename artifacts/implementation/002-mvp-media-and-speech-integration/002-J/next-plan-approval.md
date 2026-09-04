# Owner decision и successor plan `002-I.0`

Дата: `2026-09-03`

Владелец проекта дал решение по части прежнего category-4 gap `B-002-J-005`:
в MVP остаются один Dispatcher и один одновременный звонок, но `Dispatcher`,
`CallSession` и `DialogueFSM` должны быть разными классами и объектами. Их
допускается разместить в одном Python-модуле. Новый plan должен называться
`002-I.0`, а не `002-K`.

Предыдущее решение не требовало отдельного `state.json`: такого входного
требования в проекте нет. Единственный обязательный итоговый артефакт звонка —
`report.md`; `conversation.jsonl` и любые in-memory snapshots могут использоваться
как внутренние implementation details.

Отдельный preflight также подтвердил, что PJSUA2/PJMEDIA поддерживает несколько
одновременных `Call`; это не меняет single-call MVP.

## Зафиксированные решения

1. `Dispatcher` остаётся единственным process-local control owner и хранит
   один active-session slot. `CallSession` — отдельный per-call
   composition/lifecycle object. `DialogueFSM` сохраняет semantic decisions,
   а SIP adapter — protocol reactions.
2. Оформить изменение отдельным child plan `002-I.0` с новой APG,
   write-set вокруг существующего `src/sip_bot/control/dispatcher.py` и
   corrective write-set только при фактическом API gap. План добавляет
   `CallSession` и сквозную композицию, но не создаёт второй Dispatcher или
   DialogueFSM и не вводит новый process boundary.
3. После реализации выпустить новую Map-I propagation revision и вернуть
   `002-J/J4`; молчаливое расширение J запрещено.

## Оставшийся owner review

Проверить, что I.0 действительно переиспользует существующие Dispatcher и
DialogueFSM, добавляет только отсутствующую CallSession composition, а также
имеет typed lifecycle для контекста и обязательной однократной финализации
`report.md`, при review
[`plan-002-I.0-call-session-orchestration-and-state.md`](../../../docs/plans/plan-002-I.0-call-session-orchestration-and-state.md).

## Следующий порядок

`I.0 owner review → I.0 implementation + tests → Map-I propagation revision 11
→ J4 clean-start full matrix → J5/Map-002 closeout`.

До review I.0 новые typed edges композиции не считаются утверждёнными.
