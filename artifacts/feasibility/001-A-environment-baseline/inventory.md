# 001-A environment inventory

Дата: 2026-08-27  
Статус: `complete` в scope environment baseline

## Итоги

| Область | Результат | Статус |
|---|---|---|
| WSL/Ubuntu | Ubuntu 24.04.4 LTS, x86_64, WSL2 kernel 6.6.87.2 | `pass` |
| User/sudo | default `sipbot`, uid 1000, sudo bootstrap подтверждён без публикации секрета | `pass` |
| Windows disk | C: free `85,727,649,792` bytes | `pass`, выше 20 ГБ |
| Linux disk | `/dev/sdf`, available `1,024,027,754,496` bytes | `pass`, выше 20 ГБ |
| GPU from Windows | RTX 5060 Ti, driver 610.88, 16311 MiB | `pass` |
| GPU from Ubuntu | RTX 5060 Ti, driver 610.88, 16311 MiB | `pass` |
| CUDA driver API | `/usr/lib/wsl/lib/libcuda.so.1` присутствует | `present` |
| CUDA toolkit compiler | `nvcc` отсутствует | `absent`, не скрыто |
| Base tooling | build-essential, pkg-config, git, curl, wget, tar, xz-utils установлены | `pass` |
| Linux source placement | `/home/sipbot/src/sip-bot` на Linux ext4, доступен `sipbot` | `pass` |
| Linux project checkout | `.git`/revision отсутствуют; source content и коммиты проекта пока не созданы | `not applicable yet` |

## Blockers

Активных обязательных blocker-ов нет. `B-001-A-003` остаётся `open on trigger`: он срабатывает, если canonical
source root станет недоступен, будущий source окажется только под `/mnt/c` или окажется недоступен `sipbot`.
Отсутствие checkout/revision сейчас не блокирует baseline, поскольку проект пока не содержит source content и коммитов.
`B-001-A-005` не открыт; наличие `libcuda.so.1` подтверждено, а необходимость `nvcc`/toolkit для конкретных
кандидатов будет установлена в следующих component plans.

## Hand-off

Проверки WSL, user, source root, disk, GPU/CUDA visibility и generic tooling готовы. Linux-side checkout/revision будут
добавлены в эту проверку, когда появится source content; это не требует копирования dirty Windows workspace. `001-B`
можно открыть.
