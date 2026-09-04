# 002-E command ledger

All commands were run from `C:\devel\sip-bot` with the host deterministic
Python 3.14 lane. No package installation or GPU inference was used.

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall -q src\sip_bot\control src\sip_bot\dialogue tests\unit\test_dialogue_fsm.py tests\contract\test_control_events.py` | 0 | pass |
| `python -m ruff check src\sip_bot\control\event_bus.py src\sip_bot\control\dispatcher.py src\sip_bot\control\__init__.py src\sip_bot\dialogue tests\unit\test_dialogue_fsm.py tests\contract\test_control_events.py` | 0 | pass |
| `python -m pytest -q tests\unit tests\contract` | 0 | 59 passed, one pre-existing pytest cache warning |
| `python -m pytest -q` | 1 | collection stopped on pre-existing duplicate `test_sip_media` module name between unit/integration |
| `python -m pytest -q --import-mode=importlib` | 1 | 59 passed; 3 existing SIP integration tests could not start Windows `baresip` (`WinError 2`) |

The two red full-suite runs were classified under APG §5.8B: the first was a
local test collection/import-mode issue and was rerun with `importlib`; the
remaining three are out-of-scope target SIP-stand environment failures. The
002-E deterministic acceptance lane is green.

## Captured stdout/stderr

The following is the captured output from the main-executor verification of
the deterministic acceptance lane. Pytest and Ruff emitted no stderr.

The delegated acceptance run recorded above had 59 tests. The main executor
then added two targeted contract assertions within the approved write-set and
reran the lane; the final result is recorded below.

### Unit and contract tests

Command:

```text
python -m pytest -q tests\unit tests\contract
```

stdout:

```text
...........................................................              [100%]
59 passed in 0.07s
```

stderr: empty; exit code: `0`.

### Final acceptance rerun after contract assertions

Command:

```text
python -m pytest -q tests\unit tests\contract
```

stdout:

```text
.............................................................            [100%]
61 passed in 0.09s
```

stderr: empty; exit code: `0`.

The corresponding final compileall and Ruff reruns produced no stdout or
stderr and exited with code `0`; Ruff reported `All checks passed!` when run
without quiet output.

### Compile check

Command:

```text
python -m compileall -q src\sip_bot\control src\sip_bot\dialogue tests\unit\test_dialogue_fsm.py tests\contract\test_control_events.py
```

stdout: empty; stderr: empty; exit code: `0`.

### Ruff

Command:

```text
python -m ruff check src\sip_bot\control\event_bus.py src\sip_bot\control\dispatcher.py src\sip_bot\control\__init__.py src\sip_bot\control\lifecycle.py src\sip_bot\dialogue tests\unit\test_dialogue_fsm.py tests\contract\test_control_events.py
```

stdout:

```text
All checks passed!
```

stderr: empty; exit code: `0`.

### Full host collection with importlib

Command:

```text
python -m pytest -q --import-mode=importlib
```

stdout summary:

```text
...............FFF............................................           [100%]
3 failed, 59 passed in 0.25s
```

stderr: empty; exit code: `1`. The three failures are the pre-existing SIP
integration tests that attempt to start the unavailable Windows `baresip`
executable and raise `FileNotFoundError: [WinError 2]`; no 002-E test failed.

The final main-executor rerun after the two additional contract assertions
reported the following summary (pytest progress dots omitted):

```text
3 failed, 61 passed in 0.24s
```

The failed test names and cause were unchanged: the three SIP integration
tests could not start Windows `baresip` (`FileNotFoundError: [WinError 2]`).
stderr: empty; exit code: `1`; no 002-E test failed.
