# 005-A deterministic results

Дата: `2026-09-04`

Команда на target runtime:

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m pytest -q tests/integration/test_map005_protocol_media.py
```

Результат: `5 passed`.

Проверены protocol reply table, callback-local `re-INVITE`/`UPDATE` response, transport failure normalization,
remote disconnect/`BYE`, unanswered `CANCEL` normalization и repeated callback/close idempotency.

Additional target regression:

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q tests/unit tests/contract
104 passed, 2 skipped
```

The attempted `-I` full regression was not classified as product failure: unit/contract conftest requires the project
root for `config` imports. The plan command without `-I` passed on the same free-threaded target.
