# Хэндофф проекта — 25.09.2026

Это текущее состояние публичного демо Василисы. Предыдущий срез от 24.09 сохранён в docs/handoffs/HANDOFF-2026-09-24.md. Архитектура и план Map-021 — в docs/architecture.md и docs/plans/plan-021-web-rag-conference-demo.md.

## Состояние на момент передачи

- Публичная страница: https://demo.libnas.ru/. Статика теперь находится на первом хопе Apache; внутренний web backend получает только API и WebSocket сессии. SIP WebSocket идёт через отдельный порт 7443.
- Сертификат Let's Encrypt для demo.libnas.ru установлен на первом хопе, действителен до 23.12.2026 20:21 UTC. Автоматическое продление настроено и проверено пробным запуском.
- HTML, JS, CSS, JsSIP, фото и новый QR отдаются с первого хопа. В живом JS текст рядом с QR: «Сканируйте, чтобы открыть Василису: https://demo.libnas.ru/».
- Внешний API и оба WebSocket успешно ответили на сетевые проверки. Полный звонок из браузера через публичный маршрут, включая RTP/аудио, после этого переключения ещё не проверялся. Не считать его подтверждённым.

## Публичная топология

| Участок | Адрес и назначение |
|---|---|
| DNS | demo.libnas.ru CNAME → libnas.ru; libnas.ru A → 195.133.38.235 |
| Первый хоп | Apache на 195.133.38.235, HTTPS 443, HTTP 80, SIP WSS 7443 |
| Туннель | SSH TUN: первый хоп 10.255.0.1 ↔ старый nginx 10.255.0.2 |
| Старый хоп | nginx stream на 142.132.210.94; пересылает 443 и 7443 к публичному шлюзу |
| Шлюз и backend | 82.138.23.215 пробрасывает нужные TCP-порты на внутренний сервер с web backend и FreeSWITCH |

Авторитетный DNS master расположен на первом хопе, secondary — на старом хопе. Оба отвечают demo.libnas.ru CNAME libnas.ru; текущий serial зоны — 2026092501. У новой CNAME TTL 300 секунд, но кэши старой записи могли сохранить прежний TTL 604800 секунд (до семи дней).

## Развёртывание на первом хопе

- Apache: /etc/apache2/sites-available/demo-http.conf и /etc/apache2/sites-available/demo-ssl.conf.
- Порт 80 перенаправляет на HTTPS, кроме /.well-known/acme-challenge/ для Certbot. Challenge webroot: /var/www/html.
- Порт 443: DocumentRoot /srv/demo-front/current. Из него локально отдаются /, /static/* и /assets/*. Только /api/ проксируется на https://10.255.0.2:443/api/, а /ws/ — на wss://10.255.0.2:443/ws/.
- Порт 7443: SIP WebSocket проксируется на wss://10.255.0.2:7443/.
- Текущий каталог статики: /srv/demo-front/current → /srv/demo-front/releases/20260925-88d2b824. Он собран из актуального demo-web/frontend/: index.html в корне, app.js, demo-config.js и styles.css в static/, изображения и JsSIP в assets/. Предыдущий выпуск /srv/demo-front/releases/20260925-faf4380b-cache1 сохранён.
- В развёрнутом index.html ссылки на app.js, demo-config.js и styles.css имеют параметр версии v=20260925-88d2b824. Для HTML и /static/ Apache выставляет Cache-Control: no-cache, must-revalidate. Версионированный HTML отличается этими ссылками от файла в рабочей копии; проверенные JS, CSS и assets совпали по SHA-256.
- Сертификат: /etc/letsencrypt/live/demo.libnas.ru/fullchain.pem и privkey.pem. Certbot использует webroot, certbot.timer включён, deploy hook /etc/letsencrypt/renewal-hooks/deploy/reload-apache.sh перезагружает конфигурацию Apache после обновления.
- Для TLS к старому хопу в Apache пока заданы SSLProxyVerify none и SSLProxyCheckPeerName Off из-за сертификата внутреннего backend. Этот участок проходит внутри SSH-туннеля.

Подключение к первому хопу: сохранённая PuTTY-сессия libnas.ru, пользователь dborisov, ключ в Pageant; sudo работает без пароля. Секреты в handoff не копировать.

## Исходники и рабочая копия

Фронтенд — demo-web/frontend/. Коллега обновил публичные адреса в demo-config.js, формирование API и WebSocket URL и текст рядом с QR в app.js, а также QR-файл assets/qr-demo-domain.png. Browser SIP WSS использует wss://demo.libnas.ru:7443. Файл с SIP demo credentials публичен по замыслу демо; пароль в документацию не переносить.

Базовый коммит до текущих изменений: 3e1d796 от 24.09.2026. Подготовлены изменения demo-web/README.md, frontend/app.js, frontend/demo-config.js, frontend/index.html, замена QR в frontend/assets/, tools/workshops/demo_web_browser_probe.mjs и новый demo-web/tests/test_frontend_public_urls.py. Эти изменения не сбрасывать и не перезаписывать. Код и собственная документация проекта лицензированы по MIT (корневой LICENSE); лицензии сторонних материалов рассматриваются отдельно в docs/licensing-policy.md.

Backend, SIP-бот, Ollama и локальная WSL/FreeSWITCH-схема описаны в архивном handoff от 24.09. Тот файл отражает прошлый локальный срез и содержит уже устаревшие утверждения о публичном домене, сертификате и QR; для публичного маршрута ориентироваться на этот документ.

## Проверки 25.09.2026

- Apache configtest: Syntax OK. Apache и BIND активны, SSH TUN поднят.
- Оба авторитетных DNS-сервера отвечают новым CNAME. С обычным разрешением имени внешний curl попадает на 195.133.38.235 и подтверждает сертификат.
- /, /static/app.js, /static/demo-config.js, /static/styles.css, /assets/jssip-3.10.0.min.js, /assets/project-author.png и /assets/qr-demo-domain.png вернули HTTP 200; до добавления параметра версии их SHA-256 совпали с подготовленным набором файлов. Размеры проблемных ранее ресурсов: JsSIP 279285 байт, фото 1443244 байта.
- /api/session вернул состояние baseline. WebSocket сессии /ws/{session_id} и SIP WebSocket на :7443 оба приняли Upgrade с HTTP 101 Switching Protocols.
- Пробное продление Certbot для demo.libnas.ru прошло успешно после настройки HTTP-перенаправления.
- Живой app.js содержит исправленный QR-текст; живой demo-config.js содержит https://demo.libnas.ru/, новый QR и wss://demo.libnas.ru:7443. HTML ссылается на версионированные JS-файлы.

## Следующие проверки и ограничения

После выпуска, описанного в [хэндоффе 25.09](docs/handoffs/HANDOFF-2026-09-25.md), публичная страница показывает новый фронтенд с портретом и формой URL-импорта. Боевой backend пока старый: `OPTIONS /api/session/example/import-url` возвращает 404. К нему нет доступа для развёртывания изменений; форму URL-импорта можно полноценно проверять после публикации backend. Публичный звонок с этим выпуском не проверен.

1. Выполнить настоящий звонок из внешнего браузера без VPN: микрофон, SIP-сигнализация, RTP в обе стороны, голос Василисы и корректное завершение. HTTP 101 подтверждает только WebSocket-рукопожатие.
2. Проверить загрузку корпуса и выбор соответствующего индекса через публичный /api/ на реальном звонке. Сетевой тест /api/session этого не доказывает.
3. Если отдельный клиент всё ещё попадает на старый IP, проверить его DNS-кэш: старый TTL CNAME был семь дней.
4. При следующем изменении фронтенда создать новый каталог в /srv/demo-front/releases/, переключить symlink current и обновить версию ссылок в index.html. Не менять напрямую исходники коллеги в рабочей копии без синхронизации.
5. Старые задачи по RAG и качеству ответов из handoff от 24.09 остаются без повторной проверки; публичный транспорт их не закрывает.
