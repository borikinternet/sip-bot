# 007-A: зафиксированный результат до corrective patch

Дата: `2026-09-13`  
Компонент: `webrtcvad-wheels 2.0.14`, native `_webrtcvad`  
Target: CPython 3.14.7t / Ubuntu 24.04 WSL2

Непатчированная сборка импортировалась как `cp314t`, но не объявляла no-GIL-безопасность. При чистом target import
CPython вывел предупреждение:

```text
RuntimeWarning: The global interpreter lock (GIL) has been enabled to load module '_webrtcvad', which has not declared that it can run safely without the GIL.
```

После import и создания `webrtcvad.Vad` значение `sys._is_gil_enabled()` оставалось `True`. Результат классифицирован
как фактическая native compatibility issue внутри утверждённого `007-A` write-set. Автоматический fallback на
`_AmplitudeVad` и переход на GIL-enabled runtime не применялись.

Корректирующее действие: добавлен [`webrtcvad-wheels-2.0.14-free-threading.patch`](../../../../patches/webrtcvad-wheels-2.0.14-free-threading.patch), объявляющий single-phase module через `PyUnstable_Module_SetGIL(module, Py_MOD_GIL_NOT_USED)`. После пересборки и повторной проверки GIL остаётся выключенным.
