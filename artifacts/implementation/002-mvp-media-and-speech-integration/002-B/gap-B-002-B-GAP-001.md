# B-002-B-GAP-001 — PJSUA2 media index binding mismatch

Дата обнаружения: `2026-09-02` (Europe/Moscow)  
Статус: `resolved; local implementation defect corrected and target rerun passed 2026-09-03`

## Обнаруженный gap

В application runtime на принятом patched PJSUA2/PJMEDIA `2.17` binding исходная
реализация вызвала `Call.getStreamInfo(-1)` из media-state callback и получила:

```text
OverflowError: in method 'Call_getStreamInfo', argument 2 of type 'unsigned int'
```

При этом фактический вызов с approved Baresip peer был установлен и получил
`CONFIRMED`; PJSUA2/PJMEDIA callback path продолжил доставлять call-state.
Причина была в application adapter: `-1` допустим как wildcard для
`getAudioMedia()`, но не может использоваться как media index для
`getStreamInfo()`, чей generated параметр имеет unsigned тип. Проблема
затрагивала способ извлечения negotiated media profile, а не import/no-GIL или
общий SIP lifecycle.

## Затронутые документы и компоненты

- `src/sip_bot/sip_media/models.py`: `NegotiatedMediaProfile.from_call()`;
- `src/sip_bot/sip_media/adapter.py`: media-state callback и media bridge setup;
- B3 `PCMU/RTP handoff` и B4 `Map-I propagation` этого plan;
- downstream `002-C`, которому нельзя передать неподтверждённые `ptime`/frame fields;
- принятое C1 generated binding/API provenance — только для проверки владельцем
  baseline при необходимости.

## Почему текущий plan был остановлен

Без подтверждённого media index adapter не получает authoritative
`StreamInfo`/PJMEDIA port profile для конкретного звонка. Молчаливый переход на
другой index, hard-coded `20 ms`, profile из Baresip log или compatibility
bridge нарушил бы APG §6 и owner decision о per-call SDP/PJMEDIA profile.

## Corrective pass

1. Adapter выбирает активный audio `CallMediaInfo.index`, проверяет, что он
   неотрицателен, и сохраняет его в scoped call context.
2. Один и тот же explicit index передаётся в `getStreamInfo()` и
   `getAudioMedia()`; в application code больше нет `-1` compatibility bridge.
3. Media events публикуют выбранный `media_index`, а teardown явно release-ит
   native `AudioMediaPort` до `Endpoint.libDestroy()`.

Это локальная corrective change в пределах write-set `002-B`; C1 generated
binding/patch provenance не менялся.

## Что блокируется

- `B3`: negotiated profile, PCMU/RTP ingress/egress evidence — закрыто;
- `B4`: фактический contract handoff в Map-I и `002-C` — закрыто.

`B1` runtime/import/no-GIL и `B2` call lifecycle, local OPTIONS response,
normal hangup и remote BYE не блокируются этим gap.

## Нужен ли новый ADR/roadmap/plan-file

Новый roadmap, ADR или owner decision не нужен: corrective change не меняет
архитектурный baseline и не затрагивает C1 generated binding/patch. APG
§5.8B требует зафиксировать локальную ошибку и повторить targeted/regression
tests; это выполнено.

## Evidence

- `lifecycle-options.json` — target import/runtime, OPTIONS `SIP/2.0 200 OK`,
  call `CONFIRMED`/local close;
- `remote-bye.json` — remote BYE during active call and local media cleanup;
- `pcmu-profile-handoff.json` — successful B3 corrective rerun with PCMU profile;
- `remote-bye.json` — successful target media lifecycle with 10 ingress and 10 egress frames;
- `../interaction-map/propagation-002-B.md` — successful B4 Map-I contract handoff;
- exact application command and target runtime are recorded in each JSON.

## Classification note

Общий вопрос «что делать при mismatch generated binding/patch» не открывается
повторно. По APG §5.8B main executor проверил исходник, команду и raw result,
классифицировал red result как локальную implementation defect, выполнил
corrective pass и повторил targeted/full tests. Owner review нужен только если
такое исправление не может быть выполнено в write-set или требует изменения
protected C1 baseline; здесь этого не произошло.
