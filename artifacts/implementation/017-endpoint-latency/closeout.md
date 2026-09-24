# Plan-017 execution closeout

Статус: `complete`  
Дата: `2026-09-23`

## Результат

Fixed hard-endpoint policy уменьшена с 520 до 360 ms. На живом 20-ms media clock зарегистрированного звонка
фактические authoritative boundaries составили `380`, `362`, `361` и `383 ms`; максимум `383 ms` меньше owner limit
`400 ms`. Четыре реальные пользовательские реплики сохранены, ложных дополнительных final turns нет.

WebRTC VAD не оказался источником прежнего предполагаемого 0.8-s gap: recorded replay снимает speech decision на
следующем 20-ms кадре. Ошибка возникла из сравнения monotonic application timestamps с Baresip WAV timeline,
восстановленным по имени файла с секундной точностью. Изменён существующий consumer `TurnDetector`, новый компонент,
typed edge или delivery owner не добавлялся.

## Изменения

- `config/constants.py`: `ENDPOINT_HARD_MS=360` и rationale;
- `src/sip_bot/speech/endpointing.py`: default hard endpoint 360 ms;
- `tools/vad_energy_replay.py`: machine-checkable turn count/max endpoint expectations;
- `tools/endpoint_latency_probe.py`: real caller + historical 480-ms sensitivity gate;
- `tools/endpoint_live_audit.py`: независимый audit registered result;
- targeted tests для config/default timing и обоих evidence tools;
- technical specification, user guide, roadmap, backlog и registry синхронизированы.

## Evidence

| Gate | Результат |
|---|---|
| Host targeted | `26 passed, 3 skipped`; после audit helper `5 passed` |
| Host full regression | `297 passed, 6 skipped` |
| Target recorded/sensitivity probe | `pass`; CPython 3.14.7t, `Py_GIL_DISABLED=1`, `gil_enabled=false`, 4 real turns, hard 360 ms |
| Historical Map-008 trace | Явно подтверждены 4 turns и один interior split прежней 480-ms паузы |
| Target focused | `29 passed`, затем live-audit tests `2 passed` |
| Target full regression | `301 passed` после синхронизации единого source/test revision |
| Registered FreeSWITCH | `registered-live-r1`, `status=pass`, 4 final turns, barge-in, RAG answers, transfer path, report, RTP/stereo, errors 0 |
| Independent live timing audit | `pass`; `[380, 362, 361, 383] ms`, maximum `383 <= 400` |
| Persistent service | Warmup complete `26443.4 ms`, registration ready, account `1002`, queue `7100` |

Основные artifacts:

- `017-3/target-endpoint-latency.json`;
- `017-5/live-endpoint-audit.json`;
- `017-5/registered-live-r1/registered-j4-full-live.json`;
- `017-5/registered-live-r1/recordings/conversation-stereo.wav`.

## Corrective passes

1. Первоначальная оценка 0.8-s VAD hangover отвергнута после replay на едином clock.
2. Windows native replay не запускался через fallback: локально отсутствует `webrtcvad`; обязательный operation выполнен
   на target patched runtime.
3. Первый target full run столкнулся с работающим service/PJSIP endpoint и завершился C++ abort. После остановки
   сервиса выявилась несинхронная серверная копия tests (старые API/assertions). Полный `src/config/tests` revision был
   синхронизирован, повтор дал `301 passed`; это исправление стенда, не ослабление тестов.
4. После live gate сервис запущен заново и полностью прогрет до регистрации.

## Blockers и остаточные задачи

- `B-017-001`: не сработал — caller recording сохранила четыре хода;
- `B-017-002`: не сработал — новый semantic/rollback boundary не понадобился;
- `B-017-003`: не сработал — target/GPU/SIP stand доступен, live gate pass.

Plan-017 не закрывает downstream latency. Отдельно остаются `TASK-022` filler phrases, `TASK-023` real SIP transfer
completion, `TASK-024` greeting TTS artifact и `TASK-025` natural caller fixture.
