# 020-A — локальный WSS/TLS baseline, 23.09.2026

Статус: `complete`; blocker register: `none`; target: WSL `Debian-Bookworm-FS`, FreeSWITCH 1.11.3.

## Команды и наблюдения

1. `wsl -d Debian-Bookworm-FS -u root -- systemctl is-active freeswitch` → `active`.
2. `wsl -d Debian-Bookworm-FS -u root -- fs_cli -x 'sofia status profile internal'` → SIP UDP/TCP `172.22.89.126:5060`, WS `:5066`, WSS `:7443`; CODECS IN/OUT `OPUS,G722,PCMU,PCMA,H264,VP8`. WSL IP динамический; перед новым прогоном брать `wsl -d Debian-Bookworm-FS -- hostname -I`.
3. `wsl -d Debian-Bookworm-FS -u root -- openssl x509 -in /etc/freeswitch/tls/wss.pem -noout -subject -ext subjectAltName -dates` → `CN=FreeSWITCH`, SAN отсутствует, `notBefore=Sep 14 14:13:40 2026 GMT`, `notAfter=Aug 28 14:13:40 2126 GMT`.
4. SHA-256 без публикации private key: `wss.pem=3c1fa614e7964a70977fedafe42dc7ee1475663b4a3f2c08a59c59e14533b844`; `dtls-srtp.pem=5fa32b6c8e768c0f324d3648b197097e04a12c1359ca76f0750b7403d7137b5a`.
5. На Windows: `node tools/workshops/webrtc_wss_probe.mjs 172.22.89.126 7443` → TLS 1.3, `authorized=false`, `DEPTH_ZERO_SELF_SIGNED_CERT`, HTTP `101 Switching Protocols`, `Sec-WebSocket-Protocol: sip`, exit 0. Проба намеренно отключает проверку доверия сертификата **только** ради транспортной диагностики; она не подтверждает пригодность сертификата для обычного браузера.

Конфигурация FreeSWITCH и сертификаты в срезе A не изменялись; SHA-256 `internal.xml` до среза B: `0d2a269e1632fa82e2077aa50ed266c25cd2ef98022d6aeb61037eee8d78beb7`. После A передано в 020-B.
