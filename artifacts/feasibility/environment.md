# Environment inventory — 2026-08-26

Статус: `environment baseline partial; user provisioning resolved`

Время фиксации: 2026-08-26, Europe/Moscow.  
Рабочий каталог: C:\devel\sip-bot.

## Выполненные проверки

| Проверка | Команда | Результат |
|---|---|---|
| WSL status | wsl.exe --status | WSL 2 доступен; default distro ранее отсутствовала как пользовательская Linux-среда |
| WSL inventory | wsl.exe --list --verbose | docker-desktop и Ubuntu-24.04, обе WSL version 2; обе остановлены на момент проверки |
| Ubuntu availability | wsl.exe --list --online | Ubuntu-24.04 доступна для установки |
| Ubuntu installation | wsl.exe --install --distribution Ubuntu-24.04 --no-launch | exit 0; дистрибутив создан |
| Ubuntu root probe | wsl.exe -d Ubuntu-24.04 -u root -- bash -lc "cat /etc/os-release; id" | Ubuntu 24.04.4 LTS, uid=0(root), systemd включён в /etc/wsl.conf |
| Ubuntu user probe | wsl.exe -d Ubuntu-24.04 -- id -u | default user sipbot, uid 1000 |
| Sudo probe | wsl.exe -d Ubuntu-24.04 -- bash -lc "printf ... | sudo -S -k -p '' id -u" | exit 0; standard passworded sudo resolves to uid 0; non-interactive sudo without password exits 1 |
| Credential exclusion | git check-ignore -v .local/wsl-ubuntu-credentials.txt | exit 0; .local/ исключён корневым .gitignore |
| Docker | docker version | Docker Desktop 4.85.0, Engine 29.6.2, Linux/amd64 server |
| GPU | nvidia-smi | RTX 5060 Ti, 16311 MiB; на момент проверки занято 4298 MiB |
| Disk | Get-PSDrive C | Свободно 107210481664 bytes на C: |
| Worktree | git status --short | До появления кода есть пользовательские .idea/.codex изменения; их write-set не смешивать |

## Обнаруженный и закрытый blocker

Первичная интерактивная настройка Ubuntu была остановлена на запросе пароля после ввода имени пользователя dbori.
Вместо продолжения незавершённой интерактивной процедуры root-процедурой WSL создан локальный пользователь sipbot,
добавленный в группу sudo; default user задан в /etc/wsl.conf. Вход и sudo проверены отдельными командами.

Blocker среза 6.2 Environment закрыт. Это не требует смены архитектуры на Docker-only. Пароль не дублируется в
evidence; его локальная запись находится под .local/ и исключена из Git.

## Не утверждается этим evidence

- CPython 3.14.7t ещё не установлен и не проверен;
- доступность CUDA из Ubuntu ещё не проверена;
- SIP/media, ASR, LLM и TTS ещё не запускались;
- environment gate ещё не закрыт полностью: CPython/free-threaded runtime, CUDA из Ubuntu и системные зависимости не
  проверены.
