# C3 execution closeout

Plan: `001-C3`
Stage: dependency/artifact preparation + authorized GPU execution
Candidate: `Qwen/Qwen3.5-9B`, primary only, 4-bit
Backend: `Ollama 0.33.1` with bundled native CUDA runner
Plan closeout status: `complete`
Candidate decision: `pass_with_isolation`

## Scope guard

The authorized GPU stage loaded the pinned model and generated the required structured answer. No fallback model was
used. The project owner explicitly accepted the external local native-process boundary with HTTP IPC. This is a
`pass_with_isolation` result, not a claim that the native inference runtime is a main-process no-GIL component.

## Owner decision

- Main process: free-threaded CPython; no Python-native inference module import.
- Inference process: local Ollama with bundled native `llama.cpp` CUDA runner.
- IPC: existing HTTP boundary over `127.0.0.1`.
- Scope: accepted for the MVP C3 baseline; no cloud/external inference API and no production-readiness claim.

## Prepared files

- `question.txt` — fixed Russian natural-science fixture.
- `prompt.json` — synthetic authoritative final-phrase handoff and restricted structured-output contract.
- `import-probe.json` — no-GIL/runtime preflight and backend discovery result.
- `inference.json` — successful GPU generation with final-phrase timing fields.
- `vram.json` and `vram-samples.csv` — sampled GPU memory evidence.
- `cancellation.json` — successful client-close cancellation observation.
- `measurements.md` — timing formulas and deferred command shape.
- `stdout.log`, `stderr.log` — preparation command output placeholders.
- `tools/llm_primary_probe.py` — preflight/import scaffolding and the executed GPU stage with the required final-phrase timing contract.
- `Modelfile` — exact local GGUF source and disposable Ollama parameters.
- `candidate-manifest.json` — pinned backend, model, artifact and hash provenance.

## Observed non-GPU baseline

- Ubuntu 24.04.4 LTS / WSL2 / x86_64.
- CPython `3.14.7t`, SOABI `cpython-314t-x86_64-linux-gnu`, `Py_GIL_DISABLED=1`, GIL disabled before backend checks.
- RTX 5060 Ti, 16,311 MiB reported memory, driver `610.88`.
- The target free-threaded environment has no installed `torch`, `transformers`, `accelerate`, `safetensors`,
  `bitsandbytes`, `llama_cpp` or `vllm` module available for a non-invasive discovery check; this does not claim that
  every possible non-Python backend was exhaustively inspected.
- Initial preflight found no local Qwen3.5-9B artifact/revision; the later authorized download is recorded below.

## Prepared backend/artifact result

- Ollama release `v0.33.1` was downloaded to the disposable WSL environment and verified against SHA-256
  `88e0d36bd90121595e5516c84f6ab61b546368fbd2d825b4aae70999c949649d`.
- The archive contains bundled CUDA 12 and CUDA 13 native runners; no CUDA toolkit or Python-native inference module
  was installed.
- Quantized artifact `unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf` at revision
  `3885219b6810b007914f3a7950a8d1b469d598a5` is present at the pinned local path and has size `5680522464` bytes and
  SHA-256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`.
- The WSL relocation did not reset the download: the final artifact was assembled from the saved range parts under
  `/home/sipbot/models/c3-qwen35-9b-gguf/ranges/`; only truncated parts 36–40 were retried with temporary files and
  atomic replacement. No full restart was performed.
- The base model relation is recorded as `Qwen/Qwen3.5-9B`, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
- The target CPython `3.14.7t` imported the standard-library `urllib.request` controller with GIL disabled before and
  after import. Ollama is used across an external native-process boundary; no Python-native backend module is involved.

## GPU execution result

- One-shot structured inference completed successfully for the fixed Russian question. The response was valid JSON with
  `action=answer` and non-empty Russian `text`; no Markdown, reasoning trace or SIP target was accepted.
- Warm GPU run timings from synthetic authoritative final-phrase handoff:
  `final_phrase_to_first_useful_output_ms=177.400` and
  `final_phrase_to_first_valid_response_ms=2121.229`.
- A preceding cold run was also recorded in the execution log: first useful output at `50076.353 ms` and first valid
  response at `52716.908 ms`. The cold-start value is not hidden by the warm-run result.
- VRAM sampling during a successful GPU request produced 375 samples at 200 ms. Maximum sampled usage was `8227 MiB`
  of `16311 MiB`, minimum free memory was `7824 MiB`, headroom at sampled peak was `8084 MiB`, and OOM was false.
- Cancellation started a streamed request, observed the first useful chunk after `222.849 ms`, closed the HTTP response,
  observed zero tokens after close and accepted no final/stale result. Ollama's HTTP API exposes no separate cancellation
  acknowledgement; this limitation is explicitly recorded in `cancellation.json`.

## Blockers

- `B-C3-S0-002`: resolved: Ollama `0.33.1` is installed and its local command/API boundary is reproducible.
- `B-C3-S0-003`: resolved: the pinned Qwen3.5-9B Q4_K_M artifact is present and hash-verified.
- `B-C3-S1-001`: resolved for the Python controller: GIL remained disabled before and after `urllib.request` import;
  the native inference server is not imported into that process.
- `B-C3-S1-002`: resolved by the owner decision accepting the existing local HTTP process boundary; it is classified as
  `pass_with_isolation`, not as a main-process inference baseline.
- `B-C3-S2-001`, `B-C3-S3-001`, `B-C3-S4-001`: resolved by `inference.json`, `vram.json`/samples and
  `cancellation.json` within the accepted isolation boundary.
- `B-C3-S5-001`: resolved; command, version, result and evidence provenance are recorded.

The dirty worktree was captured before preparation. Existing changes outside the C3 write-set were preserved and not
modified by this stage.

## Required next step

The next step is to carry the accepted C3 boundary into `001-D` and the concrete LLM adapter design: the main process
must use the existing HTTP IPC, while Dispatcher remains the owner of structured decisions and call state. No fallback
model is authorized by this result.
