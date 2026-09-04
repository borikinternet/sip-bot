# 002-D commands, stdout/stderr and exit codes

Все команды выполнены 2026-09-03. Heavy GPU inference не запускался.

## 1. Targeted host tests

Command:

```text
python -m pytest -q tests/unit/test_speech_ingress.py tests/contract/test_speech_contracts.py
```

Exit code: `0`

stdout:

```text
...........                                                              [100%]
11 passed in 0.04s
```

stderr: empty.

## 2. Target free-threaded speech tests

The first direct `-I -m pytest` invocation failed during collection because the pre-existing unit conftest adds only
`src/`, while `src/sip_bot/__init__.py` imports the project-root `config/` package. It exited `1` with two collection
errors (`ModuleNotFoundError: No module named 'config'`). Raw stderr is in `target-collection-error.stderr.log`. This is
a test-launcher/bootstrap issue outside the write-set, not a speech implementation failure.

Corrective command with explicit source/project bootstrap:

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys; sys.path.insert(0, \"/mnt/c/devel/sip-bot\"); sys.path.insert(0, \"/mnt/c/devel/sip-bot/src\"); import pytest; raise SystemExit(pytest.main([\"-q\", \"/mnt/c/devel/sip-bot/tests/unit/test_speech_ingress.py\", \"/mnt/c/devel/sip-bot/tests/contract/test_speech_contracts.py\"]))"'
```

Exit code: `0`

stdout:

```text
...........                                                              [100%]
11 passed in 0.42s
```

stderr: empty.

## 3. Target compileall

Command:

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m compileall -q /mnt/c/devel/sip-bot/src/sip_bot/speech /mnt/c/devel/sip-bot/tests/unit/test_speech_ingress.py /mnt/c/devel/sip-bot/tests/contract/test_speech_contracts.py'
```

Exit code: `0`; stdout/stderr empty.

## 4. Target import/no-GIL probe

Command used the same target executable with explicit src/project bootstrap and imported `sip_bot.speech` after
capturing the runtime state.

Exit code: `0`

stdout (`target-runtime-import.stdout.log`):

```text
{"before": {"executable": "/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t", "implementation": "cpython", "version": "3.14.7", "Py_GIL_DISABLED": 1, "gil_enabled_before": false}, "after": {"Py_GIL_DISABLED": 1, "gil_enabled_after": false}}
```

stderr: empty.

## 5. Target controlled concurrency

The first attempt was a malformed `python -c` command (`def` after a semicolon), exit `1`, classified as command/test
fixture error under APG §5.8B. Corrective command completed successfully.

Exit code: `0`

stdout (`target-runtime-concurrency.stdout.log`):

```text
{"results": ["тест", "тест", "тест", "тест"], "gil_enabled_after": false, "Py_GIL_DISABLED": 1}
```

stderr: empty.

## 6. Full host regression

Command:

```text
python -m pytest -q tests/unit tests/contract
```

Exit code: `1`.

Final stdout summary:

```text
..............F.F.F......................................                [100%]
3 failed, 54 passed in 0.12s
```

The three failures are pre-existing `tests/unit/test_dialogue_fsm.py` failures, documented in
`pre-existing-host-regression.md`; the raw final summary is in `host-regression.stdout.log`. No speech test failed.

## 7. Read-only project audits

Commands:

```text
python tools/check_document_registry.py
python tools/check_task_backlog.py
```

Exit code: `0` for both.

stdout:

```text
document registry audit: actual=36 registry_rows=36 registry_unique=36 missing=0 extra=0 duplicate_paths=0
document registry audit: PASS
task backlog audit: rows=6 unique_ids=6
task backlog audit: PASS
registry_exit=0 backlog_exit=0
```

stderr: empty.

## 8. Evidence JSON validation

Command:

```text
python -c "from pathlib import Path; import json; root=Path('artifacts/implementation/002-mvp-media-and-speech-integration/002-D'); [(json.loads(p.read_text(encoding='utf-8')), print('json ok', p.name)) for p in sorted(root.glob('*.json'))]"
```

Exit code: `0`.

stdout:

```text
json ok cancellation-stale.json
json ok contract-manifest.json
json ok endpointing.json
json ok target-runtime.json
json ok transcript-revisions.json
json ok vad-candidate.json
```

stderr: empty.
