# 001-A closeout

Статус исполнения child plan: `complete`  
Дата: 2026-08-27

## Выполнено

- A-001: Ubuntu/WSL/user/sudo/bootstrap и dirty-worktree inventory;
- A-003: host/Ubuntu GPU visibility, CUDA driver/toolkit distinction и disk threshold;
- A-004: generic OS/tooling manifest, APT update и установка build/inventory tooling;
- A-002: canonical Linux source root создан и проверен на ext4 под `sipbot`; checkout/revision пока неприменимы,
  поскольку проект ещё не содержит source content и коммитов.

## Ограничение результата

Linux source root пока пуст: Windows repository не имеет коммитов, а рабочее дерево содержит незакоммиченные документы
и tooling. Автоматическая копия dirty-содержимого не выполнялась и не требуется для этого baseline. Когда появится
первый source content, нужно повторить E-001-A-SRC-001 и зафиксировать repository root, revision и worktree state.

Активных обязательных blocker-ов нет. `001-B` открыт к execution; CPython, native imports, модели и аудио в `001-A`
не запускались.
