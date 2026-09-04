# PJSUA2/PJMEDIA capacity preflight for Map-002-I.0

Дата: `2026-09-03`

## Вывод

Принятый PJSUA2/PJMEDIA `2.17` поддерживает несколько одновременных вызовов.
Это подтверждается документацией PJSUA2 и локальным чтением конфигурации
целевого patched no-GIL runtime. Ограничение MVP «один разговор» является
проектным ограничением нагрузки, а не ограничением библиотеки.

PJSUA2 использует отдельный объект `Call` для каждого вызова, а media-объекты
вызовов регистрируются в общем основном PJMEDIA conference bridge. Поэтому при
будущем расширении потребуется таблица `call_id → Call/session/media context`,
но не отдельный PJMEDIA bridge для каждого вызова.

## Локальная проверка

Команда:

```text
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc '/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import pjsua2; ep=pjsua2.Endpoint(); ep.libCreate(); cfg=pjsua2.EpConfig(); print({\"maxCalls\": cfg.uaConfig.maxCalls, \"threadCnt\": cfg.uaConfig.threadCnt, \"mainThreadOnly\": cfg.uaConfig.mainThreadOnly, \"maxMediaPorts\": cfg.medConfig.maxMediaPorts, \"mediaThreadCnt\": cfg.medConfig.threadCnt}); ep.libDestroy()"'
```

Наблюдаемый результат:

```text
maxCalls=4
threadCnt=1
mainThreadOnly=False
maxMediaPorts=254
mediaThreadCnt=1
```

Проверка подтверждает конфигурационную возможность более одного вызова и не
является тестом двух реальных звонков одновременно. Такой live-сценарий не
входит в MVP и остаётся отдельной production/scale-задачей.

## Ограничения и последствия

- `maxCalls` задаётся на уровне `EpConfig.uaConfig` и не может превышать
  compile-time `PJSUA_MAX_CALLS`; при текущей конфигурации runtime default равен
  `4`.
- Один общий primary conference bridge содержит порты разных вызовов; PJSUA2
  умеет соединять один источник с несколькими назначениям и обслуживать второй
  вызов через повторение media connections.
- Callback-и могут выполняться worker thread-ами. Для Python допустим режим с
  `threadCnt=0` и обработкой событий через `libHandleEvents()` в выбранном
  потоке, но это отдельное решение I.0 и не меняет объектную модель вызовов.
- Наш текущий `SipMediaAdapter` хранит один `_CallContext`; поэтому способность
  библиотеки не означает готовность application adapter к нескольким звонкам.
  I.0 не расширяет MVP до multi-call, а фиксирует совместимую модель для одного
  активного `CallSession` и не закрывает production scaling.

## Источники

- [PJSUA2: Working with audio media, Second call](https://docs.pjsip.org/en/2.17/pjsua2/using/media_audio.html)
- [PJSUA2: Calls](https://docs.pjsip.org/en/latest/pjsua2/using/call.html)
- [PJSUA2 API: `maxCalls`](https://docs.pjsip.org/en/2.17/api/generated/pjsip/group/group__PJSUA2__UA.html)
- [PJSUA2: general concepts and threading](https://docs.pjsip.org/en/2.16/pjsua2/general_concept.html)
- [PJMEDIA conference bridge](https://docs.pjsip.org/en/latest/specific-guides/audio/conference_bridge.html)
