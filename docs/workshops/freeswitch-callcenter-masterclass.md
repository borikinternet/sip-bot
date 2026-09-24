# Мастер-класс: собираем колл-центр FreeSWITCH своими руками

Статус: сценарий для ведущего и участников. Основной путь — Windows 11, Debian 12 Bookworm в WSL2, FreeSWITCH и два MicroSIP. Он опирается на [проверенный технический runbook](freeswitch-callcenter-runbook.md), но показывает внутреннее устройство конфигурации, которое runbook автоматизирует. Фрагменты конфигов ниже — учебный снимок на 23.09.2026; актуальные рабочие значения принадлежат файлам в `config/workshops/freeswitch/`.

## Результат, который унесёт слушатель

К концу занятия участник сможет объяснить и повторить маршрут `абонент 1000 → FreeSWITCH → оператор 1001`, затем маршрут `1000 → очередь support@default → 1001`. Он создаст и вторую очередь `science-bot@default` для односессионного SIP-ассистента: `7100 → бот 1002`; пока бот не подключён, проверим конфигурацию очереди, а полноценный звонок через неё оставим второму мастер-классу. Участник увидит, какие строки отвечают за регистрацию, маршрутизацию, удержание, выбор агента, запись и возврат к человеку.

Планируемое время — 90 минут: 15 минут установка, 15 минут прямой SIP-звонок, 30 минут сборка двух очередей, 15 минут живые проверки и диагностика, 15 минут вопросы и связь со вторым мастер-классом. Это **план подачи**, не замеренный тайминг установки: скачивание и `apt` зависят от сети. Ведущий заранее готовит скачанный rootfs, пакеты и контрольный восстановительный снимок, но вводимые команды и редактируемые строки показывает живьём.

## 0. На доске: что именно строим

```text
MicroSIP 1000 (клиент)
       │ REGISTER / INVITE / RTP
       ▼
FreeSWITCH, internal SIP profile :5060
       ├─ 1001 ──────────────────────► MicroSIP 1001 (прямой вызов)
       ├─ 7000 → support@default ───► оператор 1001
       └─ 7100 → science-bot@default ► SIP-ассистент 1002 (подключим позже)
                                          │ transfer по решению бота
                                          └───────────────► 7000 → оператор
```

Здесь `1000/1001/1002` — SIP-учётки, `7000/7100` — номера назначения в dialplan, а `support@default`/`science-bot@default` — имена очередей `mod_callcenter`. Это разные сущности: регистрация `1002` сама по себе не направит на бота вызов `7100`.

**Ведущий спрашивает:** «Что произойдёт, если очередь есть, но номер `7100` не описан в dialplan?» Ответ проверим после редактирования: входящему вызову неоткуда узнать имя очереди.

## 1. Поднимаем Debian, совместимый с пакетами FreeSWITCH

**Где:** PowerShell Windows. **Показываем:** версия WSL, свободное место не менее 20 GiB, существующие дистрибутивы. Не импортируем поверх чужой машины.

```powershell
wsl --version
wsl --list --verbose
Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{Name='FreeGiB';Expression={[math]::Round($_.Free / 1GB,1)}}
```

Пакетное зеркало, согласованное для проекта, содержит Debian `bookworm`, но не Ubuntu `jammy`. Поэтому учебная ОС — Debian 12. На компьютере с Windows импортируем её как **отдельную** WSL-машину. Ниже для краткости место `D:\WSL`; если на D: нет 20 GiB, выберите другой подходящий диск до выполнения команд.

```powershell
$Distro = 'Debian-Bookworm-FS'
$Rootfs = 'D:\WSL\debian-bookworm-rootfs.tar.gz'
$InstallDir = 'D:\WSL\Debian-Bookworm'
$Url = 'https://raw.githubusercontent.com/debuerreotype/docker-debian-artifacts/8f962b15d7884a90e17876a9303cbac909d119aa/bookworm/oci/blobs/rootfs.tar.gz'
$Expected = 'EAAC70C68ABDF6FFACF6DE10D31ED9DE4813505D1A794EB7393CB27FCEB624A6'
if (-not (Test-Path 'D:\') -or (Get-PSDrive D).Free -lt 20GB) { throw 'Нужны D: и 20 GiB свободного места; выберите другую директорию' }
if (wsl --list --quiet | Where-Object { ($_ -replace "`0", '').Trim() -eq $Distro }) { throw 'Имя WSL уже занято' }
New-Item -ItemType Directory -Force -Path (Split-Path $Rootfs),$InstallDir | Out-Null
Invoke-WebRequest -Uri $Url -OutFile $Rootfs
if ((Get-FileHash -LiteralPath $Rootfs -Algorithm SHA256).Hash -ne $Expected) { throw 'SHA-256 rootfs не совпадает' }
wsl --import $Distro $InstallDir $Rootfs --version 2
wsl -d $Distro -u root -- cat /etc/os-release
```

Ожидаем `VERSION_ID="12"`, `VERSION_CODENAME=bookworm`. Хеш защищает от неполной или подменённой загрузки; при несовпадении **не продолжаем**.

Открываем root shell: `wsl -d Debian-Bookworm-FS -u root`. В нём:

```bash
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  systemd systemd-sysv sudo dbus-user-session ca-certificates curl gnupg \
  locales procps iproute2 kmod nano
adduser sipbot
usermod -aG sudo sipbot
nano /etc/wsl.conf
```

В `/etc/wsl.conf` вводим:

```ini
[boot]
systemd=true

[user]
default=sipbot
```

После выхода в PowerShell:

```powershell
wsl --terminate Debian-Bookworm-FS
wsl -d Debian-Bookworm-FS -- bash -lc 'whoami; ps -p 1 -o comm='
```

Ожидаем `sipbot` и `systemd`. Объясняем: `systemctl enable` впоследствии поднимет FreeSWITCH **при старте Debian WSL**, но не запустит WSL вместе с Windows. Во время занятия держим окно Debian открытым.

## 2. Устанавливаем FreeSWITCH, видя откуда пришли пакеты

**Где:** root shell Debian (`wsl -d Debian-Bookworm-FS -u root`). Ведущий показывает: web-страницы autoindex у зеркала нет, но apt читает `InRelease`/`Packages`. Репозиторий должен быть привязан к проверенному ключу; `trusted=yes` не используем.

```bash
curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x36B4249FA7B0FB03' -o /tmp/freeswitch-packaging.asc
actual="$(gpg --show-keys --with-colons /tmp/freeswitch-packaging.asc | awk -F: '$1 == "fpr" { print $10; exit }')"
test "$actual" = '655DA1341B5207915210AFE936B4249FA7B0FB03' || { echo 'Чужой ключ'; exit 1; }
gpg --dearmor --yes --output /usr/share/keyrings/freeswitch-packaging.gpg /tmp/freeswitch-packaging.asc
nano /etc/apt/sources.list.d/freeswitch.list
```

Единственная строка в новом файле:

```text
deb [signed-by=/usr/share/keyrings/freeswitch-packaging.gpg] http://fi.itlnk.ru/freeswitch bookworm main
```

```bash
apt-get update
apt-cache policy freeswitch freeswitch-mod-callcenter
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  freeswitch-meta-vanilla freeswitch-mod-callcenter freeswitch-systemd
systemctl enable --now freeswitch
systemctl is-active freeswitch
fs_cli -x status
```

Разбираем `apt-cache policy`: откуда будет взят кандидат и почему `mod_callcenter` — отдельный пакет. На проверенном стенде FreeSWITCH был `1.11.3`; в новом прогоне версия может измениться. Если установка оборвалась, не выдаём установленный бинарник за завершение: сначала `dpkg --audit`, затем разбираем ошибку. На отдельном Ubuntu-сервере первая попытка упёрлась в конфигурацию `ssmtp` — это полезный пример того, почему `fs_cli -x status` нужен после apt, а не вместо проверки apt.

## 3. Первый живой результат: два SIP-телефона без очереди

**Где:** Windows для MicroSIP; Debian для `fs_cli`. Загружаем portable MicroSIP и помещаем `MicroSIP.exe` в **две разные папки**. Это две независимые копии с собственными `MicroSIP.ini`, а не два окна одного экземпляра:

```powershell
$Url = 'https://www.microsip.org/download/MicroSIP-3.22.16.zip'
$Archive = Join-Path $env:TEMP 'MicroSIP-3.22.16.zip'
$Extracted = Join-Path $env:TEMP 'MicroSIP-3.22.16-workshop'
$ClientRoot = Join-Path $env:LOCALAPPDATA 'Programs\MicroSIP-Workshop'
$Expected = 'B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4'
Invoke-WebRequest -Uri $Url -OutFile $Archive
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $Expected) { throw 'SHA-256 MicroSIP не совпадает' }
Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted -Force
$Exe = Get-ChildItem -LiteralPath $Extracted -Recurse -Filter MicroSIP.exe | Select-Object -First 1
foreach ($Name in 'Caller-1000','Agent-1001') {
    $Target = Join-Path $ClientRoot $Name
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Copy-Item -LiteralPath $Exe.FullName -Destination (Join-Path $Target 'MicroSIP.exe') -Force
}
```

Получаем адрес Debian: в PowerShell `wsl -d Debian-Bookworm-FS -- hostname -I`. В обеих копиях MicroSIP создаём аккаунты вручную через «Добавить аккаунт» и сетевые настройки либо редактируем независимые INI **при закрытых приложениях**:

| Параметр | Клиент | Оператор | Зачем |
|---|---|---|---|
| SIP user / auth ID | `1000` | `1001` | Идентичность для REGISTER |
| Domain / SIP server | IPv4 Debian WSL, порт `5060` | тот же | Оба разговаривают с одной АТС |
| Password | `Workshop-2026!` после изменения `default_password` ниже | тот же | Учебный пароль, не для реальной сети |
| Transport | UDP | UDP | Соответствует стенду |
| Local SIP port | `5062` | `5064` | Две копии не спорят за один порт |
| RTP ports | `40000–40100` | `40200–40300` | Раздельные диапазоны звука |
| Audio codec | PCMU/8000 | PCMU/8000 | Совместим с ботом и проверкой |

Если параметры удобнее видеть как файл, ключевая часть каждого `MicroSIP.ini` выглядит так; меняются `PBX_IP`, номер, имя, `sourcePort` и `rtpPortMin/Max` согласно таблице:

```ini
[Settings]
audioCodecs=PCMU/8000/1
forceCodec=1
sourcePort=5062
rtpPortMin=40000
rtpPortMax=40100

[Account1]
server=PBX_IP:5060
domain=PBX_IP
username=1000
authID=1000
password=Workshop-2026!
transport=udp
```

Для второй копии заменяем `1000→1001`, `5062→5064`, `40000–40100→40200–40300`. Полный [проектный шаблон](../../config/workshops/freeswitch/microsip/MicroSIP.ini.template) содержит дополнительные настройки запуска и UI, но SIP-смысл виден в этом блоке. Не пишем в оба файла одновременно и не копируем один работающий INI в обе папки без смены портов.

**До REGISTER меняем пароль vanilla.** В Debian `nano /etc/freeswitch/vars.xml`: найдите `default_password=1234`, замените на `default_password=Workshop-2026!`, сохраните и выполните `systemctl restart freeswitch`. В vanilla-файлах `directory/default/1000.xml` и `1001.xml` проверьте, что пароль берётся из `$${default_password}`, а не задан отдельно. Это намеренно публичный лабораторный секрет; на доступном извне сервере его необходимо заменить уникальным и не повторять в демонстрации.

Запускаем обе копии MicroSIP. В Debian:

```bash
fs_cli -x 'sofia status profile internal reg'
```

Ожидаем регистрации `1000` и `1001`. Если зарегистрирован только один — прежде всего смотрим адрес Debian, пароль, SIP-порты и лог FreeSWITCH. Затем звоним `1000 → 1001`, отвечаем, произносим фразу и показываем:

```bash
fs_cli -x 'show channels'
```

Ожидаем две активные SIP-ноги и `PCMU/8000`. Это важно сделать **до** очередей: доказали, что регистрация и RTP работают, значит последующие неисправности легче локализовать в dialplan/callcenter. При двух клиентах на одном компьютере используем гарнитуру и mute, чтобы избежать акустической обратной связи.

## 4. Включаем `mod_callcenter`: пакет ≠ загруженный модуль

**Где:** Debian root shell. Открываем `/etc/freeswitch/autoload_configs/modules.conf.xml`, находим строку с `mod_callcenter`. В vanilla она закомментирована; меняем:

```xml
<!--<load module="mod_callcenter"/>-->
```

на:

```xml
<load module="mod_callcenter"/>
```

После `systemctl restart freeswitch` проверяем `fs_cli -x 'module_exists mod_callcenter'`: должно быть `true`. Объясняем три разных состояния: пакет установлен, модуль загружен, очередь сконфигурирована. Каждое проверяется отдельно.

## 5. Пишем две очереди и их агентов

**Где:** `/etc/freeswitch/autoload_configs/callcenter.conf.xml`. Ведущий **вводит и разбирает**, а не только копирует готовый файл. Для занятия можно сначала добавить `support@default` и проверить `fs_cli`, затем добавить `science-bot@default`. Итоговый проверенный конфиг проекта на дату подготовки:

```xml
<configuration name="callcenter.conf" description="CallCenter">
  <settings/>
  <queues>
    <queue name="support@default">
      <param name="strategy" value="longest-idle-agent"/>
      <param name="moh-sound" value="$${hold_music}"/>
      <param name="time-base-score" value="system"/>
      <param name="max-wait-time" value="0"/>
      <param name="max-wait-time-with-no-agent" value="0"/>
      <param name="max-wait-time-with-no-agent-time-reached" value="5"/>
      <param name="tier-rules-apply" value="false"/>
      <param name="tier-rule-wait-second" value="300"/>
      <param name="tier-rule-wait-multiply-level" value="true"/>
      <param name="tier-rule-no-agent-no-wait" value="false"/>
      <param name="discard-abandoned-after" value="60"/>
      <param name="abandoned-resume-allowed" value="false"/>
    </queue>
    <queue name="science-bot@default">
      <param name="strategy" value="longest-idle-agent"/>
      <param name="moh-sound" value="$${hold_music}"/>
      <param name="time-base-score" value="system"/>
      <param name="max-wait-time" value="0"/>
      <param name="max-wait-time-with-no-agent" value="0"/>
      <param name="max-wait-time-with-no-agent-time-reached" value="5"/>
      <param name="tier-rules-apply" value="false"/>
      <param name="tier-rule-wait-second" value="300"/>
      <param name="tier-rule-wait-multiply-level" value="true"/>
      <param name="tier-rule-no-agent-no-wait" value="false"/>
      <param name="discard-abandoned-after" value="60"/>
      <param name="abandoned-resume-allowed" value="false"/>
    </queue>
  </queues>
  <agents>
    <agent name="1001@default" type="callback"
           contact="[leg_timeout=15]user/1001@$${domain}"
           status="Available" max-no-answer="3" wrap-up-time="5"
           reject-delay-time="5" busy-delay-time="10"/>
    <agent name="1002@default" type="callback"
           contact="[leg_timeout=15,absolute_codec_string=PCMU]user/1002@$${domain}"
           status="Available" max-no-answer="3" wrap-up-time="1"
           reject-delay-time="2" busy-delay-time="2"/>
  </agents>
  <tiers>
    <tier agent="1001@default" queue="support@default" level="1" position="1"/>
    <tier agent="1002@default" queue="science-bot@default" level="1" position="1"/>
  </tiers>
</configuration>
```

Разбор у доски:

- `queue` — место ожидания вызова; `moh-sound` — что слышит звонящий, пока агент не ответил; `max-wait-time=0` здесь означает отсутствие общего лимита ожидания.
- `callback`-агент задаёт **куда звонить**. Для живого оператора — `user/1001@$${domain}`. Литерал `user/1001@default` у нас приводил к `SUBSCRIBER_ABSENT`; `$${domain}` разворачивается в домен текущего профиля.
- Для бота в контакт добавлен `absolute_codec_string=PCMU`: это ограничивает исходящую ногу нужным кодеком. Один экземпляр бота рассчитан на один разговор; очередь нужна, чтобы второй звонящий ждал свободного агента, но корректность ожидания следует **проверить двумя реальными звонками** во втором мастер-классе, а не выводить только из XML.
- `status=Available` не доказывает, что SIP-контакт зарегистрирован; отдельно проверим `sofia ... reg`. `tier` связывает агента с очередью. Без tier обе сущности существуют, но агент не обслуживает данную очередь.
- Разные задержки `wrap-up-time` и `busy-delay-time` — учебные настройки поведения после разговора/неудачной попытки, не требования продукта. Параметры ожидания при отсутствии агента будем оценивать в живом сценарии, а не обещать бесконечное ожидание по одному числу в конфиге.

После сохранения: `systemctl restart freeswitch`, затем по очереди:

```bash
fs_cli -x 'module_exists mod_callcenter'
fs_cli -x 'callcenter_config queue list'
fs_cli -x 'callcenter_config agent list'
fs_cli -x 'callcenter_config tier list'
```

Ожидаем **две** queue, **два** agent и **два** tier. Если видим `true`, но не видим `science-bot@default`, проблема в конфиге очередей, а не в установке модуля.

## 6. Связываем номера с очередями в dialplan

**Где:** `/etc/freeswitch/dialplan/default/20_workshop_callcenter.xml`. Здесь не «регистрируем» очередь, а объясняем FreeSWITCH, что делать при наборе `7000` или `7100`:

```xml
<include>
  <extension name="workshop_support_queue">
    <condition field="destination_number" expression="^7000$">
      <action application="answer"/>
      <action application="callcenter" data="support@default"/>
    </condition>
  </extension>
  <extension name="workshop_science_bot_queue">
    <condition field="destination_number" expression="^7100$">
      <action application="answer"/>
      <action application="set" data="RECORD_STEREO=true"/>
      <action application="set" data="recording_follow_transfer=true"/>
      <action application="set" data="workshop_recording=$${recordings_dir}/sip-bot/${strftime(%Y%m%d-%H%M%S)}-${uuid}.wav"/>
      <action application="log" data="NOTICE SIP bot stereo recording: ${workshop_recording}"/>
      <action application="record_session" data="${workshop_recording}"/>
      <action application="callcenter" data="science-bot@default"/>
    </condition>
  </extension>
</include>
```

Для записи создаём каталог от имени service user: `install -d -o freeswitch -g freeswitch -m 0750 /var/lib/freeswitch/recordings/sip-bot`. Проверяем `$${recordings_dir}` через `fs_cli -x 'global_getvar recordings_dir'`; если он указывает не на `/var/lib/freeswitch/recordings`, каталог создаём по фактическому пути, а не наугад. `RECORD_STEREO=true` позволит слушать стороны отдельно; запись — функция учебного FreeSWITCH, не обязанность бота. Участникам объясняем согласие на запись и что реальные разговоры нельзя публиковать без разрешения.

После `systemctl restart freeswitch` звоним с MicroSIP `1000` на `7000`. До ответа `1001` показываем:

```bash
fs_cli -x 'callcenter_config queue list members support@default'
fs_cli -x 'callcenter_config agent list 1001@default'
fs_cli -x 'show channels'
```

Ожидаем `Trying`/`Receiving`, удержание со стороны caller и вызов на `1001`. После ответа: `Answered`, `In a queue call`, два `ACTIVE`-канала PCMU и голос в обе стороны. Именно здесь становится слышна разница между прямым звонком и распределением через очередь.

Номер `7100` **пока не звоним как успешный бот-сценарий**: очередь и dialplan есть, но `1002` в этой части занятия ещё не зарегистрирован. Задаём аудитории вопрос: «Какая проверка докажет, что после второго мастер-класса он действительно вошёл в линию?» Ответ: REGISTER `1002`, вызов `7100`, изменение queue member/agent, звук, затем второй одновременный вызов на занятого бота и перевод на `7000`.

## 7. Убираем сетевую магию: NAT/STUN и граница WSL/сервера

На локальном стенде автоматическое угадывание внешнего IP может привести к RTP-адресу, недостижимому для клиента. Показываем `fs_cli -x 'sofia status profile internal'`: слушаем `SIP-IP`, `RTP-IP`, `Ext-SIP-IP`, `Ext-RTP-IP`. В проверенной конфигурации FreeSWITCH запускается с `-nonat -nonatmap` через systemd override:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/freeswitch -u ${USER} -g ${GROUP} -ncwait -nonat -nonatmap
```

Файл — `/etc/systemd/system/freeswitch.service.d/10-workshop-nonat.conf`. Пустой `ExecStart=` сбрасывает пакетную команду, следующая строка задаёт новую. После редактирования: `systemctl daemon-reload`, `systemctl restart freeswitch`, `systemctl status freeswitch`.

В `/etc/freeswitch/vars.xml` ищем активные `stun-set` для `external_rtp_ip` и `external_sip_ip`. В учебной сети оба вызова STUN комментируем и ниже задаём адрес, который FreeSWITCH определил как локальный:

```xml
<!-- <X-PRE-PROCESS cmd="stun-set" data="external_rtp_ip=stun:stun.freeswitch.org"/> -->
<X-PRE-PROCESS cmd="set" data="external_rtp_ip=$${local_ip_v4}"/>
<!-- <X-PRE-PROCESS cmd="stun-set" data="external_sip_ip=stun:stun.freeswitch.org"/> -->
<X-PRE-PROCESS cmd="set" data="external_sip_ip=$${local_ip_v4}"/>
```

**Проверяем результат** в `sofia status profile internal`; не предполагаем, что флаг `-nonat` сам отменяет preprocess-переменные в `vars.xml`. Это относится к нашему изолированному LAN/WSL-стенду, а не универсальная настройка SIP за NAT.

На отдельном сервере с Ubuntu 22.04 Debian Bookworm-пакеты нельзя было установить напрямую: несовместимые библиотеки подтверждены [серверным журналом](../../artifacts/deployment/ubuntu22-runtime-20260922/freeswitch-server/execution-journal.md). Там та же Debian-конфигурация живёт в `systemd-nspawn` с общей сетью хоста; FreeSWITCH слушает `10.0.0.45:5060`. Для аудитории это архитектурный вывод: меняется способ доставки runtime, но не смысл queue/agent/tier/dialplan. Точный unattended-рецепт серверной установки пока **не выдаём** за готовый мастер-класс: историческая команда исправления пакетной ошибки `ssmtp` не сохранилась.

## 8. Проверяем повторяемость и готовим мост ко второму мастер-классу

Ведущий закрывает звонок, перезапускает FreeSWITCH и показывает, что после старта живы сервис, оба SIP-клиента, обе очереди и маршрутизация `7000`:

```bash
systemctl is-enabled freeswitch
systemctl is-active freeswitch
fs_cli -x 'module_exists mod_callcenter'
fs_cli -x 'callcenter_config queue list'
fs_cli -x 'sofia status profile internal reg'
fs_cli -x 'show channels'
```

На WSL можно дополнительно выполнить `wsl --terminate Debian-Bookworm-FS` из PowerShell, открыть Debian снова и повторить те же проверки; это доказывает автозапуск unit при старте дистрибутива. После восстановления IP WSL MicroSIP может потребовать обновить серверный адрес и перерегистрироваться — это не отказ FreeSWITCH.

**Финальное действие слушателя:** на схеме у доски провести пальцем один вызов на `7000` и один будущий на `7100`, назвать для каждого SIP-аккаунт, dialplan extension, очередь и агента. Во втором мастер-классе мы подключим к `1002` уже подготовленного SIP-ассистента, загрузим другой RAG-корпус, прогреем модели до объявления доступности и проверим `7100 → бот`, ожидание при занятости и перевод в `7000 → оператор`.

### Если что-то не работает во время занятия

Сначала определяем **слой**: `systemctl` и `fs_cli -x status` → пакет/сервис; `module_exists` → модуль; `sofia ... reg` → учётки/пароль/IP; прямой `1000→1001` и `show channels` → SIP/RTP; `callcenter_config ...` → queue/agent/tier; вызов `7000` → dialplan. Журналы: `journalctl -u freeswitch -b -n 100 --no-pager` и `/var/log/freeswitch/freeswitch.log`. Не исправляем проблему очереди изменениями в ASR/LLM/TTS: эти компоненты пока вообще не участвуют в занятии.

Восстановительный [скрипт конфигурации](../../tools/workshops/configure_freeswitch_workshop.sh), [генератор двух MicroSIP INI](../../tools/workshops/prepare_freeswitch_microsip.ps1) и [технический runbook](freeswitch-callcenter-runbook.md) существуют для проверки/возврата стенда после занятия. Они **не заменяют** разбор строк на мастер-классе.
