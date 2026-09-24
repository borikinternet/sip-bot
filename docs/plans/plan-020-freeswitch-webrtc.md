# Карта 020: WebRTC-доступ к FreeSWITCH через SIP/WSS

Уровень: `map`  
Статус: `blocked` на 020-C (локальные 020-A/020-B complete); серверный rollout не начат  
Owner review: локальная репетиция разрешена владельцем 23.09.2026; публичная/локальная граница серверного доступа открыта.

## Цель и граница

На `Debian-Bookworm-FS` в WSL проверить сквозной путь браузерного SIP-клиента через WSS, REGISTER, ICE/DTLS-SRTP и двусторонний звук. Затем воспроизвести подтверждённую конфигурацию на целевом FreeSWITCH `inrack@10.0.0.45` после включения сервера. Выбираем SIP-over-WSS в `mod_sofia`, потому что существующий стек уже SIP и `internal` profile содержит `wss-binding`; Verto не вводим. [Руководство FreeSWITCH по SIP/WebRTC](https://developer.signalwire.com/freeswitch/users-and-endpoints/webrtc-sip/) является источником транспортных и media-требований.

Входит: WSS/TLS, браузерная SIP-регистрация, аудиозвонок, ICE/DTLS-SRTP, сертификат и сетевые правила целевого сервера. Не входит: изменение SIP-бота, замена очередей, видеозвонки, TURN как обязательный компонент, публичная публикация стенда без отдельного решения владельца.

Protected baseline: работающие UDP SIP `1000/1001/1002`, очереди `7000/7100`, `-nonat -nonatmap`, записи, конфигурация бота и удалённый сервер до его включения. Локальный WSL-сервис допускается менять только по узкому плану с копией/rollback.

## Факты preflight

- Локальный FreeSWITCH уже активен; `internal` показывает WS `172.22.89.126:5066`, WSS `:7443`, OPUS/PCMU и активные TLS-сокеты. Адрес WSL динамический и не закрепляется в плане.
- `$${certs_dir}` — `/etc/freeswitch/tls`; автоматически созданные `wss.pem` и `dtls-srtp.pem` имеют `CN=FreeSWITCH`, не имеют SAN и не пригодны как доверенный browser-cert. Их наличие не доказывает WebRTC media.
- 23.09.2026 локальные 020-A/020-B закрыты: WSS `101`, два браузерных REGISTER, двусторонний ICE/DTLS-SRTP audio и BYE. Для приватных ICE-кандидатов понадобился явный `apply-candidate-acl=rfc1918.auto`; сохранены patch, rollback и [evidence](../../artifacts/webrtc/020/B/closeout.md). Самоподписанный WSS cert принимался только изолированным диагностическим браузером.
- По сохранённому [серверному evidence](../../artifacts/deployment/ubuntu22-runtime-20260922/freeswitch-server/freeswitch-validation.txt) `10.0.0.45` также показывал WSS `:7443`. На 23.09.2026 сервер выключен, SSH недоступен; его фактическое текущее состояние неизвестно.

## Применимые правила и source-map

| Источник | Локальное правило | Влияние и проверка | Stop condition |
|---|---|---|---|
| [APG](../architectural-planning-gate.md) §§0,2,5 | Несколько независимых acceptance boundaries требуют карты и child plan; частичная готовность не закрывает карту | A/B/C закрываются отдельно, с evidence и blocker register | WSS-порт выдан за WebRTC-звонок |
| [Development guidelines](../development-guidelines.md) §§1,6 | Узкий slice, красный gate исправляется в scope, упрощения и недоказанный fallback запрещены | Отдельно проверяются TLS/REGISTER и ICE/DTLS/RTP; ошибки классифицируются и перепроверяются | Провал media скрыт успешной регистрацией |
| [Documentation process](../documentation-process.md) | Один владелец факта; история не переписывается | Новый evidence в `artifacts/webrtc/020/`; текущий runbook дополняется после проверки | Старый `sofia status` выдан за новый live gate |
| [FreeSWITCH SIP/WebRTC](https://developer.signalwire.com/freeswitch/users-and-endpoints/webrtc-sip/) | WSS — сигнализация; браузеру нужны DTLS-SRTP и ICE; TLS для WSS должен быть доверен | Проверка сертификата, SIP REGISTER, SDP fingerprints/candidates и media stats | Нет защищённого media/ICE |

| Область | Фактический/будущий путь | Разрешённое изменение |
|---|---|---|
| Локальный профиль | WSL `/etc/freeswitch/sip_profiles/internal.xml` | Только требуемые WebRTC-параметры после baseline/backup |
| Локальные сертификаты | WSL `/etc/freeswitch/tls/{wss,dtls-srtp}.pem` | Диагностика; замена лишь при доказанной необходимости и rollback |
| Browser probe | `tools/workshops/webrtc_probe.*` | Новый тестовый клиент/скрипт, без изменения приложения бота |
| Сервер | `inrack@10.0.0.45`, FreeSWITCH в Debian `systemd-nspawn` | Только после C-preflight и решения LAN/public |
| Документы | эта карта, A/B/C, workshop runbook, registry/backlog | Синхронизировать факты после исполнения |

Владелец поведения: FreeSWITCH `mod_sofia` владеет SIP/WSS/DTLS/ICE, браузерный SIP-клиент — собственным `RTCPeerConnection`. Нового прикладного фасада или delivery-компонента нет. Стык `browser SIP over WSS → mod_sofia`, обратные SIP-ответы и `browser ICE/DTLS-SRTP ↔ FreeSWITCH media` проверяются отдельно; BYE/cleanup заканчивает звонок. Существующие UDP/RTP ноги к MicroSIP и боту остаются неизменными.

## Child plans и порядок

| План | Узкий результат | Зависимость | Review | Evidence |
|---|---|---|---|---|
| [020-A](plan-020-A-local-wss-preflight.md) | Локальный transport/cert baseline и WSS upgrade | нет | user approved local practice | `artifacts/webrtc/020/A/` |
| [020-B](plan-020-B-browser-call.md) | Браузерные REGISTER и аудиозвонок с ICE/DTLS stats | A | user approved local practice | `artifacts/webrtc/020/B/` |
| [020-C](plan-020-C-server-rollout.md) | Перенос на `10.0.0.45` и отдельный live gate | B; сервер включён; LAN/public решение | `open` | `artifacts/webrtc/020/C/` |

### Map-level gate

Локальная репетиция завершена лишь после A+B. Вся карта закрыта только после C: WSS с правильным сертификатом, регистрация, звонок, двусторонний media и регрессия прежних UDP/очередей на целевом сервере. Планы не закрываются статусом `foundation complete`; допустимы только `complete` или конкретный `blocked`. Fallback register: `none`; изолированный browser-профиль с отключённой проверкой самоподписанного локального cert — только диагностический инструмент A/B, **не** критерий серверной TLS-приёмки.

## Blocker register / owner review

| ID | Срез | Условие | Что блокирует | Владелец | Снятие |
|---|---|---|---|---|---|
| B-020-1 | C | Сервер `10.0.0.45` выключен | Все серверные изменения/звонки | владелец сервера | SSH, свежий baseline и окно изменения |
| B-020-2 | C | Не выбрана доступность только LAN или из интернета | DNS, доверенный cert, firewall/ICE адреса | владелец проекта | явное решение до публикации WSS/RTP |
| B-020-3 | B | Browser test не получает media при успешном REGISTER | local closeout | исполнитель | SDP/ICE/DTLS диагностика, corrective pass и повторный звонок |

На этом этапе A/B можно исполнять без C. Целевой сервер не меняется из локальной репетиции автоматически.
