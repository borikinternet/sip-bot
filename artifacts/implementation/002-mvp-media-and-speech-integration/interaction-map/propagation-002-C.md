# Map-002-I propagation: 002-C

Дата: `2026-09-03`  
Входная ревизия: `Map-002-I revision 4`  
Результат: `accepted by main executor; propagated into revision 5`

## Проверенный output

`002-C` передал в speech boundary:

- `PcmFrame` с per-call `NegotiatedMediaProfile`;
- `PcmFanOutSubscription` для независимых bounded direct channels `vad` и
  `asr_input_accumulator`;
- `AsrAudioChunk` из `sip_bot.media.asr_chunker` с PCM S16LE, profile,
  `FlushReason` и `is_final`.

Сохранены timer/target/hard-endpoint/close/cancel и overflow semantics.
Аудио и chunk payload не проходят через Dispatcher/Event Bus.

## Проверка propagation

На I1 было обнаружено, что D содержал дублирующий одноимённый тип
`AsrAudioChunk` с другой схемой. Тип удалён из speech-local contracts; D теперь
использует authoritative тип C. Contract-файл
`tests/contract/test_boundary_propagation.py` проверяет identity типа,
`NegotiatedMediaProfile`, `FlushReason` и приём chunk в
`StreamingAsrAdapter`.

Результат после corrective pass: `64 passed` для unit/contract текущего
дерева; `compileall: PASS`.

## Downstream handoff

- `N3 → N5`: `PcmFrame` напрямую в VAD;
- `N3 → N4`: тот же `PcmFrame` в независимый ASR accumulator;
- `N4 → N7`: `media.AsrAudioChunk` напрямую в ASR adapter.

Публичная/authoritative revision Map-I обновлена с 4 до 5.
