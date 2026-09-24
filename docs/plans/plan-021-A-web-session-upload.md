# 021-A: web-сессия, upload и heartbeat

Уровень: `child plan` · Родитель: [`Map-021`](plan-021-web-rag-conference-demo.md)
Статус: `complete`
Evidence root: `artifacts/implementation/021-web-rag-sip-demo/A/`

## Цель и граница

Создать минимальный backend/frontend foundation под `demo-web/`: временная web-сессия, назначение caller ID,
WebSocket ping-pong около 5 секунд, загрузка `.md`/`.txt`/текстового `.pdf` до `640 KiB`, status API и переходы `created → preparing →
ready/failed/stale`.

Авторизация, SIP media и RAG embeddings в этот child plan не входят.

## Source-map, owner и write-set

Владелец поведения: `WebSessionRegistry` и `UploadStatusService`. Write-set: новые файлы `demo-web/`, focused tests
и evidence root; существующий SIP/RAG runtime не менять. Принятый кандидат backend runtime — Python `aiohttp` в
локальном demo sidecar: он закрывает HTTP/static/upload/WebSocket в одном минимальном процессе. До первого code slice
нужен import probe и фиксация фактической версии/установки в execution report.

## Acceptance

- reload создаёт новую volatile session;
- caller IDs уникальны в пределах demo lease;
- heartbeat death удаляет только waiting/preparing mapping;
- active-call lease не удаляется heartbeat-ом;
- upload boundary принимает ровно `640 KiB`, larger payload отвергается;
- status event `rag_ready` содержит corpus title/topic/questions и разрешает button;
- websocket reconnect не оживляет старую session автоматически;
- no auth is explicit and visible in runbook.

## Blocker register

| ID | Trigger | What blocks | Status |
|---|---|---|---|
| B-021-A-1 | target URL/session hosting topology unknown | final browser deployment | `open — URL is still external input` |
| B-021-A-2 | `aiohttp` unavailable in selected local demo runtime | backend execution | `resolved locally: aiohttp 3.14.3` |

## Test/evidence и closeout

Unit/contract tests cover leases, size, status schema, WebSocket `ping/pong`, `rag_ready` and active-call retention;
the local selector is green (`demo-web/tests`: `6 passed`). The final URL/browser deployment remains deferred, so
the plan is complete for the local sidecar foundation but does not claim a hosted conference gate. Evidence is in
[`A/closeout.md`](../../artifacts/implementation/021-web-rag-sip-demo/A/closeout.md).
