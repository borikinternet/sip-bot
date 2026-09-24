# План 019-A: две чистые WSL-дорожки и сетевой preflight

Уровень: `child plan`  
Статус: `proposed; не исполнялся`  
Owner review: `pending вместе с Map-019`  
Родитель: [`Map-019`](plan-019-dual-wsl-freeswitch-live-masterclass.md)

## Цель и граница

**До открытия занятия** подготовить два **разных** Debian 12 WSL2-дистрибутива на одном Windows-хосте с одинаковым чистым baseline и изолированными файловыми write-set. Названия по умолчанию `Debian-FS-Human`, `Debian-FS-Agent`; существующие одноимённые дистрибутивы не удалять/переиспользовать без явного решения. Проверить ≥20 GiB свободного места для каждого экземпляра и подтвердить реальное разделение/совместное использование адресов и портов. Зафиксировать порядок exclusive service/live windows. FreeSWITCH на обеих дорожках ещё отсутствует; только так 60-минутное сравнение начинается с равной линии. Время этого preflight не засчитывается ни одному участнику.

Входит: WSL/rootfs, версии, хеш, дисковый бюджет, имена/пути, сетевой/socket audit, выделение MicroSIP-каталогов. Не входит: FreeSWITCH installation, SIP test, Docker, изменение глобального `.wslconfig`, изменение исторического `Debian-Bookworm-FS`.

## Materialized rules и source-map

| Источник | Правило | Применение / проверка | Stop condition |
|---|---|---|---|
| [APG](../architectural-planning-gate.md) §§3, 5 | До исполнения зафиксировать scope, source-map, test/evidence и blocker каждого slice | Этот план закрывает только одинаковую исходную среду, не SIP acceptance | Нет двух доказанных исходных экземпляров |
| [Development guidelines](../development-guidelines.md) §§1, 4, 7–8 | Непересекающиеся write-set, запрет молчаливого fallback и частичного closeout | Проверить WSL names/paths; не трогать чужой distro; итог `complete` или `blocked` | Требуется удалить/изменить чужой дистрибутив |
| [Documentation process](../documentation-process.md) §6 | Новый запуск получает своё evidence; исторические результаты не подменяют его | Evidence только `artifacts/workshops/freeswitch-dual-wsl-019/019-A/` после исполнения | Нет собственных логов preflight |
| [Microsoft WSL issue #4304](https://github.com/microsoft/WSL/issues/4304) | WSL2-дистрибутивы могут разделять network namespace и конфликтовать по порту | Сравнить `hostname -I`, `ss -lntup` обеих дорожек; назначить exclusive windows | Нельзя доказать отсутствие конфликта при запуске |

Target: Windows PowerShell + два WSL2 Debian 12. Команды выбора rootfs/hash и установки systemd берутся из [учебного сценария](../workshops/freeswitch-callcenter-masterclass.md) §§1–2; обе дорожки используют одну и ту же проверенную загрузку, но собственные директории импорта. Никакой native Python/runtime probe здесь не нужен.

Write-set H: только `Debian-FS-Human` и его каталог; write-set A: только `Debian-FS-Agent` и его каталог. Общий `wsl --list -v`, хостовая сеть, каталог проекта — read-only audit. Запрет: `wsl --shutdown`, `wsl --unregister` любого дистрибутива, Docker и глобальный network hack. MicroSIP-пары получают разные каталоги; их одновременный запуск не требуется.

## Порядок и acceptance

1. Ведущий назначает имена и директории, проверяет отсутствие незнакомого совпадения и свободное место.
2. Каждая дорожка импортирует тот же Debian 12 rootfs либо получает подготовленный **чистый** экземпляр; фиксирует SHA-256, `/etc/os-release`, WSL version, PID 1/systemd.
3. Ведущий сравнивает адреса/socket ownership обеих дорожек, объявляет расписание exclusive installation/start/live windows. Общий namespace не пытаются скрыть.
4. Фиксируются стартовые timestamp, конфигурация Windows MicroSIP-каталогов и целевые evidence roots. До этого B не запускается.

Test/evidence: `wsl --list --verbose`, `Get-FileHash` rootfs, `wsl -d <имя> -- cat /etc/os-release`, `ps -p 1 -o comm=`, `hostname -I`, `ss -lntup`, дисковый остаток и выбранные пути с exit codes. Акустика/SIP здесь неприменимы, потому что FreeSWITCH ещё не установлен. Владелец поведения по §5.3A APG: WSL-host/ведущий владеет назначением и расписанием shared ресурса; нового software owner не создаётся.

## Blocker register и closeout

| ID | Триггер | Что блокирует | Owner | Проверка/снятие | Статус |
|---|---|---|---|---|---|
| B-019-A-1 | Нет двух независимых чистых distro или места | B–D | ведущий | Два имени/пути, одинаковый Bookworm, ≥20 GiB каждый | `open until preflight` |
| B-019-A-2 | Конфликт общего host/network ресурса не учтён | Живой gate | ведущий | `ss`/адреса и расписание окон | `open until preflight` |

Fallback: `none`. Закрыть план только при полном preflight двух дорожек и собственном evidence; наличие уже готового исторического WSL не считается второй новой дорожкой. План не содержит execution report.
