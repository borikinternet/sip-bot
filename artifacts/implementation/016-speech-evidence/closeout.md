# Map-016 execution closeout

Статус: `complete`  
Дата: 2026-09-22

## Результат

Исправлены два независимых слоя исходного дефекта без phrase blacklist, amplitude-VAD fallback и новой AEC/media
reference edge:

- `AdaptiveEnergyGate` использует robust per-call near-end reference и отдельный строгий barge-in threshold;
- `FasterWhisperC2Backend` сохраняет typed model evidence, а `SpeechIngress` атомарно отбрасывает matching rejected
  final без `FinalUserTurn`;
- если слабый кадр уже открыл локальный VAD-ход, последующая подтверждённая near-end речь в том же ходе всё равно
  материализует `BARGE_IN` через существующий control edge.

## Evidence

- Исходный звонок: `016-B/problem-call-vad-replay.json`, authoritative turns `12 → 4`.
- ASR model gate: `016-A/problem-call-speech-evidence.json`; четыре настоящих хода приняты, три точных ложных
  интервала отклонены (`no_speech_prob=0.883…0.941`).
- Controlled corpus: `016-B/controlled-corpus-replay.json`, `3/3` ожидаемых хода.
- Host suite: `291 passed, 6 skipped`.
- Target Ubuntu 24.04 / CPython 3.14.7t: `294 passed, 3 skipped in 51.88s`, GIL off; native PJSUA2 operation прошла.
- Server affected suite: `33 passed` перед deploy.
- Deploy: systemd service прогрет за `26.7 s`, регистрация `200 OK`, account `1002`, queue `7100`.
- Registered gate: `016-C/registered-live-r3/registered-j4-full-live.json`, `status=pass`.
  Четыре user turns, source-aware ответы, настоящий barge-in, подтверждённый transfer, report и stereo WAV;
  `2792/2792` egress frames, `egress_underruns=0`, drops/callback/runtime errors `0`.

Первый registered run (`r1`) зафиксировал неполное test-runner library environment. Второй (`r2`) корректно прогрел
runtime, но FreeSWITCH отклонил устаревший peer secret кодом `403`; заведомо несостоявшийся звонок был остановлен.
Оба результата сохранены как corrective trace. `r3` повторён с фактическим runtime environment и текущей стендовой
учётной записью, без изменения application policy.

## APG audit

- Все child plans `016-I`, `016-A`, `016-B`, `016-C` имеют бинарный статус `complete` и собственное evidence.
- Accepted revision `speech-evidence-I1` проведена producer-first до consumers; новый delivery owner не создан.
- Protected baseline сохранён: WebRTC VAD mode 2, hard endpoint 520 ms, один звонок, direct data plane,
  Dispatcher/FSM control plane и free-threaded target runtime.
- Blockers `B-016-001…003` и `B-016-C-001…002` не сработали; AEC/media-reference остаётся только условным будущим
  gap при новом отрицательном evidence.
- Документы-владельцы, roadmap, registry и backlog синхронизированы.

## Primary artifacts

- `016-C/registered-live-r3/recordings/conversation-stereo.wav`;
- `016-C/registered-live-r3/reports/call-in-0-168e8f4344f647a7a70c39440c3779b4/report.md`;
- `016-C/registered-live-r3/registered-j4-full-live.json`;
- `016-A/problem-call-speech-evidence.json`;
- `016-B/problem-call-vad-replay.json`.
