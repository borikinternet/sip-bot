# Map-010: Непрерывный PCMU/RTP и comfort noise в idle

Уровень документа: `map`  
Идентификатор: `Map-010`  
Статус: `complete`  
Родительская roadmap: [`roadmap.md`](../roadmap.md)

## 1. Цель и проверяемый результат

Устранить дефект, обнаруженный при прослушивании registered full-AI записи `cold-20260913-r15`:
при отсутствии полезного TTS PJMEDIA/PJSUA2 прекращает передачу RTP, а Baresip `sndfile` записывает `dec`
без временных промежутков. Производный stereo WAV поэтому содержит ответы бота в начале, а пользовательские
реплики — позднее на своей исходной временной шкале.

Целевой результат Map-010:

- в `IDLE`, `PREROLL`, `DRAINING`, `CANCELLED` и при аварийном egress fallback media-clock получает PCM-кадр
  каждого negotiated `ptime` и передаёт непрерывный PCMU/RTP-поток;
- вместо цифровой тишины передаётся настраиваемый малый псевдослучайный comfort-noise PCM-сигнал;
- существующий `PcmAudioBridge` остаётся владельцем выбора egress-источника; новый control-plane или delivery-owner
  не создаётся;
- Baresip raw `enc`/`dec` сохраняются, а производный stereo и его temporal alignment проверяются отдельно;
  длительности raw tracks не используются как proxy для непрерывности egress RTP;
- registered full-AI live gate проходит с доказательством непрерывного RTP в окне отвеченного вызова, корректного
  negotiated profile и отсутствия media underruns/errors; recording mismatch остаётся отдельным diagnostic result.

## 2. Почему это карта, а не один узкий plan-file

Работа имеет три независимые acceptance boundaries:

1. изменение владельца idle egress-источника и его конфигурации;
2. изменение аудио-evidence helper-а, который обязан отдельно обнаруживать потерю временной шкалы записи;
3. полноценная registered SIP/RTP проверка на стенде с raw recording и event-window continuity evidence.

Поэтому Map-010 декомпозирована на child plans `010-A`–`010-C`. Они не исполняются до прохождения review карты
и соответствующих APG-проверок.

## 3. Применимые документы и извлечённые правила

| Источник | Точная применимая формулировка | Влияние на Map-010 | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | SIP-бот должен передавать голос пользователю через согласованный PCMU/RTP путь; MVP рассчитан на один звонок | Idle media не должен выглядеть как разрыв звонка и не должен расширять scope до multi-call | Registered live call, PCMU/RTP evidence | Внешний SIP/API gap |
| [`architecture.md`](../architecture.md) | `PcmAudioBridge`/media owner выбирает источник непосредственно перед media callback; PCM не проходит через Dispatcher/Event Bus | Comfort-noise source является частью существующего egress owner-а | Source-map, unit/contract tests, source audit | Требуется новый boundary или delivery-owner |
| [`technical-specification.md`](../technical-specification.md) | Параметры negotiated media берутся из SDP; PJMEDIA callback выдаёт ровно один кадр за media tick; runtime не записывает аудио | Размер и частота кадров определяются per-call profile; запись остаётся обязанностью Baresip test peer | Profile-aware tests, raw Baresip evidence | Нельзя сохранить negotiated profile |
| [`development-guidelines.md`](../development-guidelines.md) §6–§8 | Обязательны typed boundaries, воспроизводимые проверки, corrective pass для красного результата и binary closeout; намеренное упрощение запрещено | Raw duration не является общей call clock; event-window recording manifest не подменяет RTP acceptance | Targeted, contract, regression и live gates | Только конкретный category-4/API gap |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) §3, §5.7A–§5.8B | Для карты нужны child plans, source-map, propagation, blocker register и evidence; для in-process edge materialization — метод получателя | `010-A`–`010-C` имеют раздельные write-set и acceptance; их исполнение идёт по зависимостям | APG audit каждого child plan | Новый unresolved вариант/архитектурный gap |
| RFC [3389](https://www.rfc-editor.org/rfc/rfc3389) и ITU-T [G.711 Appendix II](https://www.itu.int/ITU-T/recommendations/rec.aspx?lang=en&rec=5132) | CN — отдельный RTP payload; для 8 kHz G.711 возможен PT 13, noise level кодируется от 0 до −127 dBov, алгоритмы VAD/DTX/CNG implementation-specific | Используются только как справочная граница: RFC 3389/CN в MVP не реализуется и не сигнализируется в SDP | Scope audit и отсутствие CN write-set | Попытка молча добавить CN payload |
| ITU-T G.711 Appendix II и ETSI [ES 202 739](https://www.etsi.org/deliver/etsi_es/202700_202799/202739/01.05.01_50/es_202739v010501m.pdf) | Абсолютный уровень comfort noise не нормирован одним числом: ITU задаёт диапазон представления `0…−127 dBov` и рекомендует учитывать энергию/спектр фона; ETSI для терминалов требует ориентироваться на исходный фон в диапазоне `−5…+2 dB` и согласовывать спектр | В нашем synthetic zero-background fixture нормативный абсолютный уровень вывести нельзя; нужен controlled sweep конфигурационного уровня и честная фиксация отсутствия claim о соответствии | Measured dBov/RMS, controlled listening и artifact metadata | Если нужен нормативный claim без background reference |

## 4. Граница задачи

```text
Цель:
  Сохранить непрерывную временную шкалу PCMU/RTP и сделать idle состояние слышимым для пользователя.

Входит:
  Существующий PcmAudioBridge и его idle/fallback source;
  конфигурация уровня comfort noise в config/constants.py;
  обязательный no-VAD media режим для application RTP path;
  event-window audit Baresip/PJMEDIA egress continuity; strict Baresip enc/dec и stereo derivative остаются
  диагностическим evidence;
  registered full-AI live evidence.

Не входит:
  RTP CN/SID payload RFC 3389, PT 13 и изменение SDP;
  новый RTP/SIP стек, новый Event Bus edge, запись аудио внутри runtime;
  multi-call, production noise profiling, production PBX compatibility campaign;
  изменение ASR/VAD входного контура или логики Dialogue FSM.

Protected baseline:
  negotiated PCMU/8000/mono, per-call ptime, direct media plane, control-only Dispatcher/Event Bus,
  Baresip sndfile raw enc/dec как primary evidence, один одновременный звонок.

Предположения о рабочем дереве:
  Закрытые планы 005 и 009 не переписываются; Map-010 добавляет новый corrective baseline.
  Исторические artifacts r14/r15 сохраняются и не перезаписываются.
```

## 5. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Idle egress | `src/sip_bot/sip_media/media_port.py`, `PcmAudioBridge._on_frame_requested` | В idle/fallback выдаются нулевые PCM-кадры; upstream VAD может подавить RTP | Выдавать exact-size comfort-noise PCM на каждом callback и не блокироваться | Отсутствует noise source и application no-VAD setting | `010-A` |
| Config | `config/constants.py`, `src/sip_bot/config.py` | Нет явного idle-noise/no-VAD параметра | Один источник конфигурации с проверяемым уровнем и media policy | Нужно добавить typed config projection | `010-A` |
| Media adapter | `src/sip_bot/sip_media/adapter.py` | `EpConfig` создаётся без целевой idle RTP policy | Применять утверждённый no-VAD режим для negotiated PCMU path | Native setting нужно проверить на target runtime | `010-A`, blocker при API gap |
| Stereo evidence | `tools/map005_stereo_recording.py` | Сборщик использовал raw duration как общую шкалу | Event window + file start offsets; padding/trimming явно в manifest | Нет event window или timestamp старта дорожки | `010-B` |
| Registered runner | `tools/freeswitch_workshop/registered_full_rehearsal.py` | Raw tracks сохраняются, но их duration boundary может различаться | Runner сохраняет noise/no-VAD metadata, event-window continuity audit и отдельный strict stereo audit | Нужен новый continuity evidence schema | `010-B`, `010-C` |
| Tests | `tests/unit`, `tests/contract`, `tests/integration` | Нет проверки ненулевого idle source и строгой temporal alignment | Проверяются source, config, builder и live RTP continuity | Новая acceptance matrix | `010-A`–`010-C` |
| Documentation | `architecture.md`, `technical-specification.md`, `user-guide.md`, registry/backlog/roadmap | Архитектура говорит о намеренной тишине; guide описывает старый recorder policy | После успешной реализации описать PCMU comfort-noise policy и новый runbook | Нельзя менять owner docs до принятого плана/реализации | `010-C` closeout |

## 6. Interaction topology и propagation контрактов

Текущая topology не расширяется:

```text
TTS output buffer ──(direct enqueue(PcmFrame))──> PcmAudioBridge.egress
                                                    │
                                                    └─ onFrameRequested(frame)
                                                       ├─ PLAYING: TTS buffer
                                                       └─ idle/fallback: ComfortNoiseSource
                                                              │
                                                              └─ PJSUA2/PJMEDIA → PCMU/RTP → Baresip sndfile
```

`ComfortNoiseSource` — внутренняя часть existing egress owner, а не самостоятельный межкомпонентный delivery
компонент. `Dispatcher`, Event Bus, ASR и ingress fan-out в этот payload edge не включаются. Учитываются только
следующие checkpoints:

- negotiated `NegotiatedMediaProfile` определяет sample rate, channels, PCM width, frame size и ptime;
- receiver-owned `onFrameRequested` получает exact capacity и обязан вернуть один audio frame без ожидания producer;
- `PcmAudioBridge` выбирает один источник на media tick; TTS buffer не заполняется idle-кадрами;
- `200 OK` на `INVITE` и `BYE`/`media_stopped` задают answered-call window; `expected_frames = round(window / ptime)`;
- `egress_frames`, peer receive/loss counters, underruns и callback errors проверяют media continuity;
- Baresip `enc`/`dec` длительности не считаются общей media clock: stereo builder выравнивает дорожки по event window
  и timestamps старта файлов, а padding/trimming явно отражает в manifest,
  но его diagnostic failure не переходит в RTP continuity failure.

## 7. Audit владельца поведения и парадигмы реализации

Владелец поведения — существующий `PcmAudioBridge`, потому что он уже владеет media-clock callback, source modes,
egress buffer и lifecycle закрытия. `ComfortNoiseSource` допускается только как его private stateless/stateful
helper для генерации exact-size PCM; он не публикует события, не владеет звонком и не меняет FSM.

Реализация остаётся неблокирующей и синхронной внутри native callback. Никакого `asyncio` ожидания, lock через
Dispatcher или отдельного потока для генерации одного media frame не вводится.

## 8. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Реализуем ли RFC 3389/CN payload, PT 13 и SDP `0 13`? | Нет, пока не реализуем | MVP передаёт обычный negotiated PCMU; CN остаётся future option | `resolved by owner decision 2026-09-14` |
| Должны ли idle-кадры идти регулярно даже при отсутствии TTS? | Да | Application media policy включает no-VAD/continuous-PCMU behavior | `resolved by owner decision 2026-09-14` |
| Должен ли idle-сигнал быть абсолютной цифровой тишиной? | Нет, нужен низкоуровневый comfort-noise PCM | Уровень и форма проверяются отдельным controlled sweep; источник настраиваемый | `resolved by owner decision 2026-09-14` |
| Какой уровень является окончательным? | Стандарт не задаёт абсолютного значения; execution проверяет небольшой диапазон в dBov и фиксирует выбранный default без claim о нормативном соответствии | При невозможности выбрать уровень по controlled artifact/listening зависимый slice останавливается на owner review | `execution decision; not open blocker yet` |
| Какой разрыв длительностей допускается для cleanup tail? | `≤500 мс` только в standalone-аудите без authoritative event window | В live recording длительность raw-файла не задаёт шкалу; event-window alignment допускает явные padding/trimming | `superseded by owner correction 2026-09-14` |
| Использовать ли разницу длительностей Baresip `enc`/`dec` как проверку непрерывности bot egress? | Нет. Непрерывность проверяется по answered-call event window, negotiated `ptime`, egress frame count и peer RTP counters; raw recording duration — diagnostic | `B-010-C-002` снимается как blocker Map-010; recording mismatch сохраняется отдельно | `resolved by owner correction 2026-09-14` |

## 9. Child plans и порядок исполнения

| Child plan | Scope | Зависимость | Acceptance | Owner review |
|---|---|---|---|---|
| [`plan-010-A-idle-pcmu-comfort-noise.md`](plan-010-A-idle-pcmu-comfort-noise.md) | Existing egress source, config, no-VAD setting и unit/contract tests | none | Exact-size non-zero comfort-noise PCM на каждом idle tick; no-GIL/target tests pass | `complete` |
| [`plan-010-B-stereo-recording-timeline.md`](plan-010-B-stereo-recording-timeline.md) | Event-window raw enc/dec temporal alignment и stereo manifest | `010-A` | Event window и per-track start offsets обязательны; standalone без них остаётся strict | `complete` |
| [`plan-010-C-live-continuity-gate.md`](plan-010-C-live-continuity-gate.md) | Registered full-AI PCMU/RTP run, Baresip recording и continuity evidence | `010-A`, `010-B` | Event-window RTP continuity, raw tracks, no callback/media errors, report/evidence complete; stereo mismatch diagnostic | `complete` |

Групповое owner review карты и всех трёх child plans принято владельцем 2026-09-14 сообщением «ладно, делай так
с настраиваемым уровнем, потом приведем все к требованию ... Исполняй». RFC 3389/CN явно остаётся deferred;
исполнение завершено по зависимостям `010-A → 010-B → 010-C`.

## 10. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-010-MAP-001` | map gate | Для continuous PCMU требуется новый SIP/RTP boundary, SDP CN или новый delivery-owner | Вся Map-010 | project owner | Source/API audit и existing architecture comparison | `none until triggered` |
| `B-010-A-001` | `010-A` | Target PJSUA2 не позволяет применить no-VAD policy к application media | `010-A`, `010-C` | project owner | Target import/operation evidence и focused retry | `none until triggered` |
| `B-010-B-001` | `010-B` | Baresip sndfile не создаёт raw tracks с общей временной шкалой даже при continuous PCMU | Recording diagnostic | project owner | Raw WAV, peer log, RTP/length evidence и corrective retry | `resolved as non-gating diagnostic 2026-09-14` |
| `B-010-C-001` | `010-C` | Registered full-AI call сохраняет пропуски RTP или смещённый stereo после corrective pass | Map-010 closeout | project owner | Fresh clean-start target run и strict audio audit | `none until triggered` |
| `B-010-C-002` | `010-C` | Baresip `enc`/`dec` recording boundary при transfer teardown расходится больше `500 ms` | Recording diagnostic only | project owner | [010-C execution evidence](../../artifacts/implementation/010-continuous-pcmu-comfort-noise/010-C/execution-evidence.md), r1/r2/r3 JSON, raw WAV и event-window audit | `superseded by event-window recording correction 2026-09-14` |

Красный результат в утверждённом write-set сначала проходит corrective protocol по APG и не становится blocker
автоматически. RFC 3389/CN не является скрытым fallback, если regular PCMU path не сработает.

## 11. Test plan и evidence

Target runtime для application checks — последний стабильный free-threaded CPython `>=3.14` в Ubuntu/WSL2, выбранный
по существующему runtime gate. GPU для `010-A`/`010-B` не требуется; `010-C` использует approved registered full-AI
runner и требует свободный GPU согласно действующему runbook.

Обязательные категории:

- unit: генератор выдаёт exact-size PCM, заданный уровень, не повторяет периодически короткий шаблон и не возвращает
  нулевой idle frame;
- contract: negotiated profile/ptime определяет размер кадра, no-VAD policy попадает в target `EpConfig`, source mode
  semantics и `egress_underruns` сохраняются;
- evidence: builder отдельно принимает/отклоняет temporal alignment recording и не используется для RTP continuity;
- live: registered full-AI call, event-window continuous RTP/PCMU, raw `enc`/`dec`, event-window stereo, manifest,
  report и exit code;
- regression: полный целевой набор `tests/unit tests/contract tests/integration` и registry/backlog audits.

Каждый child plan фиксирует точную команду, stdout/stderr, exit code, runtime/GIL, artifact root и corrective pass.

## 12. Fallback/deferred register

| Что введено | Почему необходимо для MVP | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| RFC 3389/CN payload | Не вводится | Явно исключён из write-set; не используется как скрытый fallback | Future map при отдельном owner decision | `deferred` |
| `none` | — | — | — | — |

Intentional simplification отсутствует. Использование обычных PCMU-пакетов вместо RFC CN — не молчаливый fallback,
а явно принятое MVP-решение с зафиксированным bandwidth/compatibility trade-off.

## 13. Map-level closeout

Map-010 может получить статус `complete` только после:

1. owner review карты и всех child plans;
2. полного исполнения `010-A`–`010-C`, без частичного/foundation closeout;
3. target evidence, где RTP не исчезает в idle: event window, negotiated `ptime`, expected/actual egress frames,
   peer receive/loss и media error counters согласованы;
4. сохранённых raw Baresip tracks и отдельного честного recording audit; stereo derivative не является proxy для RTP
   continuity;
5. corrective pass для каждого красного результата либо конкретного category-4 blocker;
6. синхронизации `architecture.md`, `technical-specification.md`, `user-guide.md`, `roadmap.md`, registry и backlog;
7. проверки document registry и task backlog.

До этого карта остаётся `proposed`/`in_progress`/`blocked`; старые r14/r15 artifacts не переписываются.

### Текущее состояние исполнения

`010-A`, `010-B` и `010-C` закрыты полностью. В target `20260914-r4` answered-call window от `200 OK(INVITE)` до
`BYE` составил `125618.477 ms`; при negotiated `ptime=20 ms` ожидалось `6281` frames, adapter egress и Baresip
peer receive дали `6281`, peer receive loss `0`, `egress_underruns=0`, `callback_errors=0`, egress drops `0`.
Отдельный Baresip recording audit также прошёл: raw `enc`/`dec` gap `360 ms`, stereo derivative создан.

Карта имеет статус `complete`. `B-010-C-002` закрыт корректировкой recording alignment и больше не является blocker:
raw `enc`/`dec` duration — диагностический атрибут, а не общая временная шкала и не проверка RTP continuity. Старые r14/r15 artifacts не
переписывались.
