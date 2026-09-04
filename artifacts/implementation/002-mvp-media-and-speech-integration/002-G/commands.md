# Commands and exit codes

Команды выполнялись из `C:\devel\sip-bot`.

| Команда | Exit code | Результат |
|---|---:|---|
| `python -m pytest -q tests/unit/test_llm_facade.py tests/contract/test_llm_http.py` | 0 | `7 passed` |
| `python -m pytest -q tests/unit tests/contract` | 0 | `80 passed` |
| `python -m compileall -q src/sip_bot/llm` | 0 | compile pass |
| `PYTHONPATH=src python -c "... import sip_bot.llm ..."` | 0 | host import pass |
| `wsl.exe -d Ubuntu-24.04 -- ... python3.14t -c "... import sip_bot.llm ..."` | 0 | target import pass, `gil_enabled=false` |
| `wsl.exe -d Ubuntu-24.04 -- ... python3.14t -` (main facade, `/api/embed` + `/api/chat`) | 0 | real embedding index/query and structured chat pass; see `real-provider-probe.json` |
| `nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader,nounits` | 0 | RTX 5060 Ti, 16311/9807/6244 MiB at sample |

Real provider probe выполнен только main executor после deterministic acceptance. Ollama 0.33.1 использовал локальные
Qwen3.5-9B Q4_K_M и `embeddinggemma`; полные model digests, параметры и latency находятся в
`real-provider-probe.json`. Subagent не запускал heavy GPU inference.
