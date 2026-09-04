# 006-D execution commands

Дата: `2026-09-05`  
Статус: `complete — target-20260905-r6 accepted`

## Preflight

Проверка свободного места перед target live gate:

```text
wsl.exe -d Ubuntu-24.04 -- df -Pk /mnt/c
```

Исторический результат исходного preflight:

```text
Filesystem     1024-blocks      Used Available Capacity Mounted on
C:\              384066556 371425500  12641056      97% /mnt/c
```

Свободно `12641056 KiB` (`12.64 GB` decimal), что меньше обязательного минимума `20 GB`; это объясняет исходную
остановку, но больше не является текущим состоянием.

## Accepted target

После очистки диска и освобождения GPU выполнен GPU-heavy target `map005_rehearsal_gate.py` для compact fixture:

```bash
cd /mnt/c/devel/sip-bot
export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs
/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/map005_rehearsal_gate.py \
  --output-root /mnt/c/devel/sip-bot/artifacts/report-preparation-20260904/006-D/target-20260905-r6 \
  --timeout-s 240 --post-report-grace-s 3
```

Результат: `pass`, 7/7 обязательных проверок, `gil_enabled=false`, `egress_underruns=0`, `callback_errors=0`,
stereo recording создана. Полный machine-readable result находится в `target-20260905-r6/map005-d-rehearsal.json`;
аудио-аудит — в `target-20260905-r6/audio-audit.md`.
