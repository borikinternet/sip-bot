# 020-B — локальный браузерный WebRTC-звонок, 23.09.2026

Статус: `complete`; blocker register: `B-020-3` снят. Target: WSL `Debian-Bookworm-FS`, FreeSWITCH 1.11.3, Chrome на Windows. Не является серверным gate.

## Последовательность и diagnosis

1. Изолированный headless Chrome с JsSIP 3.10.0 (`https://jssip.net/download/releases/jssip-3.10.0.min.js`), лабораторные SIP-учётки `1000/1001`. Команда:

   ```powershell
   $env:WEBRTC_PROBE_PASSWORD='Workshop-2026!'
   $env:RUNTIME_NODE_MODULES='C:\Users\dbori_4xv9zwb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
   $sipBotWslIp=(wsl -d Debian-Bookworm-FS -- hostname -I).Trim().Split(' ')[0]
   & 'C:\Users\dbori_4xv9zwb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tools/workshops/webrtc_browser_probe.mjs $sipBotWslIp
   ```

   Скрипт из [tools/workshops/webrtc_browser_probe.mjs](../../../../tools/workshops/webrtc_browser_probe.mjs) использует временный браузерный процесс и `--ignore-certificate-errors` **только** из-за локального self-signed WSS cert. Системное хранилище доверия Windows не менялось. Для server gate C этот bypass недопустим. Обе учётки зарегистрировались по WSS.

2. Первый вызов `1000 → 1001` получил `488 Not Acceptable Here`. Лог FreeSWITCH (`/var/log/freeswitch/freeswitch.log`, около `18:12:04 MSK`) содержит последовательность: `NO candidate ACL defined, Defaulting to wan.auto` → `no suitable candidates found` → `CODEC NEGOTIATION ERROR` → `Responding to INVITE with: 488`. Реальная причина — отфильтрованы приватные IPv4 ICE-кандидаты браузера; совпадение кодеков само по себе не помогло. Это соответствует [описанному поведению FreeSWITCH](https://developer.signalwire.com/freeswitch/users-and-endpoints/webrtc-sip/).

3. Сохранён rollback `/etc/freeswitch/sip_profiles/internal.xml.pre-webrtc-20260923` (SHA-256 `0d2a269e1632fa82e2077aa50ed266c25cd2ef98022d6aeb61037eee8d78beb7`). На локальном WSL установлен штатный Debian `patch`; [узкий патч](../../../../config/workshops/webrtc-candidate-acl.patch) добавил к `internal.xml` одну настройку `apply-candidate-acl=rfc1918.auto`. Команды: `patch --dry-run -d /etc/freeswitch -p0 -i /mnt/c/devel/sip-bot/config/workshops/webrtc-candidate-acl.patch`, затем без `--dry-run`; `fs_cli -x reloadxml`; `fs_cli -x 'sofia profile internal restart'`. Новый SHA-256 профиля: `c2ef8e4ace03068d547d8468d3206c1c1915eb3bd097335cbf049e28defe08b0`. Бот и очереди не менялись.

4. Повторный звонок после настройки: WSS connected и REGISTER у `1000`/`1001`, INVITE содержит `a=ice-ufrag` и `a=fingerprint`, `caller.confirmed`, `RTCPeerConnection.connectionState=connected`, ICE `connected`, DTLS `connected` у обоих клиентов. В контрольном окне ~4,5 с:

   | Endpoint | Audio sent | Audio received |
   |---|---:|---:|
   | 1000 | 229 пакетов / 36 640 байт | 213 / 34 080 |
   | 1001 | 209 / 33 440 | 209 / 33 440 |

   На обеих сторонах local/remote SDP содержали fingerprint, ICE и rtcp-mux; `BYE` завершился. Проба вышла с кодом 0 (`ok: true`). Это доказывает двусторонний поток RTP/SRTP в браузерном тесте; реальное прослушивание человеком отдельно не проводилось (использован fake-audio device).

5. После звонка `show channels` → `0 total`; `sofia status profile internal reg` → `0` (unregister). `systemctl is-active freeswitch` → `active`; очереди `science-bot@default` и `support@default` остались. UDP smoke: `sipsak -s sip:1000@172.22.89.126:5060 -v` → `SIP/2.0 200 OK`, `CSeq: 1 OPTIONS`, exit 0. Это не заменяет повторный голосовой MicroSIP-тест на сервере в C.

## Ограничения и следующий gate

Локальный self-signed сертификат без SAN не годится для обычного браузера; ничего из него не переносить на сервер. `rfc1918.auto` соответствует данному стенду, но для целевого окружения candidate ACL надо выбрать по фактической LAN/public топологии. На сервере `10.0.0.45` изменений не было: он выключен, поэтому 020-C заблокирован до его включения и решения о границе доступа. Private keys в Git/артефакты не копировались.
