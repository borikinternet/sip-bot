# 001-D input evidence index

Дата исполнения: `2026-08-27`  
Статус входного gate: `pass`

Этот индекс фиксирует только входы для синтеза D. Raw evidence не копируется и не изменяется: авторитетными остаются
closeout и stage-specific records соответствующего child plan.

## 1. Environment и runtime

| D input | Source evidence | Что подтверждено | Exact command/provenance | Runtime / workdir | stdout/stderr/exit |
|---|---|---|---|---|---|
| `D-IN-A-ENV` | `../001-A-environment-baseline/closeout.md`, `commands.md`, `inventory.json` | Ubuntu 24.04.4 LTS, WSL2, `sipbot`, ext4 source root, RTX 5060 Ti, 20 GiB minimum free-space threshold | Exact command set in `../001-A-environment-baseline/commands.md` (`wsl.exe`, Ubuntu identity/GPU/disk/source probes) | Host + Ubuntu-24.04 WSL2; source root `/home/sipbot/src/sip-bot` | Raw outputs in `../001-A-environment-baseline/raw/`; child plan closeout `complete` in environment scope |
| `D-IN-B-ID` | `../001-B/runtime-manifest.json`, `evidence-index.md` | CPython `3.14.7t`, SOABI `cpython-314t-x86_64-linux-gnu`, `Py_GIL_DISABLED=1` | Exact build/probe commands in `../001-B/commands.md` | Ubuntu-24.04 WSL2; `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` | `run-01`–`run-03` stdout/stderr and exit-code files; all exit `0` |
| `D-IN-B-GIL` | `E-001B-GIL-001`–`E-001B-GIL-003`, `../001-B/run-*/runtime-probe.json` | GIL disabled before/after explicit imports; no automatic-GIL warning; controlled concurrency repeated three times | `../001-B/commands.md`, `run-*/command.txt` | Same CPython free-threaded runtime | `run-*/stderr.log`, `run-*/exit-code.txt`; pass |

## 2. Component decisions

| D input | Source evidence | Candidate / decision | Exact command/provenance | Process boundary | Result |
|---|---|---|---|---|---|
| `D-IN-C1-CAND` | C1 `candidate-manifest.json`, `evidence-index.md`, `closeout.md` | PJSUA2 + PJMEDIA `2.17`; SWIG `4.2.0`; two explicit generated-wrapper patches | Build, import and probe commands retained in `../001-C1-sip-pjsua2-pjmedia/commands.md` | Tested in main free-threaded CPython process | `pass` within recorded patch/test limits |
| `D-IN-C1-IMPORT` | `patched-import-lifecycle.json` and `unpatched-import-lifecycle.json` | Unpatched binding re-enabled GIL; patched binding imported/initialized with GIL disabled | `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -X faulthandler /mnt/c/devel/sip-bot/tools/feasibility/pjsua2_pjmedia_probe.py --output .../patched-import-lifecycle.json --initialize` | Main process; exact patches in `patches/` | Patched exit `0`; negative unpatched result retained |
| `D-IN-C1-SIP-MEDIA` | `../001-S-voip-test-stand/{lifecycle,pcmu,bye,transfer}.json`, C1 closeout | SIP lifecycle, PCMU/8000/1 RTP and BYE during active work pass; transfer is stand-only | Exact peer commands retained in `../001-C1-sip-pjsua2-pjmedia/commands.md` and `001-S` evidence | Product candidate + separate local peer process | Pass for tested lanes; full application integration not claimed |
| `D-IN-C2-CAND` | C2 `C2-OR-001`–`C2-OR-007`, `candidate-freeze.md`, `runtime-manifest.json` | `ASR-PRIMARY-001-faster-whisper`, `faster-whisper==1.2.1`, large-v3 revision `edaa852...`; CTranslate2 `4.8.1` patched | Exact candidate/build/download provenance in `../001-C2/commands-and-versions.txt` and `patch-build.md` | Tested in main free-threaded CPython process | Primary accepted; no fallback |
| `D-IN-C2-IMPORT` | `C2-OR-003`, `import-no-gil-before-patch.json`, `import-no-gil.json` | Unpatched CTranslate2 re-enabled GIL; patched binding and listed imports pass | Exact import command stored in `import-no-gil.json.command` and `../001-C2/evidence-index.md` | Main process after exact local patch | Pass after patch |
| `D-IN-C2-OPERATION` | `C2-OR-008`, `operation.json`; `C2-OR-009`, `partial-final.json` | CUDA/int8_float16 operation pass; partial revisions and authoritative final observed | Exact commands are recorded in both JSON records | Main process; partial/final data path observed | Pass; model load `8.375 s`; final text non-empty and Russian |
| `D-IN-C2-CANCEL` | `C2-OR-010`, `cancellation.json`, C2 closeout | Generator close and stale suppression pass; no independent native cancel token | Exact cancellation command is recorded in `cancellation.json.command` | Main process; channel-close semantics at candidate boundary | Pass with explicit hard-native-cancel limitation |
| `D-IN-C3-CAND` | C3 `E-C3-CANDIDATE-001`, `candidate-manifest.json`, closeout | Qwen3.5-9B Q4_K_M; Ollama `0.33.1`; bundled native CUDA runner | Exact preparation/GPU command shape and artifact provenance in `../001-C3-llm-primary/measurements.md` and `Modelfile` | Main no-GIL controller + separate local native Ollama process | `pass_with_isolation`, owner accepted 2026-08-27 |
| `D-IN-C3-RESULT` | `E-C3-QUESTION-001`/`E-C3-TOKEN-001` via `inference.json`, `measurements.md` | Structured JSON `action=answer`, Russian text; warm first useful `177.400 ms`, valid response `2121.229 ms` | GPU command shape in `measurements.md`; result record in `inference.json` | HTTP over `127.0.0.1`; no native inference import in controller | Pass for tested fixture; not a statistical benchmark |
| `D-IN-C3-VRAM-CANCEL` | `E-C3-VRAM-001`, `vram.json`; `E-C3-CANCEL-001`, `cancellation.json` | Peak `8227 MiB` of `16311 MiB`, no OOM; client stream close suppresses stale result | Exact probe command shape in `measurements.md`; records retain timings/paths | Isolated native server; client-side cancellation boundary | Pass with no separate native cancellation acknowledgement |
| `D-IN-C4-CAND-IMPORT` | C4 `E-C4-SELECT-001`, `E-C4-PATCH-001`, `E-C4-IMPORT-001`, evidence-index and closeout | XTTS-v2 v2.0.3; exact torchaudio/tokenizers/MAS no-GIL patches; Triton disabled | Exact package/import commands in `../001-C4-tts-primary/commands.md`; stage records retain command and exit code | Tested in main free-threaded CPython process | Pass for patched path |
| `D-IN-C4-AUDIO` | `E-C4-PCM-001`, `E-C4-LATENCY-001`, `E-C4-AUDIO-001`, `E-C4-PCMU-001` | Four PCM chunks; first PCM `1308.4 ms`, complete `1776.8 ms`; WAV and PCMU/8000/1 boundary pass | Exact operation/PCMU commands in `operation.stdout.json` and `pcmu-boundary.stdout.json` | Main process; direct audio boundary | Pass for tested path |
| `D-IN-C4-CANCEL` | `E-C4-CANCEL-001`, `cancellation.json`, closeout | Generator close after first chunk; no stale PCM; no independent native cancel token | Exact command and exit `0` in `cancellation.stdout.json` | Main process; candidate-owned stream boundary | Pass with explicit hard-native-cancel limitation |

## 3. Input gate conclusion

1. Все обязательные dependency closeout доступны: A, B, C map, C1, C2, C3 и C4.
2. На каждый AI/VoIP-контур имеется ровно один accepted primary decision; fallback не запускался.
3. C3 имеет отдельную owner-approved process boundary; это не внешний/cloud API.
4. Для C1–C4 сохранены команды, версии, runtime и stage evidence; raw evidence принадлежит child roots.
5. D может продолжать synthesis. Не закрыты этим input gate: application-level thread affinity, совместная GPU
   нагрузка, сквозной channel lifecycle и full end-to-end call.
