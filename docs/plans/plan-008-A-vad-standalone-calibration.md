# Plan-008-A: standalone calibration WebRTC VAD

Уровень: `child plan`  
Статус owner review: `accepted by explicit execution instruction`  
Статус исполнения: `complete`  
Родительская карта: [`plan-008-vad-turn-calibration.md`](plan-008-vad-turn-calibration.md)  
Предшественник: [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md)  
Evidence root: `artifacts/implementation/008-vad-turn-calibration/008-A/`

## 1. Цель и границы

Независимо от полного SIP-бота сравнить режимы `0..3` ранее принятого WebRTC VAD на воспроизводимом наборе русских
TTS-фраз одного фиксированного голоса в телефонном PCM-тракте.

Вход калибровки — сохранённые TTS-фразы и timing manifest. Выход — immutable corpus, raw VAD masks, scorecard и
evidence-based mode recommendation. ASR, LLM, Dispatcher, TurnDetector и SIP live gate в этот child plan не входят.

## Применимые документы и извлечённые правила

Применимые правила материализованы в таблице ниже и в parent Map-008: typed-first, target no-GIL runtime, immutable
evidence, no silent simplification, ASR только как diagnostic и binary child closeout. Повторное описание общих
требований не создаёт новый source of truth; источником остаётся Map-008 и ссылки из неё.

## Граница задачи

Входит только test-only corpus generation, PCMU conditioning, standalone WebRTC mode sweep, raw masks, metrics и
evidence. Не входят production `src/` changes, TurnDetector, ASR/LLM, SIP/live gate и новый fallback.

## 2. Материализованные правила

| Источник/правило | Применение | Проверка | Stop condition |
|---|---|---|---|
| Map-008: один голос, много фраз, manifest — первичная разметка | Не перегенерировать WAV в сравнительном цикле; offsets берутся из сборщика | Fixture manifest/hash audit | Нет повторяемого manifest |
| Map-008: phone baseline PCMU/8 kHz/mono/20 ms | Перед VAD выполнить явный codec round-trip и frame replay | Media manifest | Требуется новый production media edge |
| Map-008: ASR только diagnostic | Не использовать ASR для принятия VAD mode | Tool dependency audit | Попытка замкнуть acceptance на ASR |
| APG/development-guidelines: raw output, tests, corrective, no simplification | Сохранить masks, metrics, exit codes; не выбрасывать неудобные фразы | Evidence audit | Category-4 gap или silent corpus reduction |
| ADR-003/Map-007: target no-GIL native binding | Использовать target `3.14.7t` и exact patched binding | Runtime/import/operation probe | Binding/API failure без разрешённого patch |

## 3. Source-map и write-set

| Объект | Действие | Допустимый write-set |
|---|---|---|
| TTS corpus | Создать набор фраз одного голоса, offsets и пауз | `artifacts/implementation/008-vad-turn-calibration/008-A/` |
| Phone conditioner | Реализовать test-only PCMU round-trip/frame replay | `tools/vad_calibration_probe.py` и tests, без `src/` |
| VAD sweep | Создавать отдельный `WebRtcVad` instance для каждого mode и прогонять кадры последовательно | Новый tool/tests/evidence only |
| Reports | Сохранить raw masks, scorecard, hashes, commands, exit codes | Собственный evidence root |

Protected: `src/sip_bot/`, `config/constants.py`, live tools, Map-I, Map-007 evidence и unrelated docs.

## Owner-review решения

| Вопрос | Решение | Статус |
|---|---|---|
| Можно ли использовать один голос TTS и много фраз? | Да, это выбранный controlled baseline; fixture сохраняется один раз | `resolved by Map-008 owner instruction` |
| Нужен ли ASR для выбора mode? | Нет; expected intervals задаёт timing manifest | `resolved by Map-008 owner instruction` |
| Можно ли менять production code в A? | Нет; A ограничен test-only tool/evidence | `resolved by write-set` |

Новых открытых owner-review вопросов в пределах A нет.

## 4. Тестовая методика

Корпус должен содержать разные длины и фонетические составы, числа/имена/термины, контролируемые паузы около 300/500
ms и более длинную тишину. Для каждой фонограммы manifest фиксирует expected speech blocks и semantic turn structure.

Для каждого mode `0..3`:

1. загрузить один и тот же hash;
2. привести/проверить `mono PCM S16LE, 8 kHz`;
3. выполнить PCMU encode/decode round-trip;
4. разбить результат на последовательные 20-ms frames;
5. вызвать `is_speech` без ASR и без параллельного изменения порядка кадров;
6. сохранить каждое решение, timing и error;
7. посчитать missed speech, false speech, onset/offset delay и fragmentation;
8. повторить хотя бы один run на том же hash для проверки детерминизма.

Выбор mode выполняется по scorecard на всём corpus. Если trade-off не даёт единственного победителя, сохраняется
явная рекомендация и причина сохранения mode 2; это не разрешает подобрать фразы или скрыть неудобный результат.

## 5. Acceptance и blocker register

`008-A` принимается, если immutable corpus и manifest повторяемы, все mode runs имеют raw output/exit code, сравнение
проведено на всём наборе, deterministic replay подтверждён, а mode recommendation сформулирована с ограничениями.

| ID | Триггер | Статус |
|---|---|---|
| `B-008-A-001` | Target binding/operation Map-007 не может быть использован | `none until triggered` |
| `B-008-A-002` | Нельзя получить immutable TTS corpus с известными offsets | `none until triggered` |
| `B-008-A-003` | Нужен новый production audio boundary | `none until triggered` |

Красные tests/metrics в собственном write-set требуют corrective pass. Новый production owner, boundary или fallback —
blocker и owner review.

## 6. Handoff

Closeout передаёт `008-B` corpus revision/hash, выбранный baseline mode, raw masks, scorecard, exact commands и
ограничения. `008-B` не принимает рекомендацию по пересказу агента без сохранённого evidence.

## 7. Interaction topology и propagation contracts

Production interaction topology для `008-A` неприменима: child plan не соединяет production components. Test-only
edges фиксированы явно:

```text
fixture PCM frame → WebRtcVadCandidate.is_speech(pcm_s16le, sample_rate_hz)
                    → bool + mode-labelled raw decision
```

`VadDecision` и `TurnDetector` не вызываются в A. Их propagation проверяется в `008-B`; новый delivery-owner не
создаётся.

## 8. Audit владельца поведения и парадигмы реализации

`WebRtcVadCandidate` остаётся владельцем только frame classification. `vad_calibration_probe.py` владеет replay,
fixture labels и metrics, но не становится частью application runtime. Один VAD instance используется
последовательно для одной mode-run; между modes создаётся новый instance, чтобы state не переносился.

## 9. Process invariant audit

| Правило | Применение | Evidence |
|---|---|---|
| Typed-first и direct data | Probe передаёт bytes/rate в существующий candidate API напрямую | Tool source audit |
| Deterministic evidence | Один corpus/hash и один frame order используются всеми modes | Manifest and repeated run |
| Corrective pass | Ошибка probe/метрика сохраняется, классифицируется и повторяется после исправления | Raw output/exit code |
| No simplification | Не удалять фразы или неудобные паузы ради лучшего mode | Corpus revision/diff |
| Binary closeout | A закрывается `complete` или `blocked`, не partial | Closeout audit |

## 10. Architecture invariant audit

| Инвариант | Проверка |
|---|---|
| Native WebRTC binding запускается в target free-threaded runtime | Runtime/GIL manifest и operation result |
| Supported input is `mono PCM S16LE`, 8 kHz, 20 ms | Frame validator and media manifest |
| Calibration tool не меняет production ownership/edges | Source-map and forbidden-path audit |
| ASR не является первичной разметкой | Dependency audit |

## 11. Implementation slices

| Срез | Действие | Acceptance | Stop condition |
|---|---|---|---|
| `A1` | Сгенерировать и сохранить corpus/manifest | Immutable hashes и expected intervals | Невозможен повторяемый corpus |
| `A2` | Выполнить PCMU conditioning и frame replay | Явный 8 kHz/20 ms trace | Нужен production boundary |
| `A3` | Выполнить modes `0..3` и repeated replay | Raw masks, metrics, recommendation | Native/API gap без решения |
| `A4` | Сохранить closeout/handoff | `008-B` получает evidence | Отсутствует обязательное evidence |

## 12. Test plan и evidence

Основная команда — target `CPython 3.14.7t` с patched binding из Map-007:

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/vad_calibration_probe.py --corpus-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/corpus --output-root /mnt/c/devel/sip-bot/artifacts/implementation/008-vad-turn-calibration/008-A/runs/mode-sweep'
```

Expected evidence: JSON с `status`, executable/SOABI/GIL, corpus hashes, modes, frame contract, raw decisions,
metrics, errors и exit code. Host Python не заменяет target evidence.

## 13. Fallback/deferred register

| Вариант | Статус |
|---|---|
| `_AmplitudeVad` как control comparison | allowed only as explicit deterministic comparison; не выбирает live mode |
| ASR-derived label | diagnostic only, не gold label |
| Human/noise corpus | deferred future map |
| Изменение WebRTC algorithm или новый fallback | forbidden; owner review required |

## 14. Execution report и closeout

Closeout обязан содержать фактические files/symbols, immutable corpus revision, commands/exit codes, target runtime/GIL,
scorecard всех modes, repeated replay, raw failures/corrective pass, pre-existing/out-of-scope findings, deferred items,
registry/backlog audit и handoff в `008-B`. `complete` разрешён только после полного A scope.
