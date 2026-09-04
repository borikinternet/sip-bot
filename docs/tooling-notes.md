# Заметки по проектным инструментам

Статус: `active`

Документ хранит сведения, которые нужно восстановить при возвращении к задаче: какие process/tooling-паттерны были
найдены в соседнем проекте, что из них переносится в SIP-бота и какие локальные проверки являются авторитетными.
Это не реестр задач и не техническое описание runtime.

## 1. Источник адаптируемых no-GIL-паттернов

В соседнем проекте `C:\devel\cpbx-camel-integration` изучены:

- [`ToolingUsage.md`](C:/devel/cpbx-camel-integration/descriptions/ToolingUsage.md) — target `CPython 3.14t`, проверки `Py_GIL_DISABLED` и `sys._is_gil_enabled()` до/после импортов и lifecycle;
- [`test_native_compatibility.py`](C:/devel/cpbx-camel-integration/third_party/pysctp/tests/test_native_compatibility.py) — проверка интерпретатора, native import/error path и независимых worker-ов;
- [`p5_r3_no_gil_native_acceptance.py`](C:/devel/cpbx-camel-integration/tests/unit/packaging/p5_r3_no_gil_native_acceptance.py) — структурированное JSON-evidence, import graph, конкурентный lifecycle и реальный peer exchange;
- `tools/audit_p2_cpython314t.py` — проверка runtime identity, wheel/ABI и native dependency evidence;
- `third_party/pysctp/docker/free-threaded/run.ps1` — отдельные free-threaded и обычный CPython lanes.

Эти файлы не копируются в проект: в них есть SCTP, DEB, Debian, systemd/journald и production-specific правила.
Переносится только методика доказательства.

## 2. Как адаптировать методику к SIP-боту

Первый feasibility-срез должен постепенно получить следующие проверки:

1. Runtime identity: CPython 3.14.7t, `SOABI`, `Py_GIL_DISABLED`, состояние GIL.
2. Import gate: явный список критичных SIP, RTP, ASR, VAD, LLM, TTS и audio-модулей; проверка после обычных и lazy imports.
3. Component smoke: создание объекта, инициализация, одна реальная операция и shutdown.
4. Controlled concurrency: SIP callback, media loop, ASR partials, LLM cancellation, TTS playback и независимая обработка
   протокольных событий (`BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, RTP timeout) в рамках одного вызова.
5. Native peer gate: SIP/RTP loopback с PCMU вместо SCTP peer exchange.
6. Evidence: JSON с версиями, командами, стадиями, stdout/stderr, статусом и причиной каждого failure.

`pkgutil.walk_packages` из соседнего import graph не переносится автоматически: наши model-пакеты могут иметь тяжёлые
импорты и побочные эффекты. Для каждого адаптера сначала создаётся явный manifest критичных модулей и операций.

## 3. Границы tooling

- Document registry и task backlog проверяются локальными stdlib-only командами, не зависящими от runtime приложения.
- No-GIL evidence для основного приложения обязан выполняться целевым CPython 3.14t; host Python для документных проверок
  не является доказательством совместимости приложения.
- Docker можно использовать для воспроизводимой сборки/probe CPython и CPU/native dependencies.
- GPU, реальные модели и SIP/RTP latency проверяются непосредственно в WSL Ubuntu, если Docker-путь не доказан отдельно.
- Filename tag `cp314t` сам по себе не считается доказательством: требуется фактическая проверка состояния GIL после импорта и операции.
- Несовместимый native-компонент не маскируется флагом `PYTHON_GIL=0`; он либо заменяется, либо изолируется процессом.

## 4. Авторитетные локальные проверки

После изменения любого Markdown-документа выполнить:

```powershell
python tools/check_document_registry.py
```

После изменения task backlog выполнить:

```powershell
python tools/check_task_backlog.py
```

Будущие no-GIL tools должны быть добавлены отдельным implementation slice, когда появятся реальные зависимости:

```text
tools/run_nogil_probe.ps1
tools/nogil_probe.py
tests/runtime/test_free_threaded_runtime.py
tests/runtime/test_component_nogil.py
```

## 5. Что не переносится

- внешний deferred-test registry и promotion governance;
- SCTP/pysctp, `libsctp`, DEB/package manifest и systemd/journald lifecycle;
- требования чужого production runtime, `ldd`/ELF policy и Debian-specific ABI limits;
- чужие task/document identifiers;
- assertion о production-ready статусе только на основании import-only smoke.
