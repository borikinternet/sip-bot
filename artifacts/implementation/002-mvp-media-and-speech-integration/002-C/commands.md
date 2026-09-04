# Commands and raw results: Plan-002-C

Рабочий каталог: `C:\devel\sip-bot` / `/mnt/c/devel/sip-bot`.

## Baseline до реализации

```text
python -m pytest -q tests/unit tests/contract
.....................                                                    [100%]
21 passed in 0.03s
exit code: 0
```

## Host checks

```text
python -m compileall -q src tests
exit code: 0

python -m pytest -q tests/unit tests/contract
.........................................................                [100%]
57 passed in 0.08s
exit code: 0
```

Targeted host additions:

```text
python -m pytest -q tests/unit/test_audio_boundaries.py tests/contract/test_audio_contracts.py
...............                                                          [100%]
15 passed in 0.06s
exit code: 0
```

## Target runtime/import

Executable:

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
```

Команда проверки no-GIL после явного импорта `sip_bot.media`:

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc '/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys, sysconfig; before=sys._is_gil_enabled(); sys.path.insert(0, \"/mnt/c/devel/sip-bot\"); sys.path.insert(0, \"/mnt/c/devel/sip-bot/src\"); import sip_bot.media; after=sys._is_gil_enabled(); print(\"executable=\", sys.executable); print(\"version=\", sys.version.split()[0]); print(\"Py_GIL_DISABLED=\", sysconfig.get_config_var(\"Py_GIL_DISABLED\")); print(\"gil_before=\", before); print(\"gil_after_media_import=\", after); assert sysconfig.get_config_var(\"Py_GIL_DISABLED\") == 1; assert before is False and after is False"'
```

Raw result:

```text
executable= /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
version= 3.14.7
Py_GIL_DISABLED= 1
gil_before= False
gil_after_media_import= False
exit code: 0
```

## Target deterministic lane

Команда выполняет тесты в isolated target process; project root добавляется явно, поэтому не меняется общий
`conftest.py`:

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot; /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys; sys.path.insert(0, \"/mnt/c/devel/sip-bot\"); import pytest; raise SystemExit(pytest.main([\"-q\", \"tests/unit/test_audio_boundaries.py\", \"tests/contract/test_audio_contracts.py\"]))"'
```

Raw stdout: [`target-tests.stdout.log`](target-tests.stdout.log)

```text
...............                                                          [100%]
15 passed in 0.45s
exit code: 0
```

Raw stderr: [`target-tests.stderr.log`](target-tests.stderr.log), пустой.

## C4 live target boundary

План включает target handoff после подтверждения 002-B; GPU и модели не нужны.

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot; /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-C/target_pcm_boundary_probe.py > /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-C/c4-target.stdout.log 2> /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-C/c4-target.stderr.log; code=$?; echo EXIT_CODE=$code; exit $code'
```

Raw stdout: [`c4-target.stdout.log`](c4-target.stdout.log)

```text
{"status": "pass", "live_pcm_frames": 100, "chunks": 2, "error": null}
exit code: 0
```

Raw stderr: [`c4-target.stderr.log`](c4-target.stderr.log) содержит только штатный startup log PJLIB/PJSUA2;
исключений нет.

Основной JSON: [`c4-target.json`](c4-target.json). Лог approved peer: [`c4.peer.log`](c4.peer.log).

## Классификация неуспешных запусков по APG §5.8B

| Команда | Exit | Классификация | Corrective pass |
|---|---:|---|---|
| `python3.14t -I -m pytest ...` | 1 | Ошибка существующего target test-path: `config` не был в `sys.path` | Изменён только invocation на isolated `python -c` с явным project root; `15 passed` |
| Probe с `getattr(sys, "Py_GIL_DISABLED", ...)` | 1 | Ошибка проверочной команды: проектный контракт использует `sysconfig` | Повторная проверка через `sysconfig.get_config_var`; exit 0 |

Ни один из этих результатов не регистрировался как APG blocker; после corrective pass обязательные проверки зелёные.
