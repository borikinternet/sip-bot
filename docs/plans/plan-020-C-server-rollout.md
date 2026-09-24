# 020-C: перенос WebRTC на целевой FreeSWITCH

Уровень: `child plan` · Родитель: [Map-020](plan-020-freeswitch-webrtc.md) · Статус: `blocked before execution` · Owner review: `open` (LAN или Internet; DNS/certificate path).

## Scope и source-map

Цель — включить на `inrack@10.0.0.45` подтверждённый в A/B SIP-over-WSS путь и доказать браузерный звонок. Целевой FreeSWITCH работает в Debian `systemd-nspawn` поверх Ubuntu 22.04; source-map после восстановления SSH уточнить фактическими путями: `/etc/freeswitch/sip_profiles/internal.xml`, `$${certs_dir}` (`wss.pem`, `dtls-srtp.pem`), host/container firewall, доступный DNS/порт 7443, RTP UDP range, `callcenter.conf.xml`, dialplan.

Из [APG](../architectural-planning-gate.md) и [development guidelines](../development-guidelines.md): защищённый baseline копируется и сравнивается до изменения; серверный SSL доверяется браузером без test bypass; REGISTER, DTLS/ICE и media проверяются независимо; существующие UDP звонки и очереди проходят регрессию. Нельзя объявлять `WSS-BIND-URL` готовым WebRTC или переносить локальный self-signed сертификат как публичный.

## Порядок и acceptance

1. После включения сервера — SSH и fresh snapshot service/profile/cert/listeners/firewall; сравнить с локальным evidence. До изменения сохранить точный rollback в защищённом каталоге на сервере.
2. Уточнить LAN/public; для публичного доступа согласовать FQDN, сертификат с верной SAN/цепочкой, TCP/WSS и UDP RTP/ICE достижимость. Для LAN — доверенный тестовым браузером cert на выбранное имя; private key не помещать в Git/artifacts. Локальный `wss.pem` без SAN и browser `--ignore-certificate-errors` в server gate не переносить.
3. Применить факт из [020-B](../../artifacts/webrtc/020/B/closeout.md): при браузерных ICE-кандидатах из частной сети отсутствие `apply-candidate-acl` привело к `488`; локально помог `rfc1918.auto`. На сервере выбрать repeatable candidate ACL по фактическим допустимым сетям, не считать локальный патч универсальным для Internet.
4. Внести минимальные изменения, restart/reload по фактическим требованиям FS, проверить WSS/TLS, browser REGISTER, вызов, ICE/DTLS-SRTP и двусторонний media. Проверить обычные MicroSIP/очереди и rollback при регрессии.
5. Сохранить raw команды, выходы, сертификатные метаданные (без ключей), звонок/статистику, closeout и runbook. Повторно оценить APG, реестр и backlog.

Blockers: `B-020-1` сервер выключен; `B-020-2` не выбран LAN/public. Stop: любой из них или регрессия SIP/RTP/queue. Fallback: `none`. Никакого серверного исполнения до снятия блокеров.
