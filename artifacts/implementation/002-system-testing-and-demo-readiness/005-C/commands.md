# 005-C commands and exit codes

Дата: `2026-09-04`  
Target: Ubuntu 24.04/WSL2, CPython `3.14.7t`, `gil_enabled=false`.

| Проверка | Команда/вариант | Exit | Результат |
|---|---|---:|---|
| C deterministic source/playback tests | `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q tests/unit/test_map005_ai_playback.py tests/contract/test_map005_ai_playback.py tests/integration/test_map005_ai_gate.py` | 0 | `6 passed in 1.05s` |
| C target preflight | `nvidia-smi` + `df -Pk /mnt/c /` + target runtime probe | 0 | RTX 5060 Ti, 16,311 MiB; C free space >20 GB; target Python free-threaded, GIL disabled |
| C main AI gate | `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/map005_ai_gate.py --allow-gpu --output-root .../005-C/target-20260904-r1 --timeout 240` | 0 | `status=pass`; source-aware RAG → Qwen3.5-9B/Ollama → XTTS PCM; no fallback |
| C clean live-path after source-mode change | `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/j4_full_live_gate.py --output-root .../005-C/target-live-20260904-r1 --timeout-s 240` | 0 | `status=pass`; Baresip SIP/RTP, 6/6 scenarios, source counters clean |
| Target regression after C changes | `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q tests/unit tests/contract tests/integration` | 0 | `147 passed, 2 skipped in 9.24s` |

The first target AI gate found two stale processes from an earlier J4 run holding VRAM; they were terminated
gracefully before the gate. The preflight immediately before the new gate then showed `13036 MiB` free VRAM.

The real gate records `embedding_index=6943.350 ms`, LLM warmup `10484.631 ms`, TTS warmup `508.794 ms`, LLM
`final_phrase→first_useful=488.600 ms`, `final_phrase→valid=1518.092 ms`, TTS first PCM `263.917 ms` from TTS start
and `1785.090 ms` from final phrase, completion `2587.321 ms`, and 11 TTS chunks. Warmup is pre-call and excluded
from the measured turn.

The `target-20260904-r1/map005-c-ai-gate.json` and `tts-answer-sample.wav` are primary evidence. The accepted `002-H`
`cancellation.json` is reused for the known XTTS generator-close limitation; the new deterministic C tests cover the
source lifecycle and stale/barge-in behavior.

The clean live-path `target-live-20260904-r1/j4-full-live.json` confirms the source-mode accounting on the actual
PJMEDIA clock: `egress_underruns=0`, `tts_startup_wait=132`, `intentional_silence_frames=4629`,
`source_mode_transitions=16`, `callback_errors=0`, and no dropped/stale frames. Baresip peer recording remains a D
rehearsal requirement and is not falsely claimed by this J4 run.
