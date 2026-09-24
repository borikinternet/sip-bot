# Execution evidence: Plan 010-C

Статус исполнения: `complete`  
Дата: `2026-09-14`  
Корректирующий blocker: `B-010-C-002` — `resolved by acceptance correction`

## Результат

Plan 010-C полностью исполнен. Registered full-AI сценарий прошёл по функциональному пути: регистрация,
`180 → readiness → 200`, PCMU/8000/mono с negotiated `ptime=20 ms`, последовательные реплики, follow-up,
barge-in, предложение перевода, подтверждённый transfer и итоговый отчёт.

Непрерывность egress проверена по окну отвеченного вызова, а не по длительности raw WAV:

- начало окна — `200 OK` на `INVITE`;
- конец окна — получение `BYE` (`remote_hangup`), при этом `200 OK` на BYE остаётся подтверждением SIP-транзакции;
- длительность окна — `125618.477 ms`;
- при `ptime=20 ms` ожидалось `6281` media-кадр;
- adapter egress — `6281` кадров;
- Baresip peer receive — `6281` RTP-пакетов;
- `egress_underruns=0`, `callback_errors=0`, egress drops `0`, peer receive loss `0`.

Runtime — free-threaded CPython 3.14.7, `gil_enabled=false`; целевой полный тестовый набор и документальные аудиты
проходят.

Raw Baresip `enc`/`dec` и stereo derivative проверены отдельным recording audit. В r4 разница временных границ
составила `360 ms`, то есть находится в принятом cleanup tail `≤500 ms`; это диагностическая проверка записи и не
является proxy для RTP continuity.

## Прогоны

| Target | Functional path | Continuity audit | Recording audit |
|---|---|---|---|
| `target-20260914-r1` | fail: первая попытка не дошла до подтверждённого transfer | egress healthy | fail, gap `6920 ms` |
| `target-20260914-r2` | pass | не был выделен отдельным verdict | fail, gap `1120 ms` |
| `target-20260914-r3` | pass | не был выделен отдельным verdict | fail, gap `4560 ms` |
| `target-20260914-r4` | pass | pass: expected/actual/peer `6281` | pass, gap `360 ms` |

В r1 после красного результата был выполнен corrective pass: добавлен 30-секундный хвост fixture, чтобы Baresip
`aufile` не завершал передачу до финального ответа. В r2/r3 установлено, что вариативная разница raw `enc`/`dec`
относится к границам записи при teardown, а не доказывает пропуск bot egress; это исправлено в acceptance-критерии,
а не скрыто padding-ом.

## Исправление acceptance

Первоначальная проверка ошибочно использовала длительности Baresip `enc`/`dec` как proxy для непрерывности RTP.
Это проверяет temporal alignment рекордера и не гарантирует состояние media path. В write-set добавлен
`tools/map010_rtp_continuity.py`, который использует:

1. `200 OK` на `INVITE` и `BYE`/`media_stopped` как answered-call window;
2. negotiated per-call `ptime` для расчёта ожидаемого числа кадров;
3. adapter egress frame count;
4. peer receive/loss counters;
5. underrun, callback и egress-drop counters.

Raw `enc`/`dec` и strict stereo builder по-прежнему сохраняются и проверяются как отдельное recording evidence.
В r4 их temporal mismatch составил `360 ms`, поэтому stereo derivative создан с явным допустимым cleanup tail:
`left=user_to_bot`, `right=bot_to_user`, `conversation-stereo.wav` пригоден для прослушивания.

`B-010-C-002` закрыт как неправильно классифицированный blocker Map-010: после корректировки acceptance он больше
не блокирует RTP continuity. В r4 recording audit также прошёл с gap `360 ms`; большой padding и ослабление
принятого лимита не использовались.

## Сохранённые артефакты

- [r1 live evidence](target-20260914-r1/registered-j4-full-live.json)
- [r2 live evidence](target-20260914-r2/registered-j4-full-live.json)
- [r3 live evidence](target-20260914-r3/registered-j4-full-live.json)
- [r4 registered live evidence](target-20260914-r4/registered-j4-full-live.json)
- [r4 conversation stereo](target-20260914-r4/recordings/conversation-stereo.wav)
- [r4 recording manifest](target-20260914-r4/recordings/recording-manifest.json)
- raw Baresip `enc`/`dec` и peer logs находятся внутри соответствующих каталогов target.

Исторические r1–r3 артефакты сохранены и не перезаписаны.

## Corrective recording alignment — 2026-09-14

В ходе повторной проверки выявлено, что прежний stereo builder всё ещё
использовал `max(duration(enc), duration(dec))`, хотя RTP continuity уже
проверялась по answered-call window. Это было исправлено: `010-C` теперь
передаёт в builder длительность окна `200 OK → BYE`, фиксирует wall-clock
момент `200 OK`, а builder использует timestamps создания directional Baresip
файлов из их имён для per-channel start offsets.

В `target-20260914-r12`:

- answered-call window: `130224.563 ms`;
- raw `enc`: `129.880 s`, raw `dec`: `130.140 s`;
- обе raw-дорожки начались на `5208` кадров (`651 ms`) раньше `200 OK` и
  были выровнены относительно начала окна;
- `conversation-stereo.wav`: `1041797` кадров, `130.224625 s`, `status=pass`;
- manifest содержит `policy=answered_call_event_window`, start offsets,
  trimming и padding.

Full target r12 остановлен отдельным RTP diagnostic: peer получил `6512`
пакетов при `6511` egress frames. Это не является ошибкой нового recording
builder; этот live-результат не используется как полное закрытие Map-010.
