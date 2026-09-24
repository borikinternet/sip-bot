# 011-C — mod_callcenter, очередь и агент

Дата: `2026-09-21`  
Технический результат: `pass`  
Полный acceptance: `pass`

## Configuration

- `mod_callcenter` установлен отдельным apt package и включён в пакетном `modules.conf.xml`.
- Queue: `support@default`, strategy `longest-idle-agent`, MOH `local_stream://moh`.
- Agent: `1001@default`, type `callback`, status `Available`.
- Contact: `[leg_timeout=15]user/1001@$${domain}`; при загрузке развёрнут в фактический WSL domain/IP.
- Tier: queue `support@default`, agent `1001@default`, state `Ready`, level/position `1/1`.
- Dialplan destination: `7000`, actions `answer` и `callcenter support@default`.

Пакетный пример `user/1001@default` в этой vanilla installation не соответствует directory domain. Первый probe дал
`SUBSCRIBER_ABSENT`, три мгновенных no-answer и `On Break`. Исправление на `$${domain}` устранило причину; скрытый
fallback не вводился.

## First and clean-start repeats

Оба технических прогона прошли. В clean-start repeat до ответа агента:

```text
member state: Trying
serving agent: 1001@default
agent state: Receiving
caller channel: ACTIVE, PCMU
agent channel: RINGING
```

После MicroSIP `/answer`:

```text
member state: Answered
agent state: In a queue call
calls_answered incremented
caller channel: ACTIVE, PCMU/8000/64000 read+write
agent channel: ACTIVE, PCMU/8000/64000 read+write
channel count: 2
```

После `hupall` channel count — 0. Module/queue/agent/tier пережили `wsl --terminate` и старт дистрибутива.

## Human acceptance

Владелец 2026-09-21 подтвердил, что final live sequence акустически произошла именно как описано: ожидание, ответ и
слышимость собственного голоса. Probe оставил caller в `Trying` на пять секунд с `moh-sound=local_stream://moh`, затем
получил `Answered` и два ACTIVE PCMU legs. `011-C-B4` закрыт; runbook сохраняет ручную проверку для нового стенда.
