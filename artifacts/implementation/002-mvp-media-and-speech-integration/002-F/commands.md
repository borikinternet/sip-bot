# Commands and exit codes

Все команды выполнялись из `C:\devel\sip-bot`.

| Команда | Exit code | Результат |
|---|---:|---|
| `python -m pytest -q tests/unit/test_context_retrieval_prompt.py tests/contract/test_f_retrieval_prompt_contracts.py` | 0 | `9 passed` |
| `python -m pytest -q tests/unit tests/contract` | 0 | `73 passed` |
| `python -m compileall -q src/sip_bot/context src/sip_bot/retrieval src/sip_bot/prompt config/constants.py` | 0 | compile pass |
| `PYTHONPATH=src python -c "... import F packages ..."` | 0 | host imports pass |
| `wsl.exe -d Ubuntu-24.04 -- ... python3.14t -c "... import F packages ..."` | 0 | target free-threaded import pass, `gil_enabled=false` |

На Windows host optional-пакеты не устанавливались. В target Ubuntu/CPython 3.14.7t они установлены и проверены:
`razdel=true`, `pymorphy3=true`, `gil_enabled=false`; query probe сохраняет `H2O`, `10^3`, отрицания и единицы
измерения. При обнаруженном расхождении между `razdel` и protected scientific-token lexer исправлен
`src/sip_bot/retrieval/query_builder.py`, после чего host regression и target no-GIL probe прошли.
