# Commands and results

Рабочий каталог для всех команд: `C:\devel\sip-bot`.

## Runtime version

Command: `python --version`

- stdout: [`runtime-version.stdout.log`](runtime-version.stdout.log)
- stderr: [`runtime-version.stderr.log`](runtime-version.stderr.log)
- exit code: [`runtime-version.exit-code`](runtime-version.exit-code)

Command: `python -c "import json,sys,sysconfig; print(json.dumps({'executable':sys.executable,'version':sys.version,'implementation':sys.implementation.name,'Py_GIL_DISABLED':sysconfig.get_config_var('Py_GIL_DISABLED'),'gil_enabled':sys._is_gil_enabled() if hasattr(sys,'_is_gil_enabled') else None}, sort_keys=True))"`

- stdout: [`runtime-probe.stdout.log`](runtime-probe.stdout.log)
- stderr: [`runtime-probe.stderr.log`](runtime-probe.stderr.log)
- exit code: [`runtime-probe.exit-code`](runtime-probe.exit-code)
- interpretation: `Py_GIL_DISABLED=0`, `gil_enabled=true`; not a free-threaded pass.

## Config import

Command (PowerShell): `$env:PYTHONPATH = 'src'; python -c "from config import constants; from sip_bot.config import RuntimeConfig; cfg = RuntimeConfig.from_constants(); print('application='+cfg.application_name); print('codec='+cfg.sip_codec); print('rate='+str(cfg.sip_sample_rate_hz)); print('channels='+str(cfg.sip_channels)); print('free_threaded_required='+str(cfg.require_free_threaded)); print('operator='+cfg.operator_target); print('media_ptime_policy='+cfg.media_ptime_policy)"`

- stdout: [`config-import.stdout.log`](config-import.stdout.log)
- stderr: [`config-import.stderr.log`](config-import.stderr.log)
- exit code: [`config-import.exit-code`](config-import.exit-code)

## Deterministic unit/contract tests

Command: `python -m pytest -q tests/unit tests/contract`

- stdout: [`pytest.stdout.log`](pytest.stdout.log)
- stderr: [`pytest.stderr.log`](pytest.stderr.log)
- exit code: [`pytest.exit-code`](pytest.exit-code)
- result: `12 passed`

## Target runtime verification

Target environment: Ubuntu-24.04/WSL2, user `sipbot`, executable
`/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`.

Command: `wsl.exe -d Ubuntu-24.04 -u sipbot -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "import sys,sysconfig; print(sys.executable); print(sys.version); print(sysconfig.get_config_var('Py_GIL_DISABLED')); print(sys._is_gil_enabled())"`

- stdout: [`target-runtime-probe.stdout.log`](target-runtime-probe.stdout.log)
- exit code: [`target-runtime-probe.exit-code`](target-runtime-probe.exit-code)
- structured result: [`target-runtime-probe.json`](target-runtime-probe.json)
- result: CPython 3.14.7t, `Py_GIL_DISABLED=1`, GIL disabled.

Command: `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && PYTHONPATH=src /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q tests/unit tests/contract'`

- stdout: [`target-pytest.stdout.log`](target-pytest.stdout.log)
- exit code: [`target-pytest.exit-code`](target-pytest.exit-code)
- result: `12 passed`.

Command: `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && PYTHONPATH=src /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m compileall -q src config'`

- exit code: [`target-compile.exit-code`](target-compile.exit-code)
- result: pass.

Command: `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && PYTHONPATH=src /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "from sip_bot.config import RuntimeConfig; print(RuntimeConfig.from_constants().application_name)"'`

- stdout: [`target-config.stdout.log`](target-config.stdout.log)
- exit code: [`target-config.exit-code`](target-config.exit-code)
- result: config import pass.

## Strict application entrypoint

Command (PowerShell): `$env:PYTHONPATH = 'src'; python -m sip_bot`

- stdout: [`entrypoint.stdout.log`](entrypoint.stdout.log)
- stderr: [`entrypoint.stderr.log`](entrypoint.stderr.log)
- exit code: [`entrypoint.exit-code`](entrypoint.exit-code)
- result: expected strict preflight rejection on the current GIL-enabled host (`2`).

Target command: `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && PYTHONPATH=src /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m sip_bot'`

- stdout: [`target-entrypoint.stdout.log`](target-entrypoint.stdout.log)
- exit code: [`target-entrypoint.exit-code`](target-entrypoint.exit-code)
- result: strict preflight pass on the target runtime.

## Document/task audits

Commands after closeout edit:

- `python tools/check_document_registry.py` — [`document-registry.stdout.log`](document-registry.stdout.log), [`document-registry.stderr.log`](document-registry.stderr.log), [`document-registry.exit-code`](document-registry.exit-code); pass after main-executor status synchronization.
- `python tools/check_task_backlog.py` — [`task-backlog.stdout.log`](task-backlog.stdout.log), [`task-backlog.stderr.log`](task-backlog.stderr.log), [`task-backlog.exit-code`](task-backlog.exit-code); pass.
- `python -m compileall -q src config` — [`compile.stdout.log`](compile.stdout.log), [`compile.stderr.log`](compile.stderr.log), [`compile.exit-code`](compile.exit-code); pass.
- `git diff --check` — [`git-diff-check.stdout.log`](git-diff-check.stdout.log), [`git-diff-check.stderr.log`](git-diff-check.stderr.log), [`git-diff-check.exit-code`](git-diff-check.exit-code); pass.

## Additional lifecycle evidence

- [`lifecycle-trace.json`](lifecycle-trace.json) — deterministic open/close/re-close sequence.
- [`terminal-stale-trace.json`](terminal-stale-trace.json) — terminal cancellation and stale generation suppression.
- [`contract-fixture.md`](contract-fixture.md) — actual control envelope fields and downstream handoff.
