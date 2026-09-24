# 009-C C1 — preflight и healthcheck

Дата проверки: 2026-09-13.

## Результат

- Docker Desktop: доступен (`desktop-linux`); compose поднимает fixture.
- WSL: `Ubuntu-24.04` доступна.
- FreeSWITCH image: `safarov/freeswitch@sha256:b31c743f4c911a19687c61e3214968f2a24f93f9d3d667cc26284192e158ffc6`, версия `1.10.12`.
- Контейнер: `sip-bot-freeswitch-workshop`, состояние `running`, health `healthy`, `RestartCount=0`.
- Свободное место на проверенных дисках Windows: больше установленного минимального бюджета 20 GiB.

## Проверка healthcheck

Команда, выполненная напрямую внутри контейнера:

```text
docker exec sip-bot-freeswitch-workshop fs_cli -x status
```

Exit code: `0`.

Нормальный результат начинается с:

```text
UP ...
FreeSWITCH (Version 1.10.12 ...) is ready
```

Итог: проверка `fs_cli -x status` подтверждает готовность FreeSWITCH. Текущий
healthcheck использует тот же status API и проверяет только начало `UP`; на
текущем fixture он проходит. Это не является доказательством успешного SIP
вызова.

## Security/evidence

В evidence не записываются startup-логи с паролями, SIP Authorization headers
или значения credential. Probe сохраняет только санитизированные строки;
`raw_logs_persisted=false`. Случайный пароль upstream entrypoint не принимается
как доказательство workshop readiness.
