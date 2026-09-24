# 011-A — Debian WSL и FreeSWITCH packages

Дата: `2026-09-21`  
Результат: `pass`

## Provenance

- Владелец передал строки зеркала `http://fi.itlnk.ru/freeswitch` для buster/bullseye/bookworm; выбран Bookworm.
- Debian rootfs: `debuerreotype/docker-debian-artifacts`, commit
  `8f962b15d7884a90e17876a9303cbac909d119aa`, `bookworm/oci/blobs/rootfs.tar.gz`.
- Rootfs: 48,503,440 bytes; SHA-256
  `EAAC70C68ABDF6FFACF6DE10D31ED9DE4813505D1A794EB7393CB27FCEB624A6`.
- Импорт: WSL2 `Debian-Bookworm-FS` в `D:\WSL\Debian-Bookworm`.
- OS: Debian GNU/Linux 12 (bookworm), фактический point release 12.15, x86_64.
- Apt source:
  `deb [signed-by=/usr/share/keyrings/freeswitch-packaging.gpg] http://fi.itlnk.ru/freeswitch bookworm main`.
- Signing key fingerprint: `655DA1341B5207915210AFE936B4249FA7B0FB03`, UID
  `FreeSWITCH Packaging Key <freeswitch@signalwire.com>`.
- `InRelease` signature проверена; insecure apt flags и `apt-key` не применялись.

## Installed packages

`freeswitch`, `freeswitch-meta-vanilla`, `freeswitch-mod-callcenter` и `freeswitch-systemd` установлены в версии:

```text
1.11.3-release-33213556856-ef32e20529~bookworm~amd64-1~bookworm+1
```

`apt-cache policy` показывает candidate и installed из `http://fi.itlnk.ru/freeswitch bookworm/main amd64`.

## Startup gate

После `wsl --terminate Debian-Bookworm-FS` и нового старта:

```text
PID 1: systemd
freeswitch.service enabled: enabled
freeswitch.service state: active
failed systemd units: 0
fs_cli: FreeSWITCH 1.11.3 ready
module_exists mod_callcenter: true
```

WSL semantics зафиксированы отдельно: systemd запускает FreeSWITCH при старте дистрибутива, но не запускает сам
дистрибутив при загрузке Windows и не удерживает WSL без открытого процесса.

## Files

- `config/workshops/freeswitch/apt/freeswitch.list`
- `tools/workshops/configure_freeswitch_workshop.sh`
- `docs/workshops/freeswitch-callcenter-runbook.md`
