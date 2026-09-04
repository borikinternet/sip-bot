# 001-B execution command manifest

Дата выполнения: 2026-08-27, Europe/Moscow.  
UTC timestamp фиксации evidence: `2026-08-27T10:37:14.0579532Z`.

| Slice | Команда/действие | Exit code | Evidence/result |
|---|---|---:|---|
| S0 | Проверка `001-A` closeout, WSL identity и pre-existing `git status --short` | 0 | `preflight.md`, `git-status.txt` |
| S1 | `curl -fL --retry 3 --output Python-3.14.7.tar.xz https://www.python.org/ftp/python/3.14.7/Python-3.14.7.tar.xz` | 0 | `runtime-manifest.json`, source SHA-256 |
| S1 | `sha256sum Python-3.14.7.tar.xz` | 0 | `3b48dac8fb59f62eaa67ac83c1eb12bda1b7a08406dd286e252c11a66be27f81` |
| S1 | `tar -xJf Python-3.14.7.tar.xz` | 0 | `/home/sipbot/src/cpython-build/Python-3.14.7` |
| S1 | `./configure --prefix=/home/sipbot/.local/cpython-3.14.7t --disable-gil --with-ensurepip=install --without-lto` | 0 | `runtime-manifest.json` |
| S1 | `make -j4` | 0 | CPython free-threading build; optional `_zstd` missing and explicitly recorded |
| S1 | `make install` | 0 | executable under `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` |
| S1 | identity command with `sysconfig`, `SOABI`, `Py_GIL_DISABLED`, `_is_gil_enabled` | 0 | `runtime-manifest.json` |
| S2/S3 | `tools/run_nogil_probe.ps1` / equivalent WSL command | 0, 0, 0 | `run-01` … `run-03` |

## Toolchain and package provenance

- Ubuntu package versions used for the build are listed in `runtime-dependencies.txt`.
- GCC: `13.3.0`; GNU Make: `4.3`.
- Source and executable digests are in `runtime-manifest.json`.
- No project/native package, SIP/RTP component, AI model or audio path was imported.

## Probe invocation

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc '/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/nogil_probe.py'
```

The probe emitted one JSON summary to stdout and no warning/error bytes to stderr on each run. The exact summaries,
exit codes and import stages are preserved under `run-01/`, `run-02/` and `run-03/`.
