# Plan-002-B execution commands

Target application evidence uses Ubuntu-24.04/WSL2, user `sipbot`, and
`/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`. Windows host Python was
used only for deterministic unit tests and is not application evidence.

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall -q src/sip_bot/sip_media` | 0 | Adapter/media modules compile. |
| `python -m pytest -q tests/unit tests/contract` | 0 | 21 passed. |
| `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc '/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -'` | 0 | `pjsua2` import, `Endpoint/libCreate/libDestroy`, pytest import; GIL false before import and after lifecycle. Full stdout/stderr are in `runtime-import.json`. |
| `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc "sha256sum /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t /home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages/_pjsua2.cpython-314t-x86_64-linux-gnu.so"` | 0 | Runtime and native binding hashes match `runtime-import.json`, `patch-identity.json`, and the accepted C1 manifests. |
| `Get-FileHash artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading.patch,artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading-buffer.patch -Algorithm SHA256` | 0 | `D5FD6DB2DCC88E8958DA73750033BA1AB85A6F32D1FE5D47B28D86A1A37F36AA`; `9C849BB28EC6D7A791E22769B8F2E975F8686B2470D286D74768E4075CA48BE5`. |
| `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m pytest -q /mnt/c/devel/sip-bot/tests/integration/test_sip_media.py -k "local_call_lifecycle or remote_bye"'` | 0 | 2 passed, 1 deselected; approved Baresip peer, local OPTIONS 200, local close and remote BYE observed without dispatcher handoff. stdout/stderr: `target-b2.stdout.log`, `target-b2.stderr.log`. |
| `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m pytest -q /mnt/c/devel/sip-bot/tests/integration/test_sip_media.py -k pcmu_profile'` | 0 | Corrective B3 rerun: 1 passed, 2 deselected; actual active media index selected from `CallInfo.media`, PCMU profile published. stdout/stderr: `target-b3.stdout.log`, `target-b3.stderr.log`. |
| `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m pytest -q /mnt/c/devel/sip-bot/tests/integration/test_sip_media.py'` | 0 | Full target B rerun: 3 passed in 6.66 s; no native endpoint teardown abort. stdout/stderr: `target-b-full.stdout.log`, `target-b-full.stderr.log`. |
| `python tools/check_document_registry.py` | 0 | 36 documents, 36 registry rows, no missing/extra/duplicate paths. |
| `python tools/check_task_backlog.py` | 0 | 6 backlog rows, unique IDs; no backlog item is added by this slice. |

The target SIP commands are run serially because the evidence harness uses
fixed local adapter port 5070. The full target integration file is green after
the corrective pass. `remote-bye.json` records 10 ingress and 10 egress
application frames; no audio recording is produced.
