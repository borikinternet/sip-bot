# C3 measurements and execution commands

Статус этого файла: GPU execution выполнен; ниже сохранены timing contract, фактические измерения и форма команды
для воспроизведения. Это не статистический benchmark и не автоматическое решение owner boundary.

## Required timing boundary

The successful S2/S3 run must create a synthetic authoritative final-phrase handoff for the already-final string from
`prompt.json`. Immediately before passing that handoff to the LLM backend, record `final_phrase_received_at` with
`time.monotonic_ns()`. Immediately before submitting the backend request, record `request_started_at` with the same
clock. Record the first non-empty useful output chunk/token and the first fully valid structured response with the same
monotonic clock.

Required derived values, in milliseconds:

```text
final_phrase_to_first_useful_output_ms = (first_useful_output_at - final_phrase_received_at) / 1_000_000
final_phrase_to_first_valid_response_ms = (first_valid_response_at - final_phrase_received_at) / 1_000_000
request_to_first_useful_output_ms = (first_useful_output_at - request_started_at) / 1_000_000
request_to_first_valid_response_ms = (first_valid_response_at - request_started_at) / 1_000_000
```

The first two intervals are the requested model-facing measurement. They deliberately exclude ASR, VAD, SIP, RTP,
network and TTS time. A non-streaming backend may set the useful-output timestamp and its derived value to
`not_available`; a successful run must still provide `final_phrase_to_first_valid_response_ms`.

## Safe preparation command already run

```text
wsl.exe -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t /mnt/c/devel/sip-bot/tools/llm_primary_probe.py --stage preflight --evidence-root /mnt/c/devel/sip-bot/artifacts/feasibility/001-C3-llm-primary
```

This command performs runtime/GIL checks, installed-module discovery and no model/backend import. It does not download,
load or generate.

Additional read-only metadata commands used for the preflight record:

```text
wsl.exe -d Ubuntu-24.04 -- nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,memory.free --format=csv,noheader
wsl.exe -d Ubuntu-24.04 -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pip list --format=json
wsl.exe -d Ubuntu-24.04 -- bash -lc "find /home/sipbot/.cache /home/sipbot/src /mnt/c/devel/sip-bot -maxdepth 4 -type d \( -iname '*qwen*' -o -iname '*model*' -o -iname '*transformers*' -o -iname '*llama*' \) -print 2>/dev/null | head -100"
```

The first command is GPU inventory only; it is not a VRAM load/peak benchmark. The third command found no matching
local Qwen/model/backend artifact in the inspected locations.

## Prepared backend and model commands

The disposable backend is `/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama`, version `0.33.1`. The exact local GGUF is
referenced by the prepared `Modelfile`. These commands register the local file in Ollama's disposable model store;
they do not perform a chat request or generation:

```text
export OLLAMA_MODELS=/home/sipbot/models/c3-ollama-store
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama serve
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama create c3-qwen35-9b-q4km --file /mnt/c/devel/sip-bot/artifacts/feasibility/001-C3-llm-primary/Modelfile
```

The `serve`/`create` pair is intentionally deferred until the main GPU execution stage, because the server may inspect
the model and create a native runner. The artifact itself is already downloaded and hash-verified.

## Actual GPU execution result

The authorized GPU run used Ollama `0.33.1` and the pinned Qwen3.5-9B Q4_K_M artifact. It returned valid structured
JSON for the fixed Russian question. Warm-run timings were:

```text
final_phrase_to_first_useful_output_ms = 177.400
final_phrase_to_first_valid_response_ms = 2121.229
request_to_first_useful_output_ms = 177.392
request_to_first_valid_response_ms = 2121.221
```

A preceding cold run measured `50076.353 ms` to first useful output and `52716.908 ms` to first valid response. The
warm/cold distinction is intentional: the user-visible model delay depends strongly on whether the local native server
has already loaded the model.

## GPU execution command shape для воспроизведения

The backend is fixed for the primary execution: Ollama `0.33.1` with the local, hash-verified GGUF above. The recorded
run used the following command shape; a повторный запуск также должен использовать primary only:

```text
OLLAMA_MODELS=/home/sipbot/models/c3-ollama-store /home/sipbot/src/c3-ollama/v0.33.1/bin/ollama serve
<CP314T> /mnt/c/devel/sip-bot/tools/llm_primary_probe.py --stage gpu --allow-gpu --ollama-url http://127.0.0.1:11434 --ollama-model c3-qwen35-9b-q4km --prompt-file /mnt/c/devel/sip-bot/artifacts/feasibility/001-C3-llm-primary/prompt.json --evidence-root /mnt/c/devel/sip-bot/artifacts/feasibility/001-C3-llm-primary
```

The probe implements this GPU command shape behind an explicit `--allow-gpu` guard. The completed run wrote
`inference.json`; VRAM and cancellation evidence are in `vram.json` and `cancellation.json`. It must not silently
select another model or treat a metadata-only preflight as a pass.
