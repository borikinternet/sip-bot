# 001-D evidence index

Дата: `2026-08-27`  
Статус: `pass`

Индекс открывает все claims D без копирования raw evidence. Подробный intake по A–C находится в
[`input-evidence-index.md`](input-evidence-index.md).

| Evidence ID | Claim | Source/output | Status |
|---|---|---|---|
| `E-001D-INPUT-001` | Все обязательные A–C closeout, owner decisions и disjoint evidence roots доступны | `input-evidence-index.md` | `pass` |
| `E-001D-MATRIX-001` | Для каждого C-контура есть единый candidate/process/status record; неопределённые affinity явно отмечены | `process-thread-boundary-matrix.md` | `pass with explicit undecided` |
| `E-001D-CONTROL-001` | Control plane принадлежит Dispatcher/SIP adapter по ownership rules; payload не транзитирует Dispatcher | `control-data-plane-map.md` | `pass with deferred integration` |
| `E-001D-BASELINE-001` | Baseline register нормализует C1–C4 без выбора кандидата «на глаз» | `baseline-register-draft.md` | `pass` |
| `E-001D-GAPS-001` | Unexpected gaps и deferred limitations различены; blocking architecture gap не найден | `unexpected-gaps.md` | `pass` |
| `E-001D-CLOSEOUT-001` | D-срезы, blockers, residual findings и handoff в E закрыты воспроизводимыми ссылками | `closeout.md` | `pass` |

## Source evidence policy

- A/B/C raw evidence, commands, logs, hashes и WAV остаются в исходных roots.
- `pass_with_isolation` не повышается до `main` и не означает, что native runtime проверен в основном Python-процессе.
- `undecided`/`deferred` — самостоятельные результаты D, а не скрытое разрешение на реализацию.

