# 006-D closeout

Статус: `complete`  
Дата: `2026-09-05`  
Target evidence: `target-20260905-r6`

## Результат

После освобождения диска обязательный preflight прошёл: на диске проекта доступно около `127.6 GiB`,
при требовании не менее `20 GB`. GPU-heavy запуск выполнен последовательно в утверждённом C4 free-threading
runtime; модель и production source не изменялись.

Принятый target gate: [`map005-d-rehearsal.json`](target-20260905-r6/map005-d-rehearsal.json).
Результат: `pass`, все `7/7` проверок.

- compact fixture profile: `compact-demo-v1`, длительность около `83.94 s`;
- SIP/RTP: PCMU, 8000 Hz, mono, negotiated `ptime=20 ms`;
- follow-up/context, barge-in, unknown-answer/offer-transfer, operator transfer и report — `pass`;
- Baresip raw `enc`/`dec` tracks и stereo recording — `pass`;
- runtime: CPython `3.14.7t`, `gil_enabled=false`;
- warmup завершён до приёма звонка.

## Playback и аудио

Playback counters: `egress_underruns=0`, `callback_errors=0`, overflow/stale/cancelled drops отсутствуют;
после завершения `buffered_bytes=0`, `pending_frames=0`. Это подтверждает исправленный dynamic bounded
TTS accumulation/frame pacing path.

Аудио-аудит сохранён в [`target-20260905-r6/audio-audit.md`](target-20260905-r6/audio-audit.md), stereo-файл
доступен в [`target-20260905-r6/recordings/conversation-stereo.wav`](target-20260905-r6/recordings/conversation-stereo.wav).
Многосекундного mid-stream исчезновения TTS, наблюдавшегося в r7, в принятом r6 не обнаружено.

## Неудачные попытки и границы вывода

- r1: остановлен до звонка из-за неработавшего после остановки Ubuntu Ollama (`Connection refused`);
- r2: низкоуровневый J4 pass без recording wrapper;
- r3: тот же внешний Ollama precondition;
- r4/r5: recording создан, но отдельные запуски дали nondeterministic ASR/runtime scenario failures;
- r6: чистый recording gate pass.

Исторические r7/r10 artifacts не перезаписывались. Project license, содержательная редактура доклада,
публикация и production hardening остаются за пределами технического closeout.
