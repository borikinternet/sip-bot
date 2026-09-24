# Plan 010-B: Stereo recording timeline audit

Уровень документа: `child plan`  
Статус: `complete`  
Родительская карта: [`plan-010-continuous-pcmu-comfort-noise.md`](plan-010-continuous-pcmu-comfort-noise.md)

## Цель и результат

Исправить evidence helper и registered recording wrapper так, чтобы Baresip raw `enc`/`dec` не выдавались за
синхронную стереозапись только на основании совпадения длительностей. Общая шкала берётся из реального answered-call
window `200 OK → BYE`/`media_stopped`, а независимые старты дорожек выравниваются по timestamp создания Baresip-файла.
Длительности raw-файлов сохраняются как диагностика; padding/trimming относительно authoritative window явно отражаются
в manifest.

Plan зависит от `010-A`: без continuous PCMU source нельзя доказать общую временную шкалу через `sndfile`.

## Применимые правила и topology

| Источник | Материализованное правило | Проверка |
|---|---|---|
| `technical-specification.md` | Baresip владеет записью; raw `enc`/`dec` — primary evidence, runtime не пишет audio | Source audit и raw artifact inventory |
| `development-guidelines.md` | Обязательный acceptance нельзя компенсировать соседним зелёным тестом | Synthetic large-gap negative test |
| `architecture.md` | Запись не проходит через Dispatcher/Event Bus | Wrapper source audit |
| APG §5.7A/§5.8B | Производный stereo не скрывает ошибку upstream и фиксирует mapping/padding | Manifest schema and closeout |

Data edge:

```text
Baresip sndfile enc/dec + creation timestamps → answered-call timeline audit → stereo interleaving → manifest
```

`map005_stereo_recording.py` остаётся helper-ом evidence, не runtime delivery owner.

## Граница и write-set

Входит: `tools/map005_stereo_recording.py`,
`tools/freeswitch_workshop/registered_full_rehearsal.py`, focused unit tests, manifest schema и evidence wrapper.

Не входит: изменение Baresip, запись в runtime, изменение SIP/SDP, RFC 3389/CN, перезапись исторических artifacts.

## Owner review

| Вопрос | Решение | Статус |
|---|---|---|
| Разрешать ли r15-подобный разрыв trailing padding? | Не использовать raw duration gap как критерий answered-call continuity; authoritative window задаётся SIP/media events | `superseded by owner correction 2026-09-14` |
| Какой малый cleanup tail разрешить? | Не более `500 мс`; фактическое значение и negotiated ptime фиксируются в manifest | `resolved by owner decision 2026-09-14` |
| Как учитывать разные старты `enc`/`dec`? | Timestamp создания из имени Baresip используется для per-channel offset; при наличии фиксируется wall-clock `200 OK` | `resolved by owner correction 2026-09-14` |
| Нужен ли новый аудиоканал в runtime? | Нет | `resolved by existing architecture` |

## Implementation slices

| Slice | Действие | Acceptance | Stop |
|---|---|---|---|
| B1 | Добавить answered-call event-window policy и per-track start-offset alignment | target frames вычисляются из `200 OK → BYE`/`media_stopped`, а не из `max(raw duration)`; начало каждой дорожки учитывается явно | Нет authoritative event window и timestamp старта обеих дорожек |
| B2 | Обновить manifest с event window, file-start offsets, expected ptime, padding/trimming и audit result | Mapping/policy/hash/timeline metadata complete | Metadata cannot be tied to event window/profile |
| B3 | Добавить unit negative/positive tests и проверить registered wrapper | Focused tests pass; old r15 is correctly rejected, not modified | Helper does not fail invalid source |

## Blocker register

| ID | Триггер | Что блокируется | Evidence | Статус |
|---|---|---|---|---|
| `B-010-B-001` | Baresip raw tracks remain non-contiguous after `010-A` and corrective retry | B2/B3 and live gate | WAV metadata, peer log, RTP evidence | `none until triggered` |
| `B-010-B-002` | Negotiated ptime is unavailable to evidence wrapper | B1/B2 | Result JSON, source/API audit | `none until triggered` |

## Test plan и evidence

- synthetic mono PCM fixtures with equal length, different start offsets, event-window padding/trimming and a large-gap
  standalone compatibility negative case;
- focused `tests/unit/test_map005_recording.py` plus registered wrapper test;
- target registered run is deferred to `010-C`, not counted as pass here;
- evidence root: `artifacts/implementation/010-continuous-pcmu-comfort-noise/010-B/`.

Красный negative test должен быть красным именно для invalid track, а valid positive case — зелёным.

## Fallback/deferred и closeout

`fallback register: none`. Автоматическое padding большого raw-duration gap без timeline запрещено. При наличии authoritative
event window padding или trimming до этой шкалы является явной операцией и не маскируется под RTP continuity. RFC CN не
реализуется.
Child plan получает `complete` только после B1–B3 и evidence; partial/foundation closeout запрещён.

## Execution closeout — 2026-09-14

Все slices `B1`–`B3` выполнены. Первоначальная strict-duration политика после review признана неверной для Baresip
recording: она использовала независимые границы закрытия файлов как общую шкалу. Корректирующая ревизия использует
answered-call event window, timestamp старта из имени каждой Baresip-дорожки и optional wall-clock `200 OK`; manifest
явно содержит per-channel offsets, leading/trailing padding и trimming. Raw duration gap больше `500 ms` больше не
блокирует построение stereo, если authoritative event window присутствует; без него сохраняется strict compatibility path.

Evidence: [`execution-evidence.md`](../../artifacts/implementation/010-continuous-pcmu-comfort-noise/010-B/execution-evidence.md).

Проверки первоначальной реализации: focused `5 passed`; positive equal/small-tail cases и negative
`4001 samples over 500 ms` case зелёные. После owner correction добавлены start-offset и event-window cases: focused
`10 passed`. Blocker не возник.
