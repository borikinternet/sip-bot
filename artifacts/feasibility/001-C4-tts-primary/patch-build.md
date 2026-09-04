# 001-C4 TTS primary — no-GIL patch build record

## Назначение

Этот файл фиксирует обязательную candidate-specific подготовку runtime для проверенного main-process пути XTTS-v2
под free-threaded CPython. Патчи не являются общим разрешением на использование непатченных wheel-файлов и не
переносят production ownership в feasibility probe.

## Исходники

| Компонент | Версия | Источник/ревизия | Изменение |
|---|---|---|---|
| `torchaudio` | `2.10.0` | git tag `v2.10.0`, commit `27b7ebdebd2d2e4d34a2f5c05b0fb26efbd1da63` | `_torchaudio` объявлен через `pybind11::mod_gil_not_used()` |
| `tokenizers` | `0.22.2` | git tag `v0.22.2`, commit `f383101a26663708484cac0727792aad74f78234` | `#[pymodule(gil_used = false)]` |
| `monotonic_alignment_search` | `0.2.1` | установленный generated `core.c` | module slot изменён на `Py_MOD_GIL_NOT_USED` |

## Патчи и контрольные суммы

| Файл | SHA-256 |
|---|---|
| `torchaudio-free-threading.patch` | `50f34731f5c539944f37d91534aeea5b966af87aedb8e44cf62b4264d2057706` |
| `tokenizers-free-threading.patch` | `a5e511cfa89ad0b8f085363be9bfffa4a8b7f68abc23f71adf464d54de1c63dc` |
| `monotonic-alignment-search-free-threading.patch` | `7d10a98959179c8f5c92a01736a824d3b27a8d26161f3a9af68fdf3152c5d4d7` |

Проверенные бинарные результаты:

| Бинарный модуль | SHA-256 |
|---|---|
| `torchaudio/_torchaudio.so` | `4dafd1cfa260a962659af100be400547f6cfaa1f0618a25996f6d6b2ebb49bd8` |
| `tokenizers/tokenizers.abi3.so` | `9c425d835732cdde613f7c75f3c3d3e46d6a7493df0f2f25847964d5b68e0e64` |
| `monotonic_alignment_search/core.cpython-314t-x86_64-linux-gnu.so` | `f01ce91a99f1c7c449535d63f33f3e5c41a09092e8cf5afb75206931f6cc0c20` |

## Сборка и установка

Сборка выполнялась в disposable runtime `CPython 3.14.7t` под Ubuntu 24.04 WSL2. GPU inference во время сборки не
выполнялся.

`torchaudio`: после применения патча исходника `_torchaudio.cpp` модуль собран вручную с теми же Torch/torchaudio
include/library путями, затем patched `_torchaudio.so` установлен поверх модуля в C4 virtual environment. Исходный
бинарь сохранён вне репозитория как `torchaudio-original-_torchaudio.so`.

`tokenizers`: после применения патча выполнена сборка wheel через maturin и установлен wheel для
`cp314-cp314t`:

```text
cd /home/sipbot/.cache/sip-bot-c4-build/tokenizers-v0.22.2
maturin build --release --interpreter /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pip install --force-reinstall --no-deps <built-tokenizers-wheel>
```

`monotonic_alignment_search`: patched generated `core.c` перекомпилирован в
`core.cpython-314t-x86_64-linux-gnu.so` с include-путями target CPython и установлен поверх исходного extension.
Исходный бинарь сохранён вне репозитория как `monotonic-original.so`.

## Runtime-ограничения

- В disposable C4 runtime каталог optional `triton` переименован в `triton.disabled`: широкий импорт `triton._C.libtriton`
  включал GIL, а проверенная XTTS operation Triton не требует.
- `torchcodec` не входит в tested operation path: его `libtorchcodec_image.so` требовал `libnvrtc.so.13`; reference
  voice загружается через `soundfile`, resampling выполняет patched `torchaudio`.
- Повторение C4 считается воспроизводимым только при тех же патчах либо при новом evidence, доказывающем эквивалентную
  no-GIL сборку. Установка исходных непатченных wheels не является успешным повторением.
