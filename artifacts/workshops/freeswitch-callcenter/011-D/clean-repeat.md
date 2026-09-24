# 011-D — чистый повтор и runbook

Дата: `2026-09-21`  
Технический результат: `pass`  
Human audio: `pass — owner heard own voice during live bridge`  
Independent context-free review: `pass`

После `wsl --terminate Debian-Bookworm-FS` выполнены:

1. запуск дистрибутива с PID 1 `systemd`;
2. проверка `freeswitch.service`: `enabled`, `active`, failed units `0`;
3. автоматическая загрузка `mod_callcenter`;
4. повторное создание двух MicroSIP profiles по динамически определённому WSL IP;
5. две `Registered`/`Reachable` регистрации;
6. прямой вызов с двумя ACTIVE PCMU-каналами;
7. очистка вызова;
8. queue call: `Trying/Receiving/RINGING → Answered/In a queue call/ACTIVE`;
9. очистка вызова, channel count `0`.

Самодостаточная инструкция создана в `docs/workshops/freeswitch-callcenter-runbook.md`. Она содержит источник пакетов,
проверку подписи, rootfs/hash, точные команды, MicroSIP mapping, ожидаемые состояния, restart semantics, stop conditions и
diagnostics.

`011-D-B3` снят owner confirmation от 2026-09-21. Независимый субагент без истории переписки выполнил read-only review.
После исправления hardcoded drive, shell transitions, session variables, integrity checks, ExecutionPolicy, helper exit-code
и `adduser` prompts финальный verdict — `PASS`; blocking/major/minor findings нет.
