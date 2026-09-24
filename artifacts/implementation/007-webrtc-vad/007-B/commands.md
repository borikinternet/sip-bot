# 007-B — команды и результаты

Дата: `2026-09-13`

## Host targeted

```text
python -m pytest -q tests/unit tests/integration/test_runtime_wiring.py tests/integration/test_map005_speech_resilience.py tests/contract
```

Результат: `136 passed, 2 skipped`, exit code `0`.

```text
python -m py_compile tools/live_i1_gate.py tools/j4_full_live_gate.py src/sip_bot/config.py config/constants.py
```

Результат: exit code `0`.

## Target free-threaded runtime

Использован `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t` с project paths,
добавленными внутри probe после `-I`.

```text
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/devel/sip-bot && /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -c "import sys; sys.path.insert(0, \"/mnt/c/devel/sip-bot\"); sys.path.insert(0, \"/mnt/c/devel/sip-bot/src\"); import pytest; raise SystemExit(pytest.main([\"-q\", \"tests/unit/test_config.py\", \"tests/unit/test_webrtc_vad_application_boundary.py\", \"tests/unit/test_speech_ingress.py\", \"tests/unit/test_map005_speech_resilience.py\"]))"'
```

Результат: `18 passed, 2 skipped`, exit code `0`.

## Фактическое изменение application boundary

- `config/constants.py`: добавлен `VAD_MODE = 2`;
- `src/sip_bot/config.py`: добавлен `RuntimeConfig.vad_mode` с явным mapping из constants;
- `tools/live_i1_gate.py` и `tools/j4_full_live_gate.py`: construction переключён на WebRTC в следующем child plan
  `007-C`, после того как B зафиксировал конфигурационный input и contract evidence;
- `tests/unit/test_webrtc_vad_application_boundary.py`: проверяет `VadProcessor → WebRtcVadCandidate → VadDecision`,
  сохранение negotiated sample rate и отсутствие изменения typed speech contract.

Amplitude test doubles не удалялись и не считаются application/live evidence.
