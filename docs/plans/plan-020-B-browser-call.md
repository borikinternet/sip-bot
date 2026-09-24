# 020-B: браузерный SIP/WebRTC звонок

Уровень: `child plan` · Родитель: [Map-020](plan-020-freeswitch-webrtc.md) · Статус: `complete` · Owner review: локальная репетиция согласована.

## Scope и границы

Один vertical slice — два браузерных SIP endpoint регистрируются по WSS и завершают аудиозвонок с ICE/DTLS-SRTP и ненулевыми media counters. Использовать изолированный тестовый профиль Chromium и две лабораторные SIP-учётки 1000/1001. Существующие очереди и бот не менять. Серверный SSL trust этим тестом не подтверждается.

Write-set: `tools/workshops/webrtc_browser_probe.mjs`, `config/workshops/webrtc-candidate-acl.patch`, `artifacts/webrtc/020/B/`; локальный FreeSWITCH config только по отдельному corrective pass после A и backup. Protected: основное приложение, Windows global trust store, сервер.

Из [APG](../architectural-planning-gate.md) и [development guidelines](../development-guidelines.md): registration, call setup, ICE/DTLS и media — разные обязательные evidence; зелёный REGISTER не компенсирует нулевой RTP. Browser WebRTC ↔ `mod_sofia` SIP/WSS и ICE/DTLS media — явные двусторонние границы, завершение BYE и unregister проверяются. Использовать открытый SIP browser client (JsSIP) в тестовом harness, не писать собственный SIP стек.

## Acceptance и stop conditions

1. WSS `connected`, оба REGISTER успешны, `sofia status profile internal reg` содержит WebSocket contacts.
2. Вызов `1000 → 1001`, `answered`, SDP содержит fingerprint/ICE, выбранная ICE-пара работает; `RTCPeerConnection.getStats()` показывает bytes/packets sent/received > 0 с обеих сторон.
3. Завершение звонка/BYE и unregister без зависших каналов; последующий обычный UDP smoke прежних функций при наличии тестового peer.
4. Если browser в тесте принимает самоподписанный cert через scoped test option, отчёт явно помечает доверие к WSS TLS как **непроверенное**; C требует сертификат с валидным именем и цепочкой.

Stop: нет media/ICE, WebRTC не может зарегистрироваться, меняется protected baseline. Blocker register: `B-020-3` из карты; новые причины записывать с raw evidence и corrective pass. Fallback: `none`. Следующий план: 020-C после включения сервера и owner decision о LAN/public.

## Corrective pass и closeout 23.09.2026

Первый звонок вернул `488`: в логе FreeSWITCH — `NO candidate ACL defined`, затем `no suitable candidates found`. Применён узкий [patch](../../config/workshops/webrtc-candidate-acl.patch), задающий `apply-candidate-acl=rfc1918.auto`, после копии исходного SIP-профиля и без правки очередей/бота. Повтор подтвердил оба REGISTER, ответ, ICE/DTLS `connected`, ненулевые пакеты в обе стороны, BYE и отсутствие зависших каналов. UDP OPTIONS вернул `200 OK`; обе очереди остались загруженными. Полный командный журнал и ограничения — [B/closeout](../../artifacts/webrtc/020/B/closeout.md). `B-020-3` снят. Следующий gate — 020-C, не автоматический перенос локального сертификата.
