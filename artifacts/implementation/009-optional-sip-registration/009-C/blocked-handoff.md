# 009-C blocked handoff

Дата: 2026-09-13  
Статус: `blocked`  
План: [`plan-009-C-freeswitch-workshop-integration.md`](../../../../docs/plans/plan-009-C-freeswitch-workshop-integration.md)

Этот handoff передаёт результат main executor-у для отдельного corrective
scope. Исправление существующего PJSUA2 inbound-answer path в рамках 009-C не
выполнялось.

## Выполнено успешно

### C1 — preflight и готовность стенда

- Docker Desktop и WSL `Ubuntu-24.04` доступны.
- FreeSWITCH image зафиксирован digest-ом; версия runtime — `1.10.12`.
- `docker exec sip-bot-freeswitch-workshop fs_cli -x status` завершился с
  exit code `0` и вернул `UP ... is ready`.
- Контейнер: `running`, health `healthy`, `RestartCount=0`.
- Healthcheck оставлен на `fs_cli -x status | grep '^UP'`: прямой вывод
  действительно начинается с `UP`, поэтому это не ложный healthcheck defect.
- Evidence: [`preflight-healthcheck.md`](preflight-healthcheck.md).

### C2 — воспроизводимый FreeSWITCH fixture

- Создан локальный Docker/FreeSWITCH fixture с registrar, bot account `tester`,
  peer account `peer` и workshop extension `7000`.
- Extension `7000` явно маршрутизируется в
  `bridge(user/tester@${domain_name})` через prefixed
  `config/dialplan/00_sip_bot_workshop.xml`; это исправляет прежний `480`, при
  котором vanilla `enum` перехватывал extension раньше workshop route.
- Образ и конфигурация воспроизводимы через compose; публичный demo credential
  не считается production secret.
- Startup password upstream entrypoint не принимается как evidence.

### C3 — enabled REGISTER

- Baresip peer и бот успешно зарегистрировались в локальном FreeSWITCH.
- Зафиксирован `200 OK`, readiness event `registered`, а также наличие обеих
  registrations в `fs_cli show registrations`.
- Источник: [`registered-call-r1.json`](registered-call-r1.json), поле
  `checks.bot_and_peer_registered=true` и registration event с `status_code=200`.

## Blocker

### `B-009-C-004` — existing inbound-answer path

После corrective pass маршрута FreeSWITCH:

1. принял вызов peer на `7000`;
2. выбрал `sip-bot-registered-endpoint`;
3. выполнил `bridge(user/tester@...)`;
4. отправил INVITE зарегистрированному PJSUA2 endpoint.

Далее существующий `SipMediaAdapter._on_incoming_call` завершился нативным
PJSIP abort до SIP answer:

```text
pjsip_dlg_modify_response: Assertion `st_code >= 100 && st_code <= 699` failed.
```

Проверка target runtime показала, что `pjsua2.CallOpParam(True)` создаётся с
`statusCode=0`. Exit code probe — `134`. Поэтому answer, PCMU/RTP, media и full
AI evidence не объявлены успешными.

Точный scope следующего corrective plan: исправить существующий inbound-answer
lifecycle так, чтобы ответ materialized с корректным успешным SIP status code,
затем повторить C4 и C6. 009-C намеренно не менял PJSUA2 lifecycle.

- Полное evidence: [`registered-call-r2.json`](registered-call-r2.json).
- Full-AI gate: отдельно отложен, без запуска тяжёлого cold GPU inference:
  [`full-ai-gate-deferred.md`](full-ai-gate-deferred.md).

## Остальные проверки

- C5 contract checks: `5 passed`, exit code `0`:
  [`c5-registration-contract-output.txt`](c5-registration-contract-output.txt).
- В artifacts нет public password, SIP Authorization headers или raw startup
  credential; сохранены только санитизированные evidence.
- `docker compose config` — exit code `0`.
- `git diff --check` — exit code `0`.

## Изменённые файлы 009-C

### Fixture и probe

- `tools/freeswitch_workshop/docker-compose.yml`
- `tools/freeswitch_workshop/scripts/entrypoint.sh`
- `tools/freeswitch_workshop/scripts/healthcheck.sh`
- `tools/freeswitch_workshop/registered_call_probe.py`
- `tools/freeswitch_workshop/config/README.md`
- `tools/freeswitch_workshop/config/directory/default/tester.xml`
- `tools/freeswitch_workshop/config/directory/default/peer.xml`
- `tools/freeswitch_workshop/config/dialplan/00_sip_bot_workshop.xml`
- `tools/freeswitch_workshop/config/dialplan/public/90_sip_bot_workshop.xml`
- `tools/freeswitch_workshop/config/baresip-peer/config`
- `tools/freeswitch_workshop/config/baresip-peer/accounts`

### Evidence

- `artifacts/implementation/009-optional-sip-registration/009-C/preflight-healthcheck.md`
- `artifacts/implementation/009-optional-sip-registration/009-C/registered-call-r1.json`
- `artifacts/implementation/009-optional-sip-registration/009-C/registered-call-r2.json`
- `artifacts/implementation/009-optional-sip-registration/009-C/c5-registration-contract-output.txt`
- `artifacts/implementation/009-optional-sip-registration/009-C/full-ai-gate-deferred.md`
- `artifacts/implementation/009-optional-sip-registration/009-C/blocked-handoff.md`

### Plan checkpoint

- `docs/plans/plan-009-C-freeswitch-workshop-integration.md` — статус
  `blocked`, без изменения main registry/backlog/roadmap.
