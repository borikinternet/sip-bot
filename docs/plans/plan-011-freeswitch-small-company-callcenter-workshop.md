# Карта 011: мастер-класс FreeSWITCH call-center на WSL Debian

Уровень: `map`  
Идентификатор: `Map-011`  
Статус: `complete — 2026-09-21`  
Owner review: `accepted — конкретный scope и запрет на невоспроизводимые обходы подтверждены владельцем 2026-09-20`  
Дата: `2026-09-20`

## 1. Цель и проверяемый результат

Подготовить и исполнить воспроизводимый для участника мастер-класса сценарий на одном Windows-компьютере:

1. установить отдельную WSL-машину Debian, совместимую с пакетами выбранного FreeSWITCH-репозитория;
2. подключить именно Debian-пакетный репозиторий из закреплённого сообщения Telegram-канала `@ru_freeswitch`, установить FreeSWITCH и включить штатный автозапуск службы при старте WSL-дистрибутива;
3. на двух локальных клиентах MicroSIP зарегистрировать две тестовые учётные записи и провести вызов между ними через FreeSWITCH;
4. включить `mod_callcenter`, настроить очередь и второго MicroSIP-абонента как агента; позвонить в очередь, услышать ожидание, дождаться вызова агента и ответить на втором MicroSIP;
5. после успешного исполнения оформить точный пошаговый runbook, пригодный для агента без истории этой переписки и для обычного участника мастер-класса.

Результат — работающий учебный стенд и проверенная инструкция, а не только план или конфигурационные примеры.

## 2. Контекст для исполнителя без истории переписки

- Хост: Windows 11, build `10.0.26200`; WSL `2.6.2.0`.
- Отдельный WSL2 `Debian-Bookworm-FS` на Debian 12.15 импортирован в `D:\WSL\Debian-Bookworm`; существующие
  `docker-desktop` и `Ubuntu-24.04` не изменялись.
- Свободное место на `C:` — около 53 GiB, на `D:` — около 273 GiB, на `E:` — около 155 GiB. Утверждённый минимальный запас для установки — 20 GiB.
- MicroSIP отсутствовал; официальный portable `3.22.16` теперь установлен двумя отдельными копиями в `%LOCALAPPDATA%\Programs\MicroSIP-Workshop\Caller-1000` и `...\Agent-1001`. Подтверждены два одновременно работающих процесса и два отдельных `MicroSIP.ini`; оба экземпляра закрываются опубликованной CLI-командой `/exit`.
- `E:\devel.arch\fs` — локальный исходный код FreeSWITCH `v1.10.9`; его `conf/vanilla` показывает, что `mod_callcenter` не загружается по умолчанию: строка в `autoload_configs/modules.conf.xml` закомментирована. `autoload_configs/callcenter.conf.xml` содержит очередь `support@default` с `longest-idle-agent` и hold music, но agent и tier закомментированы. Эти файлы — диагностическая подсказка, не конфигурация для безусловного копирования в пакет другой версии.
- Владелец передал exact mirror lines из закреплённого сообщения `@ru_freeswitch`; выбран
  `http://fi.itlnk.ru/freeswitch bookworm main`. Autoindex зеркала намеренно отключён; apt metadata доступна и подписана.
- MicroSIP штатно управляется опубликованными командами dial/answer; registrations, direct bridge и queue bridge
  проверены. Codex-сессия по-прежнему не может субъективно подтвердить слышимость; это выполняет человек.

## 3. Owner-approved границы и ограничения

### Входит

- стандартная установка отдельного Debian-дистрибутива в WSL2;
- пакеты FreeSWITCH только из указанного владельцем источника `@ru_freeswitch`;
- установка обычных недостающих инструментов, включая официальный MicroSIP;
- стандартное включение systemd-службы FreeSWITCH;
- минимальные локальные учётные записи, маршрут прямого вызова, одна очередь и один агент;
- конфигурация существующего `mod_callcenter`, без собственного модуля и без сборки FreeSWITCH из исходников;
- работа по runbook и сбор проверяемых текстовых evidence.

### Не входит

- Docker, изменение или очистка Docker, изменения уже установленных WSL-дистрибутивов;
- модификация `E:\devel.arch\fs`, исходников FreeSWITCH, MicroSIP или проекта SIP-бота;
- компиляция FreeSWITCH, собственный SIP-клиент, недокументированная автоматизация GUI;
- внешние SIP-провайдеры, удалённые абоненты, публикация портов в Интернет, TLS/SRTP, production hardening;
- утверждение, что WSL-сервис сам запускает WSL при старте Windows: systemd стартует при запуске дистрибутива, но сам по себе не удерживает WSL живым.

Все шаги должны быть воспроизводимы обычным участником по стандартным командам WSL/apt/systemd и настройке MicroSIP. Если для SIP/RTP потребуется нестандартная сетевая схема, изменение глобального `.wslconfig`, небезопасный apt bypass или другой невоспроизводимый обход, остановиться и представить доказательства владельцу.

## 4. Materialized rules и решения

| Источник | Правило/решение | Применение и проверка |
|---|---|---|
| Запрос владельца от 2026-09-20 | Debian в WSL; пакетный источник из pinned post `@ru_freeswitch`; MicroSIP ×2; сначала прямой звонок, затем очередь/агент | Повторить именно эти стадии и зафиксировать результат каждой; источник не подменять |
| Уточнение владельца от 2026-09-20 | Недостающие обычные программы устанавливать можно и нужно; не делать нетривиальных шагов, которые участник не сможет повторить | Использовать штатные installer/package manager/systemd/UI; никаких патчей и скрытых механизмов |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Задача по тестовому VoIP-стенду требует scope, source-map, blocker register, тестов и evidence; карта разлагается на зависимые child plans | Map-011 и планы A–D, sequential gates, финальный audit |
| [`development-guidelines.md`](../development-guidelines.md) | Не маскировать красные результаты, не вводить fallback и не объявлять частичное выполнение закрытым | Конкретный stop condition у каждой стадии, полный финальный сценарий |
| [`documentation-process.md`](../documentation-process.md) | Один факт имеет одного владельца; runbook хранит точные проверенные команды, реестр — инвентаризацию | После исполнения обновить только workshop runbook, эту карту, child plans, roadmap/backlog/registry |
| Официальный FreeSWITCH Getting Started | Текущая пакетная документация поддерживает Debian/Ubuntu, разбитые пакеты и systemd; фактические версии выбираются по repo metadata | Сверить pinned repository с поддерживаемым Debian codename; наличие пакета, модуля и unit доказать локально: [Getting Started](https://developer.signalwire.com/freeswitch/foundations/getting-started/) |
| Microsoft WSL docs | WSL поддерживает systemd; сервисы не удерживают дистрибутив живым | Автостарт проверяется при старте WSL-дистрибутива; ограничения Windows boot объясняются явно: [systemd on WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd), [WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) |
| MicroSIP help | Для клиента существует опубликованный CLI вызова, ответа и завершения вызовов | Разрешены только документированные команды; визуальная/акустическая проверка требует участника с доступом к GUI: [MicroSIP help](https://www.microsip.org/help) |

## 5. Source-map и write-set

| Область | Источник/путь | Действие | Ограничение |
|---|---|---|---|
| Планирование | `docs/plans/plan-011-*.md` | Карта и sequential child plans A–D | Не менять закрытые планы 001–010 |
| Результирующая инструкция | `docs/workshops/freeswitch-callcenter-runbook.md` | Создать после проверки точных команд | Не утверждать непроверенные команды как tested |
| Реестр/планирование | `docs/roadmap.md`, `docs/task-backlog.md`, `docs/document-registry.md` | Добавить Map-011/TASK и записи документов при актуализации | Не переписывать соседние пользовательские изменения |
| Внешний источник | переданный владельцем текст pinned message `@ru_freeswitch` | Использовать mirror `fi.itlnk.ru` и Bookworm; проверять apt signature отдельным keyring | Не подбирать другой repo и не отключать signature verification |
| Windows/WSL | новая WSL Debian distribution | Установка и конфигурация внутри нового дистрибутива | Не менять `Ubuntu-24.04`, Docker, глобальный `.wslconfig` без доказанной необходимости и review |
| MicroSIP | официальный installer/portable package | Установка двух повторно запускаемых локальных клиентов | Не менять binary/source; если два независимых профиля штатно не запускаются — blocker, не workaround |
| FreeSWITCH package config | только конфигурация новой Debian install | Активировать `mod_callcenter`, agent/tier и queue dialplan | Не редактировать `E:\devel.arch\fs`; сохранять исходные package defaults/evidence |
| Workshop assets | `config/workshops/freeswitch/**`, `tools/workshops/**` | Хранить минимальные повторяемые apt/FreeSWITCH/MicroSIP templates и setup scripts | Не менять application `src/`, закрытые bot test stands или внешние исходники |
| Evidence | `artifacts/workshops/freeswitch-callcenter/` | Команды, versions, logs, SIP call/queue states и manifest | Не сохранять пользовательские разговоры и реальные secrets; публичный demo password маркировать как лабораторный |

В этом track нет application code. Разрешены только `config/workshops/freeswitch/**` и `tools/workshops/**`;
изменение `src/`, `tests/`, остальных `config/` и `tools/freeswitch_workshop/` запрещено: последний каталог принадлежит
существующему Docker/registered-SIP тестовому стенду бота.

## 6. Typed boundaries и целевая схема

```text
MicroSIP caller (1000)
    -- SIP REGISTER / INVITE, RTP from negotiated SDP -->
FreeSWITCH on Debian/WSL2
    -- SIP REGISTER / INVITE, RTP from negotiated SDP -->
MicroSIP agent (1001)

Direct demonstration: 1000 -> FreeSWITCH dialplan -> 1001
Queue demonstration: 1000 -> queue extension -> mod_callcenter queue
                    -> available callback agent 1001 -> answered/bridged
```

SIP signaling and RTP are both required evidence. Успешная регистрация или наличие `mod_callcenter` в списке модулей само по себе не доказывает ни прямой вызов, ни постановку в очередь, ни подключение агента. Acceptance требует фактических channel/queue/member transitions в логах FreeSWITCH и участия обоих MicroSIP endpoints.

## 7. Порядок дочерних планов

| Порядок | Child plan | Результат | Зависимость |
|---:|---|---|---|
| 1 | [`011-A`](plan-011-A-debian-wsl-freeswitch-packages.md) | Совместимый Debian WSL, подписанный apt source из закрепа, установленные пакеты, FreeSWITCH active после чистого старта дистрибутива | `complete` |
| 2 | [`011-B`](plan-011-B-microsip-two-endpoint-call.md) | Два локальных MicroSIP account/profile зарегистрированы; вызов 1000→1001 проходит через FreeSWITCH | 011-A pass |
| 3 | [`011-C`](plan-011-C-mod-callcenter-queue-agent.md) | mod_callcenter загружен, очередь обслуживает вызов и соединяет caller с MicroSIP agent 1001 | 011-B pass |
| 4 | [`011-D`](plan-011-D-clean-start-and-agent-runbook.md) | Чистый повтор после остановки/старта WSL и опубликованный runbook для агента без контекста | 011-A–C pass |

Области используют один новый WSL-дистрибутив и один FreeSWITCH instance, поэтому исполнение строго последовательное; распараллеливание технически не полезно.
Техническую подготовку следующих стадий разрешено продолжить при открытом manual-only audio blocker B, но статусы B–D и
карты не закрываются до человеческой акустической проверки.

## 8. Blocker register

| ID | Триггер | Что блокирует | Статус и условие снятия |
|---|---|---|---|
| `B-011-001` | В текущем окружении публичный Telegram preview не отдаёт закреплённое сообщение `@ru_freeswitch` | Выбор Debian codename и установка указанного пакета | `resolved 2026-09-21`: владелец передал exact mirror lines; выбран Bookworm |
| `B-011-002` | У MicroSIP отсутствует штатно повторяемый запуск двух независимых клиентов либо невозможно создать второй профиль | 011-B и дальнейшие live checks | `resolved 2026-09-21`: две portable instances, два profiles, registrations и calls доказаны штатными средствами |
| `B-011-003` | Пакет не содержит штатного `freeswitch.service`/`mod_callcenter`, либо запуск требует source build/ручного systemd unit | 011-A/011-C | `resolved 2026-09-21`: оба package есть, штатный unit enabled/active, source build/custom unit не потребовались |
| `B-011-004` | SIP/RTP между Windows MicroSIP и WSL не работает с обычной повторяемой WSL networking настройкой | 011-B/011-C | `resolved 2026-09-21`: registrations, direct/queue bridge и PCMU проходят без глобальных network/firewall changes |
| `B-011-005` | Исполнитель не может проверить слышимый результат MicroSIP | Визуальная и акустическая часть финальной приёмки | `resolved 2026-09-21`: владелец подтвердил final acoustic sequence — ожидание, answer и слышимость собственного голоса; probe выдержал 5 s MOH interval до answer |

## 9. Общий acceptance и closeout

Map-011 закрывается только когда все условия ниже пройдены на новом Debian-дистрибутиве:

1. Debian codename совпадает с метаданными repo из закрепа; apt package authenticity/signature проверена, insecure apt options отсутствуют.
2. Установленный FreeSWITCH package source/version и наличие `mod_callcenter` записаны; service enabled и после `wsl --terminate <Debian>` + повторного запуска дистрибутива `systemctl is-active freeswitch` возвращает `active`.
3. После старта оба MicroSIP account показывают registered; вызов 1000→1001 виден в FreeSWITCH logs/channels и устанавливается.
4. Queue call от 1000 остаётся в очереди до вызова агента; `callcenter_config` показывает queue/member/agent transitions; второй MicroSIP звонит и отвечает, после чего caller/agent связаны.
5. Владелец/участник подтверждает слышимое ожидание и двусторонний звук либо отдельно фиксирует акустический gap. CLI/log evidence не объявляются доказательством слышимости.
6. Проверенная инструкция содержит prerequisites, точные команды, GUI-поля MicroSIP, account/queue mapping, expected output, restart semantics, cleanup и troubleshooting.
7. Реестр документов и backlog согласованы; все открытые gaps остаются конкретными и не замаскированы.

Под Windows reboot понимается явно: служба включена на старте Debian WSL-дистрибутива. WSL не запускает Debian автоматически при старте Windows; если понадобится именно host-boot auto-launch до ручного старта дистрибутива, это отдельный owner-reviewed шаг с Windows Task Scheduler.

## 10. Execution checkpoint — 2026-09-21

- `011-A` complete: Debian 12.15 Bookworm WSL2, подписанный owner-provided mirror, FreeSWITCH 1.11.3 package set,
  штатный systemd autostart и post-terminate gate доказаны.
- `011-B` complete: две MicroSIP 3.22.16 registrations, direct `1000 → 1001`, два ACTIVE PCMU legs после answer и
  owner confirmation слышимости.
- `011-C` complete: module/queue/agent/tier/dialplan, first run, clean-start repeat и final 5 s queue wait с переходами
  `Trying/Receiving/RINGING → Answered/In a queue call/ACTIVE`; owner confirmed live audibility.
- `011-D` complete: self-contained [`freeswitch-callcenter-runbook.md`](../workshops/freeswitch-callcenter-runbook.md)
  создан, clean repeat и owner audio acceptance выполнены; независимый context-free review после corrective iterations
  дал финальный PASS без blocking/major/minor findings.
- Все child plans `011-A`–`011-D`, acceptance gates и blocker register закрыты; Map-011 complete.
- Docker, `Ubuntu-24.04`, `E:\devel.arch\fs`, application source и глобальная WSL network configuration не изменялись.
