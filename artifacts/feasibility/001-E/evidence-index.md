# 001-E evidence index

Дата исполнения: `2026-08-27`  
Статус E: `complete; Map-001 complete; Map-002 deferred to separate map`

Этот индекс сводит только уже существующие A–D и `001-S` evidence. Новые candidate probes, установка пакетов и
реализация в E не выполнялись. Raw commands, stdout/stderr, exit codes, hashes и результаты остаются в исходных
evidence roots.

## 1. Intake и provenance

| Evidence ID | Source / owner | Exact command или provenance | Runtime / workdir | stdout / stderr / exit | Result |
|---|---|---|---|---|---|
| `E-001E-ENV-001` | [`001-A/closeout.md`](../001-A-environment-baseline/closeout.md), `commands.md`, `inventory.json` | `wsl.exe --status`; `wsl.exe --list --verbose`; Ubuntu `/etc/os-release`, `uname`, `id`, `/etc/wsl.conf`; Windows `Get-PSDrive C`; Ubuntu `df -B1 -P`; `nvidia-smi` | Host + Ubuntu 24.04.4 LTS / WSL2; source root `/home/sipbot/src/sip-bot` | [`001-A/raw/`](../001-A-environment-baseline/raw/), closeout; recorded commands pass | `complete` в scope environment baseline; RTX 5060 Ti visible; 20 GiB minimum free-space rule recorded |
| `E-001E-RUNTIME-001` | [`001-B/runtime-manifest.json`](../001-B/runtime-manifest.json), `commands.md`, `run-01`–`run-03` | `./configure --prefix=/home/sipbot/.local/cpython-3.14.7t --disable-gil --with-ensurepip=install --without-lto`; `make -j4`; `make install`; `wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc '/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/nogil_probe.py'` | Ubuntu 24.04.4 LTS / WSL2; `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` | `run-*/stdout.log`, `run-*/stderr.log`, `run-*/exit-code.txt`; all probe exits `0` | CPython `3.14.7t`, SOABI `cpython-314t-x86_64-linux-gnu`, `Py_GIL_DISABLED=1`, controlled concurrency pass |
| `E-001E-SIP-001` | [`001-C1/candidate-manifest.json`](../001-C1-sip-pjsua2-pjmedia/candidate-manifest.json), C1 closeout, [`001-S`](../001-S-voip-test-stand/closeout.md) | PJSIP `./configure --prefix=/home/sipbot/.local/pjsip-2.17t CFLAGS=-fPIC CXXFLAGS=-fPIC`; binding `make PYTHON_EXE=/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`; import probe `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -X faulthandler /mnt/c/devel/sip-bot/tools/feasibility/pjsua2_pjmedia_probe.py --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patched-import-lifecycle.json --initialize` | Main free-threaded process; peer and fake operator in separate local Baresip processes | [`001-C1/commands.md`](../001-C1-sip-pjsua2-pjmedia/commands.md), `patched-import-lifecycle.json`, `001-S` JSON/logs; exit `0` for patched path | PJSUA2/PJMEDIA `2.17`, SWIG `4.2.0`, PCMU/BYE/lifecycle pass with two recorded patches; PJSIP source `COPYING` is GPL-2.0 |
| `E-001E-ASR-001` | [`001-C2/closeout.md`](../001-C2/closeout.md), `operation.json`, `partial-final.json`, `cancellation.json` | `/home/sipbot/.local/c2-faster-whisper-1.2.1t/bin/python -I /mnt/c/devel/sip-bot/tools/asr_primary_probe.py --stage operation --evidence-root /mnt/c/devel/sip-bot/artifacts/feasibility/001-C2 --fixture /mnt/c/devel/sip-bot/artifacts/feasibility/001-C2/fixture.mp3 --model-id /home/sipbot/.local/models/faster-whisper-large-v3-edaa852e --device cuda --compute-type int8_float16 --language ru --allow-model-load`; аналогично `--stage streaming` и `--stage cancellation` | Ubuntu WSL2; disposable C2 venv; workdir `/mnt/c/devel/sip-bot` | Commands and results are embedded in the three JSON records; exits `0` | `faster-whisper==1.2.1`, model revision `edaa852...`, patched CTranslate2 `4.8.1`; Russian operation, partial/final and stale suppression pass |
| `E-001E-LLM-001` | [`001-C3/candidate-manifest.json`](../001-C3-llm-primary/candidate-manifest.json), `inference.json`, `vram.json`, `cancellation.json` | `OLLAMA_MODELS=/home/sipbot/models/c3-ollama-store /home/sipbot/src/c3-ollama/v0.33.1/bin/ollama serve`; probe `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t /mnt/c/devel/sip-bot/tools/llm_primary_probe.py --stage gpu --allow-gpu --ollama-url http://127.0.0.1:11434 --ollama-model c3-qwen35-9b-q4km --prompt-file /mnt/c/devel/sip-bot/artifacts/feasibility/001-C3-llm-primary/prompt.json --evidence-root /mnt/c/devel/sip-bot/artifacts/feasibility/001-C3-llm-primary` | Main no-GIL controller + local Ollama native process; HTTP `127.0.0.1:11434` | [`001-C3/measurements.md`](../001-C3-llm-primary/measurements.md), `stdout.log`, `stderr.log`, JSON records; successful run recorded | Qwen3.5-9B GGUF Q4_K_M, Ollama `0.33.1`, structured `answer`; warm final-phrase→valid-response `2121.229 ms`, peak `8227/16311 MiB`, owner-approved isolation |
| `E-001E-TTS-001` | [`001-C4/closeout.md`](../001-C4-tts-primary/closeout.md), `operation.json`, `pcmu-boundary.json`, `cancellation.json` | `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python /mnt/c/devel/sip-bot/tools/feasibility/tts_primary_probe.py --manifest /mnt/c/devel/sip-bot/artifacts/feasibility/001-C4-tts-primary/manifest.json --stage operation --allow-tts-operation`; аналогично exact `--stage pcmu-boundary` и `--stage cancellation` commands in C4 command manifest | Main free-threaded process; disposable C4 environment; WSL paths from command manifest | `operation.stdout.json`, `operation.stderr.txt`, `pcmu-boundary.stdout.json`, cancellation records; all exits `0` | XTTS-v2 v2.0.3; first PCM `1308.4 ms`, complete `1776.8 ms`; WAV and PCMU/8 kHz/mono boundary pass |
| `E-001E-STAND-001` | [`001-S/closeout.md`](../001-S-voip-test-stand/closeout.md), `lifecycle.json`, `pcmu.json`, `bye.json`, `transfer.json` | Exact Baresip/PJSUA2 peer commands retained in [`001-S/commands.md`](../001-S-voip-test-stand/commands.md); lifecycle, PCMU, BYE and transfer scenarios are separately named by evidence IDs | Ubuntu 24.04.4 LTS / WSL2; peer `127.0.0.1:5080`, fake operator `127.0.0.1:5090` | Scenario JSON and peer logs; closeout records pass and command/exit-code provenance | Baresip `1.0.0-4build14`, BSD-3-Clause package metadata; local PCMU/BYE/fake-transfer stand pass |
| `E-001E-D-001` | [`001-D/evidence-index.md`](../001-D/evidence-index.md), D closeout and five synthesis outputs | D is a read/reconciliation stage; no component command or new GPU operation was run | Workspace `C:\devel\sip-bot`; source roots read-only | D evidence index and closeout; no new runtime exit code claimed | Process/thread matrix, control/data map, baseline draft and gaps reconciled; C3 HTTP isolation owner-approved |

## 2. Requirement coverage

| Requirement ID | Обязательная граница | Evidence | Статус в E | Что ещё не доказано |
|---|---|---|---|---|
| `REQ-E-001` | SIP answer/hangup, local lifecycle и независимая реакция на protocol-level events; BYE — проверенный пример | `E-001E-SIP-001`, `E-001E-STAND-001`, D control map | `baseline ready` | Полный lifecycle внутри реализованного бота и расширенная protocol-event matrix |
| `REQ-E-002` | PCMU 8 kHz mono RTP boundary | `E-001E-SIP-001`, `E-001E-STAND-001`, C4 PCMU boundary | `pass at candidate/stand boundaries` | Сквозной media channel приложения |
| `REQ-E-003` | Русский ASR с partial/final | `E-001E-ASR-001` | `pass at candidate boundary` | VAD, assembler и application endpointing |
| `REQ-E-004` | VAD и fixed soft/hard endpointing | Requirements/technical specification, D deferred register | `deferred` | Runtime behavior и false-positive/negative evidence |
| `REQ-E-005` | Structured LLM answer и ограниченные actions | `E-001E-LLM-001`, ADR-001, D baseline | `answer baseline pass` | Полный Dispatcher validation для всех actions |
| `REQ-E-006` | Локальная curated KB по естественным наукам и retrieval | Requirements, scope-freeze, D `DEFER-001D-RAG-001` | `deferred` | Материализация индекса и retrieval operation |
| `REQ-E-007` | Русский TTS, потоковый первый PCM и PCMU boundary | `E-001E-TTS-001` | `pass at candidate boundary` | Реальный playback и RTP egress |
| `REQ-E-008` | Barge-in, закрытие generation/playback, stale suppression | C2/C3/C4 cancellation, D map | `candidate boundary pass; integration deferred` | Barge-in во время реального RTP и channel lifecycle |
| `REQ-E-009` | Явный transfer на локального fake operator | `E-001E-STAND-001` | `stand pass` | Transfer из реализованного Dialogue FSM |
| `REQ-E-010` | Контекст и итоговый report | Requirements/technical specification, D deferred integration | `deferred` | Внутренний `conversation.jsonl` (если нужен реализации) и обязательный `report.md`; `state.json` не является требованием |
| `REQ-E-011` | Один разговор, локальность, отсутствие аудиозаписи | A/D scope evidence, `001-S` policy | `scope preserved` | Нагрузка и production readiness намеренно не проверялись |

## 3. Reconciliation conclusion

- Все обязательные component feasibility inputs A–D и локальный stand `001-S` доступны, имеют disjoint roots и owner
  closeout.
- `M-G1`, `M-G2` и `M-G3` могут считаться закрытыми; C3 остаётся `pass_with_isolation`, а не main-process pass.
- Полный demo-flow не заявляется выполненным: VAD/assembler/RAG/application channels/context/report и full barge-in
  остаются deferred для следующего implementation plan.
- Изменения source/code/config и новые candidate probes в E не выполнялись.
- `M-G4` закрыт после owner review Map-002 и Map-002-I от `2026-09-02`; реализация Map-002 не входит в scope
  завершённого Map-001 и ведётся отдельной картой.
