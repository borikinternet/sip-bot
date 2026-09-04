# 005-A commands and exit codes

| Command | Runtime | Exit | Result |
|---|---|---:|---|
| `python -m pytest -q tests/integration/test_map005_protocol_media.py tests/integration/test_map005_speech_resilience.py` | Windows CPython 3.14.3 | 0 | `11 passed` |
| `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m pytest -q tests/integration/test_map005_protocol_media.py tests/integration/test_map005_speech_resilience.py` | Ubuntu/WSL CPython 3.14.7t, GIL disabled | 0 | `11 passed` |
| `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q tests/unit tests/contract` | Ubuntu/WSL CPython 3.14.7t, GIL disabled | 0 | `104 passed, 2 skipped` |
| `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/map005_protocol_probe.py --scenario matrix --output-root .../005-A/live-20260904-r1` | Ubuntu/WSL CPython 3.14.7t, GIL disabled | 0 | `status=pass` |

Live output: [`live-20260904-r1`](live-20260904-r1/).
