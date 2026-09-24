# Мастер-класс: FreeSWITCH call-center в Debian WSL

Этот технический runbook сохраняет проверенный однолинейный сценарий Map-011 на 21.09.2026. Сценарий **выступления с ручным разбором двух очередей** и актуального учебного конфига — [freeswitch-callcenter-masterclass.md](freeswitch-callcenter-masterclass.md); не подменяйте им исторический результат Map-011.

Статус: `verified — technical clean repeat and owner audio confirmation`  
Проверено: `2026-09-21`  
Целевая схема: Windows 11 + WSL2 Debian 12 Bookworm + FreeSWITCH + два MicroSIP 3.22.16.

Этот документ самодостаточен: исполнитель не должен искать контекст в истории чата. Он устанавливает обычные пакеты и
использует штатные WSL, apt, systemd, FreeSWITCH и MicroSIP. Docker, существующие WSL-дистрибутивы, исходный код
FreeSWITCH и глобальный `.wslconfig` не трогаются.

## 1. Что получится

- отдельный WSL2-дистрибутив `Debian-Bookworm-FS` на Debian 12;
- FreeSWITCH из зеркала, указанного владельцем из закреплённого сообщения `@ru_freeswitch`;
- штатный `freeswitch.service`, запускающийся при старте дистрибутива;
- два локальных MicroSIP: caller `1000` и agent `1001`;
- прямой вызов `1000 → 1001`;
- очередь `7000 → support@default → callback-agent 1001`.

Ограничение WSL: включённый systemd-unit запускается при старте самого дистрибутива, но не запускает WSL при загрузке
Windows и не обязан удерживать дистрибутив работающим после закрытия последнего WSL-процесса. Во время мастер-класса
оставьте окно Debian открытым.

## 2. Предварительные условия и stop conditions

Нужно не менее 20 GiB свободного места, Windows x64, WSL2 и PowerShell. Команды выполняются из корня клона `sip-bot`,
если прямо не указано иное. Минимальная WSL для systemd — `0.67.6`; проверенный стенд использует WSL `2.6.2.0`.
Если версия ниже, сначала выполните `wsl --update` и перезапустите Windows.

```powershell
wsl --version
wsl --list --verbose
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw "This tested workshop path requires Windows x64/AMD64"
}
$FileSystemDrives = Get-PSDrive -PSProvider FileSystem
$FileSystemDrives | Select-Object Name,@{Name='FreeGiB';Expression={[math]::Round($_.Free / 1GB, 1)}}
```

Остановиться, если:

- имя `Debian-Bookworm-FS` уже занято неизвестным дистрибутивом;
- контрольная сумма rootfs отличается;
- apt не подтверждает подпись репозитория;
- потребовались `trusted=yes`, отключение проверки подписи, port-forward daemon или изменение `.wslconfig`;
- нет 20 GiB свободного места.

## 3. Установка Debian 12 Bookworm в WSL2

В актуальном каталоге WSL имя `Debian` может означать более новый выпуск, а предоставленное зеркало явно перечисляет
Bookworm. Поэтому проверенный сценарий импортирует зафиксированный официальный Debian rootfs стандартной командой
`wsl --import`.

```powershell
$Distro = 'Debian-Bookworm-FS'
$CandidateDrives = foreach ($DriveName in 'D','C') {
    if (Test-Path -LiteralPath "${DriveName}:\") {
        Get-PSDrive -Name $DriveName
    }
}
$TargetDriveInfo = $CandidateDrives | Where-Object { $_.Free -ge 20GB } | Select-Object -First 1
if (-not $TargetDriveInfo) {
    throw 'Neither D: nor C: has the required 20 GiB free'
}
$TargetDrive = "$($TargetDriveInfo.Name):"
$WslBase = Join-Path $TargetDrive 'WSL'
$ImageDir = Join-Path $WslBase 'images'
$InstallDir = Join-Path $WslBase 'Debian-Bookworm'
$Rootfs = Join-Path $ImageDir 'debian-bookworm-12.15-8f962b15-rootfs.tar.gz'
$RootfsUrl = 'https://raw.githubusercontent.com/debuerreotype/docker-debian-artifacts/8f962b15d7884a90e17876a9303cbac909d119aa/bookworm/oci/blobs/rootfs.tar.gz'
$ExpectedRootfsHash = 'EAAC70C68ABDF6FFACF6DE10D31ED9DE4813505D1A794EB7393CB27FCEB624A6'

if (wsl --list --quiet | Where-Object { ($_ -replace "`0", '').Trim() -eq $Distro }) {
    throw "WSL distribution '$Distro' already exists"
}

New-Item -ItemType Directory -Force -Path $ImageDir,$InstallDir | Out-Null
Invoke-WebRequest -Uri $RootfsUrl -OutFile $Rootfs
$ActualRootfsHash = (Get-FileHash -LiteralPath $Rootfs -Algorithm SHA256).Hash
if ($ActualRootfsHash -ne $ExpectedRootfsHash) {
    throw "Rootfs SHA-256 mismatch: $ActualRootfsHash"
}
```

Ожидаемый SHA-256:

```text
EAAC70C68ABDF6FFACF6DE10D31ED9DE4813505D1A794EB7393CB27FCEB624A6
```

```powershell
wsl --import $Distro $InstallDir $Rootfs --version 2
wsl -d $Distro -u root -- cat /etc/os-release
```

Ожидаются `VERSION_ID="12"` и `VERSION_CODENAME=bookworm`.

Откройте root-shell:

```powershell
wsl -d $Distro -u root
```

В Debian установите базовые пакеты, создайте обычного пользователя и задайте ему локальный пароль интерактивно.
`adduser` после пароля также спросит необязательные сведения о пользователе: их можно оставить пустыми клавишей Enter,
после чего подтвердить итоговый ответ `Y`.

```bash
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  systemd systemd-sysv sudo dbus-user-session ca-certificates curl gnupg locales procps iproute2 kmod
adduser sipbot
usermod -aG sudo sipbot
printf '[boot]\nsystemd=true\n\n[user]\ndefault=sipbot\n' > /etc/wsl.conf
exit
```

Вернитесь в PowerShell:

```powershell
wsl --terminate $Distro
wsl -d $Distro -- bash -lc 'whoami; ps -p 1 -o comm='
```

Ожидается пользователь `sipbot` и PID 1 `systemd`.

## 4. Репозиторий и пакеты FreeSWITCH

Владелец передал текст закреплённого сообщения `@ru_freeswitch`:

```text
deb http://fi.itlnk.ru/freeswitch buster main
deb http://fi.itlnk.ru/freeswitch bullseye main
deb http://fi.itlnk.ru/freeswitch bookworm main
```

У зеркала намеренно нет web-autoindex; ошибка при открытии корня в браузере не означает недоступность apt-репозитория.
Проверенный signing key:

```text
655D A134 1B52 0791 5210 AFE9 36B4 249F A7B0 FB03
FreeSWITCH Packaging Key <freeswitch@signalwire.com>
```

Снова откройте root-shell Debian из PowerShell:

```powershell
$Distro = 'Debian-Bookworm-FS'
wsl -d $Distro -u root
```

Затем выполните в Debian:

```bash
curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x36B4249FA7B0FB03' \
  -o /tmp/freeswitch-packaging.asc
expected_fingerprint='655DA1341B5207915210AFE936B4249FA7B0FB03'
actual_fingerprint="$(gpg --show-keys --with-colons /tmp/freeswitch-packaging.asc | awk -F: '$1 == "fpr" { print $10; exit }')"
if [ "$actual_fingerprint" != "$expected_fingerprint" ]; then
  echo "Signing-key fingerprint mismatch: $actual_fingerprint" >&2
  exit 1
fi
gpg --dearmor --yes --output /usr/share/keyrings/freeswitch-packaging.gpg \
  /tmp/freeswitch-packaging.asc
printf '%s\n' \
  'deb [signed-by=/usr/share/keyrings/freeswitch-packaging.gpg] http://fi.itlnk.ru/freeswitch bookworm main' \
  > /etc/apt/sources.list.d/freeswitch.list
apt-get update
apt-cache policy freeswitch freeswitch-mod-callcenter
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  freeswitch-meta-vanilla freeswitch-mod-callcenter freeswitch-systemd
systemctl enable --now freeswitch
exit
```

На `2026-09-21` проверенная версия-кандидат:

```text
1.11.3-release-33213556856-ef32e20529~bookworm~amd64-1~bookworm+1
```

Настройте учебный пароль, очередь и dialplan проектным идемпотентным скриптом. В PowerShell из корня проекта:

```powershell
$Distro = 'Debian-Bookworm-FS'
$ProjectWin = (Get-Location).Path -replace '\\','/'
$ProjectLinux = (wsl -d $Distro -u root -- wslpath -a $ProjectWin).Trim()
wsl -d $Distro -u root -- bash "$ProjectLinux/tools/workshops/configure_freeswitch_workshop.sh"
```

Скрипт включает существующий `mod_callcenter`, устанавливает только конфигурации из
`config/workshops/freeswitch/`, меняет опасный vanilla-пароль `1234` на публичный лабораторный
`Workshop-2026!` и перезапускает штатный unit. Этот пароль нельзя использовать вне изолированного стенда.

Проверка:

```powershell
wsl -d $Distro -u root -- systemctl is-enabled freeswitch
wsl -d $Distro -u root -- systemctl is-active freeswitch
wsl -d $Distro -u root -- fs_cli -x status
wsl -d $Distro -u root -- fs_cli -x "module_exists mod_callcenter"
wsl -d $Distro -u root -- fs_cli -x "callcenter_config queue list"
wsl -d $Distro -u root -- fs_cli -x "callcenter_config agent list"
wsl -d $Distro -u root -- fs_cli -x "callcenter_config tier list"
```

Ожидаются `enabled`, `active`, `true`, очередь `support@default`, агент `1001@default` со статусом `Available` и
tier `Ready`.

## 5. Два MicroSIP

Скачайте официальный portable MicroSIP и создайте две отдельные копии:

```powershell
$Url = 'https://www.microsip.org/download/MicroSIP-3.22.16.zip'
$Archive = Join-Path $env:TEMP 'MicroSIP-3.22.16.zip'
$Extracted = Join-Path $env:TEMP 'MicroSIP-3.22.16-workshop'
$Root = Join-Path $env:LOCALAPPDATA 'Programs\MicroSIP-Workshop'
$ExpectedArchiveHash = 'B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4'

Invoke-WebRequest -Uri $Url -OutFile $Archive
$ActualArchiveHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
if ($ActualArchiveHash -ne $ExpectedArchiveHash) {
    throw "MicroSIP archive SHA-256 mismatch: $ActualArchiveHash"
}
Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted -Force
$Exe = Get-ChildItem -LiteralPath $Extracted -Recurse -Filter MicroSIP.exe | Select-Object -First 1
foreach ($Name in 'Caller-1000','Agent-1001') {
    $Target = Join-Path $Root $Name
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Copy-Item -LiteralPath $Exe.FullName -Destination (Join-Path $Target 'MicroSIP.exe') -Force
}
```

Ожидаемый SHA-256 архива:

```text
B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4
```

Сгенерируйте два штатных INI-профиля с текущим WSL IP и запустите оба клиента:

```powershell
$Distro = 'Debian-Bookworm-FS'
$Caller = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Caller-1000\MicroSIP.exe"
$Agent = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Agent-1001\MicroSIP.exe"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\workshops\prepare_freeswitch_microsip.ps1
if ($LASTEXITCODE -ne 0) { throw 'MicroSIP profile preparation failed' }
Start-Process -FilePath $Caller -WorkingDirectory (Split-Path $Caller)
Start-Process -FilePath $Agent -WorkingDirectory (Split-Path $Agent)
```

`ExecutionPolicy Bypass` действует только в дочернем процессе, запускающем проверенный локальный script, и не меняет
machine/user policy. Перед перезаписью INI helper принудительно завершает только процессы MicroSIP из двух workshop
каталогов. Не запускайте его во время разговора; сначала завершите оба звонка.

Профили используют отдельные SIP-порты `5062`/`5064`, RTP-диапазоны `40000–40100`/`40200–40300`, UDP и только
PCMU. MicroSIP при первом успешном запуске может переписать пароль в INI в собственном зашифрованном формате — это
штатно.

Проверка регистрации:

```powershell
$Distro = 'Debian-Bookworm-FS'
wsl -d $Distro -u root -- fs_cli -x "sofia status profile internal reg"
```

Должны присутствовать `1000` и `1001` с `Registered`/`Reachable`.

## 6. Прямой вызов

В PowerShell:

```powershell
$Distro = 'Debian-Bookworm-FS'
$Caller = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Caller-1000\MicroSIP.exe"
$Agent = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Agent-1001\MicroSIP.exe"
& $Caller 1001
```

У `Agent-1001` должен появиться входящий вызов. Ответьте кнопкой в GUI либо документированной командой:

```powershell
& $Agent /answer
wsl -d $Distro -u root -- fs_cli -x "show channels"
```

Ожидаются два `ACTIVE`-канала и `PCMU,8000,64000` в read/write codec. Произнесите короткую фразу и подтвердите звук.
На одном компьютере возможна акустическая обратная связь; используйте гарнитуру, небольшую громкость и mute/unmute.
Завершите вызов в GUI. Для аварийной очистки только учебного однозвонкового стенда:

```powershell
wsl -d $Distro -u root -- fs_cli -x "hupall"
```

## 7. Очередь call-center

Позвоните с caller на `7000`:

```powershell
$Distro = 'Debian-Bookworm-FS'
$Caller = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Caller-1000\MicroSIP.exe"
$Agent = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Agent-1001\MicroSIP.exe"
& $Caller 7000
Start-Sleep -Seconds 2
wsl -d $Distro -u root -- fs_cli -x "callcenter_config queue list members support@default"
wsl -d $Distro -u root -- fs_cli -x "callcenter_config agent list 1001@default"
wsl -d $Distro -u root -- fs_cli -x "show channels"
```

До ответа ожидаются member `Trying`, agent `Receiving`, входящий канал caller `ACTIVE` и исходящий канал agent
`RINGING`. Ответьте на agent:

```powershell
& $Agent /answer
Start-Sleep -Seconds 2
wsl -d $Distro -u root -- fs_cli -x "callcenter_config queue list members support@default"
wsl -d $Distro -u root -- fs_cli -x "callcenter_config agent list 1001@default"
wsl -d $Distro -u root -- fs_cli -x "show channels"
```

После ответа ожидаются member `Answered`, agent `In a queue call`, два `ACTIVE`-канала и PCMU в обе стороны.
Caller до ответа должен слышать hold music. Подтвердите голос в обе стороны и завершите вызов.

Если агент мгновенно становится `On Break`, смотрите FreeSWITCH log. Ошибка `Can't find user [1001@default]` означает,
что в contact ошибочно использован литерал `default`; проверенный конфиг использует
`user/1001@$${domain}`, который при загрузке разворачивается в текущий WSL IP.

## 8. Проверка после чистого старта

Закройте оба MicroSIP, оставьте проект на месте и выполните:

```powershell
$Distro = 'Debian-Bookworm-FS'
$Caller = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Caller-1000\MicroSIP.exe"
$Agent = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop\Agent-1001\MicroSIP.exe"
wsl --terminate $Distro
wsl -d $Distro -- bash -lc 'ps -p 1 -o comm=; systemctl is-enabled freeswitch; systemctl is-active freeswitch'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\workshops\prepare_freeswitch_microsip.ps1
if ($LASTEXITCODE -ne 0) { throw 'MicroSIP profile preparation failed' }
Start-Process -FilePath $Caller -WorkingDirectory (Split-Path $Caller)
Start-Process -FilePath $Agent -WorkingDirectory (Split-Path $Agent)
```

Повторите разделы 6 и 7. Проверенный прогон после restart сохранил service/module/queue configuration и снова дал
два зарегистрированных endpoint, прямой bridge и queue bridge.

## 9. Диагностика

```powershell
$Distro = 'Debian-Bookworm-FS'
wsl -d $Distro -u root -- journalctl -u freeswitch -b --no-pager -n 200
wsl -d $Distro -u root -- tail -n 200 /var/log/freeswitch/freeswitch.log
wsl -d $Distro -u root -- fs_cli -x "sofia status profile internal reg"
wsl -d $Distro -u root -- fs_cli -x "show channels"
wsl -d $Distro -u root -- fs_cli -x "callcenter_config queue list members support@default"
```

Vanilla `modules.conf.xml` может ссылаться на необязательные модули, не установленные meta-package, и оставить CRIT-строки
об отсутствующих `.so`. Для этого мастер-класса критичны active service, `mod_sofia`, `mod_callcenter`, PCMU и успешные
вызовы; не устанавливайте большой multimedia stack и не редактируйте список модулей только ради очистки нерелевантных
warning-строк.

## 10. Что подтверждено и что должен проверить человек

Автоматически подтверждены installation provenance, systemd restart, две регистрации, прямой SIP bridge, queue
member/agent transitions, два ACTIVE channel и PCMU/8 kHz/64 kbit/s в обе стороны. Владелец 2026-09-21 подтвердил,
что во время live bridge слышал собственный голос, а final queue probe акустически прошёл в описанном порядке: период
ожидания, ответ и голосовой тракт. В новом окружении ведущий всё равно повторяет ручную проверку hold music и голоса:
её нельзя заменять успешным exit code CLI.
