# Plan-016-C: recorded regression и registered live closeout

Уровень: `child plan`  
Статус: `complete`  
Зависимость: `016-A complete`, `016-B complete`

## 1. Цель

Доказать исправление на исходной записи, controlled corpus, target runtime и зарегистрированном FreeSWITCH path, затем
синхронизировать документы и закрыть Map-016.

## 2. Материализованные правила

| Источник | Правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| `development-guidelines.md` §6 | Обязательный gate нельзя заменить соседними зелёными тестами | Replay + full affected suite + registered call | raw outputs | Любой обязательный check red |
| `ADR-003` | Native imports/operations на target 3.14t, GIL off | WebRTC/faster-whisper operational gate | runtime JSON | GIL on/wrong executable |
| `documentation-process.md` | Обновлять документы-владельцы и registry/backlog | architecture/TS/roadmap/registry/backlog | check scripts | Registry/backlog mismatch |
| `architectural-planning-gate.md` | Binary child closeout и map closeout только по evidence | execution report + blockers | audit | Partial/foundation claim |

## 3. Write-set

Разрешено: replay/live gate tools и tests, `artifacts/implementation/016-speech-evidence/016-C/`, актуальные
`architecture.md`, `technical-specification.md`, `roadmap.md`, `document-registry.md`, `task-backlog.md`, Map/child
status/closeout sections.

Закрытые execution artifacts предыдущих карт не изменяются.

## 4. Gate

1. Host contract/unit/integration regression.
2. Исходный `conversation-stereo.wav`, caller channel: ожидаемые содержательные интервалы сохраняются; hallucinated
   finals/phrase blacklist отсутствуют.
3. Map-008 controlled TTS corpus и synthetic scaled/noise matrix.
4. Target CPython 3.14t: imports, WebRTC operation, faster-whisper operation, GIL off.
5. Deploy/restart на `inrack@10.0.0.45`; readiness/registration active.
6. Registered call/replay через FreeSWITCH: speech answer, barge-in, report, RTP continuity, recording and trace.

## 5. Acceptance

- `Продолжение следует...` и другие no-speech hallucinations не появляются в authoritative context;
- echo во время playback не отменяет TTS; настоящий barge-in отменяет;
- минимум один source-aware ответ и clean call closeout;
- zero runtime errors/dropped mandatory control results;
- ASR rejection и VAD/barge diagnostics присутствуют в evidence;
- все blockers `none/resolved`, документы синхронизированы.

## 6. Blocker register

| ID | Триггер | Статус |
|---|---|---|
| `B-016-C-001` | Target/SIP/GPU недоступны после corrective retry | `not triggered; r3 passed` |
| `B-016-C-002` | Recorded gate зелёный, но реальный registered echo по-прежнему отменяет playback | `not triggered; real barge-in passed without false cancellation` |

## 7. Execution result

- Host regression: `291 passed, 6 skipped`.
- Target Ubuntu 24.04 / CPython 3.14.7t: `294 passed, 3 skipped`, GIL off; WebRTC VAD, faster-whisper и patched
  PJSUA2 выполняли операции в целевом runtime.
- Проблемная запись: четыре ожидаемых хода; три точных no-speech участка отклонены по `no_speech_prob`, без
  фразового blacklist.
- Controlled Map-008 corpus: `3/3` ожидаемых хода.
- Server deploy: `sip-bot.service` прогрет, зарегистрирован как `1002` и доступен через очередь `7100`.
- Registered FreeSWITCH gate: `registered-live-r3`, `status=pass`, четыре user turns, настоящий barge-in,
  source-aware RAG answers, transfer, report, stereo recording, `2792/2792` egress frames и ноль runtime errors,
  drops/underruns.

Corrective runs сохранены, а не перезаписаны: `r1` выявил неполное test-runner environment, `r2` — устаревший
пароль Baresip peer; оба стендовых дефекта исправлены в `r3` без изменения production policy.

Evidence: `artifacts/implementation/016-speech-evidence/016-C/` и map closeout рядом с каталогами child plans.
