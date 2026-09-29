# Мастер-класс: развёртывание SIP-ассистента с нуля

Дата прогона: 29.09.2026. Статус: контрольный SIP-звонок выполнен; ограничения и ещё не проверенные маршруты перечислены в конце журнала.

Этот журнал предназначен человеку, повторяющему установку без истории разработки. В нём приведены смысловые команды установки и проверки, а не внутренние диагностические команды исполнителя. Разделы помечают, что **исполнено в этом прогоне**, а что дано **для повторения участником и здесь не исполнялось**. В частности, веса моделей в данном прогоне восстанавливаются из предварительно проверенной локальной копии; приведённые вместо этого команды их скачивания из интернета не выдаются за фактически выполненные.

**Внимание перед повторением по публичному GitHub:** стенд первоначально клонирован на commit `6be81a…`; журнал, unit-файлы и две коррекции исходников появились уже после него. Для повторения нужна более новая ревизия, содержащая этот журнал. Само развёртывание из полностью сетевой пересборки патченного native runtime не выполнялось по условию задачи. Страховочные архивы остаются на локальном диске; контрольная WAV-запись исключена `.gitignore` и в Git не публикуется.

## Цель и состав стенда

Один новый WSL2-дистрибутив Ubuntu 24.04 LTS содержит Python 3.14t, SIP-бота, Ollama с Qwen3.5-9B и embeddinggemma, faster-whisper large-v3, XTTS-v2, RAG-корпус и демонстрационную веб-страницу. FreeSWITCH с двумя очередями устанавливается в Debian Bookworm `systemd-nspawn` внутри этого же WSL-дистрибутива: используемое пакетное зеркало FreeSWITCH рассчитано на Debian 12, а не на пакеты Ubuntu. Это одна новая WSL-машина, не второй WSL-дистрибутив. Существующие `Ubuntu-24.04` и `Debian-Bookworm-FS` остаются нетронутыми.

Приёмка этого прогона: запуск без подмены моделей или CPU fallback; `Py_GIL_DISABLED=1` и GIL выключен после импортов и операций; готовность Ollama/ASR/TTS/RAG; работа FreeSWITCH и регистрация односессионного бота; контрольный звонок и текстовый отчёт. Контрольный звонок сам по себе не доказывает работающий SIP-перевод на оператора или браузерный WebRTC-звонок: это отдельные проверки.

## 1. Исходные условия — исполнено

- Хост: Windows x64, WSL2, NVIDIA RTX 5060 Ti (16311 МиБ VRAM).
- Диск `D:` до начала копирования: около 246 ГиБ свободно, что выше минимального запаса 20 ГиБ.
- Код проекта: публичный `https://github.com/borikinternet/sip-bot`, исходный commit `6be81ab338a72e62a875ef5126f05af104494767`, чистое рабочее дерево.
- В исходной Ubuntu найдены активные веса `Systran/faster-whisper-large-v3`, `coqui/XTTS-v2`, `Qwen3.5-9B-Q4_K_M.gguf` и Ollama-модели `embeddinggemma`/`c3-qwen35-9b-q4km`. Их бинарные копии и подготовленный no-GIL runtime сохранены на Windows в `D:\sip-bot-workshop-cache\20260929`. Эти локальные операции не являются учебными командами скачивания.

| Локальный страховочный архив | Размер, байт | SHA-256 |
|---|---:|---|
| `models.tar` | 17 152 942 080 | `97dd473cb06642e0808f3d1dd47482448f1f4c7444240815d2c79bf3e7d2c772` |
| `runtime.tar` | 14 804 602 880 | `b0acf07fc8175322dbe179cae09cd1792d4971000c81abcdc39d39ad2d11e583` |

Архивы не публикуются и не заменяют интернет-источники для участников. Перед использованием проверены хеши обоих архивов; после восстановления будут отдельно проверены хеши файлов весов и работа native-модулей.

## 2. Свежий Ubuntu WSL — исполнено

Для повторения используется [официальный WSL-образ Ubuntu 24.04.5](https://releases.ubuntu.com/noble/ubuntu-24.04.5-wsl-amd64.wsl), а не экспорт существующего дистрибутива. Его SHA-256 из [официального списка Canonical](https://releases.ubuntu.com/noble/SHA256SUMS): `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`.

В PowerShell:

```powershell
$Distro = 'SIP-Bot-Workshop-20260929'
$Image = 'D:\sip-bot-workshop-cache\20260929\ubuntu-24.04.5-wsl-amd64.wsl'
$Install = 'D:\WSL\SIP-Bot-Workshop-20260929'
curl.exe -fL --retry 3 -o $Image https://releases.ubuntu.com/noble/ubuntu-24.04.5-wsl-amd64.wsl
if ((Get-FileHash -LiteralPath $Image -Algorithm SHA256).Hash -ne 'BB415D824822C4B878125729AF451A5D18FB13D1CF5CBED9A7393AD64AC6039E') {
    throw 'Контрольная сумма образа Ubuntu не совпала'
}
New-Item -ItemType Directory -Path $Install -Force | Out-Null
wsl --import $Distro $Install $Image --version 2
wsl -d $Distro -u root -- cat /etc/os-release
```

Образ скачан и проверен: фактический SHA-256 `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`. Импортированный `SIP-Bot-Workshop-20260929` сообщил `Ubuntu 24.04.5 LTS`. Имя `$Distro` должно быть новым; существующий одноимённый WSL-инстанс нельзя перезаписывать.

Для самого бота создан обычный пользователь, а исходники клонированы из публичного репозитория на фиксированном коммите:

```powershell
wsl -d $Distro -u root -- useradd --create-home --shell /bin/bash sipbot
wsl -d $Distro -u sipbot -- git clone --depth 1 https://github.com/borikinternet/sip-bot.git /home/sipbot/sip-bot
wsl -d $Distro -u sipbot -- git -C /home/sipbot/sip-bot rev-parse HEAD
```

Фактический commit: `6be81ab338a72e62a875ef5126f05af104494767`, рабочее дерево чистое. В новой Ubuntu подтверждены `systemd` PID 1, доступ к GPU и сеть. Существующие WSL-дистрибутивы не переименовывались и не удалялись.

Разделение прав в этом прогоне: `sipbot` создан **без** членства в группе `sudo`; приложения и загрузка моделей работают от него, а системные команды для Debian/FreeSWITCH и systemd выполнялись из административной оболочки, открываемой в PowerShell командой `wsl -d $Distro -u root -- bash`. Далее слово «в Ubuntu» для привилегированных блоков означает именно эту root-оболочку; `sudo` в таких примерах технически избыточен. Нельзя запускать эти блоки от обычного `sipbot` и ожидать, что у него есть пароль sudo. После выхода из root-оболочки пользовательские команды запускаются через `wsl -d $Distro -u sipbot -- bash`.

## 3. Системные пакеты Ubuntu — исполнено

Команда установки не скрывает выбор зависимостей в проектном скрипте. `systemd-container`, `debootstrap` и Debian keyring нужны для FreeSWITCH в Debian Bookworm; остальные — для native Python/SIP/audio и проверок.

```powershell
wsl -d $Distro -u root -- apt-get update
wsl -d $Distro -u root -- env DEBIAN_FRONTEND=noninteractive apt-get install -y `
  build-essential cmake pkg-config curl git ca-certificates libssl-dev zlib1g-dev `
  libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev libncurses-dev `
  libgdbm-dev uuid-dev libsndfile1 ffmpeg sox libsox-fmt-all libportaudio2 `
  baresip systemd-container debootstrap debian-archive-keyring libnss-mymachines rsync `
  swig zstd qrencode
```

`apt-get update` и установка перечисленных пакетов завершились с кодом `0`; они были установлены несколькими вызовами `apt-get` из подписанных стандартных репозиториев Ubuntu Noble. `swig` нужен binding PJSUA2 при сборке из исходников, `zstd` — официальному архиву Ollama, `qrencode` — QR локального стенда. После установки `systemctl is-system-running` вернул `running`.

## 4. Debian 12 и пакетный FreeSWITCH — исполнено

Пакетное зеркало, выбранное для конференционного стенда, публикует `bookworm`, но не `noble`. Поэтому Debian установлен как контейнер ОС в *той же* новой Ubuntu WSL. Он разделяет с Ubuntu сетевое пространство; отдельная WSL-машина для него не создавалась. В Ubuntu исполнено:

```bash
debootstrap --variant=minbase --arch=amd64 bookworm \
  /var/lib/machines/freeswitch-bookworm http://deb.debian.org/debian
systemd-nspawn -D /var/lib/machines/freeswitch-bookworm --pipe apt-get update
systemd-nspawn -D /var/lib/machines/freeswitch-bookworm --pipe \
  env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  systemd systemd-sysv dbus ca-certificates curl gnupg locales procps iproute2
```

`debootstrap` проверил подпись Debian Release и закончил `Base system installed successfully`; контейнер сообщает `Debian GNU/Linux 12 (bookworm)`. Файл `/etc/systemd/nspawn/freeswitch-bookworm.nspawn` был установлен из [сохранённой конфигурации](freeswitch-bookworm.nspawn). В root-оболочке откройте `nano /etc/systemd/nspawn/freeswitch-bookworm.nspawn` и внесите именно эти значения:

```ini
[Exec]
Boot=yes
PrivateUsers=no
Hostname=freeswitch-bookworm

[Files]
BindReadOnly=/home/sipbot/sip-bot:/srv/sip-bot

[Network]
VirtualEthernet=no
```

`BindReadOnly` предоставляет Debian исходники конфигурации, не давая ему изменять клон. `VirtualEthernet=no` оставляет общие SIP/RTP-адреса. Запуск и проверка:

```bash
machinectl start freeswitch-bookworm
systemctl enable systemd-nspawn@freeswitch-bookworm.service
machinectl list
machinectl shell freeswitch-bookworm
```

При первой проверке автозапуска WSL контейнер однажды попал в гонку создания cgroup (`Failed to create ... payload subcgroup: Device or resource busy`); ручной `machinectl start` прошёл. Для повторной попытки добавлен drop-in [`10-wsl-nspawn-retry.conf`](10-wsl-nspawn-retry.conf) со значениями `Restart=on-failure` и `RestartSec=5`. В root-оболочке его можно внести через `nano /etc/systemd/system/systemd-nspawn@freeswitch-bookworm.service.d/10-wsl-nspawn-retry.conf`, затем `systemctl daemon-reload`. Результат повторного холодного старта отмечен в итогах.

Внутри Debian (`machinectl shell`) были выполнены приведённые ниже смысловые действия. В этом прогоне они передавались в уже работающий контейнер через `systemd-run --machine=freeswitch-bookworm --pipe --wait --collect`; это способ неинтерактивного ввода тех же команд, а не проектный скрипт.

Источник пакетов FreeSWITCH — предоставленное владельцем зеркало `http://fi.itlnk.ru/freeswitch bookworm main`. По HTTPS получен ключ `FreeSWITCH Packaging Key <freeswitch@signalwire.com>`; *до* помещения его в keyring проверен fingerprint `655DA1341B5207915210AFE936B4249FA7B0FB03`:

```bash
curl -fsSL --get --data-urlencode 'op=get' \
  --data-urlencode 'search=0x36B4249FA7B0FB03' \
  -o /tmp/freeswitch-packaging.asc https://keyserver.ubuntu.com/pks/lookup
gpg --show-keys --with-colons /tmp/freeswitch-packaging.asc
gpg --dearmor --yes --output /usr/share/keyrings/freeswitch-packaging.gpg \
  /tmp/freeswitch-packaging.asc
install -m 0644 /srv/sip-bot/config/workshops/freeswitch/apt/freeswitch.list \
  /etc/apt/sources.list.d/freeswitch.list
apt-get update
apt-cache policy freeswitch freeswitch-mod-callcenter freeswitch-meta-vanilla
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  freeswitch-meta-vanilla freeswitch-mod-callcenter freeswitch-systemd
DEBIAN_FRONTEND=noninteractive apt-get install -y nano
systemctl enable freeswitch
```

Не продолжайте при ином fingerprint или ошибке проверки подписи apt. `apt-get update` принял подписанный `InRelease`. Все три пакета FreeSWITCH имеют версию-кандидат и фактически установленную версию `1.11.3-release-33213556856-ef32e20529~bookworm~amd64-1~bookworm+1`. При установке получены vanilla dialplan, mod_sofia и mod_callcenter.

### 4.1. Две очереди и SIP-профиль

Использованы не генераторы конфигурации, а четыре понятных фрагмента проекта. В `callcenter.conf.xml` очередь `science-bot@default` содержит ровно одного callback-агента `1002@default`, очередь `support@default` — живого агента `1001@default`. В dialplan номер `7100` направлен на бота со стереозаписью, `7000` — на операторов. Отдельный профиль `bot-vpn` слушает `172.16.15.72:15062`, согласует `PCMU` и использует локальную тестовую domain `192.168.1.74`. Эти адреса — не универсальные значения: перед повторением их надо сопоставить с `hostname -I` собственной WSL и с `config/constants.py` бота.

```bash
install -d -m 0755 /etc/systemd/system/freeswitch.service.d
install -m 0644 /srv/sip-bot/config/workshops/freeswitch/systemd/freeswitch.service.d/10-workshop-nonat.conf \
  /etc/systemd/system/freeswitch.service.d/10-workshop-nonat.conf
install -m 0644 /srv/sip-bot/config/workshops/freeswitch/autoload_configs/callcenter.conf.xml \
  /etc/freeswitch/autoload_configs/callcenter.conf.xml
install -m 0644 /srv/sip-bot/config/workshops/freeswitch/dialplan/default/20_workshop_callcenter.xml \
  /etc/freeswitch/dialplan/default/20_workshop_callcenter.xml
install -d -o freeswitch -g freeswitch -m 0750 \
  /var/lib/freeswitch/recordings/sip-bot
```

Изначально профиль `bot-vpn.xml` ставился из репозитория, затем его пришлось изменить для этой WSL-сети. **Итоговая** версия сохранена в [`bot-vpn.xml`](bot-vpn.xml): `sip-ip`, `rtp-ip`, `ext-sip-ip`, `ext-rtp-ip` указывают на `172.16.15.72`, `sip-port=15062`, `wss-binding=:7443`, `force-register-domain=192.168.1.74`, `apply-candidate-acl=rfc1918.auto`. При ручном повторении откройте `nano /etc/freeswitch/sip_profiles/bot-vpn.xml`, внесите эти поля и замените адреса на свои; приложенный полный файл служит сверкой, а не скрытым установочным скриптом.

В vanilla `/etc/freeswitch/vars.xml` изменены `default_password`, две STUN-директивы **и** `local_ip_v4`/`domain`. Сохранённые результаты редактирования — [vars.xml](vars.xml) и [modules.conf.xml](modules.conf.xml); при обучении их надо разобрать по строкам, а не просто вслепую скопировать. Исходный `default_password=1234` заменён на публичный **только для лабораторного стенда** `Workshop-2026!`; применять его для реального сервера нельзя. Обе строки `stun-set` для `external_rtp_ip`/`external_sip_ip` закомментированы и каждая заменена на `set ...=$${local_ip_v4}`. Добавлены `local_ip_v4=192.168.1.74` и `domain=192.168.1.74`. Без них FreeSWITCH в общей WSL-сети выбрал Docker bridge `172.18.0.1`; регистрация `1002@192.168.1.74` получила `403 Can't find user`. После явного указания LAN-домена регистрация прошла. Это изменение **не затрагивает Docker**, а только выбор интерфейса FreeSWITCH. В `modules.conf.xml` раскомментирована строка `<load module="mod_callcenter"/>`. При ручном повторении откройте файлы в редакторе и внесите перечисленные изменения:

```bash
nano /etc/freeswitch/vars.xml
nano /etc/freeswitch/autoload_configs/modules.conf.xml
systemctl daemon-reload
systemctl restart freeswitch
systemctl is-active freeswitch
fs_cli -x status
fs_cli -x 'module_exists mod_callcenter'
fs_cli -x 'callcenter_config queue list'
fs_cli -x 'sofia status profile bot-vpn'
```

Получено `active`, `FreeSWITCH 1.11.3 ... is ready`, `module_exists mod_callcenter=true`, обе очереди в `queue list`; профиль `bot-vpn` слушает `172.16.15.72:15062`, `Auto-NAT=false`, `CODECS IN/OUT=PCMU`. На этом этапе `REGISTRATIONS=0`: бот ещё не запущен, это ожидаемо. Для автозапуска включены `freeswitch.service` внутри контейнера и `systemd-nspawn@freeswitch-bookworm.service` в Ubuntu; пока сам WSL не запущен, они не стартуют автоматически вместе с Windows.

## 5. Сохранённые веса и runtime — локально исполнено; интернет-команды ниже не исполнялись

Тяжёлые бинарные артефакты перед пересозданием среды сохранены на Windows в архивах из раздела 1. В новую Ubuntu они восстановлены из этих проверенных копий по исходным путям `/home/sipbot`. Команды внутреннего копирования в учебный журнал намеренно не включены. Для повторения участником ниже приведён **другой**, сетевой маршрут: он скачивает оригинальные ресурсы, а не наши архивы, и **в этом прогоне не запускался**. Его нельзя принимать за проверку скорости или доступности зеркал на дату мастер-класса.

После восстановления проверены реальные SHA-256 четырёх крупных файлов:

| Компонент | Версия / точный источник | SHA-256 фактически проверенного файла |
|---|---|---|
| ASR `model.bin` | [`Systran/faster-whisper-large-v3` @ `edaa852ec7e145841d8ffdb056a99866b5f0a478`](https://huggingface.co/Systran/faster-whisper-large-v3/tree/edaa852ec7e145841d8ffdb056a99866b5f0a478), 3 087 284 237 байт | `69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1` |
| TTS `model.pth` | [`coqui/XTTS-v2` v2.0.3 @ `6b8036b35d787cf43d18d640587956b9db8fd1b8`](https://huggingface.co/coqui/XTTS-v2/tree/6b8036b35d787cf43d18d640587956b9db8fd1b8), 1 867 929 118 байт | `98f7297340c09d9d33cb3e2580f8cfb02e8b496270e2cf678ffcfe38b535d218` |
| LLM `Qwen3.5-9B-Q4_K_M.gguf` | [`unsloth/Qwen3.5-9B-GGUF` @ `3885219b6810b007914f3a7950a8d1b469d598a5`](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5), 5 680 522 464 байта | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
| embeddinggemma Ollama blob | `embeddinggemma:latest`, GGUF BF16, 621 867 104 байта | `0800cbac9c2064dde519420e75e512a83cb360de3ad5df176185dc69652fc515` |

Остальные файлы ASR/TTS и их контрольные суммы перечислены в [ASR manifest](../../feasibility/001-C2/model-manifest.json) и [XTTS manifest](../../feasibility/001-C4-tts-primary/asset-manifest.json). XTTS распространяется по **Coqui Public Model License 1.0.0**, а не как обычная MIT-модель; отдельный `LICENSE.txt` обязателен при скачивании, условия использования следует прочитать до публичной демонстрации.

### 5.1. Интернет-вместо-копии: веса моделей — **не исполнялось**

Команды для Ubuntu под пользователем `sipbot` после установки совместимого Python-runtime и `huggingface-hub==0.36.2` (`hf download`). Ревизии закреплены, изменившийся SHA-256 — стоп, а не повод «подобрать похожий» файл. Войдите в Python-окружение, содержащее `hf`, либо вызывайте его по полному пути:

```bash
source /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/activate
hf download Systran/faster-whisper-large-v3 \
  .gitattributes README.md config.json model.bin preprocessor_config.json tokenizer.json vocabulary.json \
  --revision edaa852ec7e145841d8ffdb056a99866b5f0a478 \
  --local-dir /home/sipbot/.local/models/faster-whisper-large-v3-edaa852e
sha256sum /home/sipbot/.local/models/faster-whisper-large-v3-edaa852e/model.bin

hf download coqui/XTTS-v2 \
  config.json dvae.pth mel_stats.pth model.pth vocab.json LICENSE.txt README.md samples/en_sample.wav \
  --revision 6b8036b35d787cf43d18d640587956b9db8fd1b8 \
  --local-dir /home/sipbot/.cache/sip-bot-c4-xtts-v2-model
sha256sum /home/sipbot/.cache/sip-bot-c4-xtts-v2-model/model.pth \
  /home/sipbot/.cache/sip-bot-c4-xtts-v2-model/LICENSE.txt \
  /home/sipbot/.cache/sip-bot-c4-xtts-v2-model/samples/en_sample.wav

hf download unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf \
  --revision 3885219b6810b007914f3a7950a8d1b469d598a5 \
  --local-dir /home/sipbot/models/c3-qwen35-9b-gguf
sha256sum /home/sipbot/models/c3-qwen35-9b-gguf/Qwen3.5-9B-Q4_K_M.gguf
```

Ожидаемые дополнительные SHA-256: XTTS `LICENSE.txt` — `190f6d7c19b8984f91b97712b94ce92d2b2e640fc677dacab966e955ece9d043`, голосовой образец `samples/en_sample.wav` — `2bb31e7bf2b1e6f98f21be9017f5daee44a40ca91126955485f430b272e1a8b5`.

### 5.2. Интернет-вместо-копии: Ollama и embedding — **не исполнялось**

Зафиксированная упаковка Ollama `0.33.1` — [`ollama-linux-amd64.tar.zst`](https://github.com/ollama/ollama/releases/tag/v0.33.1), SHA-256 `88e0d36bd90121595e5516c84f6ab61b546368fbd2d825b4aae70999c949649d`. После проверки архива распаковать его в выбранный префикс и создать локальную модель из GGUF. Содержимое [`Modelfile`](../../feasibility/001-C3-llm-primary/Modelfile) фиксирует `num_ctx=8192`, `temperature=0.2`, `top_p=0.95`, `top_k=20`.

```bash
curl -fL --retry 3 -o /home/sipbot/ollama-linux-amd64-v0.33.1.tar.zst \
  https://github.com/ollama/ollama/releases/download/v0.33.1/ollama-linux-amd64.tar.zst
sha256sum /home/sipbot/ollama-linux-amd64-v0.33.1.tar.zst
mkdir -p /home/sipbot/src/c3-ollama/v0.33.1
tar --zstd -xf /home/sipbot/ollama-linux-amd64-v0.33.1.tar.zst \
  -C /home/sipbot/src/c3-ollama/v0.33.1
OLLAMA_HOST=127.0.0.1:11434 \
  /home/sipbot/src/c3-ollama/v0.33.1/bin/ollama serve
```

Последнюю команду выполняют в отдельном терминале или через systemd-службу из следующего раздела. При работающем Ollama:

```bash
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama create c3-qwen35-9b-q4km \
  --file /home/sipbot/sip-bot/artifacts/feasibility/001-C3-llm-primary/Modelfile
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama pull embeddinggemma:latest
curl -fsS http://127.0.0.1:11434/api/tags
```

`embeddinggemma:latest` — изменяемый тег; после `pull` сравните digest manifest с `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`, а blob с хешем таблицы. Несовпадение означает другую версию и требует перепостроения RAG-индекса, а не молчаливого использования. Фактически восстановленные в этом прогоне теги дали **ровно** эти значения: `embeddinggemma:latest` → `85462619…`, `c3-qwen35-9b-q4km:latest` → `d635207483a7c97ea76ddd48eb2ad187e9846eff5a2f5e8369d7475956b002e1`.

### 5.3. Интернет-вместо-копии: Python и native-модули — **не исполнялось**

Локальный архив `runtime.tar` содержит не только Python 3.14t, но и *специально исправленные* native-модули. Непатченные бинарные пакеты из PyPI вместо них применять нельзя: они могут включить GIL обратно. Ниже — основные проверяемые исходники и команды сборки для независимого повторения; в **данном** развёртывании они не запускались и потому не объявлены заново доказанным полностью сетевым маршрутом. Подробности/эталонные результаты именно наших сборок: [CPython manifest](../../feasibility/001-B/runtime-manifest.json), [PJSUA2 build](../../feasibility/001-C1-sip-pjsua2-pjmedia/commands.md), [CTranslate2 build](../../feasibility/001-C2/patch-build.md), [XTTS build](../../feasibility/001-C4-tts-primary/patch-build.md), [WebRTC VAD build](../../implementation/007-webrtc-vad/007-A/commands.md). Эти документы содержат команды и не являются установочными скриптами.

| Исходный артефакт | Интернет-источник / идентификатор | Контрольная сумма исходника или проверенного патча |
|---|---|---|
| CPython 3.14.7 | [официальный `Python-3.14.7.tar.xz`](https://www.python.org/ftp/python/3.14.7/Python-3.14.7.tar.xz) | SHA-256 `3b48dac8fb59f62eaa67ac83c1eb12bda1b7a08406dd286e252c11a66be27f81` |
| PJSIP/PJSUA2/PJMEDIA 2.17 | [`pjproject` tag 2.17](https://github.com/pjsip/pjproject/archive/refs/tags/2.17.tar.gz) | SHA-256 tar `065fe06c06788d97c35f563796d59f00ce52fe9558a52d7b490a042a966facce` |
| PJSUA2 no-GIL, часть 1 и 2 | [`pjsua2-free-threading.patch`](../../feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading.patch), [`pjsua2-free-threading-buffer.patch`](../../feasibility/001-C1-sip-pjsua2-pjmedia/patches/pjsua2-free-threading-buffer.patch) | SHA-256 `d20752498ac86a03c2999e8fa97b1517caaa65486147ba468fbc8824da12d401` и `9c849bb28ec6d7a791e22769b8f2e975f8686b2470d286d74768e4075ca48be5` |
| CTranslate2 4.8.1 | [tag `v4.8.1`](https://github.com/OpenNMT/CTranslate2/tree/v4.8.1), commit `0d8bcd362ac75ef860ef161d6f0efad0ae439ff0` | [наш patch](../../feasibility/001-C2/ctranslate2-free-threading.patch) SHA-256 `6c118e2707adf715bdccd3b74f772490373927f455a25a857b991160d73ed619` |
| torchaudio 2.10.0 | [tag `v2.10.0`](https://github.com/pytorch/audio/tree/v2.10.0), commit `27b7ebdebd2d2e4d34a2f5c05b0fb26efbd1da63` | [наш patch](../../feasibility/001-C4-tts-primary/torchaudio-free-threading.patch) SHA-256 `50f34731f5c539944f37d91534aeea5b966af87aedb8e44cf62b4264d2057706` |
| tokenizers 0.22.2 | [tag `v0.22.2`](https://github.com/huggingface/tokenizers/tree/v0.22.2), commit `f383101a26663708484cac0727792aad74f78234` | [наш patch](../../feasibility/001-C4-tts-primary/tokenizers-free-threading.patch) SHA-256 `a5e511cfa89ad0b8f085363be9bfffa4a8b7f68abc23f71adf464d54de1c63dc` |
| monotonic-alignment-search 0.2.1 | [исходники PyPI](https://pypi.org/project/monotonic-alignment-search/0.2.1/) | [наш patch](../../feasibility/001-C4-tts-primary/monotonic-alignment-search-free-threading.patch) SHA-256 `7d10a98959179c8f5c92a01736a824d3b27a8d26161f3a9af68fdf3152c5d4d7` |
| webrtcvad-wheels 2.0.14 | [исходники PyPI](https://pypi.org/project/webrtcvad-wheels/2.0.14/) | SHA-256 source archive `5f59c8e291c6ef102d9f39532982fbf26a52ce2de6328382e2654b0960fea397`; [наш patch](../../../patches/webrtcvad-wheels-2.0.14-free-threading.patch) SHA-256 `bbfb5d441939e078ca3f3445ea539b6cd671ee998a585130db8c0144950d6d50` |

Прямые команды, которые участник **может выполнить вместо восстановления нашего архива**, сначала для CPython и PJSIP. Перед `make install` нужно остановиться при несовпадении хешей или ошибке сборки. Патчи PJSUA2 в проверенном процессе применялись *к сгенерированному SWIG wrapper*, а не к исходному `.i` до `make`:

```bash
mkdir -p /home/sipbot/src/cpython-build /home/sipbot/src/pjsip-build
curl -fL --retry 3 -o /home/sipbot/src/cpython-build/Python-3.14.7.tar.xz \
  https://www.python.org/ftp/python/3.14.7/Python-3.14.7.tar.xz
echo '3b48dac8fb59f62eaa67ac83c1eb12bda1b7a08406dd286e252c11a66be27f81  /home/sipbot/src/cpython-build/Python-3.14.7.tar.xz' | sha256sum -c -
tar -xf /home/sipbot/src/cpython-build/Python-3.14.7.tar.xz -C /home/sipbot/src/cpython-build
cd /home/sipbot/src/cpython-build/Python-3.14.7
./configure --prefix=/home/sipbot/.local/cpython-3.14.7t --disable-gil --with-ensurepip=install --without-lto
make -j4
make install
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c 'import sys,sysconfig; print(sysconfig.get_config_var("Py_GIL_DISABLED"),sys._is_gil_enabled())'

curl -fL --retry 3 -o /home/sipbot/src/pjsip-build/pjproject-2.17.tar.gz \
  https://github.com/pjsip/pjproject/archive/refs/tags/2.17.tar.gz
echo '065fe06c06788d97c35f563796d59f00ce52fe9558a52d7b490a042a966facce  /home/sipbot/src/pjsip-build/pjproject-2.17.tar.gz' | sha256sum -c -
tar -xf /home/sipbot/src/pjsip-build/pjproject-2.17.tar.gz -C /home/sipbot/src/pjsip-build
cd /home/sipbot/src/pjsip-build/pjproject-2.17
./configure --prefix=/home/sipbot/.local/pjsip-2.17t CFLAGS=-fPIC CXXFLAGS=-fPIC
make dep
make -j4
make install
```

Затем по [PJSUA2 build](../../feasibility/001-C1-sip-pjsua2-pjmedia/commands.md) надо сгенерировать SWIG binding, применить **оба** патча, собрать и установить Python extension в target `3.14t`; эталон SHA-256 установленного `_pjsua2...so` — `510117d59355d3ea0f30f84d9fdc5fbd6ec6d019eb989dabe9660661846cd01d`. Для CTranslate2 исходник берётся из указанного Git tag/commit, patch применяется к `python/cpp/module.cc`, затем собирается wheel командой из [CTranslate2 build](../../feasibility/001-C2/patch-build.md), сохраняя native CUDA-библиотеку из CTranslate2 4.8.1 wheel; эталон extension SHA-256 `1bd716e70b94274e8d91d1160d7e0a565f889f57f01aea9beb8d27d1a3b16e9a`. Для XTTS требуется `coqui-tts==0.27.5`, `torch==2.10.0`, `torchaudio==2.10.0`, `tokenizers==0.22.2` и три указанных патча; для VAD — patched `webrtcvad-wheels==2.0.14`. Версии, требования компоновки и sha бинарных результатов приведены в документах сборки. Это **не обещание**, что команда `pip install` непатченных пакетов даёт эквивалентный runtime: такая независимая установка в этом прогоне не выполнялась.

Для приобретения **остальных исходников из Интернета**, без локального архива, в мастер-классе нужны следующие команды. Это именно получение с проверкой версии/хеша, **не** готовая сборка patched wheel:

```bash
git clone --branch v4.8.1 --depth 1 https://github.com/OpenNMT/CTranslate2.git \
  /home/sipbot/src/ctranslate2-v4.8.1
git -C /home/sipbot/src/ctranslate2-v4.8.1 rev-parse HEAD
# Ожидаемый commit: 0d8bcd362ac75ef860ef161d6f0efad0ae439ff0

git clone --branch v2.10.0 --depth 1 https://github.com/pytorch/audio.git \
  /home/sipbot/src/torchaudio-v2.10.0
git -C /home/sipbot/src/torchaudio-v2.10.0 rev-parse HEAD
# Ожидаемый commit: 27b7ebdebd2d2e4d34a2f5c05b0fb26efbd1da63

git clone --branch v0.22.2 --depth 1 https://github.com/huggingface/tokenizers.git \
  /home/sipbot/src/tokenizers-v0.22.2
git -C /home/sipbot/src/tokenizers-v0.22.2 rev-parse HEAD
# Ожидаемый commit: f383101a26663708484cac0727792aad74f78234

mkdir -p /home/sipbot/src/webrtcvad-source /home/sipbot/src/mas-source
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pip download \
  --no-binary=:all: --no-deps --dest /home/sipbot/src/webrtcvad-source \
  webrtcvad-wheels==2.0.14
sha256sum /home/sipbot/src/webrtcvad-source/*
# Ожидаемый SHA-256 архива: 5f59c8e291c6ef102d9f39532982fbf26a52ce2de6328382e2654b0960fea397
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pip download \
  --no-binary=:all: --no-deps --dest /home/sipbot/src/mas-source \
  monotonic-alignment-search==0.2.1
sha256sum /home/sipbot/sip-bot/patches/webrtcvad-wheels-2.0.14-free-threading.patch \
  /home/sipbot/sip-bot/artifacts/feasibility/001-C2/ctranslate2-free-threading.patch \
  /home/sipbot/sip-bot/artifacts/feasibility/001-C4-tts-primary/*free-threading.patch
```

Для `monotonic-alignment-search` зафиксирована точная версия и patch, но исходный PyPI-архив не имеет отдельного зафиксированного SHA в прежнем evidence. Его нужно получить/проверить непосредственно перед независимой сборкой и записать digest; **не считать текущий журнал полностью проверенным интернет-воспроизведением native runtime**. Исходный локально восстановленный runtime при этом проверен по binary SHA и реальной работе.

Фактическое восстановление из локального архива проверено на готовой новой Ubuntu: `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` сообщает `3.14.7 free-threading build`, `Py_GIL_DISABLED=1`, `sys._is_gil_enabled()=False`. Совпали SHA-256 PJSUA2, CTranslate2, torchaudio, tokenizers, monotonic-alignment-search и `_webrtcvad` (последний — `39849a1fbe4435263c7ad67d5890818a7200803dd5427c61e1bd7f87ac885236`). В combined runtime импортированы `pjsua2`, `webrtcvad`, `ctranslate2`, `faster_whisper`, `torch`, `torchaudio`, `tokenizers`, `TTS`; GIL остался выключенным.

## 6. Запуск сервисов и устранение двух ошибок cold start — исполнено

В исходном клоне проекта содержится штатный предсозданный индекс `data/knowledge/index/telecom-voice-assistants-v1.json` (SHA-256 `6d87707dc78782e15d54259be04341a79a2a1986afd29956df361cf0ca34c07f`) и корпус `data/knowledge/telecom-corpus`. Это базовый **телекоммуникационный** RAG, а не обещанная в прежних опытах научная база. Из сети отдельно его скачивать не нужно: он приходит с зафиксированным Git commit. Для другого массива документов используется веб-загрузка или процедура [RAG onboarding](../../../docs/workshops/rag-corpus-onboarding-runbook.md); замена корпуса не является переобучением Qwen.

Фактически в `/etc/systemd/system/` установлены три небольших unit-файла: [`sip-bot-ollama.service`](sip-bot-ollama.service), [`sip-bot.service`](sip-bot.service), [`sip-bot-demo-web.service`](sip-bot-demo-web.service). В root-оболочке откройте каждый через `nano`, внесите соответствующий полный текст из приложенного файла и проверьте эти ключевые строки:

| Unit | От какого пользователя и что запускает | Зачем |
|---|---|---|
| `sip-bot-ollama` | `sipbot`; `OLLAMA_HOST=127.0.0.1:11434`, `OLLAMA_MODELS=/home/sipbot/.ollama/models`, `.../ollama serve` | Один локальный HTTP-сервер для Qwen и embeddinggemma; наружу не опубликован |
| `sip-bot` | `sipbot`; combined Python `.../sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/run_live_bot.py` | Прогревает AI, только затем регистрируется как `1002` на FreeSWITCH; `LD_LIBRARY_PATH` содержит native/CUDA-библиотеки CTranslate2 |
| `sip-bot-demo-web` | `sipbot`; `python -m backend.server`, `PYTHONPATH` проекта | Локальные HTTP `8080`/HTTPS `8443`, загрузка корпуса и управление демо-сессиями |

Команды оператора после создания unit-файлов:

```bash
systemctl daemon-reload
systemctl enable --now sip-bot-ollama.service
curl -fsS http://127.0.0.1:11434/api/tags
systemctl enable --now sip-bot.service
journalctl -u sip-bot.service -f
```

В первом cold start бот **не прошёл** подготовку: новый GPU-хост ещё загружал модель, и первое обращение к Ollama оборвалось по обычному live-таймауту `30 s`. Это не основание отвечать на звонок неподготовленным ботом. В [`config/constants.py`](../../../config/constants.py) отделён `LLM_WARMUP_READ_TIMEOUT_S=120.0` от live `LLM_READ_TIMEOUT_S=30.0`, а в [`tools/run_live_bot.py`](../../../tools/run_live_bot.py) warmup использует отдельный HTTP facade. После прогрева создаётся обычный live facade; ожидание долгого первого ответа **не увеличивает** допускаемую задержку очередного вопроса клиента. Для мастер-класса нужна эта поправка в исходниках; в исходном Git commit `6be81a…` её ещё нет.

Второй cold-start дефект: `tools/run_live_bot.py` ставил `TARGET_SITE` раньше окружения XTTS. Там обнаружился `tokenizers 0.23.1`, несовместимый с ожидаемым `0.22.2`; поправлен приоритет путей — `TARGET_SITE` теперь добавляется *после* XTTS site. Проверены импорт модели и GIL-off. Исправлено также неверное название профиля в сообщении о готовности. Это именно исправления кода этого прогона, не неявная установка других пакетов.

Ожидаемый порядок в журнале сервиса: warmup RAG/LLM/ASR/TTS, затем инициализация SIP, затем `SIP registration ready` и `assistant available: account=1002 queue=7100`. Проверка со стороны FreeSWITCH:

```bash
fs_cli -x 'sofia status profile bot-vpn'
fs_cli -x 'show registrations'
fs_cli -x 'callcenter_config queue list'
```

После исправлений: оба systemd-сервиса `active`, бот зарегистрирован как `1002@192.168.1.74`, одна линия бота в очереди `science-bot@default`. Пока бот не прогрелся и не зарегистрировался, FreeSWITCH не может подать ему вызов из очереди.

## 7. Локальная HTTPS-страница, WSS и загрузка RAG — исполнено частично по уровню проверок

Для локального стенда сгенерирован **самоподписанный** сертификат с SAN для `192.168.1.74`, `172.16.15.72` и `localhost` (срок 30 суток); ключ находится только внутри WSL в `demo-web/runtime/tls/`. Глобальное хранилище доверенных сертификатов Windows не менялось. FreeSWITCH ожидает combined PEM для WSS и слушает `7443`; сайт слушает `8443`. Веб-приложение использует HTTPS/WSS, иначе браузер не выдаст микрофон. Участнику потребуется вручную доверить сертификат *для своего стенда*, не использовать этот ключ где-либо ещё. В этом прогоне выполнены следующие содержательные действия:

```bash
mkdir -p /home/sipbot/sip-bot/demo-web/runtime/tls
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 30 \
  -keyout /home/sipbot/sip-bot/demo-web/runtime/tls/demo.key \
  -out /home/sipbot/sip-bot/demo-web/runtime/tls/demo.crt \
  -subj /CN=192.168.1.74 \
  -addext 'subjectAltName=IP:192.168.1.74,IP:172.16.15.72,DNS:localhost'
openssl pkcs12 -export \
  -inkey /home/sipbot/sip-bot/demo-web/runtime/tls/demo.key \
  -in /home/sipbot/sip-bot/demo-web/runtime/tls/demo.crt \
  -out /home/sipbot/sip-bot/demo-web/runtime/tls/demo.p12 \
  -passout pass:workshop
openssl pkcs12 -in /home/sipbot/sip-bot/demo-web/runtime/tls/demo.p12 \
  -nodes -out /home/sipbot/sip-bot/demo-web/runtime/tls/wss.pem \
  -passin pass:workshop
```

`wss.pem` установлен в контейнер FreeSWITCH как `/etc/freeswitch/tls/wss.pem`; предшествующий файл сохранён в том же контейнере с суффиксом `.pre-workshop-20260929`. Для учебного повтора смысл действий — проверить существующий `/etc/freeswitch/tls/wss.pem`, сохранить исходный вариант, установить только что сгенерированный combined PEM с доступом для `freeswitch`, затем `systemctl restart freeswitch` и проверить `ss -lntp | grep 7443`. **Копировать сюда чьи-то закрытые ключи нельзя.**

В локальном клоне `demo-web/frontend/demo-config.js` заменён на [локальную конфигурацию](demo-config-local.js), где публичный адрес страницы определяется через `window.location`, WSS идёт на тот же host порт `7443`, `sipDomain=192.168.1.74`, пользователь `1000`, пароль `Workshop-2026!`, цель `sip:7100@192.168.1.74`. Исходная публичная конфигурация `demo.libnas.ru` в Windows-репозитории не менялась. Локальный QR создан командой:

```bash
qrencode -o /home/sipbot/sip-bot/demo-web/frontend/assets/qr-local-workshop.png \
  'https://192.168.1.74:8443/'
systemctl enable --now sip-bot-demo-web.service
curl -kfsS https://127.0.0.1:8443/api/session
```

HTTP/HTTPS `GET /` и `/static/demo-config.js` вернули `200`, локальный QR доступен с `200`; WSS handshake с SIP-subprotocol на `172.16.15.72:7443` вернул `101 Switching Protocols`. На этом хосте Windows клиент смог открыть HTTPS на VPN-адресе `172.16.15.72:8443`; LAN-адрес `192.168.1.74:8443` с Windows timeout из-за топологии WSL mirrored. Поэтому QR с LAN-адресом **пока нельзя считать проверенным пользовательским путём с этого компьютера**. Перед мастер-классом надо проверить фактический адрес, по которому браузеры участников достигают WSL, и пересоздать QR для него. Полный браузерный WebRTC audio-call здесь не проводился.

Отдельно испытан RAG import: через API создана сессия, загружен `config/workshops/rag/corpus/pricing-and-terms.md`, сервер принял файл (`202`), построил индекс и сообщил `state=ready`, `call_enabled=true`. Повторить это вручную можно следующими запросами (после первого перенести выданный `session_id` во второй):

```bash
curl -kfsS https://127.0.0.1:8443/api/session
curl -kfsS -F 'file=@/home/sipbot/sip-bot/config/workshops/rag/corpus/pricing-and-terms.md' \
  https://127.0.0.1:8443/api/session/SESSION_ID/upload
curl -kfsS https://127.0.0.1:8443/api/session/SESSION_ID
```

`-k` здесь допустим только для локального самоподписанного лабораторного сертификата. CLI-проверка не держала WebSocket heartbeat, и примерно через 15 секунд её сессия перешла в `stale`; это не ошибка индексатора. Веб-страница держит heartbeat. **Разговор с загруженной именно через веб-страницу новой базой здесь ещё не выполнен** — проверены API/индекс и отдельно SIP-разговор на базовом индексе.

## 8. Контрольный SIP-звонок — исполнено

Для контролируемого прогона взят Baresip из Ubuntu, зарегистрированный на FreeSWITCH как `1000@192.168.1.74:5060`, и локально записанный ранее речевой WAV длительностью 85,28 с, 8 kHz mono PCM16, SHA-256 `5a0b7c000756f3f3c49e9dcee5d9d44d6a42835d4ad522c02e39da840f09c396`. Этот WAV — **внутренняя тестовая фикстура, не опубликованный интернет-ресурс**. Поэтому команду копирования фикстуры из нашего локального хранилища в учебном рецепте не приводим и вымышленную ссылку для скачивания не подставляем. Слушатель повторяет проверку с реальным MicroSIP и микрофоном или с собственным PCM WAV. Доступные для сверки Baresip-параметры — [`config`](baresip-peer/config), [`accounts`](baresip-peer/accounts); пароль `Workshop-2026!` исключительно лабораторный.

На работающем стенде порядок действий таков:

```bash
# Терминал Baresip; при живом микрофоне задайте своё audio_source в config.
baresip -f /home/sipbot/baresip-workshop -t 150
# В консоли Baresip набрать d sip:7100@192.168.1.74:5060
```

Перед звонком проверить `fs_cli -x 'show registrations'`: должны присутствовать `1002` (бот) и `1000` (тестовый абонент). Во время звонка `fs_cli -x 'show channels'` показал две активные PCMU-стороны FreeSWITCH (caller→queue и queue→bot); на стороне Baresip наблюдались 4301 исходящий и 4173 входящих RTP-пакета без ошибок. По окончании `fs_cli -x 'show calls count'` вернул `0 total`.

Бот выдал приветствие, обработал несколько пользовательских фраз через ASR и RAG, синтезировал ответы TTS и создал текстовый отчёт. FreeSWITCH сохранил стереозапись разговора `85,36 s`, `2 channels`, `8000 Hz`, `PCM16`; её копия — [контрольная запись](control-call-stereo.wav), SHA-256 `5ca3cb3167d86fb39f7e7ef7a05449c5166335f3278b7c78a73638b05410a348`. Рядом лежат [отчёт](control-call-report.md), SHA-256 `f59e477b18c657e89ec3fa777c489a4de5bc4169174a5ea095b00d2d0d257c14`, и [история фраз/событий](control-call-conversation.jsonl). Таким образом, в **этом прогоне** доказаны SIP-регистрация, вызов через очередь 7100, PCMU/RTP, ASR, Qwen/RAG-решение об отказе, TTS, запись PBX и формирование отчёта. Не подменять эти факты общим утверждением «всё работает».

Содержимое ответов в данном звонке выявило ещё одну границу качества: на вопросы «Сколько стоит диагностический выезд мастера?», «А ночью сколько будет стоить?» и «Какие данные нужны для заявки?» бот говорил, что база знаний недостаточна, и предлагал оператора. Контрольный вопрос «Почему небо днём голубое?» также не относился к загруженному телеком-корпусу. Диагностика отчёта показывает `insufficient_lexical_support`; это не сбой SIP/TTS. Для мастер-класса по своей базе нужно действительно загрузить релевантный корпус и задать контрольные вопросы из него.

Особенно важно: финальное `transfer_completed / operator_connected` в отчёте **не является подтверждением реального соединения с оператором**. В текущем live runner используется `FakeOperator` и `TransferOrchestrator`; после решения моделью процесс инициирует `sip_media.transfer(...)`, но результат fake-orchestrator отмечается до подтверждения реального SIP REFER. Более того, сейчас `OPERATOR_TARGET=sip:operator@127.0.0.1:5090`, а очередь живых операторов FreeSWITCH находится на `7000`. Проверенного прохождения REFER до живого `1001` здесь не было. Нельзя демонстрировать участникам «успешный перевод на оператора» на основании этого отчёта; это отдельная интеграционная доработка/проверка.

## 9. Холодный рестарт и итоговая матрица

После звонка WSL-дистрибутив `SIP-Bot-Workshop-20260929` **один раз остановлен и вновь запущен** без активных вызовов. При перезапуске `sip-bot-ollama`, `sip-bot`, `sip-bot-demo-web`, `systemd-nspawn@freeswitch-bookworm` сообщили `active`, контейнер `freeswitch-bookworm` появился в `machinectl list`. Затем журнал бота подтвердил не только `active`, но и `application warmup completed elapsed_ms=36238.787 stages=5`, `SIP registration ready` и `assistant available: account=1002 queue=7100`; `fs_cli -x 'show registrations'` внутри Debian снова показал `1002@192.168.1.74`. Это проверяет успешный холодный рестарт с retry-drop-in. WSL сам прекращает работу при отсутствии удерживающего процесса/терминала, поэтому для длительной демонстрации WSL необходимо оставить запущенным; включённый systemd unit не делает WSL самостоятельным Windows-сервисом.

Тесты изменённого кода: узкий набор `test_runtime_readiness.py`, `test_llm_facade.py`, `test_llm_http.py` в новой WSL — `10 passed`; полный набор `tests/unit tests/contract demo-web/tests` на исходном проекте в combined Python — `292 passed` (10 предупреждений aiohttp `NotAppKeyWarning`). В локальном *клоне стенда* тот же полный набор дал `291 passed, 1 failed`: тест `test_frontend_public_urls.py` специально закрепляет адрес публичного сайта `https://demo.libnas.ru/`, а клон намеренно переключён на локальный HTTPS/WSS. Это **конфликт теста публичной конфигурации с локальной конфигурацией стенда**, не ошибка API звонка; в основном проекте тест остался зелёным. Проверка `tools/check_document_registry.py` выявила две уже существовавшие незарегистрированные страницы `docs/handoffs/HANDOFF-2026-09-24.md` и `HANDOFF-2026-09-25.md`; это не созданные данным развёртыванием документы, реестр здесь не изменялся.

| Проверка | Результат этого прогона |
|---|---|
| Чистая Ubuntu 24.04.5 WSL + отдельный Debian Bookworm FreeSWITCH | Выполнено, без изменения других WSL и Docker |
| FreeSWITCH, `mod_callcenter`, две очереди, PCMU | Выполнено; пакетная версия `1.11.3-release-33213556856-ef32e20529~bookworm~amd64-1~bookworm+1` |
| Модели, no-GIL и патченные native-модули | Файлы восстановлены из проверенной локальной копии; хеши и импорты проверены; **интернет-пересборка не исполнялась** |
| Warmup перед SIP-регистрацией, односессионный бот | После двух исходных исправлений выполнено; контрольный звонок через очередь 7100 прошёл |
| Baresip/FreeSWITCH стереозапись и отчёт | Выполнено, вложены в этот каталог |
| Веб API и импорт нового корпуса | `ready` получено; звонок с этим корпусом не проводился |
| HTTPS/WSS | HTTP 200, WebSocket 101; браузерный аудиозвонок не проверен, локальный QR-адрес зависит от сети |
| Перевод на живого оператора | **Не доказан**, несмотря на строку `transfer_completed` в отчёте |

Запас места после создания WSL и локальных архивов на `D:` — около `180,6 GiB`; внутри новой Ubuntu корневой раздел использует около `34 GiB`, размер её `ext4.vhdx` на Windows — `37 263 245 312` байт. Страховочные копии находятся в `D:\sip-bot-workshop-cache\20260929`; новая WSL — в `D:\WSL\SIP-Bot-Workshop-20260929`. Эти каталоги не удалены. Лабораторные логины/пароль, сертификат и адреса относятся к стенду и должны быть изменены для чужой сети.
