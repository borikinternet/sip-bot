# Map-010-A execution evidence

Дата: 2026-09-14

## Результат

`010-A1`–`010-A4` выполнены. В `PcmAudioBridge` добавлен внутренний
`ComfortNoiseSource`, который выдаёт exact-size PCM16 S16LE для каждого
запрошенного PJMEDIA-кадра в `IDLE`, `PREROLL`, `DRAINING`, `CANCELLED` и
egress fallback. Источник не блокируется, не пишет в TTS buffer и не публикует
события. Уровень задаётся `config/constants.py` через
`COMFORT_NOISE_LEVEL_DBOV_MAGNITUDE` (текущий execution candidate: `50`).

В существующий `EpConfig.medConfig.noVad` передаётся typed-параметр
`SIP_MEDIA_NO_VAD=True`. Обновлены config projection и contract fixtures.

## Проверки

| Проверка | Результат |
|---|---|
| Focused source/config/media/registration tests | `32 passed` |
| Полный затронутый non-GPU lane | `191 passed, 5 skipped` |
| Target comfort-noise probe | CPython `3.14.7t`, `Py_GIL_DISABLED=1`, GIL `False` до/после import и operation, `320` bytes, non-zero |
| Target PJSUA2 no-VAD probe | `pjsua2.EpConfig().medConfig.noVad=True`, GIL `False` до/после import и operation |
| Registry/backlog audit | выполняется после обновления статусов |

Target probe выполнялся без GPU inference; отдельный live RTP gate остаётся в
`010-C`.

## Изменённые границы

- `ComfortNoiseSource` — private in-process helper существующего
  `PcmAudioBridge`, не новый delivery owner.
- `PcmAudioBridge` продолжает считать `PLAYING`-empty кадры настоящими
  `egress_underruns`; intentional idle source не маскирует эту метрику.
- RFC 3389/CN/PT13 и SDP не добавлялись.

## Передача

`010-A` закрыт бинарным статусом `complete`. Следующий исполняемый child plan —
`010-B`: strict raw Baresip `enc`/`dec` timeline audit.
