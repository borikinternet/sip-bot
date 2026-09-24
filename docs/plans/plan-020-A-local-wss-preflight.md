# 020-A: локальный WSS baseline

Уровень: `child plan` · Родитель: [Map-020](plan-020-freeswitch-webrtc.md) · Статус: `complete` · Owner review: локальная репетиция согласована.

## Scope, source-map и правило APG

Один срез — доказать, что локальный FreeSWITCH реально отвечает на WSS/WebSocket upgrade и понять состояние TLS/cert. Write-set: только `artifacts/webrtc/020/A/` и при необходимости узкая конфигурация WSL `/etc/freeswitch/sip_profiles/internal.xml`, `/etc/freeswitch/tls/wss.pem` после backup. Protected: UDP SIP, очереди, bot config, Windows trust store, сервер `10.0.0.45`.

Из [APG](../architectural-planning-gate.md) и [development guidelines](../development-guidelines.md): фактический output WSS (адрес, TLS-ошибки, HTTP 101, subprotocol `sip`) проверяется до подачи в браузер; порт LISTEN сам по себе не является успешным контрактом. Красный WSS upgrade исправляется в этом write-set с повтором, не маскируется `fs_cli status`. Не вводить временное отключение TLS как целевой вариант.

## Проверки и acceptance

1. Зафиксировать WSL IP, сервис, `sofia status profile internal`, `ss -lntup`, `certs_dir`, SHA-256 и subject/SAN/expiry `wss.pem`/`dtls-srtp.pem` (без вывода private key).
2. С Windows выполнить TLS handshake с WSS и настоящий WebSocket upgrade с `Sec-WebSocket-Protocol: sip`; зафиксировать статус `101`, а также ожидаемую недоверенность локального auto-generated cert.
3. При необходимости обновить только локальные WebRTC-параметры/сертификат с backup и повторить WSS/UDP checks. Не импортировать локальный root CA в глобальное хранилище Windows без отдельного решения.

Stop: отсутствие WSS handshake, повреждённый cert, или изменение UDP/очередей. Evidence: команды, stdout/stderr, exit codes, актуальные значения без private key. Blocker register: `none` на старте; обнаруженный красный gate классифицировать по правилам, не закрывать план частично. Fallback: `none`. Следующий план: 020-B.

## Closeout 23.09.2026

Локальный baseline и командный журнал находятся в [A/closeout](../../artifacts/webrtc/020/A/closeout.md). TLS 1.3 и `HTTP 101` с subprotocol `sip` подтверждены. Сертификат самоподписан, SAN отсутствует; это ограничение тестового профиля браузера, не серверное решение. Профиль SIP и сертификаты в срезе A не изменялись. Blocker register: `none`. Передано в 020-B.
