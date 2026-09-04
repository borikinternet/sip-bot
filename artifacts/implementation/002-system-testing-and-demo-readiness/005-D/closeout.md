# 005-D closeout

Статус: `complete`  
Дата: `2026-09-04`  
Исполнитель: main executor  
Финальный evidence root: [`target-20260904-r7`](target-20260904-r7/)

## Результат

Выполнен clean-start full live rehearsal на target Ubuntu 24.04/WSL2 и CPython `3.14.7t` с отключённым GIL.
Один локальный Baresip peer провёл реальный SIP/RTP-вызов с PCMU/8000 Hz/mono, а второй локальный peer подтвердил
перевод на оператора. J4 внутри rehearsal завершился `pass`: follow-up/context, barge-in, unknown-answer/offer-transfer,
operator transfer и terminal report присутствуют; pipeline/wiring ошибок нет.

## Evidence

- requirement matrix: [`requirement-matrix.md`](target-20260904-r7/requirement-matrix.md);
- freeze checklist: [`freeze-checklist.md`](target-20260904-r7/freeze-checklist.md);
- raw Baresip `enc`/`dec` и manifest: [`recordings/`](target-20260904-r7/recordings/);
- stereo artifact: [`conversation-stereo.wav`](target-20260904-r7/recordings/conversation-stereo.wav);
- dialogue report: [`report.md`](target-20260904-r7/reports/j4-full-live-call/report.md);
- complete machine-readable gate result: [`map005-d-rehearsal.json`](target-20260904-r7/map005-d-rehearsal.json).

Stereo mapping: left=`user_to_bot`, right=`bot_to_user`. Raw tracks сохранены. Из-за разницы времени завершения
media-пайплайнов левый raw track был дополнен в конце `27360` явными нулевыми PCM-кадрами (`3.42 s`); эта операция
зафиксирована в `recording-manifest.json` и не меняет raw evidence.

## Проверки

```text
map005 source-mode/recording/rehearsal tests: 7 passed
full target regression: 151 passed, 2 skipped in 9.50s
J4 rehearsal: pass, 6/6 scenario checks
runtime: CPython 3.14.7t, gil_enabled=false
media: PCMU/8000/mono, ptime=20 ms, drops=0, egress_underruns=0, callback_errors=0
```

Финальный runner применяет in-memory `pjsua2.EpConfig().medConfig.noVad=True`, чтобы idle media передавалась явными
RTP-кадрами и Baresip decode-запись сохраняла временную ось. Это тестовая настройка runner-а; application source,
закрытый J4 и production recording не изменялись.

## Корректирующие попытки и ограничения

Попытки `r1`–`r6` сохранены. Исправлены рекурсия monkeypatch, target library path/result handling и sparse decode
timeline; `r4` дал единичную позднюю ASR-ошибку после transfer и не был принят, `r6` — нестабильный corrective run
с незавершившимся внешним operator peer. После D-r5 обнаружена и исправлена финальная гонка TTS/media-egress:
добавлен typed `DRAINING`, а `r7` повторил тот же сценарий с ошибками wiring/pipeline `0`, полным transfer и
`egress_underruns=0`; он принят как финальный.

Известное ограничение качества не маскируется: общая задержка final phrase→first PCM превышает ориентир комфорта
200–500 ms, как зафиксировано в closeout `005-C`. Это не blocker Map-005, поскольку требование предписывает измерить
и показать деградацию, а не объявляет этот ориентир бинарным запретом для MVP.

Нерешённых category-4 blocker-ов и новых owner-review вопросов нет. `TASK-008` синхронизирован и закрыт.
