# 011-B — два MicroSIP и прямой вызов

Дата: `2026-09-21`  
Технический результат: `pass`  
Полный acceptance: `pass`

## Endpoints

- MicroSIP portable `3.22.16`, официальный archive SHA-256
  `B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4`.
- Caller `1000`: UDP 5062, RTP 40000–40100, PCMU only.
- Agent `1001`: UDP 5064, RTP 40200–40300, PCMU only.
- Оба endpoint зарегистрированы в internal profile FreeSWITCH как `Registered(UDP)` и `Reachable`.

## Clean-start direct call

После остановки/старта WSL и повторного запуска MicroSIP вызов `1000 → 1001` дал:

```text
caller leg: inbound, destination 1001, ACTIVE
agent leg: outbound, destination 1001, ACTIVE
read codec:  PCMU / 8000 Hz / 64000 bit/s
write codec: PCMU / 8000 Hz / 64000 bit/s
call count: 1; channel count: 2
```

Вызов создан опубликованной MicroSIP CLI-командой `MicroSIP.exe 1001`, ответ — `MicroSIP.exe /answer`.
После `fs_cli -x "hupall"` channel count стал 0.

## Human acceptance

Владелец 2026-09-21 подтвердил слышимость собственного голоса во время live bridge. Вместе с двумя ACTIVE legs и
двунаправленным PCMU media contract это закрывает `011-B-B3`.
