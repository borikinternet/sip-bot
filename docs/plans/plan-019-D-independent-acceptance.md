# План 019-D: независимая приёмка двух WSL-дорожек и сравнение

Уровень: `child plan`  
Статус: `proposed; не исполнялся`  
Owner review: `pending вместе с Map-019`  
Родитель: [`Map-019`](plan-019-dual-wsl-freeswitch-live-masterclass.md)  
Зависимости: [`019-A`](plan-019-A-dual-wsl-preflight.md), [`019-B`](plan-019-B-packages-and-sip.md), [`019-C`](plan-019-C-two-queues.md) complete

## Цель и граница

Ведущий после окончания обоих исполнений одинаково проверяет две установки, фиксирует raw evidence, отличает активную работу от ожидания эксклюзивного окна и готовит честное сравнение на завершающий слайд мастер-класса. Отчёт агента не является доказательством без повторной проверки. Работа этого плана — финальный gate, не новая функция FreeSWITCH и не подключение SIP-бота.

## Materialized rules и source-map

| Источник | Правило | Применение / проверка | Stop condition |
|---|---|---|---|
| [APG](../architectural-planning-gate.md) §§5.7–5.10 | Closeout требует фактического diff/команд/exit codes, blocker и evidence | Отдельный manifest каждой дорожки, audit карты | Срез объявлен complete без acceptance |
| [Development guidelines](../development-guidelines.md) §§4, 6–9 | Главный executor проверяет handoff; красный gate не компенсируется зелёным соседней дорожки; статус child бинарен | Повторные direct и queue calls, raw logs и human hearing | Самоотчёт агента принят без проверки |
| [Documentation process](../documentation-process.md) §6 | Новые факты в новом отчёте; registry/backlog audit после Markdown | Не править исторические Map-011/evidence | Исторический log выдан за новый |
| [Map-019](plan-019-dual-wsl-freeswitch-live-masterclass.md) §§3, 8 | Общая сеть сериализует live gates; обе дорожки получают один acceptance | Timestamp окна и активного времени отдельно | Неясно, к какому WSL привязан вызов |

Write-set: только будущий `artifacts/workshops/freeswitch-dual-wsl-019/019-D/`, фактические status/evidence поля этих plan-файлов, document registry/roadmap/backlog после проверки главным исполнителем. Runtime: Windows/WSL/Debian/FreeSWITCH/MicroSIP; Python/GPU/RAG неприменимы. Поведение сравнения и распределение live windows принадлежит ведущему, а не агенту.

## Порядок и acceptance

1. Сверить отсутствие пересечения agent/human файлов, пакетов и MicroSIP INI; у каждого — своё имя WSL, сервис, installed config, подписанный пакет, `dpkg --audit` без ошибок.
2. В окне H выполнить clean restart своего WSL, проверить service/module/две регистрации/direct PCMU call/операторскую очередь и человеческую слышимость; затем освободить сокеты.
3. В окне A повторить **те же** проверки независимо. До live call проверить `ss` и `sofia status`, чтобы не попасть на чужой FreeSWITCH. Акустику подтверждает человек.
4. Проверить `7100` только как загруженный маршрут к `science-bot@default` и агенту `1002`; бот не должен ошибочно значиться прошедшим звонок.
5. Сопоставить timestamp начала, готовности конфигурации, ожидания окна, прямого звонка, очереди и финального closeout. Вывести две строки с pass/fail по одинаковым критериям; причину расхождения объяснить evidence. Отдельно указать pre-existing и out-of-scope findings.
6. Выполнить document registry/task backlog audit. Карта complete только если все A–D полностью complete и закрыты map-level gates. Любой настоящий blocker имеет ID, owner, raw evidence и условие снятия; частичный итог не маскировать.

Evidence: два независимых SIP/channel/queue журнала, installed config hashes, exit codes, человеческое audio confirmation, календарь активного/ожидаемого времени, final comparison и scope audit. Точное место файлов задаётся при исполнении в новом evidence root; сейчас никаких готовых результатов нет.

## Blocker register и closeout

| ID | Триггер | Что блокирует | Owner | Проверка/снятие | Статус |
|---|---|---|---|---|---|
| B-019-D-1 | Нельзя доказать, к какому WSL подключился MicroSIP | Сравнение результатов | ведущий | SIP server address/port, `ss`, FS unique log и повтор | `open until live gate` |
| B-019-D-2 | Один стенд не проходит обязательный звонок/звук после corrective pass | Финальный closeout | ведущий | Raw trace и повтор; статус `blocked` при реальном impasse | `open until gate` |
| B-019-D-3 | Время ожидания смешано с активной работой | Корректность сравнения | ведущий | Timeline по timestamp обоих окон | `open until audit` |

Fallback/deferred: `none`. Execution report и сравнение не предзаполнены; этот документ остаётся планом до фактического мастер-класса.
