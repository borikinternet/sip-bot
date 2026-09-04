# Plan-002-B: SIP/media adapter

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-02`  
Статус исполнения: `complete` — B1–B4 имеют acceptance evidence и propagation handoff от `2026-09-03`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Собрать application boundary поверх принятого PJSUA2/PJMEDIA baseline и approved `001-S`: установить/принять/завершить
локальный SIP-звонок, передавать PCMU/RTP, выдавать внутренние media frames и самостоятельно отвечать на применимые
протокольные события. Адаптер не ждёт Dispatcher, ASR, LLM, TTS или отчёт.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | SIP/media входят в MVP, PBX-логика и запись аудио — нет | Работа только с обычным локальным SIP peer и PCMU | `001-S` smoke | Реализуется PBX или recording |
| [`architecture.md`](../architecture.md) | Protocol reaction локальна, прикладное событие публикуется наверх | Callback не блокируется центральным Dispatcher | SIP event timing tests | BYE/OPTIONS/re-INVITE ждут AI |
| [`technical-specification.md`](../technical-specification.md) | PCMU, внутренний PCM, 30 ms RTP budget | Adapter не меняет media baseline | PCMU loopback | Иной codec без decision |
| [`plan-001-C1-sip-pjsua2-pjmedia.md`](plan-001-C1-sip-pjsua2-pjmedia.md) | Сохранить patches и no-GIL tested path | Generated SWIG patches входят в write/evidence boundary | Import/operation evidence | Patch не воспроизводится |
| [`plan-001-S-voip-test-stand.md`](plan-001-S-voip-test-stand.md) | Approved Baresip peer/fake operator | Стенд используется как локальный peer | Baresip PCMU/BYE/transfer smoke | Стендовый контракт расходится |

## 3. Граница задачи

**Цель:** SIP call/media lifecycle и PJSUA2/PJMEDIA callbacks.

**Входит:** adapter, SIP command/event mapping, RTP ingress/egress handoff, media failure/timeout events, local replies
на `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume и применимые transport/media failures.

**Не входит:** PBX routing, операторская логика, PCM conversion/framing ownership, ASR/VAD/TTS, LLM, RAG, report.

**Protected baseline:** PJSUA2/PJMEDIA, PCMU, patches из C1, `001-S`, один вызов, direct media channels, no-GIL main
process unless C evidence requires approved isolation.

**Предположения:** `002-A` предоставляет runtime/lifecycle; generated bindings и зависимости уже подготовлены feasibility
планом, но их фактические import/operation checks повторяются в application environment.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| SIP adapter | `src/sip_bot/sip_media/` | Отсутствует | Typed adapter over PJSUA2/PJMEDIA | Нет app callback layer | Создать adapter и lifecycle owner |
| Media bridge | `src/sip_bot/sip_media/media_port.py` | Отсутствует | Handoff media frames to `002-C` | Точный callback shape должен быть проверен | Зафиксировать фактический output в Map-I |
| Control mapping | `src/sip_bot/sip_media/protocol_events.py` | Отсутствует | Local reply + normalized event | Неявные SIP event mappings | Создать table-driven mapping |
| Integration tests | `tests/integration/test_sip_media.py` | Отсутствуют | `001-S` PCMU/call/event evidence | Нет app harness | Создать smoke tests |
| Evidence | `artifacts/.../002-B/` | Отсутствует | Call/event/media logs | Нет application evidence | Записывать только after execution |

Допустимый write-set: `src/sip_bot/sip_media/`, SIP/media tests и собственный evidence root; минимальные изменения в
`src/sip_bot/control/` разрешены только для typed event handoff. PJSIP source/patches из `001-C1` не переписываются
молча; при необходимости изменения останавливаются на owner review.

## 5. Interaction topology и propagation контрактов

Основные рёбра: `N1 ⇄ N9` SIP lifecycle, `N1 → N2` PCMU/RTP ingress, `N2 → N3` internal `PcmFrame`, `N2/N3 → N9`
normalized `SpeechEvent`/`MediaFailure`. На protocol edge сначала выполняется обязательный локальный ответ, затем
может публиковаться control event. `BYE` во время LLM/TTS должен завершить SIP transaction и закрыть call channels без
ожидания результата модели. Фактические callback fields и media frame fields передаются в `Map-002-I` до handoff `002-C`.

## 6. Audit владельца поведения и парадигмы реализации

SIP/media adapter владеет protocol transaction, media lifecycle и callback affinity; Dispatcher владеет только смыслом
нормализованного события. Callback-объекты являются owner objects, а pure mapping/validation helpers не меняют состояние.
Ни один helper не выполняет LLM/ASR/TTS и не обходит закрытие call scope.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Сохраняем PJSUA2/PJMEDIA? | Да, baseline C1 и `001-S` принят | Новый SIP stack не рассматривается в этом plan | `resolved` |
| Какой codec? | PCMU; internal PCM boundary передаётся `002-C` | Codec conversion не скрывается в Dispatcher | `resolved` |
| Какие protocol events обязательны? | BYE, CANCEL, OPTIONS, re-INVITE/UPDATE, hold/resume, RTP/media failure | BYE — минимальный тест, но не единственный контракт | `resolved` |
| Откуда брать media parameters? | Из согласованного SDP и соответствующих словарей/объектов PJMEDIA для каждого конкретного звонка | Adapter публикует `NegotiatedMediaProfile`; downstream не зашивает `ptime` или frame size | `resolved: owner review accepted 2026-09-02` |
| Что делать при mismatch generated binding/patch? | Применять протокол gap из APG §6: остановить затронутый slice, зафиксировать gap и вынести на owner review только при фактическом trigger | Запрещён молчаливый compatibility bridge; заранее утверждённое правило не является открытым вопросом | `resolved: APG §6; review only if triggered` |

## 8. Process invariant audit

- SIP adapter не расширяется до PBX или fake operator semantics.
- PCMU/media callbacks и control events имеют отдельные тесты.
- Docker используется только для approved peer/test stand; сам adapter не объявляется production-ready.
- Execution command и exact patch/import evidence сохраняются в собственном root.
- Owner review принят 2026-09-02. Execution выполнен по APG §3.1 на выбранном target runtime по APG §3.2.
- Исторический mismatch B3 классифицирован по APG §5.8B как локальная ошибка application adapter: wildcard `-1` был
  передан в `getStreamInfo()` с unsigned media index. Исправление использует фактический `CallMediaInfo.index` и
  явно освобождает native media port до уничтожения endpoint; target rerun прошёл.

## 9. Architecture invariant audit

- Local protocol replies не ждут Dispatcher или AI.
- Большие audio payload не проходят через Dispatcher.
- Call close идемпотентен и закрывает media channels; новые каналы не используют старый producer.
- PJSUA2/PJMEDIA patches C1 сохраняются; no-GIL regression проверяется в application runtime.
- Adapter публикует только normalized control events и media handoff, не structured LLM decisions.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| B1 | Повторить import/lifecycle probe patched PJSUA2/PJMEDIA | Binding импортируется и basic call objects работают в approved runtime | Import/GIL/patch failure |
| B2 | Реализовать call setup/accept/close и local protocol reactions | `001-S` устанавливает и завершает вызов; BYE/CANCEL/OPTIONS отвечают без AI | Callback блокируется |
| B3 | Подключить PCMU/RTP ingress/egress handoff | PCMU loopback и media failure event наблюдаемы | Codec/ptime фактически иной без review |
| B4 | Передать callback fields/contracts в Map-I | `002-C` получает фактические `PcmFrame` assumptions | Candidate contract не подтверждён |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-B-001` | B1 | Child plan не прошёл owner review | SIP code/execution | project owner | APG review | `resolved: owner review accepted 2026-09-02` |
| `B-002-B-002` | B1–B3 | Application import не воспроизводит C1 patch/no-GIL baseline | Весь SIP/media lane | project owner + C1 owner | [`runtime-import.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/runtime-import.json) | `resolved for B1: target import/init/no-GIL pass 2026-09-02; B3 has separate gap` |
| `B-002-B-003` | B2–B3 | Local protocol callback требует ожидания main Dispatcher | Protocol correctness и downstream integration | media owner | [`lifecycle-options.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/lifecycle-options.json), [`remote-bye.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/remote-bye.json) | `resolved for B2 2026-09-02: local reply/event queue and live BYE timing pass` |
| `B-002-B-GAP-001` | B3–B4 | Historical application adapter passed wildcard `-1` from `getAudioMedia()` into unsigned `getStreamInfo()` | PCMU/profile extraction, bridge and Map-I handoff | media owner | [`gap-B-002-B-GAP-001.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/gap-B-002-B-GAP-001.md), [`pcmu-profile-handoff.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/pcmu-profile-handoff.json) | `resolved: local implementation correction and target rerun passed 2026-09-03` |

## 12. Test plan и evidence

- import/no-GIL check patched PJSUA2/PJMEDIA;
- local Baresip call setup, accept, normal hangup;
- remote `BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, hold/resume;
- RTP timeout/media failure and normalized event delivery;
- PCMU loopback with media timestamps and no audio recording by project;
- close/re-close and terminal event while a model operation is represented by a non-blocking stub;
- сохранять SIP traces, media counters, timing, exit codes и patch identity.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Process isolation for SIP binding | Допускается ADR-003 при фактической incompatibility | Только evidence-backed, без молчаливого изменения baseline | Новое owner decision/ADR if triggered | `deferred unless triggered` |
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Дата исполнения: `2026-09-03`.

Итог: `complete`; B1–B4 имеют acceptance evidence. Исторический B3 gap устранён в application code и подтверждён
повторным target-прогоном; `002-C` получил фактический media contract через `Map-002-I` revision 4.

### 14.1 Acceptance по срезам

| Срез | Результат | Фактическое evidence |
|---|---|---|
| B1 import/lifecycle/no-GIL | `pass` | [`runtime-import.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/runtime-import.json): target executable `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`, Ubuntu-24.04/WSL2, user `sipbot`, CPython 3.14.7t, `pjsua2` import, `Endpoint/libCreate/libDestroy`, `gil_before_import=false`, `gil_after_import_and_lifecycle=false`, exit code 0. |
| B2 call setup/accept/close/local protocol reaction | `pass` | [`lifecycle-options.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/lifecycle-options.json): approved Baresip peer, OPTIONS `SIP/2.0 200 OK`, call answered and local `CALL_ENDED`; [`remote-bye.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/remote-bye.json): remote BYE produced `remote_hangup` and active call cleared. |
| B3 PCMU/RTP ingress/egress/profile | `pass` | [`pcmu-profile-handoff.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/pcmu-profile-handoff.json): target test passed with PCMU profile from the actual per-call media index; [`remote-bye.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/remote-bye.json) records 10 ingress and 10 egress application frames with no callback errors; approved `001-S` provides the bidirectional RTP loopback baseline. |
| B4 Map-I contract handoff | `pass` | [`propagation-002-B.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/interaction-map/propagation-002-B.md): actual media index/profile, `PcmFrame`, direct media channels, control events and lifecycle rules propagated to `Map-002-I` revision 4. |

### 14.2 Реализованный application boundary

Изменённые application/test файлы:

- `src/sip_bot/sip_media/models.py` — immutable `NegotiatedMediaProfile` и `PcmFrame`; codec/payload/ptime/rate/channels/frame-size читаются из PJMEDIA values, профиль закрепляется на каждом frame.
- `src/sip_bot/sip_media/protocol_events.py` — table-driven local replies и компактные normalized events без audio payload.
- `src/sip_bot/sip_media/media_port.py` — bounded bidirectional `AudioMediaPort` handoff, callback-safe ingress/egress queues, counters и failure notification.
- `src/sip_bot/sip_media/adapter.py` — endpoint/account/call owner, call lifecycle, incoming auto-answer, local hold/resume/update/transfer operations, OPTIONS/PJSUA2 local protocol behavior, immediate failure reactions, explicit `dispatch_events` outside native callbacks.
- `src/sip_bot/sip_media/__init__.py` — public exports.
- `tests/unit/test_sip_media.py` — profile, bounded callback handoff, protocol table, UPDATE/re-INVITE and non-blocking failure reaction tests.
- `tests/integration/conftest.py`, `tests/integration/test_sip_media.py` — target-runtime Baresip harness and explicit B1/B2/B3 evidence tests.

PJSIP source, generated binding, C1 patches, protected documents, `002-A`, ASR/VAD/LLM/TTS/RAG/transfer behavior and
production services не изменялись. Audio recording и external PBX не использовались. Heavy GPU inference не запускался.

### 14.3 Runtime, patch и peer identity

- Runtime: Ubuntu 24.04.4 LTS / x86_64 / WSL2 / `sipbot`; executable `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`; executable SHA256 `0a916f87168ea31199a34188aa6bd528efaa2c9ce451e51ead13cc4a9dc32fa4`; SOABI `cpython-314t-x86_64-linux-gnu`; `Py_GIL_DISABLED=1`.
- PJSUA2/PJMEDIA: 2.17, native module SHA256 `510117d59355d3ea0f30f84d9fdc5fbd6ec6d019eb989dabe9660661846cd01d`.
- C1 patch identity сохранена в [`patch-identity.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/patch-identity.json); hashes `d5fd6d...f36aa` и `9c849b...48be5`.
- Approved peer: Baresip `1.0.0-4build14`, config `artifacts/feasibility/001-S-voip-test-stand/config/peer-5080`, observed peer codec baseline `PCMU/8000/1`.

### 14.4 Команды и результаты

Полный command ledger, stdout/stderr runtime probe, exit codes и interpretation находятся в [`commands.md`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/commands.md) и [`runtime-import.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/runtime-import.json).

- `python -m compileall -q src/sip_bot/sip_media` — exit 0.
- `python -m pytest -q tests/unit tests/contract` — exit 0, `21 passed` (host deterministic lane; не application evidence).
- Target B2 command — exit 0, `2 passed, 1 deselected`.
- Target B3 corrective rerun — exit 0, `1 passed, 2 deselected`; профиль PCMU получен по фактическому media index.
- Полный target B integration command — exit 0, `3 passed`; native endpoint teardown завершился без abort.
- `python tools/check_document_registry.py` — exit 0, 36/36, PASS.
- `python tools/check_task_backlog.py` — exit 0, 6 unique rows, PASS.

### 14.5 Gap, corrective pass и handoff

[`B-002-B-GAP-001`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-B/gap-B-002-B-GAP-001.md) был фактическим trigger APG §6, но по APG §5.8B после проверки исходника и команды
классифицирован как локальная ошибка реализации, а не owner/external blocker. Причина: application code использовал
`getAudioMedia(-1)` как wildcard и переносил тот же `-1` в `getStreamInfo()`, чей generated параметр имеет unsigned тип.
Исправление выбирает active audio `CallMediaInfo.index`, передаёт один и тот же неотрицательный index в `getStreamInfo()`
и `getAudioMedia()`, сохраняет его в call scope и добавляет его в media event details.

При первой corrective rerun дополнительно обнаружилось, что callback-owned native `AudioMediaPort` мог пережить
уничтожение PJMEDIA из-за reference cycle. Adapter теперь останавливает оба направления, закрывает bounded channels и
явно release-ит native port до `Endpoint.libDestroy()`; это подтверждено полным target integration rerun без native abort.

Pre-existing/out-of-scope findings: рабочее дерево изначально содержит многочисленные user-owned staged/untracked файлы;
они не смешивались с этим срезом. Старые `001-S` и C1 feasibility artifacts используются как baseline.
`lifecycle-pcmu.json` в evidence root — superseded preliminary run до разделения B2/B3 и не является acceptance evidence.

Следующий шаг: использовать `Map-002-I` revision 4 в `002-C` и последующих consumers. Новый owner decision, isolation
или изменение C1 patches не требуется.
