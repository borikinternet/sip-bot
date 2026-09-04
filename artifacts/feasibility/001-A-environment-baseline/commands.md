# 001-A command manifest

Date of execution: 2026-08-27, Europe/Moscow. Commands were run from the Windows workspace or Ubuntu-24.04 WSL2 as
indicated. Full concise outputs are stored under `raw/`.

| Evidence ID | Execution | Result |
|---|---|---|
| E-001-A-WSL-001 | `wsl.exe --status`; `wsl.exe --list --verbose` | pass; Ubuntu-24.04 and Docker Desktop are WSL2 distros |
| E-001-A-OS-001 | Ubuntu `/etc/os-release`, `uname`, `id`, `/etc/wsl.conf` | pass; Ubuntu 24.04.4, x86_64, WSL2 kernel, sipbot uid 1000 |
| E-001-A-USER-001 | Ubuntu user/group and existing sudo bootstrap reference | pass; sudo behavior recorded without secret |
| E-001-A-DISK-001 | Windows `Get-PSDrive C`; Ubuntu `df -B1 -P` | pass; both relevant filesystems exceed 20 GiB free |
| E-001-A-GPU-001 | Host and Ubuntu `nvidia-smi --query-gpu=...` | pass; RTX 5060 Ti visible from both |
| E-001-A-CUDA-001 | Ubuntu `command -v nvcc`; `ldconfig`; WSL `libcuda.so.1` check | pass with explicit absent toolkit compiler; driver API present |
| E-001-A-SRC-001 | `mkdir -p /home/sipbot/src/sip-bot`; `pwd`; `findmnt`; `df`; `stat`; `git rev-parse` | pass; Linux source root exists on ext4 and is accessible to `sipbot`; checkout/revision not applicable yet because the project has no source content or commits |
| E-001-A-PKG-001 | Ubuntu APT update/install and package inventory | pass; generic build/inventory manifest installed and recorded |
| E-001-A-WT-001 | Windows `git status --short` and source-path comparison | pass; dirty worktree classified, not copied |

No CPython, Python package, native component, model, audio or project runtime was imported or executed.
