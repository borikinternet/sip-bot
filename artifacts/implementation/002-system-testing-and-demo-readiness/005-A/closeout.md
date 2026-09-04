# 005-A closeout

Дата: `2026-09-04`

`005-A` полностью исполнен и закрыт статусом `complete`. Обязательный scope доказан без изменения SIP/media owner,
typed contracts или approved PJSUA2/PJMEDIA baseline.

Подтверждено:

- deterministic protocol matrix: `5 passed` на CPython 3.14.7t;
- live `OPTIONS` получил `SIP/2.0 200 OK`, вызов принят, удалённый `BYE` обработан, call scope очищен;
- negotiated media: PCMU, payload 0, 8000 Hz, mono, ptime 20 ms;
- media counters: 25 ingress и 25 egress frames, по 8000 bytes, без dropped frames и callback errors;
- Baresip `sndfile` сохранил первичные `enc`/`dec` WAV и manifest с mapping/hash;
- target unit/contract regression: `104 passed, 2 skipped`.

Не утверждается live-воспроизведение `CANCEL` до ответа, peer hold/resume и RTP timeout: в bounded peer-run эти
стимулы deferred, их deterministic normalization coverage сохранена в A1. `egress_underruns=25` относится к probe без
TTS producer и передан в `005-C` для проверки выбора источника тишины/аудио.

Evidence: [`live-20260904-r1`](live-20260904-r1/), [`deterministic-results.md`](deterministic-results.md),
[`commands.md`](commands.md), основной отчёт плана [`plan-005-A`](../../../docs/plans/plan-005-A-protocol-media-failure-matrix.md).
