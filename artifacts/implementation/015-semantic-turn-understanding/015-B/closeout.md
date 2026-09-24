# Plan-015-B closeout

Дата: `2026-09-22`  
Статус: `complete`

Реализована revision `semantic-turn-I1`: runtime парсит `FinalUserTurn` один раз с read-only expectation FSM;
composition сохраняет raw turn один раз и последовательно применяет acts; pipeline кэширует content act до
синхронного `START_INFERENCE` и передаёт в retrieval/prompt только residual content.

FSM владеет pending transfer/reconfirmation. Compound positive отвечает на content и выпускает
`PLAY_TRANSFER_CONFIRMATION`; configured text проходит существующий TTS path. Pure confirm переводит, reject снимает
pending intent, explicit operator request переводит без LLM. Barge-in/clarify сохраняют reconfirmation; terminal
lifecycle очищает его. Semantic act outcomes записываются в `report.md`.

Проверки на `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`:

- affected full suite: `282 passed, 2 skipped`, exit `0`;
- GIL before `false`, after `false`;
- compound negative и positive, no duplicate offer, raw context once, static TTS reconfirmation, report trace,
  stale/cancel/BYE/barge-in regressions зелёные.

Новый queue/process/delivery owner не введён. Blockers `B-015-B-001`–`004` не сработали. `015-D` получает полный
deterministic handoff; live dependency Plan-014 остаётся отдельной.
