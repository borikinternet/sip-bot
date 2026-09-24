# Closeout 007-A: WebRTC VAD runtime и no-GIL gate

Статус: `complete`  
Дата: `2026-09-13`  
Plan: [`plan-007-A-webrtc-vad-runtime-gate.md`](../../../../docs/plans/plan-007-A-webrtc-vad-runtime-gate.md)

## Результат

`webrtcvad-wheels==2.0.14` принят как фактический binding WebRTC VAD для текущего target runtime после corrective
patch. Непатчированная native-сборка включала GIL при import; это было исправлено в согласованном `007-A` scope, без
fallback и без process isolation. Патч и его hashes сохранены в [`commands.md`](commands.md).

Patched binding прошёл один и тот же probe в базовом и combined live runtime:

- CPython `3.14.7t`, SOABI `cpython-314t-x86_64-linux-gnu`, `Py_GIL_DISABLED=1`;
- GIL выключен до/после import, construction, operation и controlled concurrency;
- 12 допустимых комбинаций WebRTC frame format/size успешно обработаны;
- 8 независимых instances и 1600 операций controlled concurrency прошли без ошибки;
- 3 invalid input cases явно отвергнуты binding;
- GPU не нужен; live SIP/RTP evidence намеренно не заявляется в этом child plan;
- distribution license — MIT.

## Проверка APG и архитектуры

- изменены только новый probe, патч и собственный `007-A` evidence; application speech boundary не менялась;
- `WebRtcVadCandidate` сохраняет контракт `is_speech(pcm_s16le, sample_rate_hz) -> bool`;
- `PcmFrame`, `VadDecision`, `TurnDetector`, Dispatcher и live composition не затрагивались;
- process isolation, GIL-enabled runtime и amplitude fallback не применялись;
- красный pre-patch результат классифицирован как corrective native compatibility issue внутри write-set и повторно
  проверен после patch.

## Передача в 007-B

`007-B` может использовать exact distribution `webrtcvad-wheels==2.0.14` и patched native artifact. Обязательное
условие: приложение запускается с тем же patched binding, а `007-B` не переопределяет typed contracts и не добавляет
новый adapter/conversion.

Blocker register `B-007-A-001`–`B-007-A-003`: `none` после corrective pass. Следующий checkpoint: `I1`.
