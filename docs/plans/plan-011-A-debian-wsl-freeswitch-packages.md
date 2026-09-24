# План 011-A: Debian WSL, FreeSWITCH packages и startup

Уровень: `child plan`  
Идентификатор: `011-A`  
Статус owner review: `accepted — scope из Map-011 принят владельцем 2026-09-20`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-011`](plan-011-freeswitch-small-company-callcenter-workshop.md)

## Цель и проверяемый результат

Создать отдельный стандартный Debian WSL2, совместимый с Debian codename из закреплённого сообщения `@ru_freeswitch`, установить оттуда FreeSWITCH и добиться запуска FreeSWITCH systemd service при старте дистрибутива.

## Materialized rules

- Только репозиторий и инструкции из pinned message, после подтверждения codename и подписи метаданных. Недоступность pinned message — остановка, не повод подставить другой источник.
- Устанавливать пакеты штатным `apt`; не использовать `trusted=yes`, отключение проверки подписи, `apt-key`-обходы или ручную сборку исходников.
- Не трогать `docker-desktop`, `Ubuntu-24.04`, Docker или глобальный `.wslconfig`.
- Свободный запас перед установкой не менее 20 GiB. Нынешние Windows-диски: C около 53 GiB, D около 273 GiB свободно.
- WSL systemd service запускается, когда запускается сам дистрибутив; systemd не запускает WSL при старте Windows и не удерживает его живым.
- Пакет, версия, apt origin, unit, команда и exit code сохраняются в evidence.

## Write-set

- WSL: отдельный distro `Debian-Bookworm-FS` в `D:\WSL\Debian-Bookworm`; существующие registrations не заменяются.
- `config/workshops/freeswitch/apt/freeswitch.list`, `tools/workshops/configure_freeswitch_workshop.sh`,
  `docs/workshops/freeswitch-callcenter-runbook.md` и `artifacts/workshops/freeswitch-callcenter/011-A/`.
- Никакие файлы приложения и E:\ source repository не меняются.

## Выполнение

1. Получить exact текст закреплённого сообщения; извлечь repository URI и поддерживаемые codename. Проверить apt metadata и подпись.
2. Проверить WSL2 и свободный диск; выбрать Debian codename только после сопоставления с repo metadata.
3. Поскольку актуальный store alias `Debian` не гарантирует Bookworm, импортировать зафиксированный официальный Debian
   Bookworm rootfs штатной командой `wsl --import`; проверить hash, `/etc/os-release` и WSL version 2.
4. Подготовить systemd согласно официальной WSL инструкции только внутри новой Debian distro; перезапустить/заново открыть distro и проверить PID 1/systemd.
5. Подключить подтверждённый signed apt repository, выполнить `apt update`, проверить origin и доступность FreeSWITCH + `mod_callcenter` package; установить FreeSWITCH и стандартный vanilla configuration.
6. Проверить, что пакет поставляет `freeswitch.service` и нужную config. Не создавать собственный service unit.
7. Включить `systemctl enable freeswitch`; перезапустить distro (`wsl --terminate Debian`, затем `wsl -d Debian --exec systemctl is-active freeswitch`), проверить active status, `fs_cli -x status`, SIP profile listener и отсутствие failed units.

## Blockers

- `011-A-B1`: `resolved 2026-09-21` — владелец передал exact mirror lines для buster/bullseye/bookworm.
- `011-A-B2`: `resolved 2026-09-21` — Bookworm metadata подписана FreeSWITCH Packaging Key, пакеты и модуль доступны.
- `011-A-B3`: `resolved 2026-09-21` — штатный `freeswitch.service` enabled/active после `wsl --terminate` и нового старта.

## Acceptance и evidence

`011-A` получает `complete`, только если package provenance/authenticity, Debian codename, WSL/systemd state, FreeSWITCH package version, module package, service-enabled state, post-termination startup и exact commands доказаны в `artifacts/workshops/freeswitch-callcenter/011-A/`. При `011-A-B1/B2` execution status становится `blocked` с raw evidence и condition promotion.

## Execution closeout — 2026-09-21

- Импортирован Debian 12.15 Bookworm rootfs с SHA-256
  `EAAC70C68ABDF6FFACF6DE10D31ED9DE4813505D1A794EB7393CB27FCEB624A6` в WSL2
  `Debian-Bookworm-FS`; PID 1 — systemd, default user — `sipbot`.
- Подключён owner-provided `http://fi.itlnk.ru/freeswitch bookworm main` через отдельный signed-by keyring; fingerprint
  `655DA1341B5207915210AFE936B4249FA7B0FB03`; insecure apt options не применялись.
- Установлены FreeSWITCH/meta-vanilla/mod-callcenter/systemd версии
  `1.11.3-release-33213556856-ef32e20529~bookworm~amd64-1~bookworm+1`.
- После clean WSL restart unit `enabled`/`active`, failed units `0`, `fs_cli` ready; evidence:
  [`011-A/environment-and-packages.md`](../../artifacts/workshops/freeswitch-callcenter/011-A/environment-and-packages.md).
- Scope выполнен полностью; открытых blocker или упрощений нет.
