# Conference web demo

Локальный demo-контур Map-021: session-scoped upload, heartbeat, подготовленный RAG-artifact и browser UI.

Загрузчик принимает UTF-8 `.md`/`.txt` и PDF размером до 640 КиБ. Для PDF backend извлекает встроенный
выделяемый текст через `pypdf`, сохраняет его как нормализованный Markdown-документ и передаёт дальше в тот же
metadata/embedding pipeline. Сканированные PDF без текстового слоя требуют отдельного OCR и этим demo не покрываются.

Запуск в WSL `Ubuntu-24.04`, где работают SIP-бот и Ollama:

```bash
wsl.exe -d Ubuntu-24.04 -- bash -lc \
  'cd /mnt/c/devel/sip-bot && export PYTHONPATH=src:demo-web && \
   exec /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -m backend.server'
```

Для HTTPS задайте `DEMO_WEB_TLS_CERT=/mnt/c/devel/sip-bot/demo-web/runtime/tls/demo.crt` и
`DEMO_WEB_TLS_KEY=/mnt/c/devel/sip-bot/demo-web/runtime/tls/demo.key` до запуска. Самоподписанный
сертификат текущей репетиции действителен до 24 октября 2026 года и содержит IP-адреса LAN и VPN.
Ollama остаётся доступной только внутри Ubuntu на `127.0.0.1:11434`.

Во время локальной репетиции доступ с телефона в локальной сети был через `https://192.168.1.74:8443/`
(самоподписанный сертификат надо было принять на устройстве). С Windows-хоста тот же backend был доступен по
`https://172.16.15.72:8443/`: прямое обращение Windows к собственному LAN-IP `192.168.1.74:8443`
в этом WSL mirrored окружении тайм-аутилось. Это два адреса одного web-сервиса, а не два сервера.
Открытие страницы по HTTP/IP не даёт браузеру доступа к микрофону; для звонка используйте HTTPS.

Для публичной страницы `frontend/demo-config.js` использует `https://demo.libnas.ru/` в QR,
API и WebSocket состояния (`wss://demo.libnas.ru/ws/...`), а для JsSIP —
`wss://demo.libnas.ru:7443`. Входящий в страницу файл JsSIP обслуживается тем же web-origin
из `/assets/jssip-3.10.0.min.js`. SIP URI пользователя и очереди тоже используют
`demo.libnas.ru`; внутренние адреса Ollama/бота от этого не меняются. Для локальной репетиции
публичные настройки можно переопределить до загрузки `demo-config.js`.

В репетиционном контуре FreeSWITCH был запущен в отдельном WSL-дистрибутиве
`Debian-Bookworm-FS`; web, bot и Ollama находятся в `Ubuntu-24.04`. Из-за одинакового зеркального
LAN-IP у обоих дистрибутивов для бота используется выделенный FreeSWITCH-профиль `bot-vpn` на
`172.16.15.72:15062` (SIP/RTP). Браузер с телефона идёт на LAN WSS `:7443`, а браузер с Windows —
через WSS-переадресацию Ubuntu `:17445` → Debian `:17443` → FreeSWITCH `:7443`. Это временная
репетиционная схема; перенос FreeSWITCH в Ubuntu уберёт междистрибутивный маршрут.
Установленные FreeSWITCH-файлы для этой схемы сохранены в `config/workshops/`: профиль
`freeswitch-bot-vpn-profile.xml`, агент `callcenter-demo.conf.xml` и dialplan
`20_workshop_callcenter.xml`. Последний передаёт SIP From user в исходящий caller ID; иначе бот
видел бы auth-user `1000` вместо `demo-…` и не нашёл бы пользовательский корпус.

Кнопка не утверждает, что вызов уже в очереди после клика: страница сначала проверяет HTTPS,
запрашивает микрофон, подключается к WSS и затем показывает реальные SIP progress/answer/error.
Caller ID страницы передаётся как SIP URI user-part. Перед публичной демонстрацией проверьте
публичный DNS, TLS для HTTPS и WSS `:7443`, доступность RTP и demo credentials.

JsSIP `3.10.0` уже лежит локально в `frontend/assets/jssip-3.10.0.min.js` и подключается страницей без CDN
(SHA-256: `06D3661907F43FD26CED77149BCBBD6D416A728DAE46213A1C10CCEE8A89698B`).

Для WSL используется конфигурация `config/workshops/wslconfig-mirrored-lan.txt`, применяемая в
`%USERPROFILE%\.wslconfig`; после изменения нужен `wsl --shutdown`. В текущей закрытой demo-схеме WSL firewall
отключён. Если на конкретной Windows-сборке он всё же включён или его нужно вернуть для более строгого режима, а
телефон не видит WSS/RTP, правила Hyper-V надо создать из elevated PowerShell (creator ID — WSL mirrored):

```powershell
$vm = "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}"
New-NetFirewallHyperVRule -Name SipBotDemo-WSS -DisplayName "sip-bot demo WSS" -Direction Inbound `
  -VMCreatorId $vm -Protocol TCP -LocalPorts 5066,7443 -RemoteAddresses 192.168.1.0/24 -Action Allow
New-NetFirewallHyperVRule -Name SipBotDemo-RTP -DisplayName "sip-bot demo RTP" -Direction Inbound `
  -VMCreatorId $vm -Protocol UDP -LocalPorts 16384-32768 -RemoteAddresses 192.168.1.0/24 -Action Allow
New-NetFirewallRule -DisplayName "sip-bot demo web" -Direction Inbound -Action Allow -Protocol TCP `
  -LocalPort 8080 -RemoteAddress 192.168.1.0/24 -Profile Private
```
