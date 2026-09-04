# 001-C4 TTS primary — preparatory preflight

Дата preflight: `2026-08-27T16:43:22.8077403+03:00`
Статус: `подготовительная execution stage; C4 не закрыт`

## Ограничение execution stage

В этой stage не выполнялись TTS generation, загрузка модели/voice asset, GPU inference,
VRAM benchmark, PCMU conversion и cancellation operation. Файл
`tts-sample.wav` намеренно не создавался: он может появиться только из разрешённого
успешного TTS operation.

## Dirty-worktree snapshot до изменений

Снимок получен до создания C4 evidence/probe-файлов. Все перечисленные изменения считаются
pre-existing и не присваиваются этому execution stage:

```text
A  .idea/.gitignore
A  .idea/inspectionProfiles/profiles_settings.xml
A  .idea/modules.xml
AM .idea/sip-bot.iml
A  .idea/vcs.xml
?? .codex/
?? .gitignore
?? .idea/deployment.xml
?? .idea/misc.xml
?? artifacts/
?? docs/
?? tools/
```

До начала stage `git diff --stat` показывал только pre-existing изменение:

```text
 .idea/sip-bot.iml | 6 ++++--
 1 file changed, 4 insertions(+), 2 deletions(-)
```

## Runtime baseline

| Поле | Наблюдение |
|---|---|
| WSL distribution | `Ubuntu-24.04` |
| Python | `3.14.7` |
| Build | `3.14.7 free-threading build`, GCC 13.3.0 |
| Executable | `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` |
| SOABI | `cpython-314t-x86_64-linux-gnu` |
| `Py_GIL_DISABLED` | `1` |
| `sys._is_gil_enabled()` | `False` |
| Installed packages | `pip==26.2.1`, `pjsua2==2.17`, `setuptools==84.0.0` |

Runtime preflight подтверждает baseline для дальнейшей проверки, но не подтверждает совместимость
TTS-кандидата: candidate package в этом окружении не установлен.

## Local candidate/asset discovery

Проверены только имена локальных каталогов и файлов под `/home/sipbot` с глубиной поиска до 6/7.
Каталоги/файлы с именами `tts`, `voice`, `piper`, `coqui`, `silero`, `kokoro`, `vits` и типами
моделей `.onnx`, `.safetensors`, `.pt`, `.pth`, `.bin` не обнаружены (кроме служебных
`distutils-precedence.pth`, не являющихся TTS asset).

Следствие: candidate-specific import и operation пока нельзя выполнить воспроизводимо. Это
фиксируется как `B-C4-001`/`B-C4-007`, а не обходится установкой пакетов, скачиванием весов,
voice asset или выбором fallback.

## Состояние обязательного sample

| Проверка | Результат |
|---|---|
| `artifacts/feasibility/001-C4-tts-primary/tts-sample.wav` до stage | отсутствует |
| Искусственный WAV создан | нет |
| Реальный TTS operation выполнен | нет |
| Что должно создать файл | только успешный разрешённый C4-S2 operation |

