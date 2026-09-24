# 009-C1 closeout — inbound answer и readiness gate

Дата: `2026-09-13`  
Статус: `complete`  
Plan: [`plan-009-C1-inbound-answer-readiness-gate.md`](../../../docs/plans/plan-009-C1-inbound-answer-readiness-gate.md)

## Результат

Исправлен входящий registered-call lifecycle:

```text
INVITE → 180 Ringing → readiness/warmup → 200 OK
                         └─ failure → 503
```

`180` отправляется непосредственно SIP adapter-ом и не ждёт AI. Aggregate warmup выполняется через основной
`asyncio`-контур вне native callback и event-loop blocking. При remote terminal event pending admission отменяется или
устаревший результат отбрасывается; поздний `200` не отправляется.

## Evidence

- Target registered FreeSWITCH/Baresip probe: [`registered-call-r7.json`](registered-call-r7.json) — `status=pass`,
  process exit code `0`.
- Target runtime: patched free-threaded CPython `3.14.7t`, `py_gil_disabled=1`, `gil_enabled_at_finish=false`.
- SIP/media: `180` перед `200`, `PCMU`, `8000 Hz`, mono, `ptime=20 ms`, `160 samples/frame`, `320 bytes/frame`;
  native abort отсутствует.
- Media counters: ingress/egress overflow `0`, `egress_underruns=0`, callback errors `0`.
- Target checks: registration/auth, incoming registered call, provisional/final answer ordering, media start, codec
  profile, bounded ingress and sanitised evidence — все `true`.

## Tests

```text
python -m pytest tests/unit/test_incoming_answer_readiness.py tests/unit/test_sip_media.py tests/integration/test_runtime_wiring.py tests/integration/test_map005_protocol_media.py -q
28 passed in 0.54s

python -m pytest -q
183 passed, 5 skipped in 0.97s

python tools/check_document_registry.py
PASS

python tools/check_task_backlog.py
PASS

git diff --check
PASS
```

## Ограничение evidence

`registered-call-r7` использует детерминированную readiness handoff после наблюдения `180`, чтобы изолированно
доказать исправленный SIP/media lifecycle. Реальный cold-start вызов aggregate `ApplicationRuntime.warmup()` покрыт
ready/cold/failure/cancel тестами gate; отдельный повторный тяжёлый GPU-прогрев в этом corrective closeout не выполнялся.
Production/workshop launcher обязан подключать те же `is_ready`/`warmup` callbacks; финальный `200` до прохождения
этого gate остаётся недопустимым.

## Handoff

`B-009-C-004` снят. SIP/media C4 и C6/runbook продолжаются без него. При попытке full-AI registered replay обнаружен
новый blocker `B-009-C-006`: adapter-generated `call-in-0` не связан с заранее созданным composition id. Исполнение
`009-C` остановлено до owner review и отдельного APG plan для dynamic incoming-session composition.
