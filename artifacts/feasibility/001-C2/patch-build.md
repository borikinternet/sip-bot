# C2 CTranslate2 free-threading patch/build evidence

Дата: 2026-08-27

## Назначение

Подготовлен узкий локальный patch для `ctranslate2==4.8.1`: Python-модуль `_ext`
декларирует поддержку работы без GIL через pybind11 module marker. Патч не
изменяет алгоритмы CTranslate2 и не является доказательством потокобезопасности
всех операций; operation/no-GIL и cancellation gates остаются обязательными
GPU/operation проверками.

## Точная база и patch

- Upstream repository: `https://github.com/OpenNMT/CTranslate2`.
- Source tag: `v4.8.1`.
- Source commit used for build: `0d8bcd362ac75ef860ef161d6f0efad0ae439ff0`.
- Source checkout: `/home/sipbot/.local/build/ctranslate2-v4.8.1`.
- Patch artifact: `artifacts/feasibility/001-C2/ctranslate2-free-threading.patch`.
- Patch SHA-256: `6c118e2707adf715bdccd3b74f772490373927f455a25a857b991160d73ed619`.
- Patch application: `git apply --check` passed; `git diff --check` passed.
- Changed source line: `python/cpp/module.cc`,
  `PYBIND11_MODULE(_ext, m)` →
  `PYBIND11_MODULE(_ext, m, py::mod_gil_not_used())`.

## Build

Build tooling was installed in the disposable preparation environment:

- CMake `4.4.2`;
- Ninja `1.13.0`;
- pybind11 `2.13.6`.

The Python binding was rebuilt from the patched source against the exact native
library from the original `ctranslate2==4.8.1` wheel. Native CTranslate2 was not
rebuilt in this restricted stage; consequently the GPU-capable native library
and CUDA compatibility still come from the pinned original wheel.

Build command:

```bash
cd /home/sipbot/.local/build/ctranslate2-v4.8.1/python
CMAKE_BUILD_PARALLEL_LEVEL=4 \
CTRANSLATE2_ROOT=/home/sipbot/.local/build/ctranslate2-link \
/home/sipbot/.local/c2-faster-whisper-1.2.1t/bin/python \
  -m pip wheel --no-build-isolation --no-deps --no-cache-dir . \
  --wheel-dir /home/sipbot/.local/build/ctranslate2-patched-wheel
```

Build output:

- Wheel: `/home/sipbot/.local/build/ctranslate2-patched-wheel/ctranslate2-4.8.1-cp314-cp314t-linux_x86_64.whl`.
- Wheel SHA-256: `2daac26a165060fcb8b8bf4d712cb3cd135c416eb17aa79a2713ea702528e4c7`.
- Installed extension:
  `/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2/_ext.cpython-314t-x86_64-linux-gnu.so`.
- Installed extension SHA-256:
  `1bd716e70b94274e8d91d1160d7e0a565f889f57f01aea9beb8d27d1a3b16e9a`.
- Native library retained from original wheel:
  `libctranslate2-23004c3b.so.4.8.1`.
- Native library SHA-256:
  `9f7b42a6119711f7ac262a6ac47d24d316314f95c9befd7009985df134d224f1`.
- Original unpatched extension SHA-256:
  `a141a20ad4abf5a225595811a969b418107a3dff3438f485c203a394d3531b59`.

The patched installation requires this runtime library path:

```bash
export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs
```

## No-GIL import gate

Baseline: CPython `3.14.7t`, `Py_GIL_DISABLED=1`, Ubuntu 24.04/WSL2.

- Before patch: `ctranslate2._ext` re-enabled the GIL and emitted the official
  free-threading `RuntimeWarning`; see `import-no-gil-before-patch.json`.
- After patch: `import-no-gil.json` passed in fresh child processes for
  `numpy`, `yaml`, `ctranslate2`, `onnxruntime`, `av`, `tokenizers`,
  `faster_whisper`, `faster_whisper.transcribe` and `faster_whisper.vad`.
  Every recorded `gil_before` and `gil_after` value is `false`, with no warnings
  or import errors.

This closes the import-level symptom for the prepared environment only. It does
not yet close the operation-level gate: model load, inference, cancellation and
GPU runtime compatibility must be tested by the parent executor.

## Explicit restricted-stage boundary

No CTranslate2 model was loaded. No GPU inference and no benchmark were run.
No fallback candidate or process-isolation alternative was selected.
