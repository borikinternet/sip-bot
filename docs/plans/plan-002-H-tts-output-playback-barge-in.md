# Plan-002-H: TTS output, playback и barge-in

Уровень: `child plan`  
Статус owner review: `accepted` — owner review принят `2026-09-03`  
Статус исполнения: `complete` — deterministic implementation, XTTS/GPU и RTP/barge-in smoke закрыты `2026-09-03`  
Родительская карта: [`plan-002-mvp-media-and-speech-integration.md`](plan-002-mvp-media-and-speech-integration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md)

Дата подготовки: `2026-09-02`

## 1. Цель и результат

Подключить принятый XTTS-v2 baseline к typed answer path, принимать произвольные PCM chunks, формировать paced media
frames с согласованным `ptime`, передавать звук в SIP/media egress и немедленно останавливать playback при barge-in,
close или cancellation. Новый пользовательский ход не должен смешиваться со старым TTS result.

## 2. Применимые документы и извлечённые правила

| Источник | Правило | Влияние на работу | Проверка | Stop condition |
|---|---|---|---|---|
| [`requirements.md`](../requirements.md) | TTS озвучивает ответ, пользователь может перебить бота | Playback cancellable and direct to SIP media | RTP smoke/barge-in | New speech does not stop playback |
| [`architecture.md`](../architecture.md) | TTS output buffer/framer/pacer — отдельная boundary | TTS chunk size не равен media ptime | Buffer/pacing tests | Raw TTS chunks sent to RTP |
| [`technical-specification.md`](../technical-specification.md) | PCMU egress, bounded output, cancel/stale policy | Output is paced and close-aware | PCMU/close tests | Stale audio delivered |
| [`plan-001-C4-tts-primary.md`](plan-001-C4-tts-primary.md) | XTTS-v2 tested baseline and patches | Preserve candidate and limitations | TTS import/audio evidence | Patch/runtime mismatch |
| [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md) | `N11/N13/N14/N15/N2` and barge-in cycle explicit | Playback commands/status and PCM edge propagate | Map-I contract | New cycle not registered |

## 3. Граница задачи

**Цель:** TTS adapter, output buffer/framer/pacer, playback channel, cancellation and barge-in handling.

**Входит:** approved text stream to XTTS, arbitrary PCM chunks, bounded output buffer, media ptime re-framing, pacing,
flush at generation completion, cancellation on new speech/terminal event and playback status.

**Не входит:** LLM generation, prompt/RAG, VAD/ASR, SIP protocol transactions, PCMU decode ownership, transfer/report.

**Protected baseline:** XTTS-v2 C4 candidate, PCMU/G.711 mu-law, internal PCM S16LE mono 8 kHz, one conversation,
direct playback data plane, Dispatcher controls only, no audio recording.

**Предположения:** `002-B` exposes media egress and `002-E` exposes barge-in/close commands; `002-G` provides approved
text stream; actual `ptime` comes from C/B evidence rather than a hard-coded assumption.

## 4. Source-map и write-set

| Область | Файл или компонент | Текущее поведение | Целевое поведение | Gap | Действие |
|---|---|---|---|---|---|
| TTS adapter | `src/sip_bot/tts/xtts_adapter.py` | Feasibility only | Typed text→PCM stream | No app adapter | Wrap C4 candidate |
| Output boundary | `src/sip_bot/tts/output_buffer.py` | Отсутствует | Bounded buffer and arbitrary chunk aggregation | No flush/cancel | Implement owner object |
| Framer/pacer | `src/sip_bot/tts/media_pacer.py` | Отсутствует | ptime frames on media clock | No pacing lifecycle | Implement and test |
| Playback | `src/sip_bot/playback/channel.py` | Отсутствует | Direct PCM egress and close/cancel | No app channel | Implement channel owner |
| Tests | `tests/unit/test_tts_output.py`, `tests/contract/test_playback_contract.py`, `tests/integration/test_barge_in.py` | Отсутствуют | Chunk/pacing/cancel/RTP smoke | No fixtures | Create deterministic and stand tests |
| Evidence | `artifacts/.../002-H/` | Отсутствует | Audio chunk, pacing, cancel and barge-in traces | No app evidence | Create at execution |

Допустимый write-set: `src/sip_bot/tts/`, `src/sip_bot/playback/`, TTS/playback tests and own evidence root. Changes to
SIP adapter, VAD/ASR, FSM action semantics and XTTS source/patches are prohibited without review.

## 5. Interaction topology и propagation контрактов

`N9 → N15` sends `PlaybackCommand`/`ChannelClose`; `N11/N13 → N15` sends approved answer text stream or TTS output;
`N15 → N2` sends paced PCM frames; `N15 → N9` reports started/stopped/failed/cancelled. `N2/N3 → N9` and speech events
trigger barge-in; playback closes its old channel and does not await TTS completion. Re-open creates a new channel; late
TTS chunks are discarded by close/stale policy.

TTS output chunks may have arbitrary size and timing; the output boundary accumulates them, creates exact media frames,
and paces on media clock. Tail flush is allowed only on successful generation completion; cancellation drops undelivered
tail.

## 6. Audit владельца поведения и парадигмы реализации

XTTS adapter owns model invocation; output buffer owns accumulation/flush; framer/pacer owns media sizing and timing;
playback channel owns delivery and cancellation. Dispatcher owns only command/state semantics. Pure PCM slicing may be a
function, but it cannot decide lifecycle, cancellation or FSM state.

## 7. Owner-review решения

| Вопрос | Решение | Последствие для реализации | Статус |
|---|---|---|---|
| Какой TTS baseline? | XTTS-v2 C4 accepted | Preserve C4 patches and tested limitations | `resolved` |
| Где преобразуется TTS output в media frames? | В отдельном output buffer/framer/pacer | TTS chunk size is independent from ptime | `resolved` |
| Как обрабатывается barge-in? | Закрыть playback channel, отменить TTS where supported, drop stale chunks | New user turn gets priority | `resolved` |
| Какой фактический `ptime`? | Берётся для каждого звонка из согласованного SDP и словарей/объектов PJMEDIA через B/C media contract | No silent 20 ms assumption; H uses the active call profile | `resolved: owner review accepted 2026-09-02` |

## 8. Process invariant audit

- TTS generation, buffering, pacing and playback are separate owners.
- Audio payload bypasses Dispatcher; control commands/events remain typed.
- Real TTS/GPU runs are sequential and not delegated; deterministic chunk tests precede them.
- No recording is created by this plan.
- Exact commands and pre-existing C4 limitations are recorded in evidence.

## 9. Architecture invariant audit

- Playback can be cancelled without waiting for TTS or Dispatcher round trip.
- Closed output channel suppresses stale audio; no channel reuse across turns.
- PCM→PCMU conversion stays in media layer, not TTS model code.
- New speech during playback is observable as barge-in and stops old playback.
- TTS cannot initiate SIP transfer/hangup.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| H1 | Define text→PCM/playback contracts | Map-I and G contracts match | Missing cancel/close fields |
| H2 | Wrap XTTS and test PCM streaming | Russian text yields PCM chunks under approved runtime | Import/patch/GIL issue |
| H3 | Implement output buffer/framer/pacer | Arbitrary chunks yield paced ptime frames and correct tail policy | Pacing or tail semantics ambiguous |
| H4 | Implement playback close/cancel | Close is idempotent, stale chunks are not delivered | Old audio after barge-in |
| H5 | Run `001-S` RTP barge-in smoke and handoff J | New speech cancels playback, media remains valid | RTP smoke fails or ptime mismatch |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence/проверка | Статус |
|---|---|---|---|---|---|---|
| `B-002-H-001` | весь plan | Child plan не прошёл owner review | TTS/playback implementation | project owner | APG review | `resolved — owner review accepted 2026-09-03` |
| `B-002-H-002` | H1/H3 | B/C media contract не подтверждён | Real media pacing | media owner | Map-I revision 8 + B/C evidence | `resolved — NegotiatedMediaProfile/PcmFrame and direct egress contract accepted` |
| `B-002-H-003` | H4/H5 | Barge-in does not close old channel or stale audio leaks | Interaction gate and demo | project owner | [`rtp-barge-in.json`](../../artifacts/implementation/002-mvp-media-and-speech-integration/002-H/rtp-barge-in.json) | `resolved — RTP/playback smoke pass` |

## 12. Test plan и evidence

- deterministic arbitrary TTS chunk sizes, buffer bounds and exact frame sizing;
- media-clock pacing, end-of-generation tail flush and cancellation tail discard;
- XTTS import/operation probe with C4 patches and Russian sample;
- close/re-close, cancellation and stale chunk suppression;
- RTP PCMU playback through `001-S`;
- barge-in while TTS is generating and while playback is active;
- evidence records text/request identity, chunk timestamps, ptime, cancel reason, media counters and exit codes.

## 13. Fallback/deferred register

| Что введено | Почему необходимо | Как ограничено | Где закрывается | Статус |
|---|---|---|---|---|
| Cancellation may close HTTP/TTS channel without hard model stop | C3/C4 runtime limitation | Stale audio must still be suppressed; no hard-stop claim | H4/H5/report | `approved with limitation` |
| `none` | — | — | — | `none` |

## 14. Execution report и closeout

Текущий статус: `complete; owner review accepted; deterministic и main-only execution закрыты`. Передан J working
playback/barge-in evidence и actual media contract; any C4 patch/runtime discrepancy remains an explicit limitation,
not a hidden fallback.
