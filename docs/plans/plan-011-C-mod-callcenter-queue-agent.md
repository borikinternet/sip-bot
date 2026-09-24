# План 011-C: очередь mod_callcenter и MicroSIP agent

Уровень: `child plan`  
Идентификатор: `011-C`  
Статус owner review: `accepted — scope из Map-011 принят владельцем 2026-09-20`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-011`](plan-011-freeswitch-small-company-callcenter-workshop.md)  
Зависимость: [`011-B`](plan-011-B-microsip-two-endpoint-call.md)

## Цель и проверяемый результат

Загрузить имеющийся `mod_callcenter`, настроить vanilla queue, привязать к ней зарегистрированный MicroSIP `1001` как агента, направить вызов `1000` в очередь, зафиксировать ожидание и answer/bridge агентом.

## Materialized rules

- В исходном `E:\devel.arch\fs\conf\vanilla` проверено: `<load module="mod_callcenter"/>` закомментирован; `support@default` уже объявлен с longest-idle и hold music; agent/tier entries закомментированы.
- Авторитетный baseline — файлы, установленные именно из выбранного apt package; исходное дерево v1.10.9 является только предварительным reference.
- Включить существующий модуль из apt package, определить очередь, agent/contact и tier, добавить один dialplan destination. Не собирать/писать новый модуль и не переводить FreeSWITCH на новый routing architecture.
- Доказать очередь фактическими `callcenter_config` state/members и FreeSWITCH channel logs; успешный прямой вызов из 011-B не заменяет очередь acceptance.
- Агент остаётся зарегистрированным MicroSIP endpoint `1001`; caller — MicroSIP `1000`; используется только один звонок.

## Write-set

- Минимальные настройки в новой Debian install: `modules.conf.xml`, `callcenter.conf.xml` и один dialplan XML в `/etc/freeswitch` либо соответствующие штатные конфиги пакета.
- `artifacts/workshops/freeswitch-callcenter/011-C-*` и этот plan.
- Не менять FreeSWITCH source tree, `tools/freeswitch_workshop/` бота и существующие evidence.

## Выполнение

1. Подтвердить `011-B` complete, `1000` и `1001` registered, direct call passed.
2. Проверить package metadata/module path; включить `mod_callcenter` в установленном `modules.conf.xml` и перезагрузить конфигурацию/службу стандартным способом.
3. Использовать существующую `support@default` очередь, если установленная версия сохранила её; добавить agent `1001@default` типа callback с contact `user/1001@default`, status `Available`, и tier level/position 1. Если package defaults отличаются, сначала отразить exact installed schema в evidence, затем применить только эквивалентную минимальную настройку.
4. Добавить простой внутренний номер очереди, например `7000`, который исполняет FreeSWITCH `callcenter` application для `support@default`.
5. Убедиться, что агент Available и состоит в tier; caller с `1000` вызывает `7000`, остаётся queued и слышит штатную музыку ожидания; `1001` звонит, участник отвечает, channels соединяются.
6. Снять queue/member/agent/channel states до звонка, в ожидании и после bridge; повторить один clean run.

## Blockers

- `011-C-B1`: `resolved 2026-09-21` — `freeswitch-mod-callcenter` есть в owner-provided Bookworm repository.
- `011-C-B2`: `resolved 2026-09-21` — installed 1.11.3 schema совпала с queue contract; использован package baseline.
- `011-C-B3`: `resolved 2026-09-21` — initial `@default` contact gap диагностирован по
  `SUBSCRIBER_ABSENT`, исправлен на `$${domain}` и подтверждён двумя successful queue bridges.
- `011-C-B4`: `resolved 2026-09-21` — owner-assisted answer и acoustic sequence подтверждены.

## Acceptance и evidence

Complete требует: module loaded, queue loaded, `1001` Available и в нужном tier, `1000` виден как waiting member, FreeSWITCH вызывает `1001`, answer завершает bridge caller-agent, оба слышат друг друга. Все переходы и exact config/commands сохраняются в `artifacts/workshops/freeswitch-callcenter/011-C/`.

## Execution checkpoint — 2026-09-21

- `mod_callcenter` включён и автоматически загружается после FreeSWITCH/WSL restart.
- Queue `support@default`, callback-agent `1001@default`, tier `Ready` и dialplan `7000` установлены из
  `config/workshops/freeswitch/`.
- Первый probe выявил `SUBSCRIBER_ABSENT`: пакетный sample contact `user/1001@default` не совпадал с фактическим
  directory domain. Исправлено без fallback на `user/1001@$${domain}`; при загрузке получен текущий WSL IP.
- Первый и clean-start повтор дали переходы `Trying → Answered`, `Receiving → In a queue call`, `RINGING → ACTIVE`;
  оба media legs — PCMU/8000/64000 read/write.
- Evidence: [`011-C/callcenter-call.md`](../../artifacts/workshops/freeswitch-callcenter/011-C/callcenter-call.md).
- Владелец 2026-09-21 подтвердил, что final live sequence акустически прошла как описано: ожидание, ответ и слышимость
  собственного голоса. Probe сохранил caller в очереди пять секунд на `local_stream://moh`, затем снова дал
  Answered/ACTIVE; `011-C-B4` resolved, plan complete.
