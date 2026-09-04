# C2 ASR primary — GPU execution closeout

Дата: 2026-08-27

Статус исполнения child plan: `complete`  
Candidate decision: `pass`

## Выполнено

- Один primary ASR frozen: `ASR-PRIMARY-001-faster-whisper` (`faster-whisper==1.2.1`).
- Зафиксированы upstream revisions, model revision, package/model/dependency licenses, artifact hashes и baseline
  `CPython 3.14.7t` в `candidate-freeze.md` и `runtime-manifest.json`.
- Создан и syntax-checked `tools/asr_primary_probe.py`.
- Выполнен CPU-safe import/no-GIL gate в отдельном свежем subprocess для каждого критичного native import.
- `tokenizers==0.23.1` собран из source под `cp314t` и прошёл индивидуальный no-GIL import.
- `numpy`, `PyYAML`, `onnxruntime`, `av` и `tokenizers` прошли индивидуальные import checks.
- Зафиксировано исходное включение GIL у `ctranslate2==4.8.1`; подготовлен узкий pybind11 patch и локальная patched
  binding-сборка на exact CTranslate2 source revision.
- После patch повторён import/no-GIL gate: все критичные imports прошли, GIL не включался, warnings отсутствуют.
- Pinned `Systran/faster-whisper-large-v3` revision скачана в WSL и проверена по manifest/sha256.
- Materialized и CPU-декодирован короткий licensed offline Russian fixture; live conversation audio не создавалось.
- Подготовлены guarded operation/streaming commands с `LD_LIBRARY_PATH`, fixture и model paths.
- Главным агентом выполнена GPU one-shot operation на `cuda/int8_float16`: модель загрузилась за 8.375 s,
  получен непустой русский результат, а `sys._is_gil_enabled()` оставался `false` до импорта, после загрузки
  модели и после operation.
- Выполнена bounded-prefix streaming probe с шагом 1.0 s: наблюдались partial-гипотезы и authoritative final;
  последний partial совпал с final, GIL оставался отключённым.
- Выполнена cancellation/close probe: после первого сегмента lazy generator закрыт, после закрытия элементов не
  поступило и stale result не принят; GIL оставался отключённым.
- Для GPU operation в отдельном disposable environment установлены и явно включены CUDA libraries
  `nvidia-cublas-cu12==12.9.2.10`, `nvidia-cuda-nvrtc-cu12==12.9.86` и `nvidia-cudnn-cu12==9.24.0.43`;
  фактический путь записан в `commands-and-versions.txt`.

## Результат

Статус: **operation evidence complete; candidate accepted for the tested main-process MVP path**.

`faster-whisper` остаётся единственным зафиксированным primary. Для exact CTranslate2 binding требуется узкий
`ctranslate2-free-threading.patch`; непатченный binding автоматически включал GIL, а patched binding прошёл
import и operation gates. В tested path model load и inference выполнялись в main process без возврата GIL.
`PYTHON_GIL=0`/`-Xgil=0` намеренно не использовались.

Итог по срезам: `C2-S1` — pass, `C2-S2` — pass, `C2-S3` — pass на границе закрытия data-plane канала,
`C2-S4` — pass.

## Ограничение cancellation

`faster-whisper==1.2.1` не предоставляет отдельный native cancellation token. Поэтому evidence доказывает
candidate-owned generator-close и правило закрытого data-plane канала: late/stale output не публикуется. Оно не
доказывает немедленное прерывание уже выполняющегося native kernel. Для принятой MVP-архитектуры это соответствует
семантике «отобрать трубу»: операция может быть дренирована/завершена отдельно, а её результат после close уходит
в никуда. Это ограничение нельзя описывать как hard native cancellation.

## Gaps и owner decisions

- Публичный mirror с фактическим shard Common Voice 26.0 имеет исторический alias `...25-0`; это подробно записано
  в `fixture.md`. Если строго требуется именно 25.0, fixture нужно заменить отдельным owner-approved шагом.
- Patched binding проверена на import и operation level; это не является доказательством полной потокобезопасности
  CTranslate2 при произвольном многопоточном доступе и не заменяет будущую интеграционную проверку.
- Текущие transient download locks/ошибка resume с кодом curl 23 обработаны повторной загрузкой; blocker по lock не
  создавался.

Изменения owner-документов не требовались для выполнения этого child plan. Точная patch-инварианта добавлена в
plan `docs/plans/plan-001-C2-asr-primary.md`; fallback и process isolation не выбирались.
