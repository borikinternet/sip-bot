# 006-B closeout

Статус: `complete`  
Дата: `2026-09-04`

Подготовлен [`demo-runbook.md`](demo-runbook.md). Он содержит target preflight, запрет параллельного GPU-heavy
запуска, обязательный warmup, exact command финального r7, сценарий, expected artifacts, cleanup и честные ограничения.

Runbook не меняет runtime, не добавляет fallback и не выдаёт warmup за latency звонка. Для нового запуска предписывает
новый evidence root; исторический r7 остаётся эталоном воспроизводимого успешного прогона.
