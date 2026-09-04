# Propagation checkpoint: `002-A`

Дата: `2026-09-02`

Источник: `artifacts/implementation/002-mvp-media-and-speech-integration/002-A/contract-fixture.md`

Target runtime: Ubuntu-24.04/WSL2, user `sipbot`,
`/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`.

## Materialized contract

`002-A` проверил control-only runtime foundation:

- `ControlEventKind`: `call_open`, `call_close`, `channel_open`, `channel_close`, `terminal`;
- `ControlEvent`: `kind`, `call_id`, `sequence`, `timestamp_ns`, typed `payload`;
- channel scope: optional `channel_id` и `channel_generation`, обязательные и согласованные для channel events;
- payload types: `CallOpen`, `CallClose`, `ChannelOpen`, `ChannelClose`, `Terminal`;
- `ControlEventSink.publish(event)` как минимальная boundary для будущего Dispatcher/FSM;
- `ChannelHandle`, `ChannelLease` и `CancelToken` для scoped lifecycle/cancellation.

## Verified semantics

- один active call;
- idempotent call/channel close и повторное close;
- cancellation scoped channel при закрытии;
- новая generation при переоткрытии channel identity;
- stale dispatch старого закрытого handle не доставляется новому поколению;
- terminal event публикуется до закрытия channel/call;
- audio, крупный text, ASR/TTS streams и RAG fragments не проходят через envelope.

## Evidence

- `../002-A/target-runtime-probe.json` — CPython 3.14.7t, `Py_GIL_DISABLED=1`, `gil_enabled=false`;
- `../002-A/target-pytest.stdout.log` — `12 passed`;
- `../002-A/target-entrypoint.stdout.log` — strict runtime preflight pass;
- `../002-A/lifecycle-trace.json` и `../002-A/terminal-stale-trace.json` — lifecycle/stale traces;
- `../002-A/contract-fixture.md` — contract fields и handoff to `002-E`.

Это уточнение не закрывает SIP/media edges `E1`–`E4` и не реализует Dispatcher/event bus; они остаются scope последующих
child plans.
