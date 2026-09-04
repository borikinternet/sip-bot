# 002-H deterministic execution commands

Дата: `2026-09-03`

Команды выполнены из `C:\devel\sip-bot`:

```text
python -m pytest -q tests/unit/test_tts_output.py tests/contract/test_playback_contract.py tests/integration/test_barge_in.py
8 passed in 0.04s
exit code: 0

python -m pytest -q tests/unit tests/contract
87 passed in 0.16s
exit code: 0

python -m compileall -q src tests config
exit code: 0
```

Target no-GIL import probe в WSL Ubuntu-24.04:

```text
wsl -d Ubuntu-24.04 -- env PYTHONPATH=/mnt/c/devel/sip-bot/src \
  /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "import sys; ...; import sip_bot.tts, sip_bot.playback; ..."

3.14.7 free-threading build ...
cpython
False
imports=ok
False
exit code: 0
```

GPU XTTS и RTP smoke этой командой намеренно не запускались: это main-only gates.
