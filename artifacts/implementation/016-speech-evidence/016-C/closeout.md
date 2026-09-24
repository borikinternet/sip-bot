# 016-C closeout

Статус: `complete`

- Host regression: `291 passed, 6 skipped`.
- Target regression: `294 passed, 3 skipped`, CPython 3.14.7t, GIL off.
- Registered FreeSWITCH `r3`: `status=pass`, four user turns, real barge-in, source-aware answers, transfer and report.
- RTP: expected/egress `2792/2792`; underruns, drops, callback errors and runtime errors are zero.
- Recording: `registered-live-r3/recordings/conversation-stereo.wav`, 55.83625 s, left=user, right=bot.
- Service after gate: active, warmup complete, registration ready, queue `7100`.
- Blockers: none.

Failed corrective attempts `r1` and `r2` remain beside the accepted `r3`; their causes and resolution are recorded in
the map closeout.
