# Plan-002-A: application runtime skeleton

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-02`  
Статус исполнения: `complete` — execution завершён `2026-09-02`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Обязательная boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Создать минимальный запускаемый каркас приложения на free-threaded CPython, единый файл конфигурационных констант,
наблюдаемый lifecycle одного разговора и базовую доставку control-plane событий к Dispatcher/FSM. Результат не должен
подключать SIP, GPU-модели или реальный пользовательский payload: он доказывает только runtime foundation и правила
запуска следующих child plans.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | MVP обслуживает один разговор и хранит текстовый context/report | Runtime имеет один явный call scope и lifecycle close | Lifecycle tests | Скрытый multi-call scope или аудиозапись |
| [`architecture.md`](../architecture.md) | Dispatcher владеет control plane, payload идёт напрямую | Каркас не становится транзитом аудио/крупного текста | Ownership audit | Runtime API принимает payload вместо каналов |
| [`technical-specification.md`](../technical-specification.md) | Конфигурация MVP — константы в `config/constants.py` | Все обязательные параметры читаются из одного файла | Config import test | Скрытые defaults или `.env`-конфигурация |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Free-threaded CPython — приоритет | Запуск проверяет `3.14t` и отсутствие непреднамеренного GIL | Runtime evidence | Main process работает на GIL-enabled runtime |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan имеет source-map, blockers, tests и closeout | Все обязательные разделы присутствуют в этом файле | APG audit | Исполнение без owner review |

## 3. Граница задачи

**Цель:** runtime/bootstrap, constants, logging, call scope и базовые control events.

**Входит:** будущие `src/sip_bot/`, `config/constants.py`, минимальные typed event envelopes, lifecycle registry,
тестовый entrypoint и evidence root.

**Не входит:** SIP/PJMEDIA, RTP, аудио-буферы, ASR/VAD, LLM/TTS, RAG, transfer и сквозной demo-flow.

**Protected baseline:** CPython `3.14.7t`/no-GIL, Ubuntu/WSL2 baseline, один разговор, PCMU, прямые data-plane каналы,
Dispatcher как владелец control plane.

**Предположения о рабочем дереве:** application source tree пока отсутствует; существующие документы `requirements.md`,
`architecture.md`, `technical-specification.md`, ADR и исполненные `001-*` не изменяются.

**Зависимости и внешние сервисы:** `001-A`, `001-B`, `001-D`, `001-E`, принятая `Map-002-I`; внешние сервисы и GPU на
этом срезе не нужны.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| Runtime package | `src/sip_bot/` | Отсутствует | Импортируемый пакет с entrypoint | Нет application code | Создать минимальный пакет |
| Config | `config/constants.py` | Отсутствует | Именованные конфигурационные константы | Нет единого источника | Создать файл и import test |
| Control foundation | `src/sip_bot/control/` | Отсутствует | Typed event envelope и lifecycle dispatch boundary | Контракты candidate в Map-002-I | Реализовать только согласованные типы |
| Tests | `tests/unit/`, `tests/contract/` | Отсутствуют | Runtime/config/lifecycle tests | Нет test runner baseline | Создать deterministic tests |
| Evidence | `artifacts/implementation/002-mvp-media-and-speech-integration/002-A/` | Отсутствует | Команды, stdout/stderr и результаты | Нет evidence root | Создать при execution |

Допустимый write-set: `src/sip_bot/`, `config/constants.py`, `tests/unit/`, `tests/contract/`, собственный evidence root
и этот plan-file. Запрещено менять protected документы, модели и внешние сервисы.

## 5. Interaction topology и propagation контрактов

Каркас не переносит data-plane payload. Он предоставляет жизненный цикл каналов и typed control boundary для будущих
`N9` Dispatcher/FSM и SIP/media adapter. Candidate-контракты берутся из актуальной ревизии `Map-002-I`; после создания
каждого типа в карту передаются фактические поля, close/cancel semantics и downstream contract fixtures.

Минимально проверяются `call_open`, `call_close`, `channel_open`, `channel_close`, terminal event и повторное закрытие.
При terminal event во время незавершённой операции закрытие должно быть идемпотентным, а stale payload не должен быть
доставлен в новый канал.

## 6. Audit владельца поведения и парадигмы реализации

Владельцем call/channel lifecycle является runtime coordinator; Dispatcher владеет смысловыми control transitions.
Typed event envelope является value object без самостоятельного lifecycle. Registry получает scoped channel handles и
cancel token; свободные функции допускаются только для pure validation/serialization и не меняют состояние FSM или канала.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Допустим ли application root `src/sip_bot/`? | Да, как implementation path этого child plan | Следующие планы используют этот root и уточняют подпакеты | `resolved: owner review accepted 2026-09-02` |
| Где хранить MVP-конфигурацию? | `config/constants.py` | Runtime не читает скрытые environment defaults | `resolved` |
| Должен ли runtime включать data-plane payload? | Нет | Аудио и крупный текст реализуются последующими boundary plans | `resolved` |

## 8. Process invariant audit

- Срез ограничен runtime foundation и не маскирует интеграцию под bootstrap.
- Write-set disjoint относительно остальных child plans, кроме согласованного package root.
- Команды проверки воспроизводимы: `python -m pytest -q tests/unit tests/contract`.
- Owner review принят 2026-09-02; execution выполняется по APG 3.1 через субагента на актуальной contract revision `Map-002-I`.
- После изменения Markdown запускаются document-registry и backlog audits.

## 9. Architecture invariant audit

- Dispatcher остаётся владельцем control plane и не получает аудиофреймы.
- Runtime не ждёт ASR/LLM/TTS и не вызывает тяжёлые операции из callback-а.
- Закрытие call/channel идемпотентно; закрытый канал не переиспользуется.
- Основной процесс запускается на free-threaded CPython; native imports на этом срезе не добавляются.
- Конфигурация берётся из `config/constants.py` без скрытого fallback.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| A1 | Создать package/entrypoint и runtime version probe | Пакет импортируется, runtime evidence сохраняется | Не удаётся подтвердить no-GIL runtime |
| A2 | Создать `config/constants.py` и typed config access | Константы импортируются, отсутствуют неявные defaults | Параметр нужен, но его владелец не определён |
| A3 | Создать call/channel lifecycle и control event envelope | Open/close/re-close и terminal event проходят deterministic tests | Stale delivery или неидемпотентное закрытие |
| A4 | Записать evidence и handoff contract revision | Следующий план получает проверенные типы и команды | Фактические типы расходятся с Map-002-I |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-A-001` | весь plan | Child plan не прошёл owner review | Любая кодовая правка и execution | project owner | Этот файл и APG review | `resolved: owner review accepted 2026-09-02` |
| `B-002-A-002` | A1 | На host/diagnostic runtime нет подтверждения free-threaded CPython | Runtime startup gate | project owner | Target runtime probe и entrypoint evidence | `resolved: target runtime verified 2026-09-02` |
| `B-002-A-003` | A4 | Фактический control envelope не передан в Map-002-I propagation checkpoint | Downstream contract handoff | main executor | Map-002-I revision 3 и interaction-map evidence | `resolved: propagation checkpoint recorded 2026-09-02` |

## 12. Test plan и evidence

- `python --version` и явная проверка free-threaded build;
- import test `config.constants` и проверка отсутствия скрытой конфигурации;
- unit tests lifecycle: open, close, повторное close, terminal event during operation;
- contract tests envelope against `Map-002-I`;
- target-runtime unit/contract run on CPython 3.14.7t/no-GIL и strict application preflight;
- сохранение команды, exit code, stdout/stderr и версии в `artifacts/.../002-A/`.

Deferred evidence не объявляется pass. Если фактический runtime path потребует иной версии или process boundary, создаётся
новый blocker и plan возвращается на review.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete` — runtime foundation, config, lifecycle,
typed control envelopes и deterministic tests реализованы; strict free-threaded
startup gate подтверждён на целевом WSL runtime.

### Фактически изменённые файлы

Разрешённый write-set затронут только в следующих областях:

- `src/sip_bot/__init__.py`, `src/sip_bot/__main__.py`, `src/sip_bot/config.py`,
  `src/sip_bot/logging_setup.py`, `src/sip_bot/runtime.py`;
- `src/sip_bot/control/__init__.py`, `src/sip_bot/control/events.py`,
  `src/sip_bot/control/lifecycle.py`;
- `config/constants.py`;
- `tests/unit/conftest.py`, `tests/unit/test_config.py`,
  `tests/unit/test_entrypoint.py`, `tests/unit/test_lifecycle.py`;
- `tests/contract/conftest.py`, `tests/contract/test_control_event_contract.py`;
- собственный evidence root
  `artifacts/implementation/002-mvp-media-and-speech-integration/002-A/`.

Protected документы, SIP/PJMEDIA, RTP, ASR/VAD, LLM/TTS, RAG, transfer,
модели и внешние сервисы не изменялись и не запускались. Ни одного GPU
inference/import не выполнялось.

### Реализация и contract handoff

- A1: package/entrypoint и runtime probe созданы. Probe проверяет фактические
  `Py_GIL_DISABLED` и `sys._is_gil_enabled()`; скрытый `--allow-gil` или иной
  fallback не добавлялся.
- A2: `config/constants.py` является единственным источником статических MVP
  настроек; `RuntimeConfig.from_constants()` создаёт immutable typed snapshot и
  не читает environment.
- A3: `LifecycleRegistry` допускает один active call, `CallScope` владеет
  каналами, `ChannelHandle` одноразовый, закрытие отменяет scoped token и
  повторное закрытие не меняет состояние. Generation-aware dispatch отбрасывает
  stale control event после закрытия старого канала.
- A4: envelope materialized по `Map-002-I` revision `3`: `ControlEvent` с
  `kind`, `call_id`, optional `channel_id`/`channel_generation`, monotonic
  `sequence`, `timestamp_ns` и immutable typed lifecycle payload. `ControlEventSink`
  — только явная boundary для будущего Dispatcher/FSM; полноценный event bus,
  Dispatcher и FSM остаются scope `002-E`.

### Выполненные проверки

Команды, раздельные stdout/stderr и exit codes сохранены в evidence root:

| Команда | Результат |
|---|---|
| `python --version` | `0`; `Python 3.14.3` |
| explicit `Py_GIL_DISABLED`/`sys._is_gil_enabled()` probe | `0`; `Py_GIL_DISABLED=0`, `gil_enabled=true` |
| explicit config import probe | `0`; `sip-bot`, `PCMU`, `8000 Hz`, mono, no-GIL required |
| `python -m pytest -q tests/unit tests/contract` | `0`; `12 passed` |
| `PYTHONPATH=src python -m sip_bot` | `2`; ожидаемая строгая ошибка preflight на GIL-enabled host |
| `python -m compileall -q src config` | `0` |
| `python tools/check_document_registry.py` после closeout | `0`; `PASS` |
| `python tools/check_task_backlog.py` после closeout | `0`; `PASS` |

### Blocker/gap и pre-existing findings

| ID | Статус | Влияние | Evidence и условие promotion |
|---|---|---|---|
| `B-002-A-001` | `resolved` | Child plan прошёл owner review | Этот файл и APG review |
| `B-002-A-002` | `resolved` | Target `Ubuntu-24.04/WSL2` runtime под пользователем `sipbot` — CPython 3.14.7t с `Py_GIL_DISABLED=1` и `gil_enabled=false`; strict startup gate проходит | `target-runtime-probe.json`, `target-entrypoint.stdout.log`; повторять probe на том же target executable после изменения runtime/native imports |
| `B-002-A-003` | `resolved` | Фактический control envelope передан в Map-002-I propagation checkpoint; contract-map evidence создан основным executor-ом | `target-runtime-probe.json`, `interaction-map/propagation-002-A.md`, Map-002-I revision 3 |

Pre-existing findings: до начала execution отсутствовали `src/`, `config/`,
`tests/`; рабочее дерево также содержит unrelated `.idea`, `.codex`, `artifacts`,
`docs` и `tools`, которые не являются частью scope A. Windows CPython 3.14.3
и default WSL Python 3.12 использовались только как host/diagnostic runtimes и
не выдавались за application evidence.

### Deferred/out-of-scope

SIP/media, RTP, speech ingress, Dispatcher/FSM/event bus, prompt/context/RAG,
LLM Facade, TTS/playback, transfer/report и сквозной demo-flow не являются
реализованными результатами этого child plan. Для них не создавался silent
skip/xfail и не объявлялся pass; их владельцы — последующие approved child
plans. No-GIL promotion подтверждён на target executable; дальнейшие native
import проверки выполняются в соответствующих child plans.

### Handoff и следующий шаг

Уровень документа: `child plan`. Незакрытых дочерних пунктов у этого plan нет.
Этот closeout является handoff делегированного execution: фактические тесты,
target runtime и diff проверены текущим executor; contract-map propagation
checkpoint синхронизирован отдельно. Следующий узкий шаг — `002-B`, который
уже передан субагенту и остановил только B3/B4 на конкретном media gap. План A
закрыт статусом `complete` в полном scope этого plan-file; SIP/media и остальные компоненты в него не входят.
