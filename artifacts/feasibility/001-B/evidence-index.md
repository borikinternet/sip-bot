# 001-B evidence index

Статус исполнения child plan: `complete`; runtime decision: `pass`  
Дата: 2026-08-27

| Evidence ID | Результат | Файл |
|---|---|---|
| `E-001B-ENV-001` | `pass`: `001-A` закрыт, target WSL identity и pre-existing status зафиксированы | `preflight.md`, `git-status.txt` |
| `E-001B-ID-001` | `pass`: CPython 3.14.7, free-threaded executable, SOABI, provenance и SHA-256 | `runtime-manifest.json` |
| `E-001B-GIL-001` | `pass`: `Py_GIL_DISABLED == 1` | `run-01/runtime-probe.json` (повторено в run-02/run-03) |
| `E-001B-GIL-002` | `pass`: GIL `False` до и после каждого explicit stdlib import и после import phase | `run-01/runtime-probe.json`, `run-02/runtime-probe.json`, `run-03/runtime-probe.json` |
| `E-001B-GIL-003` | `pass`: stderr не содержит automatic-GIL warning; каждый запуск завершён с exit code 0 | `run-*/stderr.log`, `run-*/exit-code.txt` |
| `E-001B-CONC-001` | `pass`: три чистых повтора, checksum `3115622`, без exception/timeout/deadlock | `run-*/runtime-probe.json` |
| `E-001B-REP-001` | `pass`: команда, paths, versions, digests, stdout/stderr и exit codes сохранены | `commands.md`, `runtime-manifest.json`, `probe-manifest.json` |

## Boundary audit

- Импортировались только stdlib-модули из manifest; project/native imports отсутствуют.
- SIP/RTP, ASR, VAD, LLM, TTS, audio, model inference и application channels не запускались.
- `_zstd` не собран как необязательный stdlib-модуль; это не скрыто и не влияет на этот runtime gate.
- Порог свободного места и GPU facts принадлежат `001-A`; здесь они не переснимаются и не дублируются.
