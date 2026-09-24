# План 019-C: две очереди и живой вызов оператору

Уровень: `child plan`  
Статус: `proposed; не исполнялся`  
Owner review: `pending вместе с Map-019`  
Родитель: [`Map-019`](plan-019-dual-wsl-freeswitch-live-masterclass.md)  
Зависимость: [`019-B`](plan-019-B-packages-and-sip.md) complete

## Цель и граница

На каждом стенде включить `mod_callcenter`, создать `support@default`/`science-bot@default`, callback agents `1001@default`/`1002@default`, соответствующие tiers и dialplan destinations `7000`/`7100`. В live window звонящий `1000` проходит очередь `7000`, слышит ожидание и после ответа `1001` разговаривает с человеком. Очередь `7100` только подготавливается к подключению бота; отсутствие зарегистрированного `1002` не выдаётся за пройденный bot call.

## Materialized rules, source-map и topology

| Источник | Правило | Применение / тест | Stop condition |
|---|---|---|---|
| [APG](../architectural-planning-gate.md) §§3, 5 | Scope очередей отделён от package/direct boundary; обязательны source-map/blocker/evidence | B complete, затем конфиг и live gate | Direct call не принят |
| [Development guidelines](../development-guidelines.md) §§1, 6–8 | Не скрывать дефект queue зелёным direct call; не ослаблять acceptance и не вводить fallback | Проверить module, queue, agent, tier, member transitions и звук | Отсутствует любое обязательное звено |
| [Workshop scenario](../workshops/freeswitch-callcenter-masterclass.md) §§4–7 | Важны явные строки `modules.conf.xml`, `callcenter.conf.xml`, dialplan, NAT/STUN и назначение двух линий | Сравнить фактически установленную схему с показанными отношениями; `fs_cli` и вызов | Выполнен только helper без аудита конфига |
| [Map-019](plan-019-dual-wsl-freeswitch-live-masterclass.md) §3 | Живые FreeSWITCH/RTP gates сериализованы по ведущему | Окно, `ss`, 0 чужих активных calls | Одна дорожка мешает другой |

Write-set: только `/etc/freeswitch` и `freeswitch.service` override **своего** Debian; собственный evidence root `artifacts/workshops/freeswitch-dual-wsl-019/019-C/<human|agent>/`. Чужой дистрибутив, Windows global network, исходники FS и SIP-бота защищены. Две дорожки используют одинаковый project config как reference, но каждая записывает собственные изменения/хеши. Владелец поведения: FreeSWITCH `mod_callcenter` владеет очередью и agent state; dialplan владеет маршрутом номера; MicroSIP владеет REGISTER/ответом. Новый application component не создаётся.

Топология: `1000 → 7000 → support queue → tier → 1001` и `1000 → 7100 → bot queue → tier → 1002`. Обратные события `agent answer/hangup` переводят member в answered/closed; при busy agent второй вызов должен остаться в очереди, но **проверка этого поведения назначена второму мастер-классу с настоящим ботом**, не является пройденным gate здесь. RTP/PCMU подтверждается для операторского вызова.

## Порядок, acceptance и evidence

1. Инвентаризировать пакетный `modules.conf.xml`, `callcenter.conf.xml`, `vars.xml`, service unit и dialplan. Не копировать вслепую файл другой версии. Включить существующий `mod_callcenter`, применить двухочередный конфиг и dialplan, проверить XML.
2. Выключить автоматическую STUN-подстановку в учебной локальной сети и запустить FS с `-nonat -nonatmap`; затем проверить `SIP-IP/RTP-IP/Ext-*` фактическим `sofia status`, а не считать флаг достаточным доказательством.
3. Поднять только свой FreeSWITCH в выделенное окно. Проверить `module_exists mod_callcenter=true`, две queue, два agent, два ready tier; маршрут `7000` и `7100` присутствует в установленном dialplan.
4. С `1000` вызвать `7000`, снять `queue list members support@default`, `agent list 1001@default` и `show channels` до и после ответа `1001`: `Trying/Receiving/RINGING → Answered/In a queue call/ACTIVE`, PCMU. Человек слушает hold music и голос.
5. Для `7100` проверить только конфигурационный маршрут/очередь. Не инициировать ложный успешный звонок без бота. После controlled restart повторить module/queue/route и один операторский вызов.

Evidence: installed config paths and hashes/diff, service command, `fs_cli` outputs, before/after queue/agent/channel states, кодек, human audio verdict, runtime errors и timestamps. Script exit code без этих проверок недостаточен. Отложенное обязательное evidence: `none`; bot call явно вне scope.

## Blocker register и closeout

| ID | Триггер | Что блокирует | Owner | Проверка/снятие | Статус |
|---|---|---|---|---|---|
| B-019-C-1 | Пакетный модуль/схема не совпадают с reference | Обе очереди | исполнитель | Фактический config/API и corrective внутри scope | `open until execution` |
| B-019-C-2 | Очередь не вызывает `1001`, не держит ожидание или нет звука | C acceptance | исполнитель + ведущий | Raw log, correct contact/domain, повтор SIP/RTP и audio | `open until live gate` |
| B-019-C-3 | Нет `7100→science-bot@default→1002` в загруженном конфиге | Готовность ко второму МК | исполнитель | `fs_cli` и dialplan audit | `open until config gate` |

Fallback: `none`. План остаётся открытым, пока обе дорожки не имеют собственного доказанного двухочередного конфига и живого операторского вызова; «очередь существует в XML» не является closeout. Execution report ещё не создан.
