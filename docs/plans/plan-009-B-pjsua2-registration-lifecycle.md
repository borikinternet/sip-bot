# План 009-B: lifecycle SIP-регистрации в PJSUA2

Уровень документа: `child plan`  
Идентификатор: `009-B`  
Статус: `complete` — execution завершено по APG  
Родитель: [`plan-009-optional-sip-registration.md`](plan-009-optional-sip-registration.md)  
Предшественник: [`plan-009-A-registration-config-contract.md`](plan-009-A-registration-config-contract.md)  
Дата: `2026-09-13`  

## 1. Цель и проверяемый результат

Реализовать в существующем `SipMediaAdapter` lifecycle SIP `REGISTER` для локального registrar/PBX через
утверждённый PJSUA2/PJMEDIA baseline. После исполнения:

- при `enabled=False` сохраняется существующий direct-URI режим;
- при `enabled=True` PJSUA2 получает registrar, identity и digest credentials из typed `RegistrationProfile`;
- registration refresh/expiry и штатный unregister принадлежат SIP adapter и не зависят от Dispatcher/LLM;
- наружу выдаются компактные typed registration status/readiness events без пароля;
- ошибка регистрации при включённом режиме делает readiness `false` и не включает скрытый direct-URI fallback;
- обязательные SIP protocol replies остаются callback-local.

Этот plan не настраивает FreeSWITCH, не реализует call-center и не изменяет PCM/RTP/AI data plane.

## 2. Входные решения и materialized rules

| Источник | Обязательное правило | Применение |
|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Child plan самодостаточен; closeout только `complete` или `blocked`; красная проверка требует corrective pass | Этот plan, blocker/evidence/closeout |
| [`development-guidelines.md`](../development-guidelines.md) | Native callback не ждёт control consumer; typed boundary; no silent fallback | Registration callbacks, event queue и negative test |
| [`architecture.md`](../architecture.md) | SIP adapter владеет SIP signaling; Dispatcher только наблюдает control events | Ownership audit |
| Map-009 | Registration optional/default-off; enabled failure → readiness=false без direct fallback | Acceptance |
| `009-A` | Единственный `RegistrationProfile`, constants-only config, public demo credential не логировать | Input contract |
| Owner decision 2026-09-13 | При включённой регистрации регистрация обязательна для readiness | Admission/readiness behavior |

## 3. Scope

1. Сформировать PJSUA2 `AccountConfig` из `RegistrationProfile`:
   `idUri`, registrar URI, digest `AuthCredInfo`, registration expiry.
2. Вызвать account registration через существующий `Account.create` lifecycle.
3. Обработать registration callback/status и нормализовать состояния минимум в `disabled`, `registering`,
   `registered`, `failed`, `unregistering`, `unregistered`.
4. Обеспечить штатные refresh/expiry semantics средствами PJSUA2/PJSIP либо зафиксировать фактическую границу
   поддержки evidence; не изобретать отдельный scheduler без необходимости.
5. Перед `account.shutdown()` выполнить unregister при enabled mode и безопасно переживать повторный close.
6. Добавить typed registration status/readiness events в существующую bounded control queue.
7. Добавить stub/contract tests, target no-GIL import/lifecycle probe и live evidence без тяжёлого AI inference.

## 4. Защищённый baseline

- PJSUA2/PJMEDIA patched no-GIL baseline из `plan-001-C1` остаётся обязательным.
- Единственный `SipMediaAdapter`, один account и ограничение одного активного вызова сохраняются.
- Direct-URI `make_call(peer_uri)` не меняется и не становится fallback-веткой enabled registration.
- `NormalizedSipEvent` остаётся компактным control payload: password и media bytes запрещены.
- Callback-local SIP reaction не вызывает Dispatcher, event sink или AI напрямую.
- Negotiated PCMU/RTP и существующий media bridge не изменяются.

## 5. Source-map и write-set

### Разрешено

- `src/sip_bot/sip_media/adapter.py`
- `src/sip_bot/sip_media/protocol_events.py`
- узкий новый `src/sip_bot/sip_media/registration.py` только при необходимости typed registration contract
- `tests/unit/test_sip_media.py`
- новый `tests/contract/test_registration_contract.py`
- отдельный target probe под `tools/` только для registration lifecycle, если нужен
- этот plan-file и execution evidence/closeout

### Не разрешено

Не менять `config/constants.py`/`src/sip_bot/config.py` (это `009-A`), Dispatcher/FSM/runtime admission
(кроме typed event emission, если это непосредственно SIP adapter contract), FreeSWITCH fixture, user guide,
AI/media components и Map-009. Не добавлять direct fallback, retry scheduler или новый IPC молча.

## 6. Boundary contract

### 6.1. SIP adapter → control plane

Typed status event включает только:

```text
state, enabled, registrar_uri_without_credentials, status_code, reason,
expires_seconds, expires_at/observed_at, sequence, readiness
```

URI должен быть очищен от userinfo/password. Event отправляется в существующую bounded очередь; переполнение
обрабатывается тем же явным drop/error policy, что и остальные adapter events.

### 6.2. Registration state machine

```text
disabled
   └─ enabled/start → registering → registered
                               ├→ failed
registered ── expiry/refresh ─→ registering → registered | failed
registered ── close ──────────→ unregistering → unregistered
failed ───── close ───────────→ unregistered
```

При `failed`/истёкшем registration в enabled mode: `readiness=False`; call admission запрещён; direct URI не
активируется автоматически. PJSUA2 transaction/reply выполняется native stack, event — только observation.

## 7. Срезы и зависимости

| Срез | Действие | Evidence | Следующий |
|---|---|---|---|
| B1 | Настроить PJSUA2 account registrar/auth из profile | stub account config без password, target no-GIL import | B2 |
| B2 | Нормализовать callback/status и state transitions | contract tests + raw callback trace | B3 |
| B3 | Проверить refresh/expiry/unregister | bounded target lifecycle evidence | B4 |
| B4 | Проверить enabled failure и отсутствие fallback | negative test + readiness evidence | B5 |
| B5 | Regression direct URI и existing SIP/media lifecycle | existing targeted suite | Closeout |

B1/B2 могут готовиться параллельно только при непересекающемся write-set; target execution и live evidence
выполняются после handoff `009-A`.

## 8. Blocker register

| ID | Триггер | Что блокируется | Статус |
|---|---|---|---|
| `B-009-B-001` | PJSUA2 baseline не позволяет задать registrar/auth/expiry без нового native API boundary | Registration | `none until triggered; patch/isolation analysis required` |
| `B-009-B-002` | Callback/status нельзя представить typed event без изменения Map-I contract | Status propagation | `none until triggered` |
| `B-009-B-003` | Enabled failure policy не определена | Readiness/admission | `resolved by owner decision 2026-09-13` |
| `B-009-B-004` | Target registration transaction не получает обязательного evidence после corrective pass | `009-B` | `none until triggered` |
| `B-009-B-005` | Registration path ломает direct-URI regression или negotiated PCMU/RTP | `009-B` | `none until triggered; corrective pass required` |

Ошибка unit/target test сама по себе не blocker: сначала сохраняется raw output, проводится corrective attempt,
затем повторяется тест. Category-4 blocker требует доказанного API/architecture gap или внешней невозможности.

## 9. Acceptance и closeout

`009-B` закрывается `complete`, только если:

1. enabled/disabled modes явно различаются и tested;
2. PJSUA2 получает typed registrar/auth/expiry configuration;
3. callback/status states представлены typed control events без credentials;
4. refresh/expiry и unregister имеют фактическое evidence или документированный tested scope;
5. enabled failure → readiness=false и не вызывает direct URI;
6. существующие direct-URI, SIP protocol, PCMU/RTP и media lifecycle tests зелёные;
7. no-GIL target import/lifecycle evidence сохранён;
8. raw outputs, changed symbols/files, corrective passes и handoff в `009-C` перечислены.

Partial/foundation статус запрещён. Незавершённость закрывается только `blocked` с проверяемым blocker и promotion condition.

## 10. Execution report contract

Closeout обязан указать PJSUA2 API fields/methods, фактическую state trace, команды и exit codes, target runtime/GIL,
положительные и отрицательные тесты, отсутствие password в output и ограничения, передаваемые `009-C`.

## 11. Execution report и closeout

Дата исполнения: `2026-09-13`  
Статус исполнения: `complete`  
Blocker: отсутствует.

### Фактически изменённые файлы

- `src/sip_bot/sip_media/adapter.py` — materialization `AccountConfig`, регистрационный lifecycle и readiness;
- `src/sip_bot/sip_media/protocol_events.py` — typed `REGISTRATION_STATE` event без media bytes/credentials;
- `src/sip_bot/sip_media/registration.py` — immutable `RegistrationStatus`, states/events и SIP URI redaction;
- `tests/unit/test_sip_media.py` — существующий SIP/media contract lane без изменения direct-URI assertions;
- `tests/contract/test_registration_contract.py` — PJSUA2 field mapping, callback state mapping, refresh/unregister,
  no-password и no-fallback tests;
- `tools/registration_lifecycle_probe.py` — target-only deterministic UDP digest registrar probe;
- `artifacts/implementation/009-optional-sip-registration/009-B/target-r4/registration-lifecycle.json` — target
  evidence.

`config/constants.py`, `src/sip_bot/config.py`, Dispatcher/FSM/runtime admission, FreeSWITCH, AI/media data plane и
документы пользовательского запуска не изменялись в рамках `009-B`.

### Материализованный PJSUA2 API

На принятом PJSUA2/PJMEDIA `2.17` API gap не обнаружен:

- `AccountConfig.idUri` получает `RegistrationProfile.identity_uri`;
- `AccountConfig.regConfig.registrarUri`, `registerOnAdd=True` и `timeoutSec` задают регистрацию и expiry;
- `AccountConfig.sipConfig.authCreds.push_back(AuthCredInfo("digest", "*", username,
  PJSIP_CRED_DATA_PLAIN_PASSWD, password))` задаёт digest credentials;
- `Account.onRegStarted(OnRegStartedParam)` даёт initial/unregister transaction boundary;
- `Account.onRegState(OnRegStateParam)` вместе с `Account.getInfo()` даёт SIP status, active flag и expiry;
- PJSUA2 сам выполняет refresh по `timeoutSec`; отдельный application scheduler не добавлялся;
- `Account.setRegistration(False)` вызывается перед `Account.shutdown()`.

### Evidence и exit codes

| Команда/проверка | Результат |
|---|---|
| `python -m pytest tests/contract/test_registration_contract.py tests/unit/test_sip_media.py -q` после corrective pass | `0`; `15 passed` |
| `python -m pytest tests/unit tests/contract tests/integration -q` | `0`; `177 passed, 5 skipped` |
| target probe r1 | `1`; устранён только ошибочный `-I` import path в probe |
| target probe r2 | `0`; базовая регистрация/unregister pass, stop condition расширена для обязательного refresh evidence |
| target probe r3 | `0`; refresh evidence pass |
| target probe r4 (итоговый) | `0`; [registration-lifecycle.json](target-r4/registration-lifecycle.json) |
| `git diff --check` по разрешённому source/test/probe write-set | `0` |

Итоговый target probe выполнен командой из [`command.txt`](target-r4/command.txt). Raw structured output сохранён в
`registration-lifecycle.json`; значения credentials и password в него не записываются.

### Фактическая state/protocol trace

Target `3.14.7t` / `Py_GIL_DISABLED=1` / `gil_enabled_at_finish=false` показал:

```text
registration_started → registration_succeeded(200, expires=2)
→ registration_refreshed(200, expires=2)
→ registration_unregistering → registration_unregistered
```

Минимальный UDP registrar получил 6 REGISTER requests: initial challenge, authenticated initial REGISTER,
refresh challenge, authenticated refresh, unregister challenge с `Expires: 0` и authenticated unregister с
`Expires: 0`. `enabled_direct_uri_fallback_blocked=true`, `password_in_output=false`, `gpu_inference=false`.

`registration_state` является call-independent control event с sentinel `call_id="__registration__"`; typed payload
содержит state/event/enabled/redacted registrar/status/reason/expiry/observed time/readiness. PCM, password и
Dispatcher calls в native callback не попадают.

### Проверенные отрицательные пути и ограничения

- enabled registration до успешного callback не допускает `make_call(peer_uri)` и не превращает direct URI в fallback;
- enabled registration failure переводит status/readiness в `failed`/`false`;
- close идемпотентен и вызывает unregister до account shutdown;
- disabled profile сохраняет существующий direct-URI путь и не требует registrar/auth полей;
- proactive `registration_expiring` event не создаётся отдельным таймером: PJSUA2 владеет refresh timer, а adapter
  наблюдает его через `onRegState`; это явная граница `009-B`;
- внешний FreeSWITCH и входящий зарегистрированный call не проверялись здесь — это scope `009-C`.

### Handoff в `009-C`

`009-C` получает готовый adapter contract: включение через `RegistrationProfile`, readiness из
`adapter.registration_ready`, наблюдение через `SipEventKind.REGISTRATION_STATE`/`RegistrationStatus`, успешный
PJSUA2 digest lifecycle и запрет direct-URI admission до readiness. FreeSWITCH fixture и workshop runbook остаются
его собственным write-set.
