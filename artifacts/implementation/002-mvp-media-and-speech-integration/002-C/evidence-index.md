# Evidence index: Plan-002-C

Статус evidence: `complete` — 2026-09-03.

Все проверки выполнены без загрузки моделей и без heavy GPU inference. Аудиоп payload в evidence не сохраняется;
сохраняются только размеры, метаданные контрактов, счётчики и контрольные результаты.

| Evidence ID | Содержание | Результат | Файл |
|---|---|---|---|
| `C-E-unit-host` | PCMU vectors, frame contract, fan-out, timer/flush/close/cancel/overflow/stale semantics | `15 passed` в targeted lane; `57 passed` в полном host lane | `target-tests.stdout.log`, `commands.md` |
| `C-E-contract-host` | `NegotiatedMediaProfile`/`PcmFrame`/`AsrAudioChunk` и прямой data-plane handoff | `pass` | `tests/contract/test_audio_contracts.py` |
| `C-E-runtime-nogil` | Target executable/import boundary | CPython 3.14.7t; `Py_GIL_DISABLED=1`; GIL до/после импорта `False` | `commands.md` |
| `C-E-c4-target-pcm-boundary` | Live approved Baresip PCMU call → 002-B PCM → C fan-out/chunker | `pass`; 100 live frames, 100 VAD, 100 ASR, 2 × 1 s chunks | `c4-target.json`, `c4-target.stdout.log`, `c4-target.stderr.log`, `c4.peer.log` |

## Зафиксированный boundary

- Входная ревизия: `Map-002-I revision 4`; она является baseline этого child plan.
- Источник профиля: фактический per-call `NegotiatedMediaProfile` от `002-B`/PJMEDIA.
- Наблюденный профиль: PCMU, payload type 0, RX/TX payload type 0, 8000 Hz, mono, 20 ms, 160 samples и 320 PCM
  S16LE bytes на media frame.
- PCMU boundary: один RTP payload профиля преобразуется в PCM S16LE и обратно без изменения call/channel/generation
  metadata.
- `PcmFanOut` — специализированный bounded fan-out с независимыми каналами `vad` и `asr_input_accumulator`;
  медленный consumer не блокирует остальные и теряет только собственные frames.
- `AsrChunker` собирает media frames в target 1000 ms, умеет timer flush, hard-endpoint flush, graceful close,
  cancel с discard stale tail и observable non-blocking overflow.

Локальные output-типы остаются candidate до propagation checkpoint `I1–I2`; они не являются authoritative для `002-D`,
VAD, ASR или Map-002-I. Main executor должен отдельно сверить `PcmFrame` на `N3→N5/N4`, `AsrAudioChunk` на `N4→N7`
и обновить следующую ревизию Map-002-I. При изменении контракта этот child plan требует corrective pass.

## Красные результаты, исправленные до closeout

Первый isolated target command с `-m pytest` получил `ModuleNotFoundError: config`: существующий unit/contract
`conftest.py` добавляет только `src`, тогда как пакетный `sip_bot` импортирует `config` из project root. Это ошибка
команды/fixture-окружения по APG §5.8B, не ошибка C-кода и не внешний blocker. Повторный запуск через isolated
`python -c` с явным project root прошёл.

Первый runtime probe проверял несуществующий `sys.Py_GIL_DISABLED` и завершился assertion failure. По принятому в
проекте runtime contract проверка исправлена на `sysconfig.get_config_var("Py_GIL_DISABLED")`; повторная проверка
прошла с `1` и `sys._is_gil_enabled() is False`.
