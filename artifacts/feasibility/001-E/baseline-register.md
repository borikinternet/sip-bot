# 001-E final baseline register

Дата: `2026-08-27`  
Статус: `evidence-backed; implementation hand-off with deferred integration`

Register не выбирает новые компоненты. Он нормализует уже принятые решения и отделяет candidate feasibility от полной
готовности демонстратора.

| Контур | Версия / лицензия | Evidence-backed result | Process / thread boundary | Control / data boundary | Observations и ограничения |
|---|---|---|---|---|---|
| Environment | Ubuntu 24.04.4 LTS / WSL2; RTX 5060 Ti 16 GiB; `sipbot` | `complete` в scope environment baseline | Host + Ubuntu WSL2; source root на ext4 | N/A | Минимальный свободный запас диска `20 GiB`; native Ubuntu и production deployment не проверялись |
| Runtime | CPython `3.14.7t`, PSF-2.0; SOABI `cpython-314t-x86_64-linux-gnu` | `pass` | Main-process baseline, GIL disabled | Runtime не владеет payload | `Py_GIL_DISABLED=1`; `_is_gil_enabled()` остаётся `False` в B probes; `_zstd` optional и out of scope |
| SIP signaling | PJSUA2/PJMEDIA `2.17`, PJSIP `GPL-2.0` по source `COPYING`; SWIG `4.2.0` | `pass` в tested patched path | Main free-threaded process; application callback affinity `undecided` | Protocol-level reactions (`BYE`, `CANCEL`, `OPTIONS`, `re-INVITE`/`UPDATE`, media/transport errors) остаются у SIP adapter; semantic events идут через Dispatcher | Обязательны `pjsua2-free-threading.patch` и `pjsua2-free-threading-buffer.patch`; tested responsiveness покрывает BYE, остальные protocol cases — implementation scope |
| RTP/media | PJMEDIA `2.17`; local Baresip peer `1.0.0-4build14`, BSD-3-Clause package metadata | `pass` для PCMU/8000/1 boundary | Product candidate + отдельный local peer process | PCMU/8000/1 на RTP boundary; PCM direct to channels | Full application ingress/egress, overflow и playback channel deferred |
| ASR | `faster-whisper==1.2.1` MIT; model `Systran/faster-whisper-large-v3`, revision `edaa852...`, MIT; CTranslate2 `4.8.1` MIT | `pass` tested patched main-process path | Main free-threaded process; generator worker/task affinity `undecided` | PCM direct in; partial/final text direct out | Exact `ctranslate2-free-threading.patch`; load `8.375 s`; native cancellation token отсутствует, close + stale suppression pass |
| VAD | `faster_whisper.vad` import path only | `deferred` | Main placement `undecided` | Audio flags direct to endpointing | Operation, thresholds and false-positive/negative behavior не проверялись |
| Transcript Assembler | Runtime candidate отсутствует | `deferred` | `undecided` | ASR revisions direct; final metadata to Dispatcher | Must keep stable prefix/revised tail separate; partial text не authoritative |
| Turn Detector / endpointing | Fixed soft/hard contract from requirements | `deferred` | `undecided` | VAD flags direct; endpoint events via control plane | Soft `250–300 ms`, hard около `500 ms` — конфигурационные inputs, not runtime evidence |
| LLM controller | Python stdlib `urllib.request`; model contract Apache-2.0 candidate | `pass` as controller boundary | Main no-GIL process | Final turn/context direct to adapter; validated action metadata to Dispatcher | No native inference module in main; full action validator and context assembly deferred |
| LLM inference | Qwen3.5-9B GGUF Q4_K_M, Apache-2.0 artifact; Ollama `0.33.1` | `pass_with_isolation` | Separate local native Ollama process; runner bundled `llama.cpp` | Existing HTTP IPC `127.0.0.1:11434`; Dispatcher is not payload proxy | Warm valid response `2121.229 ms`; cold valid response `52716.908 ms`; peak `8227 MiB`; no hard native cancel ack |
| Retrieval / RAG | Russian Wikipedia thematic slice; CC BY-SA 4.0/GFDL obligations per requirements | `deferred` | `undecided` | Compact retrieval fragments direct to LLM | No selected index/runtime; attribution and ShareAlike materials required before publication |
| TTS | XTTS-v2 v2.0.3, CPML 1.0.0; `coqui-tts==0.27.5` MPL-2.0 | `pass` tested patched main-process path | Main free-threaded process; stream worker/task affinity `undecided` | Approved text direct in; PCM direct to playback | Exact torchaudio/tokenizers/MAS patches; first PCM `1308.4 ms`, complete `1776.8 ms`; no hard native cancel |
| Playback | Local C4 PCM/PCMU boundary only | `deferred` for real call | `undecided` | TTS PCM direct to media egress | Real RTP playback, queued audio close and barge-in remain integration work |
| Fake operator | Baresip `1.0.0-4build14`, BSD-3-Clause package metadata | `pass` as local test infrastructure | Separate local peer process | SIP transfer/RTP direct to test stand | Not a real PBX/operator service; final product transfer adapter deferred |

## Baseline promotion rules

1. Main process uses free-threaded CPython `3.14.7t`; automatic GIL re-enable is not accepted.
2. C1/C2/C4 enter the main process only with their exact recorded patches and build constraints. Unpatched wheels are
   not equivalent to the accepted baseline.
3. C3 enters the system only as `main no-GIL controller + isolated local Ollama inference + HTTP IPC`.
4. Dispatcher owns control plane, Dialogue FSM and semantic action validation; audio and large text payload do not pass
   through it.
5. No current result closes integrated VAD/assembler/RAG, application callback affinity, concurrent ASR+LLM+TTS VRAM,
   full end-to-end latency, real RTP barge-in or production readiness.
