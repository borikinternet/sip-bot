# Plan 010-A: Idle PCMU comfort-noise source

Уровень документа: `child plan`  
Статус: `complete`  
Родительская карта: [`plan-010-continuous-pcmu-comfort-noise.md`](plan-010-continuous-pcmu-comfort-noise.md)

## Цель и результат

Изменить существующий egress source `PcmAudioBridge` так, чтобы каждый callback PJMEDIA в idle/fallback получал
ровно один negotiated PCM-кадр с низкоуровневым comfort-noise сигналом, а PJMEDIA не подавлял эти кадры VAD-логикой.
RFC 3389/CN и SDP не входят.

Acceptance: exact-size non-zero PCM для всех idle modes, configurable level, no blocking, no new delivery boundary,
target no-GIL import/operation и regression tests зелёные.

## Применимые правила

| Источник | Материализованное правило | Проверка | Stop condition |
|---|---|---|---|
| `architecture.md` | `PcmAudioBridge` владеет source selection; PCM не проходит через Dispatcher/Event Bus | Source-map и contract tests | Новый owner/boundary требуется |
| `technical-specification.md` | Размер кадра следует `NegotiatedMediaProfile`, а не глобальной константе ptime | Profile/ptime matrix | Profile не может задать exact size |
| `development-guidelines.md` | Native runtime проверяется на free-threaded CPython; красный тест исправляется corrective pass | Target import/operation/regression | Доказанный native API-gap |
| APG §5.7A/§5.8B | Метод существующего получателя материализует edge; no silent fallback | Source audit и evidence | Protected boundary change |

## Граница и write-set

Входит:

- `config/constants.py`, `src/sip_bot/config.py`;
- `src/sip_bot/sip_media/media_port.py`, при необходимости узкий private helper;
- `src/sip_bot/sip_media/adapter.py` для target `EpConfig.medConfig.noVad`;
- focused unit/contract tests и evidence.

Не входит: SIP/RTP wire-format, SDP/CN PT 13, ASR/VAD ingress, Event Bus, TTS producer, stereo builder, live GPU gate.
Закрытые планы 005/009 не изменяются.

## Typed boundary и ownership

`PcmAudioBridge._on_frame_requested(frame)` остаётся consumer method, который материализует media edge. На входе —
native frame capacity и текущий source mode; на выходе — exact-size PCM16 frame или существующий native error path.
Внутренний helper генерации шума не публикует типы наружу и не владеет lifecycle звонка.

Начальный execution candidate для поля конфигурации: `COMFORT_NOISE_LEVEL_DBOV_MAGNITUDE = 50`, то есть −50 dBov
по знаковой конвенции RFC 3389. Это кандидат для controlled sweep, а не утверждение универсального стандарта.
ITU-T/ETSI не дают абсолютного default: сопоставление с фоном в диапазоне `−5…+2 dB` применимо только при наличии
измеренного исходного background noise. В нашем synthetic zero-background fixture итоговый уровень выбирается
экспериментально и маркируется как MVP compatibility setting, не как нормативное соответствие.

## Owner review

| Вопрос | Решение | Статус |
|---|---|---|
| Использовать ли RFC 3389/CN? | Нет, пока не реализуем | `resolved 2026-09-14` |
| Генерировать ли noise в existing egress owner? | Да | `resolved 2026-09-14` |
| Требуется ли continuous no-VAD PCMU path? | Да | `resolved 2026-09-14` |
| Какой default level? | Проверить ограниченный controlled sweep; при неразрешимом выборе вынести owner review | `execution decision` |

## Implementation slices

| Slice | Действие | Acceptance | Stop |
|---|---|---|---|
| A1 | Добавить bounded/deterministic noise generator, который выдаёт exact-size PCM16 и не блокируется | Unit: size, RMS band, non-zero, seed/repeatability, no unbounded storage | Нельзя безопасно генерировать exact-size frame |
| A2 | Подключить generator к `IDLE`, `PREROLL`, `DRAINING→IDLE`, `CANCELLED` и аварийному fallback без записи в TTS buffer | Existing source-mode tests + no false `egress_underruns` for intentional idle; PLAYING underrun still counted | Требуется новый control edge |
| A3 | Передать no-VAD policy в target PJSUA2 `EpConfig` через существующий config source | Contract + target import/operation evidence | PJSUA2 API does not expose/apply setting |
| A4 | Выполнить regression/no-GIL checks и APG audit | Full affected test lane pass | Category-4 native gap |

## Blocker register

| ID | Триггер | Что блокируется | Evidence | Статус |
|---|---|---|---|---|
| `B-010-A-001` | no-VAD setting отсутствует/игнорируется в target binding | A3, Map-010 live gate | Target runtime log, focused retry и source/API evidence | `none until triggered` |
| `B-010-A-002` | Noise source ломает exact-size callback или lifecycle close | A2, A4 | Unit/contract output и corrective retry | `none until triggered` |

## Test plan и evidence

- target executable: существующий free-threaded CPython из runtime guide;
- focused commands: unit/contract selectors для `media_port`, `config`, `adapter`;
- full commands: `python -m pytest tests/unit tests/contract tests/integration` и no-GIL/runtime probe;
- evidence: output JSON/markdown под `artifacts/implementation/010-continuous-pcmu-comfort-noise/010-A/`;
- без GPU, если тесты не импортируют/не прогревают AI providers.

Красный targeted test проходит обязательный corrective pass до регистрации blocker.

## Fallback/deferred

`fallback register: none`. RFC 3389/CN — deferred future capability, не fallback этого плана. Молчаливое возвращение
к абсолютной тишине для зелёного теста запрещено.

## Closeout

Child plan закрывается только статусом `complete` после A1–A4 и evidence. Частичный/foundation closeout запрещён.

## Execution closeout — 2026-09-14

Все slices `A1`–`A4` выполнены. Реализованы `ComfortNoiseSource`, typed config
`SIP_MEDIA_NO_VAD`/`COMFORT_NOISE_LEVEL_DBOV_MAGNITUDE`, подключение источника к
каждому idle/fallback source mode и применение `EpConfig.medConfig.noVad`.

Evidence: [`execution-evidence.md`](../../artifacts/implementation/010-continuous-pcmu-comfort-noise/010-A/execution-evidence.md).

Проверки: focused `32 passed`; полный затронутый non-GPU lane `191 passed, 5 skipped`;
target `3.14.7t` comfort-noise probe и PJSUA2 `noVad` probe прошли с
`Py_GIL_DISABLED=1` и GIL disabled до/после операций. Blocker не возник.
