# Corrective Plan-017: ограничение задержки конца пользовательского хода

Уровень: `child plan / corrective slice`  
Статус: `complete`  
Owner review: `accepted by explicit owner requirement, 2026-09-22`

## 1. Цель и проверяемый результат

Отделить время классификации WebRTC VAD от времени, намеренно добавляемого `TurnDetector`, и уменьшить
authoritative hard endpoint с прежних 520 ms до значения, которое гарантированно укладывается в заданный владельцем
предел 300–400 ms на 20-ms телефонном frame clock.

План считается выполненным только если:

- WebRTC VAD на реальной caller-дорожке завершает speech range без скрытого многосекундного tail;
- каждый authoritative hard endpoint имеет `silence_ms <= 400`;
- на записи реального звонка сохраняются четыре содержательных пользовательских хода;
- изменение проверено на target CPython 3.14t с отключённым GIL и в зарегистрированном звонке через FreeSWITCH;
- старая искусственная 480-ms пауза не маскируется: её новое поведение явно зафиксировано как следствие изменённого
  требования.

## 2. Фактический дефект и измерительная поправка

Первоначальное сравнение monotonic timestamps приложения с WAV timeline, восстановленным по имени файла Baresip с
секундной точностью, ошибочно приписало WebRTC VAD приблизительно 0.8 s задержки. Replay той же caller-дорожки на
едином frame clock показал:

- переход WebRTC VAD из speech в silence происходит на следующем 20-ms кадре;
- `TurnDetector` затем намеренно ждёт `ENDPOINT_HARD_MS=520`;
- оставшиеся примерно 1.6–1.8 s до начала ответа относятся к downstream ASR/retrieval/LLM/TTS и не входят в этот
  plan.

Следовательно, меняется не алгоритм WebRTC VAD, а fixed endpoint policy его consumer-а.

## 3. Применимые правила

| Источник | Материализованное правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| `requirements.md` / owner instruction | Пользователь оценивает суммарную паузу; speech boundary не должен занимать больше 300–400 ms | Hard endpoint получает верхнюю границу 400 ms | recorded + live timing | Любой hard endpoint превышает 400 ms |
| `architecture.md` | VAD классифицирует кадр, `TurnDetector` владеет endpoint state | Владелец и typed boundaries не меняются | source/interaction audit | Потребовался новый component или edge |
| `technical-specification.md` | Параметры endpointing конфигурационные, hard endpoint authoritative | Меняется только константа и проверки её фактического действия | config/contract tests | Скрытый default либо иной runtime value |
| `development-guidelines.md` §6–§7 | Красный обязательный gate исправляется; упрощение и ослабление теста запрещены | Старая 480-ms пауза остаётся sensitivity evidence и явно меняет ожидаемый результат | old corpus replay + real caller replay | Старый конфликт удалён или скрыт |
| `ADR-003` | Native operation проверяется в target free-threaded runtime | WebRTC operation и replay выполняются на CPython 3.14t, GIL off | runtime evidence | GIL включён или runtime иной |
| `architectural-planning-gate.md` | Corrective plan имеет scope, blockers, evidence и бинарный closeout | Этот plan-file и отдельный artifact root | APG/registry/backlog audits | Открытый category-4 blocker |

## 4. Граница задачи

```text
Входит:
  измеримый VAD/endpoint timing на едином 20-ms frame clock;
  ENDPOINT_HARD_MS и default EndpointingConfig;
  recorded caller-channel regression;
  явная sensitivity-проверка старой 480-ms TTS-паузы;
  target/no-GIL и registered live validation.

Не входит:
  filler phrases при ожидании AI;
  downstream ASR/retrieval/LLM/TTS latency;
  реальный SIP transfer completion;
  содержимое/разбиение greeting TTS;
  изменение WebRTC VAD mode или adaptive energy policy;
  semantic endpointing и новый компонент.
```

Protected baseline: WebRTC VAD mode 2, adaptive energy/near-end gate, ASR speech evidence, turn-scoped ASR boundary,
control/data-plane ownership, FreeSWITCH registered path и continuous PCMU.

## 5. Interaction topology и owner audit

```text
PCM 20 ms -> WebRtcVadCandidate -> AdaptiveEnergyGate -> VadDecision
                                                      -> TurnDetector.consume()
                                                           -> PAUSE_CANDIDATE
                                                           -> SOFT_ENDPOINT @ 300 ms
                                                           -> HARD_ENDPOINT @ 360 ms
```

Typed edge, метод consumer-а и владелец состояния не меняются. Новый delivery owner, queue, event type или
межкомпонентный сигнал не требуются. Это настройка существующего `TurnDetector` и усиление evidence tool.

## 6. Принятое timing-решение

- `ENDPOINT_SOFT_MS=300` сохраняется;
- `ENDPOINT_HARD_MS=360` становится новым baseline;
- 360 ms оставляет два 20-ms кадра запаса до абсолютного owner limit 400 ms;
- hard endpoint остаётся единственной authoritative границей;
- возобновление речи до 360 ms отменяет soft endpoint как раньше;
- пауза 480 ms теперь закономерно разделяет ходы. Предыдущая Map-008 настройка 520 ms и её evidence остаются
  исторически корректными, но их operational baseline superseded этим owner requirement.

## 7. Source-map и write-set

| Area | Разрешённые файлы | Назначение |
|---|---|---|
| Config/runtime | `config/constants.py`, `src/sip_bot/speech/endpointing.py` | Новый explicit hard endpoint |
| Evidence tool | `tools/vad_energy_replay.py`, при необходимости отдельный узкий timing helper | Метрики и fail-fast предел 400 ms |
| Tests | `tests/unit/test_config.py`, endpoint/VAD targeted tests | Exact config и timing contract |
| Owner docs | `docs/technical-specification.md`, `docs/user-guide.md` | Фактический technical/operation baseline |
| Governance | этот plan, `docs/roadmap.md`, `docs/task-backlog.md`, `docs/document-registry.md` | Статус, blockers, closeout |
| Evidence | `artifacts/implementation/017-endpoint-latency/` | Raw recorded/target/live results |

Закрытые artifacts Map-008/Map-016 не изменяются. SIP transfer, prompt/filler и TTS source files защищены.

## 8. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| `017-1` | Добавить явные endpoint timing metrics/assertions в recorded replay | Tool сообщает max hard silence и падает при `>400 ms` | Метрика требует несогласованного clock |
| `017-2` | Установить hard endpoint 360 ms и targeted tests | Config/default совпадают; pause/resume и single-hard invariants проходят | Меняется typed boundary/owner |
| `017-3` | Replay caller channel и historical TTS corpus | Caller: 4 turns, max 360 ms; old 480-ms pause: explicit expected split, не скрытый pass | Реальный caller content дробится/сливается |
| `017-4` | Host regression и target 3.14t/no-GIL gate | Affected/full suite green; GIL off | Native/runtime failure после corrective retry |
| `017-5` | Deploy и registered live validation | Реальные turns, endpoint trace `<=400 ms`, no false barge-in/runtime error | SIP/GPU stand unavailable либо live boundary broken |
| `017-6` | Синхронизация owner docs и closeout | Audits pass; blockers closed; binary status | Evidence неполно |

Исполнитель: основной executor. GPU/SIP live gate синхронизируется им же; отдельная делегация для этого узкого
корректирующего write-set не требуется.

## 9. Blocker register

| ID | Триггер | Что блокируется | Owner | Статус |
|---|---|---|---|---|
| `B-017-001` | Реальная caller-дорожка при 360 ms дробится или сливается | 017-3 и далее | project owner | `not triggered; recorded/live each preserve 4 turns` |
| `B-017-002` | Для соблюдения 400 ms требуется новая semantic/rollback boundary | Implementation | project owner | `not triggered; existing TurnDetector sufficient` |
| `B-017-003` | Target GPU/SIP stand недоступен после corrective retry | 017-4/017-5 | project owner | `not triggered; registered-live-r1 passed` |

## 10. Owner review

| Вопрос | Решение | Статус |
|---|---|---|
| Сохранять прежние 520 ms ради 480-ms искусственной паузы | Нет; новый предел 300–400 ms явно заменяет прежний критерий | `resolved by owner instruction` |
| Какое значение внутри диапазона использовать | 360 ms: два телефонных кадра запаса до 400 ms | `resolved engineering choice` |
| Использовать ли реальную caller-дорожку | Да; channel 0 последнего registered call становится обязательной regression | `resolved by owner instruction` |
| Исправлять ли одновременно filler/transfer/greeting | Нет; задачи записываются отдельно и не смешиваются с endpointing | `resolved by owner sequencing` |

Открытых owner-review вопросов нет.

## 11. Test plan и evidence

Обязательны:

1. contract/unit tests exact config и `TurnDetector` pause/resume/hard semantics;
2. replay `016-C/registered-live-r3/recordings/conversation-stereo.wav`, caller channel 0, `4` hard endpoints,
   каждый `<=400 ms`;
3. historical Map-008 mode-2 trace с явным результатом для 480-ms паузы;
4. host affected/full regression;
5. target CPython 3.14t native WebRTC operation, `Py_GIL_DISABLED=1`, `gil_enabled=false`;
6. registered FreeSWITCH call с endpoint timestamps на одном application clock.

Нельзя подменять live gate синтетическим WAV, а VAD transition — сравнением несогласованных WAV/monotonic clocks.

## 12. Fallback/deferred register

Fallback для текущего плана: `none`. Возврат к amplitude-only VAD, скрытое сохранение 520 ms, text blacklist,
ослабление числа реальных turns или test-only endpoint policy запрещены.

Semantic endpointing, filler phrases и downstream latency — отдельные задачи, а не способ объявить этот план зелёным.

## 13. Execution report и closeout

План может перейти только в `complete` при наличии всех обязательных evidence и закрытом blocker register либо в
`blocked` при конкретном category-4 условии. Статусы `foundation complete`, `partial` и аналогичные запрещены.

## 14. Execution closeout

Plan-017 закрыт `complete` 2026-09-23. `ENDPOINT_HARD_MS=360`; target recorded probe сохранил четыре реальные реплики
при GIL off, а registered live audit измерил `[380, 362, 361, 383] ms`, максимум `383 <= 400`. Target regression:
`301 passed`; зарегистрированный full gate прошёл barge-in, RAG, transfer path, report, RTP continuity и stereo
recording без runtime errors. Историческая 480-ms пауза явно даёт один дополнительный split согласно новой policy.

Полный отчёт: [`artifacts/implementation/017-endpoint-latency/closeout.md`](../../artifacts/implementation/017-endpoint-latency/closeout.md).
