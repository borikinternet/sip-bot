# 005-B commands and exit codes

Дата: `2026-09-04`  
Target: Ubuntu 24.04/WSL2, CPython `3.14.7t`, `gil_enabled=false`.

| Проверка | Команда/вариант | Exit | Результат |
|---|---|---:|---|
| Unit/integration B matrix | `python -m pytest -q tests/unit/test_map005_speech_resilience.py tests/integration/test_map005_speech_resilience.py` на target runtime | 0 | `9 passed` |
| ASR streaming, первая попытка | `asr_primary_probe.py --stage streaming` с только `ctranslate2.libs` | 1 | Category 3: внешний CUDA `libcublas.so.12` не найден; raw output в `target-20260904-r1` |
| ASR streaming, corrective retry | `asr_primary_probe.py --stage streaming`, patched C2 env и `nvidia/{cublas,cuda_nvrtc,cudnn}/lib` в `LD_LIBRARY_PATH` | 0 | Partial 1/2/3/4 s, authoritative final, `model_load=9.365 s`, `final=0.350 s` |
| ASR cancellation | `asr_primary_probe.py --stage cancellation` с тем же target env | 0 | Generator close, 0 post-close items, stale not accepted |
| Application PCMU boundary, первая попытка | `map005_speech_probe.py` до фиксов runner | 1 | Category 2: при `-I` не найден `asr_primary_probe`; затем serialization gap `AsrHypothesis.as_dict` |
| Application PCMU boundary, corrective retry | `map005_speech_probe.py` после добавления paths и explicit serializers | 0 | `status=pass`, 253 frames, 3 ASR chunks, 1 final turn, 300/500 ms endpoints |
| Full target regression | `python -m pytest -q tests/unit tests/contract tests/integration` | 0 | `141 passed, 2 skipped` |
| Registry | `python tools/check_document_registry.py` | 0 | `actual=45 registry_rows=45 ... PASS` |
| Backlog | `python tools/check_task_backlog.py` | 0 | `rows=8 unique_ids=8 ... PASS` |

Для ASR target-команд использовался executable `/home/sipbot/.local/c2-faster-whisper-1.2.1t/bin/python`; для
регression и детерминированной матрицы — `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`. Полные JSON и raw
командные параметры сохранены в каталогах `target-20260904-r1`, `target-20260904-r2` и `target-20260904-r4`.
