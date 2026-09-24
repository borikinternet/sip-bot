# Plan-015-A closeout

Дата: `2026-09-22`  
Статус: `complete`  
Contract revision: `semantic-turn-I1` / parser `ru-semantic-turn-v1`

Реализованы immutable `DialogueExpectation`, `SourceSpan`, variant dialogue acts и `SemanticTurn`, а также
stateless `SemanticTurnParser`. Parser не импортирует FSM/SIP/RAG/LLM, не создаёт потоки и не исполняет side effects.

Покрытая матрица: pure yes/no, polite no, compound reject + question, compound confirm + question, explicit operator
request, ordinary question и ambiguous confirmation (`Нет ли...`, `Даже...`) без critical act. Raw
`FinalUserTurn` сохраняется объектом source; spans упорядочены и не перекрываются.

Проверки:

- target CPython `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`;
- `tests/unit/test_semantic_turn_parser.py`: `16 passed`, exit `0`;
- import + parse operation: `Py_GIL_DISABLED=1`, GIL before `false`, after `false`;
- sample acts: `reject_pending`, `knowledge_request`;
- новые native/model dependencies: `none`.

Blockers `B-015-A-001`–`003` не сработали. Handoff в `015-B`: использовать публичные types/method
`SemanticTurnParser.parse(FinalUserTurn, DialogueExpectation)` без mapping adapter и без legacy raw-turn FSM path.

