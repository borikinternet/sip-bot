# План 019-B: пакеты FreeSWITCH и прямой SIP-звонок в двух дорожках

Уровень: `child plan`  
Статус: `proposed; не исполнялся`  
Owner review: `pending вместе с Map-019`  
Родитель: [`Map-019`](plan-019-dual-wsl-freeswitch-live-masterclass.md)  
Зависимость: [`019-A`](plan-019-A-dual-wsl-preflight.md) complete

## Цель и граница

В каждой Debian-дорожке установить пакетный FreeSWITCH и два независимых MicroSIP `1000/1001`; в назначенное exclusive window доказать `1000→1001` с двумя ACTIVE PCMU/8 kHz legs и слышимым голосом. Установку и конфигурацию можно готовить параллельно, но пакетный post-install/start и живые SIP gates координирует ведущий. Бот, очереди, исходники приложения и сеть хоста не входят.

## Materialized rules и source-map

| Источник | Правило | Применение / тест | Stop condition |
|---|---|---|---|
| [APG](../architectural-planning-gate.md) §§3, 5 | Зависимый child plan исполняется только после полного A; raw evidence и blocker обязательны | Сверить A closeout и своё окно до apt/start | A не закрыт или окно занято |
| [Development guidelines](../development-guidelines.md) §§4, 6–8 | Чужой write-set и общий ресурс защищены; красный gate исправляется в scope; partial нельзя закрыть | Агент не останавливает сервис ведущего; регистрация и звонок нужны сверх `apt` | Только один endpoint или нет RTP/акустики |
| [Workshop scenario](../workshops/freeswitch-callcenter-masterclass.md) §§1–4 | Signed Bookworm apt, две SIP-учётки, direct call до очереди | Fingerprint, apt origin, `fs_cli`, REGISTER, `show channels` | Репозиторий без подписи или Baresip вместо MicroSIP |
| [Map-019](plan-019-dual-wsl-freeswitch-live-masterclass.md) §3 | WSL shared network не позволяет молча стартовать два default FreeSWITCH | Проверить все listeners до/после запуска, получить окно у ведущего | Port bind конфликт не устранён в разрешённом scope |

Target: Debian 12 в `Debian-FS-Human` и `Debian-FS-Agent`, PowerShell/Windows MicroSIP. Write-set каждого исполнителя ограничен своим дистрибутивом, своей MicroSIP-парой и будущим `artifacts/workshops/freeswitch-dual-wsl-019/019-B/<human|agent>/`. Project config/scripts — read-only source; если исполнитель применяет helper, он обязан записать фактически изменённые package config и параметры. Два MicroSIP-профиля разных дорожек не перезаписывают друг друга.

SIP boundary: `MicroSIP 1000 → FreeSWITCH internal → MicroSIP 1001`; проверяются REGISTER, INVITE/answer, negotiated SDP codec и RTP/слышимость. WSL и SIP clients владеют своим состоянием; отдельного Python-владельца или typed application contract нет.

## Порядок, тесты и evidence

1. В пределах разрешённого окна подключить Bookworm mirror с проверкой fingerprint `655DA1341B5207915210AFE936B4249FA7B0FB03`; `apt-cache policy`, установить `freeswitch-meta-vanilla`, `freeswitch-mod-callcenter`, `freeswitch-systemd`. При этом после `apt` проверить `dpkg --audit` и service состояние: наличие бинарника не равно корректной установке.
2. Включить штатный unit в своём дистрибутиве; проверить `systemctl is-enabled/is-active freeswitch`, `fs_cli -x status`, SIP listeners. До отдачи окна остановить только собственный сервис. На WSL `enable` означает старт при следующем запуске дистрибутива, а не при Windows boot.
3. Создать собственные два MicroSIP профиля на Windows, не занимая профили ведущего. Конкретные SIP/RTP local ports записать до запуска; при одном временном окне пары можно запускать последовательно, не одновременно.
4. В своём окне проверить обе регистрации через `sofia status profile internal reg`, выполнить direct call, снять `show channels` до/после answer, codec PCMU/8000, завершить звонок и проверить 0 channels. Человек подтверждает двустороннюю слышимость отдельно от CLI.
5. После чистого старта своего WSL и собственного окна повторить service/register/direct essentials. Не использовать `wsl --shutdown`.

Evidence: exact version/origin, signing check, apt output/exit, `dpkg --audit`, `systemctl`, listeners, registrations, channel transitions, codecs, human audio verdict, timestamp и ожидание окна. Команды и сырой вывод складываются только в новый root после исполнения. Регистрация без звонка и звонок без слышимости не закрывают B.

## Blocker register и closeout

| ID | Триггер | Что блокирует | Owner | Проверка/снятие | Статус |
|---|---|---|---|---|---|
| B-019-B-1 | Подпись/пакет/unit не проходят после corrective pass | Установку | исполнитель дорожки | Raw apt/dpkg/systemd, исправление без смены repo | `open until execution` |
| B-019-B-2 | Общий listener занят чужим WSL | Живой gate | ведущий | Окно и `ss`, без остановки чужого сервиса агентом | `open until gate` |
| B-019-B-3 | Нет двух REGISTER, PCMU bridge или слышимости | C и closeout | исполнитель + ведущий | Повторяемый direct call с human audio verdict | `open until gate` |

Fallback: `none`. Plan `complete` только для полного результата **обеих** дорожек; если одна завершила раньше, записать её milestone, но не closeout плана. Нового execution report пока нет.
