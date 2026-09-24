# Plan-007-A: WebRTC VAD runtime и no-GIL gate

Уровень: `child plan`  
Статус owner review: `accepted — inherited from Map-007 owner approval, 2026-09-13; no additional owner question`  
Статус исполнения: `complete — target and combined runtime gate passed after approved free-threading patch, 2026-09-13`  
Родительская карта: [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md)  
Boundary map: [`plan-002-I-boundary-interaction-map.md`](plan-002-I-boundary-interaction-map.md), revision 21  
Evidence root: `artifacts/implementation/007-webrtc-vad/007-A/`

## 1. Цель и результат

Получить воспроизводимое доказательство, что фактически выбранный binding открытого WebRTC VAD можно использовать в
target free-threaded CPython 3.14.7t/Ubuntu 24.04 WSL2 и что он выполняет реальную операцию на PCM-кадре. Точный
package/version/revision выбирается по факту latest stable, доступности в target runtime, лицензии и no-GIL evidence;
заранее несуществующая версия не pin-ится.

Результат `007-A` — runtime manifest с командами, версиями, source/license, GIL-состоянием до и после import/operation,
валидными решениями для 8 kHz mono PCM S16LE 10/20/30 ms и корректно классифицированными ошибками invalid input.
`007-A` не подключает candidate к live composition и не меняет application contracts.

## 2. Применимые документы и извлечённые правила

| Источник | Материализованное правило | Влияние на `007-A` | Проверка | Stop condition |
|---|---|---|---|---|
| [`plan-007-webrtc-vad-migration.md`](plan-007-webrtc-vad-migration.md) | WebRTC VAD уже выбран; live fallback на amplitude запрещён; exact binding выясняется evidence | Проверяем binding, а не переизбираем алгоритм | Candidate/runtime manifest | Новый алгоритм или fallback требуется молча |
| [`ADR-003-free-threaded-python.md`](../decisions/ADR-003-free-threaded-python.md) | Native binding проверяется в CPython 3.14t; GIL не должен включаться после import/operation | Host Python не считается evidence; process isolation не вводится автоматически | `Py_GIL_DISABLED`, `sys._is_gil_enabled()` | GIL/API failure без corrective patch |
| [`development-guidelines.md`](../development-guidelines.md) §5 | Сначала рассматривается patch, затем только explicit isolation; команды, stdout/stderr, exit code и версии сохраняются | Не ограничиваться import-only probe; выполнить operation | Raw logs and JSON manifest | Необъяснимый red или silent GIL fallback |
| [`development-guidelines.md`](../development-guidelines.md) §6–§7 | Красный результат классифицируется, исправляется в scope; intentional simplification/fallback запрещены | Ошибку binding нельзя объявить «допустимой» без patch/gap | Corrective attempt and rerun | Category-4 gap оформлен отдельно |
| [`tooling-notes.md`](../tooling-notes.md) | Target executable — `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`; no-GIL evidence структурируется JSON | Использовать существующий target runtime и локальные команды | Runtime manifest | Target executable недоступен |
| [`plan-002-D-speech-ingress.md`](plan-002-D-speech-ingress.md) | WebRTC VAD — принятый candidate, native verification была отложена | Проверка закрывает именно отложенный native/live gap | `007-A` evidence | Candidate не проходит обязательный gate |

## 3. Граница задачи

**Входит:** поиск/проверка фактического Python binding WebRTC VAD, installation/runtime inspection, license/source
manifest, import/operation/no-GIL, controlled-concurrency smoke, valid/invalid frame matrix и evidence.

**Не входит:** изменение `VadProcessor`, `VadDecision`, `TurnDetector`, `SpeechIngress`, runtime wiring, live tools,
endpoint thresholds, ASR, SIP/RTP и автоматический fallback.

**Protected baseline:** CPython 3.14.7t/no-GIL, WebRTC algorithm decision, `PcmFrame`/`VadDecision` boundary,
Map-I revision 21, один call generation, deterministic test backends.

**Предположения:** target WSL runtime и рабочая директория `/mnt/c/devel/sip-bot` доступны; VAD не требует GPU; package
manager lock contention не считается немедленным blocker и повторяется с случайной задержкой по guidelines.

## 4. Source-map и write-set

| Область | Файл/ресурс | Действие | Write-set |
|---|---|---|---|
| Probe | `tools/webrtc_vad_nogil_probe.py` | Создать воспроизводимый import/operation/concurrency probe, если существующие команды недостаточны | Новый probe tool |
| Evidence | `artifacts/implementation/007-webrtc-vad/007-A/` | Сохранить manifest, stdout/stderr, exit codes, package/source/license data | Только собственный evidence root |
| Existing adapter | `src/sip_bot/speech/vad.py` | Не менять; менять только если фактическая binding API incompatibility не позволяет проверить уже предусмотренный adapter contract | Только минимальная compatibility правка в `WebRtcVadCandidate`; без нового API/fallback |
| Docs | `plan-007-A...` и после closeout registry/backlog | Обновить execution/closeout фактом | Child plan sections; registry/backlog sequentially main executor |

Защищены: `config/constants.py`, live tools, `runtime_wiring.py`, speech contracts/endpointing, Map-I, closed plans и
unrelated changes.

## 5. Interaction topology и propagation

`007-A` не материализует новое runtime-ребро. Проверяемый local call соответствует существующему контракту кандидата:

```text
PcmFrame.pcm_s16le + PcmFrame.profile.sample_rate_hz
  → WebRtcVadCandidate.is_speech(bytes, sample_rate_hz) → bool
  → VadProcessor → VadDecision       (application propagation выполняется в 007-B)
```

Binding не должен менять формат, добавлять confidence или владеть endpoint state. Operation probe проверяет только input
contract и candidate lifecycle. Candidate instance не shared между независимыми call generations.

## 6. Audit владельца поведения и парадигмы реализации

`WebRtcVadCandidate` владеет только вызовом внешнего VAD binding для одного PCM frame. `007-A` не создаёт VAD manager,
delivery owner, event bus или собственный endpointing state. Probe вызывается главным executor-ом в target runtime; он не
запускается из PJMEDIA callback.

## 7. Owner-review решения

| Вопрос | Решение | Последствие | Статус |
|---|---|---|---|
| Какой algorithm проверять? | WebRTC VAD, решение принято в `002-D` и Map-007 | Comparative VAD selection не входит | `resolved` |
| Какой exact package/version? | Выбрать на execution stage по latest stable + target/no-GIL/license evidence | Версия фиксируется только в manifest после проверки | `resolved execution rule` |
| Что делать при no-GIL failure? | Попытаться patch binding; automatic GIL-enabled runtime, amplitude fallback и isolation без owner review запрещены | При непредусмотренном API/boundary gap остановить `007-A` | `resolved by ADR-003/APG` |

Открытых owner-review вопросов нет. Эти решения не требуют повторного согласования ранее принятого WebRTC выбора.

## 8. Process invariant audit

| Инвариант | Действие | Evidence |
|---|---|---|
| Target runtime | Все import/operation probes запускаются target CPython 3.14.7t | Runtime manifest |
| No-GIL | GIL проверяется до import, после import, после construction и после operation | JSON + raw output |
| Reproducibility | Команда, executable, package/source revision, stdout/stderr/exit code сохраняются | `commands.md`, logs |
| Corrective protocol | Native failure сначала анализируется и patch-ится; соседние зелёные тесты не заменяют красный gate | Failure classification |
| Scope | Ни live wiring, ни fallback, ни contract changes не маскируются probe-ом | Diff audit |

## 9. Architecture invariant audit

- Проверяется существующий input contract mono PCM S16LE, sample rates 8/16/32/48 kHz и frame duration 10/20/30 ms.
- WebRTC boolean не превращается в искусственный confidence; application `VadDecision.confidence` остаётся `None`.
- Candidate не владеет endpointing и не публикует control events.
- Probe не проходит через Dispatcher и не имитирует live SIP evidence.

## 10. Implementation slices

| Slice | Работа | Acceptance | Stop condition |
|---|---|---|---|
| `A1` | Inspect target runtime и наличие доступных bindings | Exact candidate/source/package/license recorded | Binding unavailable или license gap |
| `A2` | Создать/запустить import probe | GIL remains disabled after import/construction | GIL enabled or import failure |
| `A3` | Выполнить operation matrix | Valid 8 kHz 10/20/30 ms frames return bool; invalid inputs fail explicitly | Operation/API/native failure |
| `A4` | Controlled concurrency и shutdown/lifecycle evidence | No crash/cross-instance leakage; raw evidence saved | Reproducible native/API defect |
| `A5` | Closeout и handoff в `007-B` | Manifest, command, hashes, limitations and promotion condition complete | Required evidence missing |

## 11. Blocker register

| ID | Срез | Триггер | Что блокируется | Владелец решения | Evidence | Статус |
|---|---|---|---|---|---|---|
| `B-007-A-001` | `A1–A3` | Binding отсутствует/не устанавливается в target или license/source не пригодны | WebRTC adoption | project owner | runtime/package/license manifest | `none until triggered` |
| `B-007-A-002` | `A2–A4` | GIL включается, binding crashes или operation API incompatible | `007-B`/`007-C` | project owner | raw probe output + patch attempt | `none until triggered` |
| `B-007-A-003` | `A4` | Не подтверждён lifecycle/isolation при предусмотренном concurrency | Target promotion | project owner | concurrency output | `none until triggered` |

Ошибка теста или fixture в утверждённом write-set сначала исправляется corrective pass и не регистрируется как APG
blocker. Category-4 gap регистрируется только после raw evidence и corrective attempt.

## 12. Test plan и evidence

Target command template:

```text
wsl.exe -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I tools/webrtc_vad_nogil_probe.py --output-root /mnt/c/devel/sip-bot/artifacts/implementation/007-webrtc-vad/007-A
```

Проба должна сохранить:

- `runtime-manifest.json` с `sys.implementation`, `sys.version`, SOABI, `Py_GIL_DISABLED` и GIL state;
- package/source/license manifest и SHA256 доступного artifact, если hash применим;
- import/operation/concurrency stdout/stderr и exit codes;
- frame matrix с размерами 10/20/30 ms, sample rates, bool result и explicit invalid-input errors;
- observed latency/CPU note без требования GPU inference;
- факт, что probe не является live SIP/RTP evidence.

После `A1–A4` запускаются targeted tests/compile checks, а затем main executor повторяет probe после любой правки.
Deferred evidence не используется: если target operation нельзя выполнить, это blocker/owner-review trigger, а не pass.

## 13. Fallback/deferred register

| Что введено | Ограничение | Статус |
|---|---|---|
| Injected fake backend в application tests | Не используется как evidence WebRTC binding | `not applicable to A; preserved downstream` |
| Amplitude VAD | Не запускается и не считается fallback в `007-A` | `forbidden in target promotion` |
| Process isolation | Не вводится без нового owner decision и boundary plan | `deferred unless triggered` |

## 14. Execution report и closeout

Фактический package/version/source/license, runtime executables, команды, raw outputs, exit codes, GIL states, operation
results и corrective attempt сохранены в [`artifacts/implementation/007-webrtc-vad/007-A/`](../../artifacts/implementation/007-webrtc-vad/007-A/).
`B-007-A-001`–`B-007-A-003` закрыты как `none after corrective pass`. Следующий propagation checkpoint — `I1` в
`007-B`. Статус child plan: `complete`; partial/foundation status не используется.
