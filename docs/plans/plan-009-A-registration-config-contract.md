# План 009-A: контракт конфигурации SIP-регистрации

Уровень документа: `child plan`  
Идентификатор: `009-A`  
Статус: `complete` — execution и closeout приняты `2026-09-13`  
Родитель: [`plan-009-optional-sip-registration.md`](plan-009-optional-sip-registration.md)  
Дата: `2026-09-13`  

## 1. Цель и проверяемый результат

Ввести в единственный файл MVP-конфигурации явный typed-контракт для опциональной SIP-регистрации. После исполнения:

- режим регистрации выключен по умолчанию;
- включённый режим нельзя включить неполным или противоречивым профилем;
- типовой конфиг содержит коммитимый, явно помеченный публичный демонстрационный SIP-пароль;
- реальные production credentials не требуются и не должны попадать в evidence/logs;
- существующий direct-URI путь работает без изменений при выключенной регистрации;
- `009-B` получает самодостаточный `RegistrationProfile` и не вводит второй источник конфигурации.

Этот plan не реализует SIP `REGISTER`, не добавляет FreeSWITCH и не меняет AI/media data plane.

## 2. Контекст и применимые решения

Материализованные правила и решения:

| Источник | Применяемое правило | Проверка |
|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Применимые правила копируются в plan; child plan закрывается только `complete` или `blocked` | Этот документ, acceptance и closeout |
| [`development-guidelines.md`](../development-guidelines.md) | Ошибку реализации исправлять в scope; тесты обязательны; скрытый fallback запрещён | Unit/contract tests и raw output |
| [`technical-specification.md`](../technical-specification.md) | MVP использует `config/constants.py` как единственный источник; локальные тестовые credentials допустимы | Source/config audit |
| [`architecture.md`](../architecture.md) | Control-plane и lifecycle отделены от PCM/RTP; SIP adapter владеет SIP boundary | Ownership audit |
| Map-009 | Registration optional, default-off; enabled failure → `readiness=false` без direct fallback | Config contract и downstream handoff |
| Owner decision 2026-09-13 | Типовой демонстрационный секрет коммитится; это не production secret | Config comments/tests |

## 3. Scope

В scope входят:

1. Новые константы в `config/constants.py`: флаг включения, registrar URI, identity/local URI,
   username, публичный demo password и срок регистрации.
2. Явный immutable `RegistrationProfile` либо эквивалентный typed value object с валидацией.
3. Расширение `RuntimeConfig`/`SipMediaConfig` только настолько, чтобы передать профиль владельцу SIP adapter.
4. Проверки согласованности enabled/disabled mode и запрет неявного чтения environment/второго config source.
5. Unit/contract tests и direct-URI regression.

Не входят: вызов PJSUA2 `Account.create`, callbacks, refresh/unregister, FreeSWITCH, TLS/SRTP, vault,
многорегистраторность, production secret handling, AI/media изменения.

## 4. Защищённый baseline

- CPython free-threaded/no-GIL и утверждённый patched PJSUA2/PJMEDIA baseline не меняются.
- `SipMediaAdapter` остаётся владельцем SIP lifecycle; его protocol reactions не ждут Dispatcher.
- PCMU/8 kHz mono, negotiated per-call `ptime`, RTP/data plane и существующий direct-URI сценарий не меняются.
- `MAX_CONCURRENT_CALLS=1` остаётся действующим ограничением.
- Единственный источник конфигурации — `config/constants.py`; demo credential публичен по замыслу и не является секретом production.

## 5. Source-map и write-set

### 5.1. Разрешённые файлы

- `config/constants.py`
- `src/sip_bot/config.py`
- `src/sip_bot/sip_media/adapter.py` — только передача профиля в `SipMediaConfig`, если это необходимо контрактом
- `tests/unit/test_config.py`
- `tests/unit/test_sip_media.py` — только config/direct-URI regression
- новый узкий contract test под `tests/contract/`, если он нужен
- этот plan-file и его execution evidence/closeout

### 5.2. Запрещённые изменения

Не менять runtime orchestration, Dispatcher/FSM, PCM fan-out, ASR, LLM, TTS, FreeSWITCH fixture,
public workshop guide и Map-009 из этого child plan. Изменение внешнего boundary оформляется gap, а не молча.

## 6. Контракт

Профиль должен представлять как минимум:

```text
enabled: bool
registrar_uri: str
identity_uri: str
username: str
password: str
expires_seconds: int
```

Инварианты:

- `enabled=False` не требует валидного registrar/auth профиля и сохраняет direct-URI путь;
- `enabled=True` требует непустые registrar, identity, username, password и положительный expiry;
- password не сериализуется в control events, не включается в `repr`, не логируется и не записывается в evidence;
- типовой password явно маркирован как `PUBLIC DEMO CREDENTIAL` в исходнике;
- конфигурация не подменяется environment variables, ignored overlay или CLI defaults.

## 7. План срезов и проверки

| Срез | Действие | Обязательное evidence | Следующий срез |
|---|---|---|---|
| A1 | Добавить константы и typed mapping | source diff, import snapshot, profile dump без password | A2 |
| A2 | Реализовать validation enabled/disabled | unit tests на valid/invalid profiles | A3 |
| A3 | Передать профиль в SIP config без изменения direct path | config contract и direct-URI regression | A4 |
| A4 | Провести target no-GIL import/test lane | executable, GIL state, exit code, raw output | Closeout |

## 8. Blocker register

| ID | Триггер | Что блокируется | Статус |
|---|---|---|---|
| `B-009-A-001` | Единственный config source нельзя расширить без второго обязательного source | Map-009 | `none until triggered` |
| `B-009-A-002` | Требуется production secret store вместо принятого public demo credential | Map-009 | `resolved by owner decision 2026-09-13` |
| `B-009-A-003` | Direct-URI regression ломается изменением disabled profile | `009-A` | `none until triggered; corrective pass required` |
| `B-009-A-004` | Target free-threaded runtime/import gate не проходит | `009-A` | `none until triggered; patch/isolation analysis required` |

Красный unit-test результат сначала классифицируется и исправляется в scope. Blocker регистрируется только при
доказанном API/architecture gap или невозможности получить обязательное target evidence.

## 9. Acceptance и closeout

`009-A` можно закрыть только статусом `complete`, если:

1. default-off profile создаётся из `config/constants.py`;
2. включённый профиль проходит positive validation, неполный — explicit failure;
3. demo credential коммитится как явно публичный и не попадает в logs/evidence/repr;
4. `RuntimeConfig`/`SipMediaConfig` имеют typed profile без второго config source;
5. direct-URI regression и полный релевантный unit/contract lane зелёные;
6. target no-GIL import/test evidence сохранён;
7. raw outputs, изменённые symbols/files, corrective attempts и остаточные gaps перечислены в closeout;
8. результат явно передан `009-B`.

Partial/foundation status не допускается. При незавершённом scope — `blocked` с evidence и условием promotion.

## 10. Execution report contract

Closeout должен содержать дату, команды, exit codes, runtime/GIL evidence, список изменённых файлов/symbols,
результаты позитивных и негативных тестов, сведения о том, что пароль не попал в output, и handoff для `009-B`.

## 11. Execution report и closeout

Дата исполнения: `2026-09-13`  
Статус исполнения: `complete`  
Blocker: отсутствует.

### Фактически изменённые файлы

- `config/constants.py` — добавлен default-off registration profile с явно публичным demo credential;
- `src/sip_bot/config.py` — добавлены immutable `RegistrationProfile`, validation и безопасный `public_view()`;
- `src/sip_bot/sip_media/adapter.py` — typed forwarding profile в `SipMediaConfig`, без реализации REGISTER;
- `tests/unit/test_config.py` — positive/negative validation и diagnostics без password;
- `tests/unit/test_sip_media.py` — forwarding и direct-URI regression.

Изменений в Dispatcher/FSM, media/data plane, AI, FreeSWITCH и production secret handling не внесено.

### Выполненные проверки

| Команда/проверка | Результат |
|---|---|
| `python -m pytest tests/unit/test_config.py tests/unit/test_sip_media.py -q` | `0`; `21 passed` |
| Полный unit/contract/integration lane субагента | `0`; `172 passed, 5 skipped` |
| Target CPython `3.14.7t`: `Py_GIL_DISABLED=1`, GIL state | `0`; GIL не включался до/после импортов и тестового lane |
| `git diff --check` по A write-set | `0` |
| GPU inference/import | Не выполнялся |

### Acceptance и handoff

- default-off режим сохранён;
- enabled profile валидируется явно и не допускает неполные поля;
- demo password исключён из `repr`/`public_view` и не выводится диагностикой;
- второй источник конфигурации не введён;
- direct-URI path не изменён;
- typed `RegistrationProfile` передан `009-B`.

План `009-A` закрыт статусом `complete`; partial/foundation статус не использовался.
