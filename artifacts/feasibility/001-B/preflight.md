# 001-B preflight

Дата: 2026-08-27, Europe/Moscow  
Статус: `pass`

## Prerequisites

- `001-A` имеет `foundation complete`; основной evidence: `../001-A-environment-baseline/closeout.md` и
  `../001-A-environment-baseline/inventory.json`.
- Авторитетная среда: Ubuntu 24.04.4 LTS x86_64 в WSL2; WSL distro и GPU visibility подтверждены в `001-A`.
- Canonical Linux source root `/home/sipbot/src/sip-bot` существует на ext4 и доступен `sipbot`. Проект пока не
  содержит source content и коммитов, поэтому checkout/revision в этом preflight имеют значение `not applicable yet`.
- `001-B` принят к execution 2026-08-27; новые user decisions для запуска не требуются. Точная stable версия
  CPython выбирается ниже по execution procedure и фиксируется digest-ом.

## Pre-existing worktree

Windows worktree был зафиксирован до начала `001-B`. В нём присутствуют staged `.idea`-файлы и untracked
`.codex/`, `.gitignore`, `.idea/deployment.xml`, `.idea/misc.xml`, `artifacts/`, `docs/`, `tools/`. Эти изменения
не принадлежат `001-B` и не синхронизируются в Linux source root.

Полный снимок состояния и команда запуска относятся к этому evidence root; новые файлы `001-B` создаются только в
`artifacts/feasibility/001-B/` и в явно разрешённом внешнем WSL prefix/temporary build path.

## Gate decision

`B-001B-001`, `B-001B-002` и `B-001B-003` не сработали: prerequisite `001-A` закрыт, owner review зафиксирован,
а pre-existing status сохранён. Можно выполнять `B-001B-S1`.
