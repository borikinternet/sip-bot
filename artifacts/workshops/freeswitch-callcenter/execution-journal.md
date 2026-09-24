# Журнал исполнения Map-011: FreeSWITCH и два MicroSIP

Период: 20–21 сентября 2026 года. Статус исходной карты: `complete`.

Это реконструкция последовательности по сохранённым отчётам `011-A`–`011-D` и проверенному [runbook](../../../docs/workshops/freeswitch-callcenter-runbook.md), а не сырая запись терминала. У нас нет полного stdout каждой исторической команды и её точного времени. Команды ниже — проверенный способ повторить соответствующий этап; наблюдённые результаты приведены отдельно. Для исполнения без контекста используйте runbook, где есть полные параметры, проверки ошибок и условия остановки.

## 20.09: подготовка MicroSIP до SIP-проверок

**Где:** Windows PowerShell. **Зачем:** установить, можно ли штатно запустить два независимых SIP-клиента.

```powershell
$Url = 'https://www.microsip.org/download/MicroSIP-3.22.16.zip'
$Archive = Join-Path $env:TEMP 'MicroSIP-3.22.16.zip'
Invoke-WebRequest -Uri $Url -OutFile $Archive
Get-FileHash -LiteralPath $Archive -Algorithm SHA256
Expand-Archive -LiteralPath $Archive -DestinationPath (Join-Path $env:TEMP 'MicroSIP-3.22.16-workshop')
```

После проверки SHA-256 исполняемый файл поместили в две отдельные папки `%LOCALAPPDATA%\Programs\MicroSIP-Workshop\Caller-1000` и `Agent-1001`, запустили обе копии. У каждой появился свой `MicroSIP.ini`; опубликованная команда `/exit` завершила каждый экземпляр. SHA-256 архива: `B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4`.

На этом этапе REGISTER, звонок и звук **ещё не проверялись**. Источник: [preflight.md](011-B/preflight.md).

## 21.09 / 011-A: отдельный Debian WSL и пакетный FreeSWITCH

### A1. Получение и импорт Debian

**Где:** Windows PowerShell. **Зачем:** создать отдельный Debian 12 Bookworm, подходящий к переданному владельцем Debian-репозиторию FreeSWITCH, не затрагивая Ubuntu бота и Docker.

```powershell
$Distro = 'Debian-Bookworm-FS'
$RootfsUrl = 'https://raw.githubusercontent.com/debuerreotype/docker-debian-artifacts/8f962b15d7884a90e17876a9303cbac909d119aa/bookworm/oci/blobs/rootfs.tar.gz'
Invoke-WebRequest -Uri $RootfsUrl -OutFile $Rootfs
Get-FileHash -LiteralPath $Rootfs -Algorithm SHA256
wsl --import $Distro $InstallDir $Rootfs --version 2
wsl -d $Distro -u root -- cat /etc/os-release
```

`$Rootfs` и `$InstallDir` выбирались после проверки свободных ≥20 GiB; полный блок их определения находится в runbook §3. Ожидались `VERSION_ID=12`, `VERSION_CODENAME=bookworm`. Фактически импортирован `Debian-Bookworm-FS` на `D:\WSL\Debian-Bookworm`, rootfs SHA-256 `EAAC70C68ABDF6FFACF6DE10D31ED9DE4813505D1A794EB7393CB27FCEB624A6`.

### A2. Подготовка Debian и systemd

**Где:** Debian WSL root shell, открытый через `wsl -d Debian-Bookworm-FS -u root`. **Зачем:** получить штатный сервисный runtime и обычного пользователя.

```bash
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y systemd systemd-sysv sudo dbus-user-session ca-certificates curl gnupg locales procps iproute2 kmod
adduser sipbot
usermod -aG sudo sipbot
printf '[boot]\nsystemd=true\n\n[user]\ndefault=sipbot\n' > /etc/wsl.conf
```

Затем из Windows PowerShell:

```powershell
wsl --terminate Debian-Bookworm-FS
wsl -d Debian-Bookworm-FS -- bash -lc 'whoami; ps -p 1 -o comm='
```

Проверено: пользователь по умолчанию `sipbot`, PID 1 — `systemd`. В исторических отчётах пароль пользователя не сохранялся.

### A3. Подключение зеркала и установка пакетов

**Где:** Debian WSL root shell. **Зачем:** установить пакетный FreeSWITCH и `mod_callcenter` из согласованного источника, с проверкой подписи пакетов.

```bash
curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x36B4249FA7B0FB03' -o /tmp/freeswitch-packaging.asc
gpg --show-keys --with-colons /tmp/freeswitch-packaging.asc
gpg --dearmor --yes --output /usr/share/keyrings/freeswitch-packaging.gpg /tmp/freeswitch-packaging.asc
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/freeswitch-packaging.gpg] http://fi.itlnk.ru/freeswitch bookworm main' > /etc/apt/sources.list.d/freeswitch.list
apt-get update
apt-cache policy freeswitch freeswitch-mod-callcenter
DEBIAN_FRONTEND=noninteractive apt-get install -y freeswitch-meta-vanilla freeswitch-mod-callcenter freeswitch-systemd
systemctl enable --now freeswitch
```

Перед установкой fingerprint ключа был **сравнен** с `655DA1341B5207915210AFE936B4249FA7B0FB03`; одна команда просмотра ключа сама по себе этой проверки не заменяет. Подписанный `InRelease` принят `apt`; `trusted=yes` и `apt-key` не применялись. Установлена версия `1.11.3-release-33213556856-ef32e20529~bookworm~amd64-1~bookworm+1`.

### A4. Конфигурация сервиса и проверка запуска

**Где:** Windows PowerShell из корня проекта, затем Debian через `wsl`. **Зачем:** применить лабораторный пароль, отключить STUN/NAT auto mapping, включить существующий модуль и загрузить dialplan/очередь.

```powershell
$ProjectWin = (Get-Location).Path -replace '\\','/'
$ProjectLinux = (wsl -d Debian-Bookworm-FS -u root -- wslpath -a $ProjectWin).Trim()
wsl -d Debian-Bookworm-FS -u root -- bash "$ProjectLinux/tools/workshops/configure_freeswitch_workshop.sh"
wsl -d Debian-Bookworm-FS -u root -- systemctl is-enabled freeswitch
wsl -d Debian-Bookworm-FS -u root -- systemctl is-active freeswitch
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x status
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "module_exists mod_callcenter"
```

Скрипт меняет установленные `/etc/freeswitch/vars.xml` и `autoload_configs/modules.conf.xml`, устанавливает проектные `callcenter.conf.xml` и `20_workshop_callcenter.xml`, ставит systemd override `-nonat -nonatmap`, перезапускает FreeSWITCH и проверяет загруженные queue/agent/tier. После `wsl --terminate` и нового запуска зафиксировано: `enabled`, `active`, 0 failed units, `fs_cli` ready, `mod_callcenter=true`. Это автозапуск сервиса **при старте Debian WSL**, а не автозапуск дистрибутива вместе с Windows.

Фактический отчёт: [environment-and-packages.md](011-A/environment-and-packages.md).

## 21.09 / 011-B: два SIP-клиента и прямой звонок

**Где:** Windows PowerShell для MicroSIP, Debian WSL для `fs_cli`. **Зачем:** сначала доказать обычный SIP/RTP bridge без очереди.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\workshops\prepare_freeswitch_microsip.ps1
Start-Process -FilePath $Caller -WorkingDirectory (Split-Path $Caller)
Start-Process -FilePath $Agent -WorkingDirectory (Split-Path $Agent)
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "sofia status profile internal reg"
& $Caller 1001
& $Agent /answer
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "show channels"
```

`$Caller` и `$Agent` — пути к двум MicroSIP из runbook §5. Helper берёт текущий IP Debian WSL и создаёт независимые `MicroSIP.ini`: аккаунты `1000` и `1001`, SIP UDP `5062`/`5064`, раздельные RTP-диапазоны, PCMU only. После запуска оба клиента показывали `Registered` и `Reachable`.

Вызов `1000 → 1001`: перед ответом outbound leg `RINGING`, после `/answer` два канала `ACTIVE`, read/write codec `PCMU/8000/64000`; после завершения каналов 0. Владелец подтвердил слышимость собственного голоса. Фактический отчёт: [direct-call.md](011-B/direct-call.md).

## 21.09 / 011-C: очередь оператора

**Где:** установленный FreeSWITCH в Debian; вызов из Windows MicroSIP. **Зачем:** добавить проверяемое распределение вызова через `mod_callcenter`.

```powershell
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "module_exists mod_callcenter"
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "callcenter_config queue list"
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "callcenter_config agent list"
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "callcenter_config tier list"
& $Caller 7000
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "callcenter_config queue list members support@default"
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "callcenter_config agent list 1001@default"
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "show channels"
& $Agent /answer
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "callcenter_config queue list members support@default"
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "show channels"
```

На этапе исходной Map-011 проверялась очередь `support@default`: extension `7000`, стратегия `longest-idle-agent`, MOH `local_stream://moh`, callback-agent `1001@default`, tier `Ready`. Первый probe с `user/1001@default` дал `SUBSCRIBER_ABSENT` и перевёл агента в `On Break`. Контакт исправили на `user/1001@$${domain}`; затем очередь дала `Trying → Answered`, агент `Receiving → In a queue call`, два PCMU-канала `RINGING → ACTIVE`. Caller оставался в очереди пять секунд до ответа агента; владелец подтвердил слышимое ожидание и голос. Фактический отчёт: [callcenter-call.md](011-C/callcenter-call.md).

## 21.09 / 011-D: проверка после чистого старта и оформление инструкции

**Где:** Windows PowerShell и Debian WSL. **Зачем:** исключить зависимость от случайно оставшегося состояния процессов или памяти FreeSWITCH.

```powershell
wsl --terminate Debian-Bookworm-FS
wsl -d Debian-Bookworm-FS -- bash -lc 'ps -p 1 -o comm=; systemctl is-enabled freeswitch; systemctl is-active freeswitch'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\workshops\prepare_freeswitch_microsip.ps1
Start-Process -FilePath $Caller -WorkingDirectory (Split-Path $Caller)
Start-Process -FilePath $Agent -WorkingDirectory (Split-Path $Agent)
wsl -d Debian-Bookworm-FS -u root -- fs_cli -x "sofia status profile internal reg"
```

Далее повторены вызовы `1000 → 1001` и `1000 → 7000` с `show channels`, `callcenter_config ... members` до/после ответа и очисткой каждого вызова. Повтор подтвердил автозапуск FreeSWITCH, модуль, обе регистрации, прямой bridge, очередь, PCMU и ноль оставшихся каналов. Независимый агент без контекста проверил runbook после двух исправлений; итоговый verdict `PASS`. Фактический отчёт: [clean-repeat.md](011-D/clean-repeat.md).

## Что изменилось после закрытия Map-011

Проверенный на 21.09 сценарий карты имел **одну** очередь операторов `7000`. Позднее проектные [callcenter.conf.xml](../../../config/workshops/freeswitch/autoload_configs/callcenter.conf.xml) и [dialplan](../../../config/workshops/freeswitch/dialplan/default/20_workshop_callcenter.xml) получили вторую очередь `science-bot@default` с номером `7100` и агентом `1002`. На локальном Debian WSL она загружена и через неё 23.09 прошёл отдельный зарегистрированный [full-live звонок](../../implementation/018-tts-first-audio-latency/wsl-rtx5060ti-registered-live-r2/registered-j4-full-live.json): статус `pass`, PCMU/20 ms, RAG/barge-in/transfer/report, `6166/6166` egress frames, `egress_underruns=0`.

Эта поздняя проверка показывает, что в текущих файлах две очереди технически работают. Исходные acceptance и runbook Map-011 пока не описывают последовательность мастер-класса с двумя очередями и поведение при занятом односессионном боте; это отдельное изменение сценария.
