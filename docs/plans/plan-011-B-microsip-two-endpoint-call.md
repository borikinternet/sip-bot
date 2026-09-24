# План 011-B: два MicroSIP endpoint и прямой вызов через FreeSWITCH

Уровень: `child plan`  
Идентификатор: `011-B`  
Статус owner review: `accepted — scope из Map-011 принят владельцем 2026-09-20`  
Статус исполнения: `complete — 2026-09-21`  
Родитель: [`Map-011`](plan-011-freeswitch-small-company-callcenter-workshop.md)  
Зависимость: [`011-A`](plan-011-A-debian-wsl-freeswitch-packages.md)

## Цель и проверяемый результат

Установить два штатных MicroSIP клиента/instance на Windows, настроить test extensions `1000` и `1001`, зарегистрировать их в FreeSWITCH и доказать реальный вызов `1000 → FreeSWITCH → 1001`.

## Materialized rules

- Использовать только официальный installer/portable package MicroSIP и документированные возможности приложения. Исходный код и binary не патчить.
- Для действий dial/answer/hangup разрешены только опубликованные MicroSIP CLI commands; они не доказывают отображение окна, регистрацию UI или акустическую слышимость.
- Профили двух клиентов должны быть независимыми и повторяемыми штатным способом. Если текущая версия не запускает два клиента с разными account settings без undocumented workaround, зафиксировать blocker.
- SIP registration и SDP/RTP между Windows и WSL проверяются на выбранной стандартной WSL network mode. Глобальный `.wslconfig`, широкие Windows firewall rules и сторонние port-forward daemons не менять без отдельного review.
- Baresip/ботский adapter не заменяет обязательный MicroSIP acceptance.

## Write-set

- Установка MicroSIP через официальный источник; два независимых профиля в стандартном UI/portable mode.
- Только `artifacts/workshops/freeswitch-callcenter/011-B-*` и этот plan.
- Конфигурация FreeSWITCH из A не меняется кроме точечной настройки тестовых extensions, если это необходимо и зафиксировано.

## Выполнение

1. Проверить `011-A` complete и active service.
2. Установить текущий stable MicroSIP из официального источника. Создать два раздельных клиента без изменения кода; зарегистрировать extension/password, выбранные для локального лабораторного FreeSWITCH.
3. На FreeSWITCH проверить `show registrations`, зарегистрированные endpoints и SIP profile. Сверить адрес/port и negotiated codec; не маскировать unreachable Contact/RTP адрес.
4. Из MicroSIP extension `1000` вызвать `1001`; второй клиент отвечает после отображения входящего вызова.
5. Зафиксировать FreeSWITCH channels/logs, SIP/SDP/RTP evidence и результат участника по двустороннему слышимому звуку.
6. Повторить после restart FreeSWITCH, чтобы исключить случайно сохранившееся состояние.

Официальная документация MicroSIP указывает поддерживаемые команды `microsip.exe <number>`, `/answer`, `/hangupall`; использовать их только для действий, которые CLI реально поддерживает. Операторская настройка accounts и субъективная проверка звука выполняются в GUI человеком.

## Blockers

- `011-B-B1`: `resolved 2026-09-21` — официальный portable MicroSIP поддержал два независимых штатных profiles.
- `011-B-B2`: `resolved 2026-09-21` — REGISTER, SIP bridge и PCMU/RTP прошли без global network workaround.
- `011-B-B3`: `resolved 2026-09-21` — владелец подтвердил live audibility; CLI/logs использованы только как
  дополняющее signaling/media evidence.

## Acceptance и evidence

`011-B` complete при двух актуальных registrations, реальном установленном вызове через FreeSWITCH, RTP/media evidence и человеческом подтверждении bidirectional audio. Evidence — `artifacts/workshops/freeswitch-callcenter/011-B/`; MicroSIP CLI exit codes сами по себе не закрывают plan.

## Execution checkpoint — 2026-09-21

- Официальный MicroSIP portable `3.22.16` получен с [официальной страницы загрузки](https://www.microsip.org/downloads) по URL `https://www.microsip.org/download/MicroSIP-3.22.16.zip`.
- Archive SHA-256: `B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4`; executable SHA-256 для обеих копий: `FE5AD81043E4F755DD8730A520917490787BB66F5AB7EF9E1172D637DB8B99DC`.
- Каталоги: `%LOCALAPPDATA%\Programs\MicroSIP-Workshop\Caller-1000` и `%LOCALAPPDATA%\Programs\MicroSIP-Workshop\Agent-1001`. Обе копии стартовали одновременно как отдельные процессы; каждая создала локальный `MicroSIP.ini`.
- Две команды штатного `/exit` вернули exit code `0`; после них активных MicroSIP processes нет.
- Authenticode certificate subject `CN=MSIP Code Signing 2025`, thumbprint `FDD0593557BAC6FAD1883DDD5403694DDAC76DF1`, срок `2025-01-03`–`2030-01-03`; Windows chain result — `UntrustedRoot`. Сертификат не устанавливался в Trusted Root и security prompts не обходились.
- Сгенерированы два независимых штатных профиля: caller `1000` на UDP 5062/RTP 40000–40100 и agent `1001` на UDP
  5064/RTP 40200–40300; оба принудительно используют PCMU.
- После чистого старта WSL оба клиента зарегистрированы как `Registered(UDP)`/`Reachable`.
- Прямой вызов `1000 → 1001` прошёл: до ответа outbound leg `RINGING`; после штатного MicroSIP `/answer` два
  `ACTIVE` channel с PCMU/8000/64000 read/write; после cleanup channel count 0.
- Технический gate доказан в
  [`011-B/direct-call.md`](../../artifacts/workshops/freeswitch-callcenter/011-B/direct-call.md). Владелец 2026-09-21
  подтвердил, что во время live bridge слышал собственный голос; `011-B-B3` resolved, plan complete.
