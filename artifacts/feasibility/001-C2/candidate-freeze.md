# C2-S0 candidate freeze: primary ASR

Дата фиксации: 2026-08-27

## Единственный primary

| Поле | Значение |
|---|---|
| Candidate ID | `ASR-PRIMARY-001-faster-whisper` |
| Пакет | `faster-whisper==1.2.1` |
| Upstream revision | tag `v1.2.1`, commit `65882eee9f5cdbeeb2d877f1131d48cf241b327d` |
| Package license | MIT |
| PyPI artifact | `faster_whisper-1.2.1-py3-none-any.whl`, SHA-256 `79a66ad50688c0b794dd501dc340a736992a6342f7f95e5811be60b5224a26a7` |
| Основной модельный artefact | `Systran/faster-whisper-large-v3` |
| Model revision | commit `edaa852ec7e145841d8ffdb056a99866b5f0a478` |
| Model license | MIT по model card Systran |
| Язык | русский (`ru`), multilingual Whisper large-v3 |
| Предполагаемый режим | `device=cuda`, `compute_type=int8_float16`, одна сессия |
| Статус | frozen as primary, not accepted yet |

`faster-whisper` выбран как один primary из-за готового Python API, multilingual Whisper large-v3 с русским языком,
CTranslate2 backend, word-level timestamps/VAD hooks и существующей экосистемы streaming adapters. Это не означает,
что его streaming boundary или latency уже приняты: upstream API возвращает генератор сегментов, а streaming-policy и
Transcript Assembler остаются нашей задачей.

Fallback-кандидат не выбран и не проверялся.

## Обновление restricted preparation stage

`ctranslate2==4.8.1` первоначально не прошёл import/no-GIL gate, поэтому подготовлена узкая локальная сборка
Python binding на исходной ревизии `0d8bcd362ac75ef860ef161d6f0efad0ae439ff0`. Изменена только регистрация
pybind11-модуля `_ext`: добавлен `py::mod_gil_not_used()`. Native library CTranslate2 не пересобиралась и взята
из точно зафиксированного исходного wheel.

- Patch: `ctranslate2-free-threading.patch`, SHA-256
  `6c118e2707adf715bdccd3b74f772490373927f455a25a857b991160d73ed619`.
- Patched wheel SHA-256:
  `2daac26a165060fcb8b8bf4d712cb3cd135c416eb17aa79a2713ea702528e4c7`.
- После patch свежий import/no-GIL gate прошёл для всех перечисленных критичных импортов; см.
  `import-no-gil.json` и `patch-build.md`.
- Operation-level no-GIL, model load, GPU inference, partial/final streaming и cancellation ещё не проверялись.

Pinned model revision `edaa852ec7e145841d8ffdb056a99866b5f0a478` скачана и проверена; подробный file manifest находится
в `model-manifest.json`. Primary остаётся frozen, но **not accepted yet** до GPU/operation stages.

## Зафиксированные зависимости

| Компонент | Версия | License | No-GIL observation |
|---|---:|---|---|
| `ctranslate2` | 4.8.1 | MIT | **FAIL**: `_ext` автоматически включает GIL |
| `tokenizers` | 0.23.1 | Apache-2.0 | PASS после CPU-only сборки из source |
| `av` | 18.1.0 | BSD-3-Clause | PASS |
| `onnxruntime` | 1.29.0 | MIT | PASS |
| `numpy` | 2.5.2 | BSD-3-Clause | PASS |
| `PyYAML` | 6.0.3 | MIT | PASS |

Полный runtime и artifact manifest находится в `runtime-manifest.json`; фактические import observations — в
`import-no-gil.json`.

## Обязательное ограничение

`ctranslate2==4.8.1` не является допустимым main-process no-GIL baseline в текущем виде. При импорте в свежем
процессе CPython `3.14.7t` получен официальный `RuntimeWarning`:

~~~text
The global interpreter lock (GIL) has been enabled to load module
'ctranslate2._ext', which has not declared that it can run safely without the GIL.
~~~

Попытка продолжить через `PYTHON_GIL=0` или `-Xgil=0` не принимается: это подавляет защитный механизм без доказанной
безопасности native-модуля. GPU model load/inference и benchmark до закрытия `C2-B-004` не выполняются.

Варианты закрытия blocker, не выбранные автоматически:

1. узкий поддерживаемый патч/сборка CTranslate2 с корректным free-threading module marker и повторным operation-gate;
2. явный отдельный process boundary для ASR с IPC, после owner decision и отдельного описания контракта.
