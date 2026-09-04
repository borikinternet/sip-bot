# J1–J3 deterministic execution commands

Дата: 2026-09-03

| Команда | Runtime | Exit code | Результат |
|---|---|---:|---|
| `python --version` | Windows Python | 0 | `Python 3.14.3` |
| `python -m pytest -q tests/integration/test_transfer_report.py` | Windows Python 3.14.3 | 0 | `6 passed in 0.07s` |
| `python -m pytest -q tests/unit tests/contract` | Windows Python 3.14.3 | 0 | `88 passed in 0.19s` |
| `python -m compileall -q src tests config` | Windows Python 3.14.3 | 0 | success |
| `wsl -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t --version` | Ubuntu-24.04 target | 0 | `Python 3.14.7` |
| `wsl -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "import sys; print(sys._is_gil_enabled())"` | Ubuntu-24.04 target | 0 | `False` |
| `wsl -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q /mnt/c/devel/sip-bot/tests/integration/test_transfer_report.py` | Ubuntu-24.04 no-GIL | 0 | `6 passed in 0.69s` |
| `wsl -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m compileall -q /mnt/c/devel/sip-bot/src /mnt/c/devel/sip-bot/tests /mnt/c/devel/sip-bot/config` | Ubuntu-24.04 no-GIL | 0 | success |

## J4 main-only execution (historical pre-`002-I.1` run)

- J4 clean-start runner (main executor, sequential heavy gates):
  `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/j4_clean_start_probe.py /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-clean-start-20260903-r2`
  — exit `0`; target regression `112 passed`, real answer and real ASR/media/transfer compositions `pass`.
- J4 generated TTS WAVs are retained under `j4-clean-start-20260903-r2/`; they are output artifacts for listening, not conversation recordings.
- Qualification at that time: the runner executed the SIP/RTP regression and
  real AI compositions as separate clean lanes. The missing live driver was
  the then-open `B-002-J-006`, not a skipped test. Successor `002-I.1` later
  materialized and proved the base live path in `live-gate-20260903-r4`; the
  remaining J4 work is the full scenario matrix.

## J4 full live clean-start gate r18

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/j4_full_live_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-full-live-20260904-r18 --timeout-s 240'
```

Exit code: `0`. `j4-full-live.json`: `status=pass`, six of six scenario checks, `errors=[]`, SIP/RTP and PCMU
established, typed transfer result accepted by the local operator, final report present, target `gil_enabled=false`.
The gate was performed by the main executor after sequential pre-call warmup. Historical r1–r19 outputs remain
preserved as diagnostic evidence and are not overwritten. r19 was a red corrective result: an early ASR common prefix
was incorrectly frozen by the Transcript Assembler. The implementation was corrected and targeted plus full target
regression were repeated before r20.

## J4 full live clean-start gate r20

```text
wsl -d Ubuntu-24.04 -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/j4_full_live_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-full-live-20260904-r20 --timeout-s 240'
```

Exit code `0`. `j4-full-live.json`: `status=pass`, six of six scenario checks, `errors=[]`, SIP/RTP and PCMU
established, typed transfer result accepted by the local operator, final report present, target `gil_enabled=false`.
Before the rerun, host/target targeted checks passed (`23 passed, 2 skipped`) and target full regression passed
(`127 passed, 2 skipped`).
