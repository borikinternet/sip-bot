# Карта 7: переход live-речевого контура на WebRTC VAD

Уровень документа: `map`  
Идентификатор: `Map-007`  
Статус: `complete — 007-A/007-B/007-C accepted; WebRTC VAD live path and evidence closed, 2026-09-13`  
Дата подготовки: `2026-09-13`  
Родитель: [`roadmap.md`](../roadmap.md)  
Предшественники: [`plan-002-D-speech-ingress.md`](plan-002-D-speech-ingress.md), [`plan-005-B-speech-audio-resilience.md`](plan-005-B-speech-audio-resilience.md), [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

## 1. Цель и проверяемый результат

Перевести рабочий live-речевой путь SIP-бота с собственного амплитудного тестового детектора на ранее выбранный
локальный WebRTC VAD, не меняя владельцев речи, typed boundary, endpointing policy и архитектуру control/data plane.

Карта должна дать следующий проверяемый результат:

- binding WebRTC VAD найден, зафиксирован по фактической версии и прошёл import/operation/no-GIL gate в целевом
  free-threaded CPython runtime либо получил явно согласованный patch;
- `WebRtcVadCandidate` является кандидатом рабочего application/live path;
- `PcmFrame` передаётся в существующий `VadProcessor.process(frame)`, а его результат остаётся тем же typed
  `VadDecision`, который принимает существующий `TurnDetector.consume(decision)`;
- live SIP/RTP gate с Baresip использует WebRTC VAD на согласованных параметрах медиа, а не `_AmplitudeVad`;
- deterministic unit/contract fixtures могут сохранить injected amplitude/fake backend, но явно не выдаются за
  проверку live VAD;
- speech endpointing, Transcript Assembler, ASR, Dispatcher/FSM, RAG, LLM, TTS и SIP protocol ownership не получают
  скрытых изменений;
- доказаны отсутствие блокировки ASR независимым VAD-потоком, корректные speech/pause/resume transitions и отсутствие
  stale-результатов после закрытия текущего call generation;
- актуальные архитектурные, технические и operational documents, registry, backlog и evidence синхронизированы.

Проектный результат карты — не обещание production-quality precision/recall для всех шумовых условий. Это проверенный
для MVP выбор VAD и воспроизводимый live/demo-путь для русского PCMU-звонка.

## 2. Почему это карта, а не один узкий plan-file

В задаче есть три независимые acceptance boundaries:

1. native Python binding и его совместимость с no-GIL runtime;
2. подключение уже существующего кандидата к application composition и сохранение typed propagation;
3. live SIP/RTP/rehearsal evidence с фактическим WebRTC VAD.

Они требуют разных runtime/test boundaries, имеют разные blocker conditions и не могут быть закрыты одним unit-тестом.
Поэтому карта декомпозируется на child plans `007-A`–`007-C`. Создание этой карты не разрешает их реализацию до
прохождения owner review и применимого APG.

## 3. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на Map-007 | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | MVP работает на русском языке, с одним SIP-звонком, PCMU, локальным ASR и фиксированным endpointing; запись аудио ботом не владеет | Карта меняет только speech classification в существующем одном-call MVP и не добавляет запись или многосессионность | Requirement/evidence matrix и live SIP gate | Изменяется пользовательский scope или появляется второй call |
| [`architecture.md`](../architecture.md) | VAD, Turn Detector и Transcript Assembler — разные owners; PCM идёт по data plane напрямую, Dispatcher не является аудиотранспортом | WebRTC VAD остаётся реализацией `VadCandidate`; `TurnDetector` и `SpeechIngress` не поглощаются новым компонентом | Ownership audit и typed boundary test | Требуется новый owner, event-bus audio path или новый delivery component |
| [`technical-specification.md`](../technical-specification.md) | Внутренний speech input — mono PCM S16LE; параметры VAD и endpointing находятся в конфигурации; negotiated media определяется на звонок | WebRTC получает фактические `PcmFrame` после PCMU decode; frame size не подменяется скрытым fixed default | Negotiated profile, format/unit and configuration evidence | WebRTC требует иной формат без согласованной boundary-conversion |
| [`development-guidelines.md`](../development-guidelines.md) §2–§3 | Typed-first, ownership, direct in-process materialization, bounded queue между потоками, явные lifecycle/cancel/close и cycles | Сохраняются `PcmFrame → VadProcessor.process → VadDecision → TurnDetector.consume`; новые очереди и фасады не добавляются | Source-map, propagation audit, close/cancel tests | Фактический consumer не принимает output или возникает новый boundary |
| [`development-guidelines.md`](../development-guidelines.md) §4 | Субагент получает self-contained write-set; parallel execution только при непересекающихся write-set; общий config/docs изменяет main executor | `007-A`–`007-C` можно готовить по зависимостям; native operation и итоговый live gate выполняет main executor | Handoff/diff/evidence review | Пересечение write-set или зависимость от незакрытого evidence |
| [`development-guidelines.md`](../development-guidelines.md) §5 | Для native import/operation в free-threaded runtime проверяются GIL до/после import и operation; при проблеме сначала рассматривается patch, затем только явно согласованная isolation | Версия binding не считается пригодной по факту установки; `webrtcvad` должен пройти отдельный no-GIL gate | `Py_GIL_DISABLED`, `sys._is_gil_enabled()`, import/operation raw output | Непредусмотренный GIL/API-gap без patch и owner decision |
| [`development-guidelines.md`](../development-guidelines.md) §6 | Обязательны targeted/contract/regression tests, raw output, exit code и corrective pass; соседние зелёные тесты не заменяют красный acceptance | Реальный WebRTC path проверяется отдельно от injected deterministic backend и затем повторяется в live gate | Test/evidence package и classification of red results | Category 4 gap либо обязательный тест не стал зелёным |
| [`development-guidelines.md`](../development-guidelines.md) §7–§8 | Молчаливое упрощение и fallback запрещены; закрытие child plan бинарно: `complete` или `blocked` | `_AmplitudeVad` остаётся только явно обозначенным deterministic test double, а не live fallback; частичный child closeout запрещён | Fallback register, blocker register, closeout audit | Live path откатился к amplitude без решения или scope не закрыт |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) §2–§5 | Замена VAD требует полного gate; карта должна иметь child graph, source-map, owner review, blocker register, test/evidence plan и closeout | Карта фиксирует границы и порядок `007-A → 007-B → 007-C`; child plans получают собственный APG | Map-level APG audit | Есть открытый architectural gap или отсутствует обязательный блок |
| [`plan-002-D-speech-ingress.md`](plan-002-D-speech-ingress.md) | WebRTC VAD — принятый локальный candidate; semantic detector не входит в MVP; VAD и endpointing разделены | Выбор WebRTC VAD не переоткрывается; карта устраняет отложенный native/live execution gap | Decision/source audit | Требуется другой алгоритм или semantic endpointing |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | В актуальной topology `N3 → N5` передаёт `PcmFrame`, `N5 → N6` — `VadDecision`; cancellation/close и stale policy принадлежат существующим owners | Новая реализация должна пройти те же рёбра и propagation checkpoints; новая ревизия Map-I нужна только при фактическом изменении типов | Boundary registry and propagation checkpoint | Фактический output отличается от authoritative contract |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Основной runtime — free-threaded CPython; native несовместимость нельзя скрывать обычным GIL-enabled Python | Binding проверяется в target runtime; process isolation не вводится молча | Runtime manifest and import/operation probe | Только новый owner decision может разрешить isolation |

## 4. Граница карты

### Входит

- проверка доступного Python binding WebRTC VAD в target runtime;
- exact package/version/revision, runtime command и лицензия фактически выбранного binding;
- no-GIL import/operation/concurrency checks для native binding;
- использование существующего `WebRtcVadCandidate` в рабочей application composition;
- при необходимости — вынос `VAD_MODE` в [`config/constants.py`](../../config/constants.py), чтобы режим не был
  скрытым default;
- проверка форматов 8 kHz/mono/PCM S16LE и кадров 10/20/30 ms, с основным negotiated `ptime=20 ms`;
- live SIP/RTP gate на утверждённом Baresip peer с PCMU и фактическим WebRTC VAD;
- unit/contract/regression проверки VAD, endpointing, pause/resume, close и stale-result policy;
- синхронизация владельцев документации, operational runbook/evidence и реестров после исполнения.

### Не входит

- изменение выбранного алгоритма на neural VAD, semantic turn detector или отдельную модель определения смысла фразы;
- изменение `VadDecision`, `EndpointEvent`, `PcmFrame`, `SpeechIngress`, `TurnDetector` или `TranscriptAssembler`, если
  текущая граница принимает фактический WebRTC output;
- новый audio fan-out, новый delivery owner, event-bus audio path или межпроцессный аудиопротокол;
- изменение ASR, LLM, TTS, RAG, SIP transaction behavior, PCMU codec ownership или Dialogue FSM;
- улучшение модели под все шумовые условия, полноценный labeled precision/recall campaign, MOS и нагрузочные тесты;
- поддержка нескольких параллельных разговоров;
- автоматический fallback с WebRTC на `_AmplitudeVad` в live path.

### Protected baseline

- `Map-002-I revision 21` и typed edges `N3 → N5 → N6`;
- существующие владельцы `VadProcessor`, `SpeechIngress`, `TurnDetector`, `PcmFanOut` и `runtime_wiring`;
- accepted WebRTC VAD candidate decision из `plan-002-D-speech-ingress.md`;
- free-threaded CPython 3.14.7t baseline и правило no-GIL/patch/isolation из ADR-003;
- PCMU → mono PCM S16LE `PcmFrame`, negotiated per-call media profile и `ptime`, не скрываемый глобальным default;
- soft/hard endpointing `300/500 ms` и `min_speech_ms=80`, если evidence не выявит фактический contract gap;
- deterministic fixtures и исторические Map-005/Map-006 evidence не переписываются;
- один одновременный звонок и обязательный итоговый `report.md`.

### Предположения

- approved PJSUA2/PJMEDIA и Baresip test stand доступны;
- главный executor может последовательно запускать target runtime checks и live gate;
- место на Windows и Linux соответствует ранее принятому минимуму 20 GB;
- exact binding/version будет зафиксирован на execution stage по фактическому latest stable и no-GIL evidence, а не
  придуман заранее;
- существующий `WebRtcVadCandidate` сохраняет внешний контракт `is_speech(pcm_s16le, sample_rate_hz) -> bool`.

## 5. Текущее состояние и gap

| Область | Фактическое состояние | Gap, который закрывает Map-007 |
|---|---|---|
| Candidate code | [`src/sip_bot/speech/vad.py`](../../src/sip_bot/speech/vad.py) содержит `WebRtcVadCandidate` с lazy `import webrtcvad`, проверкой 8/16/32/48 kHz и 10/20/30 ms | Binding не имеет собственного актуального target-runtime/no-GIL evidence в рабочем baseline |
| VAD boundary | `VadProcessor` преобразует bool candidate result в typed `VadDecision`; `TurnDetector` принимает этот тип | Boundary менять не требуется; нужно доказать propagation на фактическом candidate |
| Application live gates | [`tools/live_i1_gate.py`](../../tools/live_i1_gate.py) и [`tools/j4_full_live_gate.py`](../../tools/j4_full_live_gate.py) подставляют `_AmplitudeVad` | Рабочий live/demo путь не использует выбранный WebRTC VAD |
| Deterministic tests | `map005_speech_probe.py` и часть unit/integration tests используют injected deterministic backend | Это допустимо для изоляции логики, но маркировка должна запрещать трактовку как live VAD evidence |
| Configuration | `VAD_SPEECH_THRESHOLD` существует для amplitude helper; явного выбранного VAD mode нет | Если режим нужен для application construction, добавить явный `VAD_MODE`; amplitude threshold не должен управлять WebRTC path |
| Endpointing | `TurnDetector` владеет fixed soft/hard timing policy | Не менять ownership; проверить, что смена classifier не нарушает accepted 300/500 ms transitions |

## 6. Source-map и write-set карты

| Область | Источник/файл | Целевое действие | Владелец | Допустимый write-set на карте |
|---|---|---|---|---|
| Native candidate | `src/sip_bot/speech/vad.py`, новый child evidence root | Проверить и зафиксировать exact WebRTC binding, import/operation/no-GIL | `007-A`, main executor принимает evidence | Child A меняет только существующий VAD adapter при необходимости минимального compatibility fix и собственный evidence; без нового fallback |
| Runtime/config | `config/constants.py`, `src/sip_bot/runtime_wiring.py` | Сконструировать WebRTC candidate в рабочем runtime и не скрывать его mode | `007-B`, main executor синхронизирует config | Child B — только VAD construction/config symbols и targeted tests; config/docs меняются последовательно |
| Speech boundary | `src/sip_bot/speech/vad.py`, `ingress.py`, `endpointing.py`, `contracts.py` | Подтвердить, что typed boundary не меняется; исправлять только фактический contract defect | `007-B` | Существующие VAD/speech symbols и speech tests; изменение public contract запрещено без Map-I propagation |
| Live composition | `tools/live_i1_gate.py`, `tools/j4_full_live_gate.py`, при необходимости `tools/real_media_composition_probe.py` | Заменить live injection на WebRTC VAD после A и сохранить deterministic helper только в deterministic paths | `007-C`, live gate — main executor | Только VAD construction, fixture metadata и VAD-related assertions; не менять AI/SIP/media owners |
| Deterministic tests | `tests/unit/`, `tests/integration/`, `tools/map005_speech_probe.py` | Сохранить injected fake/amplitude tests и маркировать уровень evidence | `007-B`/`007-C` | Targeted tests/fixtures; закрытые Map-005 tests не переписывать без фактической регрессии |
| Architecture/TЗ | `docs/architecture.md`, `docs/technical-specification.md`, `docs/tooling-notes.md` | После фактического выбора/проверки обновить только owner sections: WebRTC primary, mode, runtime/evidence command | main executor | Только синхронизация факта; не дублировать APG и не менять требования молча |
| Registry/backlog/roadmap | `docs/document-registry.md`, `docs/task-backlog.md`, `docs/roadmap.md` | Добавить карту, задачу и следующий шаг; после каждого Markdown change запустить локальные checker tools | main executor | Последовательное изменение общих документов; child agents не пишут их |

Защищены от child-изменений: `requirements.md`, accepted ADR, закрытые `001-*`, закрытые Map-002/005/006 plans,
`plan-002-I-boundary-interaction-map.md`, contracts и unrelated worktree changes. Если фактическая интеграция требует
изменить protected baseline, это не исправляется в child scope, а регистрируется как APG gap.

## 7. Interaction topology и propagation

Map-007 не создаёт новых рёбер. Authoritative topology остаётся в [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21:

```text
N3 PCM fan-out / direct bounded audio channel
  └─ E5: PcmFrame ──> N5 VAD / VadProcessor.process(frame)
                         └─ E8: VadDecision ──> N6 TurnDetector.consume(decision)
                                                    └─ EndpointEvent ──> SpeechIngress/assembler/FSM existing edges
```

Материализация и lifecycle:

- `PcmFanOut` выдаёт VAD-потребителю независимый typed `PcmFrame`; VAD не ждёт заполнения ASR chunk и не проходит
  через Dispatcher/Event Bus;
- `VadProcessor` вызывает `candidate.is_speech(frame.pcm_s16le, frame.profile.sample_rate_hz)` и единолично строит
  `VadDecision` с call/channel/generation/sequence/timestamp metadata;
- WebRTC binding выдаёт boolean decision, поэтому `VadDecision.confidence` остаётся `None`; добавление искусственной
  confidence-оценки не входит в карту;
- `TurnDetector.consume(decision)` остаётся владельцем последовательности speech/pause, soft endpoint, resume и
  authoritative hard endpoint;
- `SpeechIngress.cancel()/close()` закрывает текущий speech lifecycle; поздний frame или result не должен попасть в
  новый generation. Для одного call generation вызовы candidate serial; shared mutable VAD instance между звонками не
  вводится;
- новый reverse edge от VAD не появляется. Ошибка candidate становится явной `VadCandidateError` и обрабатывается
  существующим speech/runtime owner, а не скрытым amplitude fallback;
- существующие циклы protocol event → Dispatcher/FSM → cancel/close speech и barge-in → playback cancellation не
  изменяются. Для Map-007 направление cancellation остаётся сверху вниз, а новое VAD-решение не выполняет control action.

### Обязательные propagation checkpoints

| Checkpoint | Что проверяется | Условие перехода |
|---|---|---|
| `I0` | Map-I rev21, текущие `PcmFrame`, `VadDecision`, `EndpointEvent` и owners зафиксированы | Source-map и protected baseline согласованы |
| `I1` | Фактический WebRTC binding принимает negotiated PCM frame и возвращает bool без нарушения no-GIL | `007-A` operation/runtime evidence pass |
| `I2` | `VadProcessor` материализует тот же `VadDecision`, `TurnDetector` принимает его без нового adapter/delivery owner | Contract/targeted tests pass; revision не меняется или изменение оформлено |
| `I3` | Live composition создаёт WebRTC candidate, а deterministic backend остаётся только в явных deterministic tests | Code/diff audit и targeted tests pass |
| `I4` | Baresip PCMU live path показывает speech/pause/resume/hard endpoint и независимый ASR fan-out | Main-executor live gate pass |
| `I5` | Документы и evidence отражают фактический baseline, а старые результаты не выданы за WebRTC evidence | Map closeout audit pass |

## 8. Audit владельца поведения и парадигмы реализации

Новый владелец поведения не создаётся:

- `WebRtcVadCandidate` владеет только вызовом выбранного VAD binding для одного входного PCM frame;
- `VadProcessor` владеет преобразованием candidate result в typed `VadDecision` и проверкой speech input format;
- `TurnDetector` владеет stateful endpointing policy и порядком VAD decisions;
- `PcmFanOut` владеет независимыми direct data-plane subscriptions;
- `SpeechIngress` владеет композиционной передачей speech results, но не классификацией frame и не endpoint policy;
- Dispatcher/FSM остаются владельцами control plane и не получают audio payload.

Новый универсальный delivery component, VAD manager или второй orchestration owner не нужен. Вызов
`VadProcessor.process(frame)` и последующий `TurnDetector.consume(decision)` — materialization существующих рёбер.
Модель исполнения — текущий основной `asyncio` loop с direct call/local queue для in-loop path; если фактический binding
потребует отдельного потока, между потоками допускается только bounded thread-safe queue, а process isolation требует
нового owner review.

## 9. Дочерние планы, зависимости и порядок

| ID | Plan-file | Назначение | Зависимости | Исполнитель | Acceptance boundary | Evidence root | Статус |
|---|---|---|---|---|---|---|---|
| `007-A` | `plan-007-A-webrtc-vad-runtime-gate.md` | Найти exact binding, проверить пакет/лицензию, import/operation/no-GIL и минимальный patch path | `I0`, closed `001-B`, `001-D`, `002-D` | main executor или субагент для подготовки; operation принимает main executor | WebRTC operation на 8 kHz mono PCM16 10/20/30 ms в CPython 3.14t, GIL remains disabled | `artifacts/implementation/007-webrtc-vad/007-A/` | `complete — patched target/combined runtime gate 2026-09-13` |
| `007-B` | `plan-007-B-webrtc-vad-application-integration.md` | Подключить проверенный candidate в application composition, config и targeted contract tests | `007-A`, `I1` | субагент допустим при непересекающемся write-set | Application VAD использует WebRTC; `PcmFrame → VadDecision → EndpointEvent` unchanged | `artifacts/implementation/007-webrtc-vad/007-B/` | `complete — config/typed boundary evidence 2026-09-13` |
| `007-C` | `plan-007-C-webrtc-vad-live-gate-and-workshop-evidence.md` | Заменить VAD в live gates, проверить SIP/RTP speech transitions и подготовить evidence/runbook handoff | `007-B`, `I2`–`I4` | подготовка может быть делегирована; live/GPU-adjacent final gate — main executor | Clean-start Baresip PCMU path с WebRTC VAD; deterministic amplitude path явно не считается live evidence | `artifacts/implementation/007-webrtc-vad/007-C/` | `complete — I1 and J4 live evidence 2026-09-13` |

Child plans не создаются как выполненные и не переходят в execution stage до owner review этой карты. После согласования
карты каждый child plan получает собственный APG, source-map, write-set, blocker register, tests и closeout. `007-A` и
подготовка fixtures могут идти параллельно только если не пересекаются их write-set; `007-B` и `007-C` зависят от
фактической propagation/evidence revision и не запускаются преждевременно.

## 10. Owner-review решения

| Вопрос | Предлагаемое решение | Последствие | Статус |
|---|---|---|---|
| Нужно ли заново выбирать VAD? | Нет. WebRTC VAD уже принят owner review в `002-D`; Map-007 закрывает отложенную проверку и фактическое подключение | Не создаётся новый comparative selection или neural VAD scope | `resolved by prior decision` |
| Можно ли менять `PcmFrame`, `VadDecision` или `TurnDetector` ради WebRTC? | Нет, пока текущий typed boundary принимает bool/result без фактического mismatch | Сохраняются `VadProcessor` и `TurnDetector`; новый adapter запрещён | `resolved by architecture/Map-I` |
| Что делать с `_AmplitudeVad`? | Оставить только injected deterministic test double с явной маркировкой; убрать его из application/live gates | Исторические deterministic tests не переписываются, live claims получают WebRTC evidence | `resolved by Map-007 scope` |
| Как выбрать exact package/version? | Определить на `007-A` по latest stable, доступности в target runtime, лицензии и no-GIL evidence; заранее не pin-ить несуществующую версию | Версия появляется в evidence и config/manifest после фактического gate | `resolved execution rule; no owner question` |
| Какой режим VAD? | Сохранить текущий `WebRtcVadCandidate(mode=2)` как стартовый baseline; если application config нужен, явно записать `VAD_MODE=2`. Менять режим можно только по evidence, а не молча | Нет скрытого перехода между режимами; mode является диагностируемым параметром | `resolved baseline; change requires evidence` |
| Что делать при GIL/API failure? | Сначала выполнить corrective patch в binding. Автоматический fallback или process isolation не вводить; новый isolation boundary — owner-review gap | Работа останавливается только на конкретном category-4 gap с raw evidence и condition promotion | `resolved by ADR-003/APG` |
| Нужна ли новая ревизия Map-I? | Нет, если фактические входы/выходы остаются `PcmFrame`, `VadDecision`, `EndpointEvent`. Да — только при фактическом contract change, через propagation и review | Проверка типа не подменяется записью в карте; решение зависит от evidence | `resolved conditional rule` |

Открытых owner-review вопросов, необходимых для подготовки child plans, нет. Указанные выше условия не являются
просьбой повторно согласовать ранее принятые решения; они задают executable gates и trigger для остановки только при
фактическом новом gap.

## 11. Process invariant audit

| Инвариант | Применимое действие в Map-007 | Evidence |
|---|---|---|
| Узкий scope и запрет silent expansion | Карта ограничена заменой live VAD; semantic endpointing, ASR, LLM, TTS и SIP не переоткрываются | Scope audit, child write-sets |
| Typed-first | Candidate принимает PCM bytes и выдаёт bool; приложение материализует только существующий `VadDecision` | Contract tests и I1/I2 checkpoints |
| Owner behavior | VAD не владеет endpoint state; `TurnDetector` не переносится в новый adapter | Ownership audit |
| Direct data plane | Audio идёт `PcmFanOut → VadProcessor`; Dispatcher/Event Bus не участвует | Fan-out/isolation test, source audit |
| Explicit cycles | Нового VAD cycle нет; existing close/cancel path и re-entrancy сохраняются | Cancellation/close and protocol-event tests |
| Parallel delegation | `007-A` preparation и fixture work могут быть разнесены по непересекающимся write-set; config/docs/live gate последовательны | Handoff and diff audit |
| No-GIL | Binding импортируется и вызывается в CPython 3.14t с проверкой GIL до/после | Runtime/import/operation manifest |
| Corrective pass | Красный targeted test классифицируется, исправляется в write-set и повторяется; не маскируется amplitude test double | Raw output, exit codes, rerun evidence |
| No fallback/intentional simplification | Amplitude backend не является live fallback; process isolation не вводится без решения | Fallback register and live-construction audit |
| Binary closeout | Каждый child получает только `complete` или `blocked`; Map-007 закрывается лишь после A–C и map gate | Child closeouts, registry/backlog check |

## 12. Architecture invariant audit

| Инвариант | Точная проверяемая формулировка | Проверка/evidence |
|---|---|---|
| PCM format | WebRTC получает negotiated mono PCM S16LE frame; для baseline проверяется 8 kHz и 20 ms, допустимые 10/20/30 ms не нарушаются | Media profile + VAD operation test |
| Frame ownership | `PcmFanOut` доставляет каждый frame в независимую VAD subscription; VAD не зависит от ASR chunker | Fan-out counters and non-blocking test |
| VAD output | `VadProcessor.process(frame)` возвращает один `VadDecision` с исходными lifecycle metadata; confidence остаётся `None` | Contract assertion and JSON evidence |
| Endpoint ownership | Только `TurnDetector.consume(decision)` определяет pause/soft/hard endpoint; WebRTC VAD не завершает turn сам | State/transition matrix |
| Control/data separation | VAD и audio не публикуют PCM через Dispatcher/Event Bus и не выполняют SIP command | Architecture audit and forbidden-path test |
| Lifecycle/stale | После cancel/close закрытый speech generation не принимает frame/result; VAD error не откатывается молча к amplitude | Close/stale/error tests |
| Live candidate | Live application composition конструирует `WebRtcVadCandidate`, а `_AmplitudeVad` присутствует только в явно deterministic tools/tests | Code audit and live manifest |
| Target runtime | Import/operation выполняются на CPython 3.14t; обычный GIL-enabled Python не засчитывается | Runtime manifest |

## 13. Blocker register

Отсутствие блокера до фактической проверки фиксируется явно на уровне child plan. Карта не объявляет blocker заранее,
но задаёт обязательные triggers:

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-007-A-001` | `007-A` | Нет binding, import/operation не проходит в target no-GIL runtime или включается GIL | Весь WebRTC execution и B/C | project owner | Runtime/import/operation raw output, patch attempt | `resolved — patched binding passes target and combined runtime 2026-09-13` |
| `B-007-A-002` | `007-A` | Лицензия binding не допускает публичную демонстрацию/распространение или exact artifact не воспроизводим | Adoption candidate | project owner | License/source manifest | `resolved — MIT source/archive and wheel preserved 2026-09-13` |
| `B-007-A-003` | `007-A` | Не подтверждён lifecycle/isolation при предусмотренном concurrency | Target promotion | project owner | Concurrency output | `resolved — 8 independent instances passed in target and combined runtime 2026-09-13` |
| `B-007-B-001` | `007-B` | Фактический WebRTC output не принимается текущим `VadProcessor`/typed boundary | Application integration | project owner | Contract failure and source inspection | `not triggered — propagation passed` |
| `B-007-B-002` | `007-B` | Для config/constructor требуется новый owner или новый boundary | Application wiring | project owner | APG gap record | `not triggered — existing owners sufficient` |
| `B-007-C-001` | `007-C` | Live WebRTC path не даёт воспроизводимых speech/pause/resume transitions или ломает ASR independence | Live/demo acceptance | project owner | Baresip raw logs, VAD decisions, endpoint trace | `not triggered — I1/J4 passed` |
| `B-007-C-002` | `007-C` | Обязательное target evidence невозможно получить из-за внешнего стенда/ресурса | Live gate only | main executor/project owner | Exact command, raw output, exit code, promotion condition | `not triggered — target evidence captured` |
| `B-007-MAP-001` | map gate | Child result требует изменения protected Map-I/contract или нового process-isolated audio IPC | Map closeout and dependent execution | project owner | Gap record per APG §6 | `not triggered — protected baseline unchanged` |

Красный unit/integration тест в пределах утверждённого write-set не является APG blocker: он требует corrective pass.
Blocker появляется только при фактической категории 4, внешнем reproducible defect либо owner-review trigger согласно APG.

## 14. Test plan и evidence

| Категория | Проверка | Target runtime/команда | Ожидаемое evidence |
|---|---|---|---|
| Static/source | `rg` на live constructions и code review write-set | Windows source tree, без GPU | Нет `_AmplitudeVad` в application/live construction; deterministic usages явно маркированы |
| Contract/unit | VAD input validation: sample rate, mono S16LE, 10/20/30 ms, sequence/lifecycle и mapping bool → `VadDecision` | CPython 3.14t target test environment | Targeted test output, exit code |
| Native import | `Py_GIL_DISABLED`, `sys._is_gil_enabled()` до/после import WebRTC binding | CPython 3.14t, Ubuntu 24.04 WSL2 | stdout/stderr, version/package/source hash, GIL state |
| Native operation | Реальные 8 kHz mono PCM16 frames, 10/20/30 ms; speech/silence/noise fixtures и invalid frame errors | CPython 3.14t, no GPU required | Operation results, errors, timing, GIL state after operation |
| Controlled concurrency | Несколько независимых вызовов/instances в предусмотренном speech worker context без shared mutable instance | CPython 3.14t | GIL state, no crash, no cross-generation metadata |
| Endpoint contract | speech start, pause candidate, soft endpoint 300 ms, resume before hard, hard endpoint 500 ms | Unit/contract tests with actual `VadDecision` sequence | Endpoint trace и один authoritative hard event |
| Fan-out | VAD consumer не ждёт ASR chunker и не блокирует второй consumer | Existing fan-out test suite | Independent counters and no audio-through-bus path |
| Target live | PCMU Baresip peer → PJMEDIA decode → `PcmFrame` → WebRTC VAD → existing endpoint/ASR path | Main executor, approved Baresip stand, clean start | Live manifest, raw SIP/RTP/logs, VAD decisions, endpoint events, no-GIL/runtime metadata |
| Regression | Existing speech/runtime tests and relevant Map-005 regression set | Target runtime; no silent skip/xpass | Full command, stdout/stderr, exit code and classification |
| Documentation | architecture/TЗ/runbook/evidence registry/backlog checker | Main executor, sequential | Checker output and updated source links |

При отложенной live-проверке child plan обязан materialize APG deferred-evidence fields (`evidence_id`, owner, exact
command, raw output, accepting document и promotion condition). Пропуск не считается pass.

## 15. Реестр fallback и упрощений

| Что введено | Почему допустимо | Ограничение | Где закрывается | Статус |
|---|---|---|---|---|
| Injected fake/amplitude backend в deterministic unit/contract fixture | Нужен для изоляции endpoint/assembler logic и воспроизводимых тестов без native binding | Только явно deterministic evidence; не используется в application/live gate и не является fallback | `007-B`/`007-C` test audit | `allowed test double, not runtime fallback` |
| `none` для runtime fallback | Live path обязан доказать выбранный WebRTC VAD | При failure работа останавливается на corrective patch или owner-review gap; silent fallback запрещён | `007-A` blocker register | `required` |

## 16. Map-level gate и closeout

Map-007 может перейти в `complete` только когда:

1. `007-A`, `007-B` и `007-C` имеют собственные APG-compliant closeout со статусом `complete`;
2. exact WebRTC binding, runtime, license, no-GIL result и operation evidence сохранены;
3. application/live construction использует WebRTC VAD, а amplitude backend остаётся только deterministic test double;
4. `PcmFrame → VadDecision → TurnDetector` проходит propagation без неразрешённого contract mismatch;
5. target Baresip PCMU live gate показывает speech/pause/resume/hard endpoint и сохраняет независимость ASR;
6. все красные acceptance результаты прошли corrective protocol либо оформлены конкретным blocker; partial/foundation
   claims не используются;
7. architecture/TЗ, evidence, registry, backlog и roadmap синхронизированы, а исторические документы не переписаны;
8. ограничение «это MVP VAD baseline, а не production noise/quality campaign» явно передано в следующий доклад/runbook.

Map-level closeout обязан перечислить фактические child plans, изменённые файлы, команды/exit codes, evidence roots,
pre-existing/out-of-scope findings, deferred evidence и следующий рабочий шаг. Создание карты не является closeout.

## 17. Фактический closeout карты

Map-007 исполнена и закрыта `2026-09-13`. Порядок `007-A → 007-B → 007-C` соблюдён, каждый child plan получил
собственный APG-compliant closeout со статусом `complete`, а главный executor принял native operation и live evidence.

- `007-A`: `webrtcvad-wheels 2.0.14`, MIT, с патчем
  [`patches/webrtcvad-wheels-2.0.14-free-threading.patch`](../../patches/webrtcvad-wheels-2.0.14-free-threading.patch);
  target и combined no-GIL manifests имеют `status=pass`, GIL не включался после import/operation/concurrency.
- `007-B`: `VAD_MODE=2` добавлен в RuntimeConfig; существующая typed propagation `PcmFrame → VadDecision →
  TurnDetector` сохранена, targeted target tests прошли.
- `007-C`: clean-start I1 и полный J4 через Baresip/PCMU прошли с `WebRtcVadCandidate`; J4 имеет 6/6 обязательных
  scenario checks, `egress_underruns=0`, `asr_chunks_dropped=0`, `errors=0` и сохранённый итоговый отчёт.
- corrective pass для late `FinalUserTurn` после terminal/closed generation выполнен в существующем runtime owner;
  результат отбрасывается как stale до вызова pipeline, без нового delivery owner и без изменения Map-I.

Полный список команд, чисел и ограничений находится в [`007-C closeout`](../../artifacts/implementation/007-webrtc-vad/007-C/closeout.md),
а краткая последовательность запуска мастер-класса — в [`007-C runbook`](../../artifacts/implementation/007-webrtc-vad/007-C/runbook.md).
Наблюдение о вариативном числе ASR-финализаций на одной fixture-фразе остаётся downstream quality observation и не
выдаётся за доказательство production precision/recall WebRTC VAD.
