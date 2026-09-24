# Журнал развёртывания FreeSWITCH на отдельном сервере

Цель: `inrack@10.0.0.45` (`a100-test`), Ubuntu 22.04.5 LTS. Дата проверки: 22 сентября 2026 года. Это **другое** развёртывание, не Debian WSL из Map-011.

Журнал восстановлен по сохранённым выводам команд и [сводному отчёту](README.md), а не по полной записи терминала. Где точная историческая команда не сохранилась, приведены только действие и наблюдённый результат; примеры команд проверки обозначены отдельно. Пароли в журнале не публикуются. Это отчёт о сделанном, не готовый скрипт повторной установки.

## 1. Проверка пакетной платформы — Ubuntu host

**Задача:** понять, можно ли поставить FreeSWITCH из предоставленного владельцем Debian-репозитория прямо в Ubuntu 22.04.

На хосте подключили `http://fi.itlnk.ru/freeswitch bookworm main`, обновили пакетный индекс и проверили пакетный план без установки. В [журнале симуляции](apt-install-simulation.log) видны несовместимости: `libopencore-amrnb0`, `libspeexdsp1`, `libjpeg62-turbo`, `libtiff6`. Решение — **не смешивать** пакеты Bookworm с системными библиотеками Jammy. Это зафиксировано в [platform-decision.txt](platform-decision.txt). После выбора иной схемы источник Bookworm с Ubuntu host удалили; сохранён [результат обновления apt](host-apt-update-after-source-removal.log).

## 2. Создание Debian Bookworm — Ubuntu host и гостевая машина

**Задача:** сохранить пакетную установку FreeSWITCH, не менять ОС физического сервера и не использовать Docker или сборку FreeSWITCH из исходников.

На Ubuntu host установлены `systemd-container`, `debootstrap`, `libnss-mymachines` ([вывод установки](host-container-tools-install.log)). Первая попытка создать Bookworm с проверкой подписи завершилась сообщением `Release signed by unknown key` ([журнал](debootstrap-signed.log)); после установки Debian keyring и повторной подготовки [базовая система была создана](debootstrap.log). Для итоговой машины сохранены [источник и SHA-256 rootfs](rootfs-provenance.txt): ожидаемый и фактический хеши совпали.

Гостевая Debian 12 размещена в `/var/lib/machines/freeswitch-bookworm`. На хосте включена `systemd-nspawn@freeswitch-bookworm.service`, внутри гостя — обычная `freeswitch.service`. [Постоянная nspawn-конфигурация](freeswitch-bookworm.nspawn) задаёт `Boot=yes`, общий сетевой namespace (`VirtualEthernet=no`) и read-only привязку проектного каталога в `/srv/sip-bot`. [Снимок проверки](host-and-container-service.txt) подтверждает, что host unit включён и активен, а гостевая ОС — Debian 12. По [сводному отчёту](README.md), проверка включала полный перезапуск гостевой машины.

Проверочные команды для этой границы (не заявляются как дословный исторический ввод):

```bash
systemctl is-enabled systemd-nspawn@freeswitch-bookworm.service
systemctl is-active systemd-nspawn@freeswitch-bookworm.service
machinectl status freeswitch-bookworm
```

## 3. Установка FreeSWITCH — Debian guest

**Задача:** поставить пакеты из подписанного Bookworm-зеркала, включая `mod_callcenter`.

Подключено предоставленное владельцем зеркало `http://fi.itlnk.ru/freeswitch bookworm main` с проверкой подписи. [Сохранённый отпечаток ключа](signing-key.txt): `655DA1341B5207915210AFE936B4249FA7B0FB03`. [APT policy](apt-policy.txt) и [статус пакетов](package-status.txt) подтверждают FreeSWITCH `1.11.3` и установку `freeswitch-meta-vanilla`, `freeswitch-systemd`, `freeswitch-mod-callcenter` из этого репозитория.

Первый [журнал пакетной установки](freeswitch-package-install.log) **заканчивается ошибкой**: post-install `ssmtp` вернул код 1, вследствие чего не сконфигурировались `freeswitch-mod-voicemail` и `freeswitch-meta-vanilla`. Позднейшая проверка показывает установленную и работающую FreeSWITCH, но точный вывод команды устранения ошибки `ssmtp` **не сохранён**. По этим артефактам нельзя честно восстановить её как факт. Это пробел в воспроизводимом сценарии, который следует закрыть отдельной проверкой перед мастер-классом.

## 4. Конфигурация и автозапуск — Debian guest

**Задача:** поднять SIP-сервис и очередь оператора в конфигурации мастер-класса.

На дату серверной проверки использованы проектные `callcenter.conf.xml` и `20_workshop_callcenter.xml`; их серверные SHA-256 записаны в [freeswitch-validation.txt](freeswitch-validation.txt). Там же подтверждены готовность FreeSWITCH, загруженные `mod_sofia` и `mod_callcenter`, очередь `support@default`, callback-agent `1001@default`, tier `Ready`. Номер `7000` направлялся в эту очередь. Гостевая `freeswitch.service` включена и активна. [Сетевая проверка](network-validation.txt) показывает общий адрес `10.0.0.45` у хоста и гостя, UDP listeners `10.0.0.45:5060` и `:5080`.

Примеры команд для повторной **проверки**, соответствующие сохранённым полям вывода:

```bash
machinectl shell root@freeswitch-bookworm /bin/bash
systemctl is-enabled freeswitch
systemctl is-active freeswitch
fs_cli -x status
fs_cli -x 'module_exists mod_sofia'
fs_cli -x 'module_exists mod_callcenter'
fs_cli -x 'callcenter_config queue list'
fs_cli -x 'callcenter_config agent list'
fs_cli -x 'callcenter_config tier list'
```

Точный исторический ввод команд копирования конфигов и перезапуска сервиса в артефактах отсутствует. Нынешний `tools/workshops/configure_freeswitch_workshop.sh` уже изменился после этой проверки и не должен выдаваться за её точную стенограмму.

## 5. Регистрация и вызовы — внешние и серверные SIP-клиенты

**Задача:** проверить достижимость SIP снаружи, прямой звонок и очередь.

1. Внешний MicroSIP зарегистрировался как `1000@10.0.0.45`: статус `Registered(UDP)`, `Reachable` ([регистрация](microsip-registration.txt)). Позже [одновременно зарегистрированы](two-microsip-registrations.txt) MicroSIP `1000` и `1001`.
2. Прямой `1000 → 1001`: [два канала после ответа](local-direct-active.txt) — `ACTIVE`, PCMU/8 kHz в обоих направлениях.
3. Очередь `1000 → 7000 → support@default → 1001`: [до ответа](local-queue-before-answer-members.txt) член очереди имел состояние `Trying`; [после ответа](local-queue-after-answer-members.txt) — `Answered`, [агент](local-queue-after-answer-agent.txt) — `In a queue call`, [каналы](local-queue-after-answer-channels.txt) — два `ACTIVE`, PCMU/8 kHz.
4. После проб вызовы и регистрации были очищены. Субъективная слышимость на этом headless-сервере отдельно не проверялась. Неудачный ранний локальный Baresip REGISTER (`400 Bad Contact Header`) сохранён в [baresip-register.log](baresip-register.log) как отвергнутая проба, а не как итог SIP-проверки.

Проверочные команды FreeSWITCH для этапа звонков:

```bash
fs_cli -x 'sofia status profile internal reg'
fs_cli -x 'show channels'
fs_cli -x 'callcenter_config queue list members support@default'
fs_cli -x 'callcenter_config agent list 1001@default'
```

## Граница отчёта

Этот журнал описывает состояние **22.09.2026**: одна очередь `support@default`, агент-оператор `1001`, номер `7000`. Он не утверждает, что позднейшая очередь бота, регистрация бота и последующие правки NAT/STUN уже были частью исходной серверной установки. Более поздние действия надо сопоставлять с их собственными артефактами. Сводка общего развёртывания Ubuntu 22.04, включая runtime бота и RAG, находится [уровнем выше](../README.md).
