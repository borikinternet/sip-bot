# План 009-C: локальный FreeSWITCH и сценарий зарегистрированного SIP-абонента

Уровень документа: `child plan`  
Идентификатор: `009-C`  
Статус: `complete` — SIP/media C4 и C6, corrective `009-C2` R1–R5 и Baresip recording gate выполнены по APG  
Родитель: [`plan-009-optional-sip-registration.md`](plan-009-optional-sip-registration.md)  
Предшественник: [`plan-009-B-pjsua2-registration-lifecycle.md`](plan-009-B-pjsua2-registration-lifecycle.md)  
Дата: `2026-09-13`  

## 1. Цель и проверяемый результат

Подготовить воспроизводимый локальный FreeSWITCH-стенд для мастер-класса и показать, что SIP-бот может работать
как зарегистрированный endpoint. После исполнения:

- локальный FreeSWITCH предоставляет registrar и две демонстрационные SIP-учётные записи;
- бот регистрируется по включённому профилю из `config/constants.py`;
- тестовый Baresip/аналогичный peer вызывает зарегистрированный endpoint по extension/URI;
- входящий вызов проходит через уже принятые answer, PCMU/RTP, speech/AI и report boundaries;
- выключение регистрации возвращает исходный direct-URI сценарий;
- failure enabled-mode виден явно и не превращается в скрытый fallback;
- пользовательский guide содержит команды подготовки, запуска, проверки и warmup.

Этот plan не реализует production PBX, call-center routing, внешнюю регистрацию, TLS/SRTP, multi-call или
новые AI/media компоненты. Исправление дефекта inbound answer вынесено в отдельный corrective child plan
[`009-C1`](plan-009-C1-inbound-answer-readiness-gate.md); после его closeout C4 повторён, а C6 остаётся следующим
обязательным срезом. При full-AI registered replay обнаружена ошибка порядка test harness: входящий SIP adapter формирует
`call-in-0`, а существующий J4 composition заранее открывался с id `j4-full-live-call`. Corrective `009-C2` сначала
принимает фактический `CALL_STARTED`, затем создаёт composition с его ID; подмена id в probe запрещена.

## 2. Входные решения и materialized rules

| Источник | Правило/решение | Применение |
|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Работы имеют source-map/write-set, blocker register, test/evidence gate и binary closeout | Структура этого plan |
| [`development-guidelines.md`](../development-guidelines.md) | Ошибка исправляется corrective pass; намеренное упрощение запрещено; public artifacts не должны выдавать stub за live | Live stand и evidence |
| [`technical-specification.md`](../technical-specification.md) | Local workshop configuration и test credentials находятся в constants; production secret store вне MVP | FreeSWITCH account fixture и guide |
| [`architecture.md`](../architecture.md) | SIP signaling принадлежит adapter; PCM/RTP и text/data path не транзитируют Dispatcher | Integration audit |
| Map-009/009-A | Registration optional/default-off; типовой public demo credential коммитится | Two-mode checks |
| Map-009/009-B | Enabled failure → readiness=false без direct fallback; typed status events | Negative/positive gate |
| `001-S` и Map-005 | Baresip/local peer, PCMU, stereo recording/evidence уже являются accepted test infrastructure | Не дублировать и не менять peer contract без gap |

## 3. Scope

1. Выбрать и зафиксировать локальный способ запуска FreeSWITCH на target Linux (предпочтительно уже доступный
   Docker/WSL workflow; не требовать внешнего PBX).
2. Добавить минимальный reproducible registrar/route fixture с ботом и peer/operator accounts.
3. Добавить команды проверки SIP registration и входящего вызова.
4. Выполнить registered incoming call через существующий адаптер и текущие negotiated PCMU/RTP/AI boundaries.
5. Выполнить disabled direct-URI regression и enabled registration failure negative scenario.
6. Обновить `docs/user-guide.md`, `docs/architecture.md`, `docs/technical-specification.md` и evidence index
   только в части фактического workshop workflow.
7. Сохранить raw FreeSWITCH/PJSUA2/Baresip logs, registration status, call evidence и recording artifacts.

## 4. Защищённый baseline

- Один бот и один параллельный разговор.
- `SipMediaAdapter` остаётся владельцем SIP registration/call protocol reactions.
- FreeSWITCH — только local test/workshop environment; его внутренний call routing не становится application logic.
- Бот не пересылает PCM через event bus; PCMU/RTP и negotiated per-call ptime остаются прежними.
- AI warmup выполняется до финального допуска вызова; provisional `180` может быть отправлен до warmup, а отсутствие
  warmup не маскируется как SIP failure.
- Публичный demo password допустим в committed constants/fixture; production credentials не используются.

## 5. Source-map и write-set

### Разрешено

- новый каталог `tools/freeswitch_workshop/` с compose/config/scripts и проверками;
- `tools/freeswitch_workshop/registered_full_rehearsal.py` — диагностический full-AI registered replay harness;
- новые fixture/evidence manifests под `artifacts/workshop/registration/`;
- `docs/user-guide.md`, `docs/architecture.md`, `docs/technical-specification.md` — только связанные additions;
- `tests/integration/test_registered_sip_workshop.py` или узкие аналогичные tests;
- этот plan-file, registry/backlog/roadmap updates — main executor при closeout.

### Не разрешено

Не менять `config/constants.py`/registration profile (009-A), PJSUA2 lifecycle (009-B), Dispatcher/FSM, AI/media
components, accepted Baresip baseline и production deployment. Если container image, FreeSWITCH module или target
environment недоступны, не подменять их fake-only pass: оформить blocker с raw diagnostics.

## 6. Интеграционный контракт

```text
FreeSWITCH registrar
  ├─ REGISTER/401/200 ↔ SipMediaAdapter (enabled profile)
  ├─ INVITE registered bot endpoint → existing SipMediaAdapter
  └─ PCMU/RTP ↔ existing negotiated media bridge ↔ existing speech/AI path

Baresip test peer → FreeSWITCH extension → registered bot
```

Регистрация проверяется как отдельный control-plane факт до вызова. Успешный `REGISTER` не считается доказанным
только наличием TCP/UDP listener; нужен status evidence и реальный INVITE на зарегистрированный endpoint.

## 7. Срезы и зависимости

| Срез | Действие | Обязательное evidence | Следующий |
|---|---|---|---|
| C1 | Preflight target Linux/Docker/FreeSWITCH availability и disk budget | versions, paths, free space, raw preflight output | C2 |
| C2 | Создать minimal registrar/accounts/routes fixture | config, checksum, startup log, SIP listener check | C3 |
| C3 | Запустить бот enabled и доказать REGISTER/auth/status | registration trace без password, readiness event | C4 |
| C4 | Вызвать зарегистрированный endpoint и пройти SIP/media path | call trace, `180 → readiness → 200`, PCMU/RTP evidence, recording artifact | C5; после `009-C1` |
| C5 | Проверить disabled mode и enabled failure/no fallback | negative evidence + direct regression | C6 |
| C6 | Обновить workshop guide и runbook, провести clean-start replay | exact commands, exit codes, artifacts manifest | Closeout |

C1/C2 могут готовиться параллельно как документационная подготовка, но C3 начинается только после green handoff
`009-B` и подтверждения target environment. Исходный protocol/media C4 был заблокирован до полного closeout `009-C1`,
затем успешно повторён; runbook C6 также закрыт. Full-AI registered C4 завершён corrective `009-C2`, включая
динамическую composition по фактическому call id и Baresip recording.

## 8. Blocker register

| ID | Триггер | Что блокируется | Статус |
|---|---|---|---|
| `B-009-C-001` | На target нет воспроизводимого способа поднять local FreeSWITCH registrar/route | Workshop registered mode | `none until triggered` |
| `B-009-C-002` | Container/image/download требует недоступного внешнего ресурса или нарушает disk budget | C1/C2 | `none until triggered; diagnostics and safe alternative required` |
| `B-009-C-003` | REGISTER успешен, но INVITE registered endpoint не проходит после corrective pass | Map-009 closeout | `none until triggered` |
| `B-009-C-004` | Registered call ломает accepted PCMU/RTP/AI path | Map-009 closeout | `resolved: 009-C1 closeout and registered-call-r7.json; explicit 180/200 path, PCMU/RTP and no abort pass` |
| `B-009-C-006` | Full-AI registered replay создавал composition до фактического incoming `CALL_STARTED`, поэтому ID не совпадал | Full-AI registered C4 и Map-009 closeout | [`plan-009-C2-runtime-readiness-coordination.md`](plan-009-C2-runtime-readiness-coordination.md): event-driven composition и shared readiness corrective pass | `resolved: target r15 actual call-in-0` |
| `B-009-C-005` | Требуется production PBX/security scope вместо local workshop fixture | C scope | `none until triggered; owner review required` |

Отсутствие warmup или занятый lock-файл package manager не являются сами по себе blocker: сначала выполняются
предписанные retry/warmup/diagnostic actions. Внешняя невозможность target evidence после corrective attempts —
единственное основание для category-4 blocker.

## 9. Acceptance и closeout

`009-C` закрывается `complete`, только если:

1. local FreeSWITCH fixture поднимается чистым запуском и описан точными командами;
2. бот при enabled profile успешно регистрируется, status/readiness видны;
3. registered incoming call проходит через существующие SIP, PCMU/RTP, speech/AI и report boundaries;
4. disabled direct-URI и enabled failure/no-fallback сценарии подтверждены отдельно;
5. password не попадает в logs/evidence; committed demo credential явно помечен как public demo;
6. запись разговора и прочие обязательные artifacts сохранены по существующему stand contract;
7. guide и технические документы не обещают production behavior;
8. raw output, checksums, exit codes, changed files, corrective passes и residual gaps перечислены.

Partial/foundation статус запрещён. При незавершённом обязательном срезе — `blocked` с evidence и promotion condition.

## 10. Execution report contract

Closeout обязан указать target environment, способ запуска FreeSWITCH, fixture accounts (без маскировки public demo
credential под production), команды, exit codes, registration/call trace, recording/artifact paths, результаты
двух режимов и handoff в Map-009 closeout.

## 11. Execution checkpoint — 2026-09-13

- C1: выполнен. Docker/WSL/FreeSWITCH доступны; прямой `fs_cli -x status` завершился с exit code `0` и вернул
  `UP ... is ready`; контейнер `healthy`, `RestartCount=0`. Evidence:
  [`preflight-healthcheck.md`](../../artifacts/implementation/009-optional-sip-registration/009-C/preflight-healthcheck.md).
- C2: выполнен. Fixture pinned по image digest, содержит registrar, bot/peer accounts, explicit `7000` route и
  sanitized probe. Случайный startup password upstream image не принимается как evidence.
- C3: выполнен. В `registered-call-r1.json` зафиксирована успешная регистрация bot и peer; credential отсутствует
  в сохранённом выводе.
- Corrective pass: маршрут `7000` перенесён в prefixed `dialplan/00_sip_bot_workshop.xml`, чтобы он выбирался до
  vanilla `enum`; проверка FreeSWITCH log показала `bridge(user/tester@...)` и INVITE зарегистрированному endpoint.
- Исторический C4 blocker закрыт corrective plan [`009-C1`](plan-009-C1-inbound-answer-readiness-gate.md). Повторный
  registered-call C4: [`registered-call-r7.json`](../../artifacts/implementation/009-optional-sip-registration/009-C/registered-call-r7.json)
  — `pass`, exit code `0`; проверены `180 → readiness handoff → 200`, регистрация, `PCMU/8000/mono`, media start,
  отсутствие native abort и bounded ingress без overflow. Исходное failure evidence [`registered-call-r2.json`](../../artifacts/implementation/009-optional-sip-registration/009-C/registered-call-r2.json)
  сохранено исторически.
- C5: выполнен контрактными тестами: `5 passed`, exit code `0`; disabled direct-URI и enabled failure/no-fallback
  не регрессировали. Evidence: [`c5-registration-contract-output.txt`](../../artifacts/implementation/009-optional-sip-registration/009-C/c5-registration-contract-output.txt).
- C6: выполнен после снятия исходного C4 blocker. Clean-start replay: `docker compose down --remove-orphans` (exit `0`),
  `docker compose up -d --force-recreate` (exit `0`), FreeSWITCH `fs_cli -x status` (exit `0`) и fresh registered
  probe r8 (`status=pass`, exit `0`). Runbook добавлен в [`docs/user-guide.md`](../user-guide.md), machine-readable
  evidence: [`registered-call-r8.json`](../../artifacts/implementation/009-optional-sip-registration/009-C/registered-call-r8.json).
   Full-AI registered gate в clean-start r13 после runtime readiness `37.519 s` прошёл по AI/readiness path; ранее
   обнаруженная ошибка порядка test harness исправлена в `009-C2`. На r13 recording path ещё не был подключён, поэтому
   r13 сохранён как диагностический результат, а не как финальный closeout. Target r15 после corrective `009-C2/R4.1`
   доказал raw Baresip recording, stereo derivative и manifest без изменения bot-side media boundary.

Plan закрыт бинарно: `complete`. C6/runbook, SIP/media registered path, runtime/readiness composition и обязательный
Baresip recording acceptance подтверждены target r15; raw `enc`/`dec`, stereo derivative и manifest сохранены в
`artifacts/implementation/009-optional-sip-registration/009-C2/cold-20260913-r15/`. Исторические r1–r14 не
перезаписывались.
