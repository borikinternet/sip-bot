# Closeout `009-B`: PJSUA2 SIP registration lifecycle

Дата: `2026-09-13`  
Статус: `complete`  
Blocker: отсутствует.

Реализован lifecycle optional SIP registration только внутри `SipMediaAdapter` поверх принятого patched PJSUA2/PJMEDIA
`2.17`. `009-A` не изменялся.

## Результат

- enabled profile materializes `idUri`, registrar URI, digest `AuthCredInfo` и expiry в PJSUA2 `AccountConfig`;
- `onRegStarted`/`onRegState` нормализуются в typed `RegistrationStatus` и bounded `NormalizedSipEvent`;
- PJSUA2 автоматически выполняет refresh по `regConfig.timeoutSec`;
- close вызывает `setRegistration(False)` до `shutdown()`;
- enabled failure/not-ready не допускает direct-URI admission и не включает скрытый fallback;
- disabled mode и существующий direct-URI путь сохранены;
- password не входит в typed status, event serialization, repr или probe output.

## Проверки

- `15 passed` в узком contract/unit lane, exit code `0`;
- `177 passed, 5 skipped` в полном unit/contract/integration lane, exit code `0`;
- target `3.14.7t`, `Py_GIL_DISABLED=1`, GIL в конце `false`, итоговый probe exit code `0`;
- target fake registrar получил initial digest registration, refresh и digest unregister (`Expires: 0`);
- `git diff --check` exit code `0`;
- GPU inference не запускался.

Подробная трасса и raw structured output: [`target-r4/registration-lifecycle.json`](target-r4/registration-lifecycle.json).
Команда и exit code: [`target-r4/command.txt`](target-r4/command.txt).

## Ограничение

FreeSWITCH interop, registered incoming call и workshop procedure не входят в `009-B`; это handoff в `009-C`.
