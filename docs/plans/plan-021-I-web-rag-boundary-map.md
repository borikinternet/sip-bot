# 021-I: boundary map web-сессии, RAG и caller ID

Уровень: `child plan` · Родитель: [`Map-021`](plan-021-web-rag-conference-demo.md)
Статус: `complete`
Evidence root: `artifacts/implementation/021-web-rag-sip-demo/I/`

## Цель и граница

Зафиксировать фактические typed edges между web backend, session/RAG registry, PJSUA2 caller ID, readiness gate,
`CallComposition` и существующей очередью FreeSWITCH. Кодовая реализация не входит, кроме минимальных contract fixtures.

## Source-map и write-set

Read-only: `architecture.md`, `technical-specification.md`, `ADR-004`, `ADR-006`, Map-012 RAG lifecycle и Map-020.
Допустимый write-set: только этот plan, contract fixtures/tests и evidence root. Не менять FreeSWITCH config, SIP adapter
или web runtime до принятия revision `web-rag-session-I1`.

## Обязательные контракты

- `session_id`/`caller_id` не проходят через Dispatcher как крупный payload;
- registry lookup возвращает immutable prepared-artifact metadata;
- `NormalizedSipEvent` содержит стабильный caller ID;
- readiness вызывает typed `load_call_rag()` до `200 OK`;
- terminal event вызывает `release_call_rag()`;
- WebSocket допускает только status/heartbeat messages.

## Acceptance и blocker register

Acceptance: source/consumer/owner/lifecycle/backpressure/cancellation/stale policy записаны для E1–E9 Map-021;
caller ID field и fallback semantics имеют одну ревизию; нет нового неразрешённого delivery owner.

| ID | Trigger | Что блокирует | Status |
|---|---|---|---|
| B-021-I-1 | actual PJSUA2 caller field не установлен | 021-C | `resolved by normalized caller_id field and contract test; live trace pending` |
| B-021-I-2 | web/bot process topology не совпадает с shared-registry assumption | 021-A/B/C | `resolved locally: same-machine atomic JSON/artifact registry` |

## Test/evidence

Команды и raw output сохранены в [`I/closeout.md`](../../artifacts/implementation/021-web-rag-sip-demo/I/closeout.md).
Boundary revision `web-rag-session-I1` принята: websocket carries compact status/heartbeat only, the shared local
registry is the cross-process boundary, and PJSUA2 exposes caller ID as a typed event field.

## Fallback/deferred и closeout

Fallback: `none`; baseline fallback является Map-021 behavior, но не разрешает скрыть boundary gap. Closeout возможен
только со статусом `complete` и принятой revision `web-rag-session-I1`.
