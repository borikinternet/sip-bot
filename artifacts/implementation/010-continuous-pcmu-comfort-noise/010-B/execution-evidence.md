# Map-010-B execution evidence

Дата: 2026-09-14

## Результат

`010-B1`–`010-B3` выполнены. Первоначальная реализация ошибочно использовала
длительности raw Baresip `enc`/`dec` как общую шкалу. После owner correction
сборщик получает authoritative answered-call window `200 OK → BYE`/`media_stopped`,
вычисляет per-channel start offsets по timestamp создания в имени Baresip-файла
и сохраняет negotiated `ptime`, offsets, trimming и padding в manifest.

Strict gap rejection сохранён только для standalone-вызова без authoritative
event window; в live registered wrapper большой raw-duration gap больше не
блокирует формирование stereo, а RTP continuity проверяется отдельным audit.

Исторические результаты и artifacts не перезаписывались. Их gap остаётся
диагностикой raw recorder, а не основанием для вывода о пропуске RTP.

## Проверки

| Проверка | Результат |
|---|---|
| Stereo builder positive/equal timeline | pass |
| Allowed cleanup tail | `1` sample / `0.125 ms` accepted and declared in manifest |
| Large-gap negative fixture | `4001` samples over the `4000`-sample / `500 ms` limit rejected |
| Registered recording wrapper contract | raw tracks retained, mapping `left=user_to_bot`, `right=bot_to_user`, event-window policy and offsets present |
| Focused B tests | `10 passed` |

## Corrective live evidence — 2026-09-14

В `010-C/target-20260914-r12` запись проверена с реальным answered-call window:

- окно `200 OK → BYE`: `130224.563 ms`;
- raw `enc`: `129.880 s`, raw `dec`: `130.140 s`;
- обе дорожки начались на `5208` кадров (`651 ms`) раньше `200 OK` по timestamp
  Baresip-файла и были одинаково обрезаны до начала окна;
- stereo derivative: `1041797` кадров, `130.224625 s`, `status=pass`;
- manifest: `policy=answered_call_event_window`, start offsets, trimming и
  padding сохранены.

Сам full-AI target r12 имеет отдельный красный RTP diagnostic (`peer receive
6512` против adapter egress `6511`); это не связано со сборщиком записи и не
выдаётся за успешный Map-010 live closeout.

## Передача

`010-B` закрыт бинарным статусом `complete`. Следующий child plan — `010-C`:
clean registered full-AI live gate with continuous RTP and strict recording
audit.
