# 001-D baseline register draft

Дата: `2026-08-27`  
Статус: `evidence-backed draft; implementation hand-off candidate`

Это не новый выбор компонентов. Register только нормализует решения, уже принятые в A–C, и показывает, что именно
можно передать в следующий implementation plan. Неизмеренные свойства остаются `deferred` или `undecided`.

| Контур | Frozen candidate | Decision | Process boundary | Thread/task status | Control/data boundary | Evidence | Ограничения и следующий hand-off |
|---|---|---|---|---|---|---|---|
| Environment | Ubuntu 24.04.4 LTS / WSL2, RTX 5060 Ti, `sipbot` | `complete` в scope environment baseline | Host + Ubuntu WSL2; source root on ext4 | N/A | N/A | A closeout, `inventory.json`, A commands | Source checkout/revision ещё не применялись; это не блокирует feasibility, но повторить source-root check после появления кода |
| Runtime | CPython `3.14.7t`, `cpython-314t-x86_64-linux-gnu` | `pass` | Main process baseline | Controlled concurrency pass; app scheduler not chosen | Runtime does not own payload | B closeout, runtime-manifest, E-001B-* | Native compatibility проверяется отдельно; `_zstd` optional and out-of-scope |
| SIP signaling | PJSUA2/PJMEDIA `2.17` | `pass` for tested MVP path | Main process with two explicit generated-SWIG patches | `undecided` for application callback affinity | Protocol-level reactions remain in SIP adapter; semantic events/commands use Dispatcher | C1 closeout, candidate manifest, patched import, `001-S` lifecycle/BYE | Arbitrary native thread-safety and complete application SIP adapter not proven; BYE is only the tested minimum example; preserve patches |
| RTP/media | PJMEDIA + approved local `001-S` peer | `pass` for PCMU boundary | Same tested SIP/media process + separate test peer | Native callback affinity `undecided` | PCMU/8000/1 at RTP boundary; PCM direct to channels | C1/`001-S` PCMU evidence | Full media ingress/egress channels and overflow policy deferred |
| ASR | `faster-whisper==1.2.1`, `Systran/faster-whisper-large-v3` revision `edaa852...` | `pass` tested patched main-process path | Main free-threaded CPython; CTranslate2 `4.8.1` local patch required | `undecided` for generator worker/task placement | PCM direct in; partial/final text direct out | C2 closeout, C2-OR-001…010 | No hard native cancel token; CTranslate2 arbitrary multithread safety not proven; preserve patch/build |
| VAD | `faster_whisper.vad` import only | `deferred` | Candidate main process not separately accepted | `undecided` | PCM flags direct to endpointing | C2 import + architecture | Separate VAD operation and false-positive/negative behavior belong to speech pipeline plan |
| Transcript Assembler | No runtime candidate yet | `deferred` | `undecided` | `undecided` | ASR revisions direct; final metadata to Dispatcher | Architecture + C2 partial/final observation | Implement after D; do not promote partial text to FSM action |
| Turn Detector / endpointing | Fixed soft/hard heuristic contract | `deferred` | `undecided` | `undecided` | VAD flags direct; endpoint events via control plane | Architecture/requirements | 250–300 ms soft and ~500 ms hard values remain configuration/design inputs, not tested application behavior |
| LLM controller | Qwen3.5-9B Q4_K_M, Python stdlib HTTP client | `pass` as controller boundary | Main no-GIL process | Request worker/task placement `undecided` | Final turn/context to adapter; action metadata to Dispatcher | C3 import/controller evidence | No native inference module in main; concrete adapter implementation deferred |
| LLM inference | Ollama `0.33.1`, bundled native CUDA runner | `pass_with_isolation` | Separate local native process | Runner-managed; Python affinity N/A | Existing HTTP IPC on `127.0.0.1` | C3 candidate/inference/VRAM/cancel evidence + owner decision | Warm valid response `2121.229 ms`; cold start `52716.908 ms`; client close suppresses stale result but no hard native cancel ack |
| Retrieval/RAG | No selected runtime | `deferred` | `undecided` | `undecided` | Compact retrieval fragments direct to LLM | ADR-002/requirements only | Natural-science KB and retrieval implementation belong to next implementation slice |
| TTS | XTTS-v2 v2.0.3, exact patched dependencies | `pass` tested patched main-process path | Main free-threaded CPython | `undecided` for stream worker/task | Approved text direct in; PCM direct to playback | C4 closeout, import/operation/PCMU/cancel evidence | First PCM `1308.4 ms`; complete `1776.8 ms`; generator close is not hard native cancellation |
| Playback | Local C4 output boundary | `deferred` for real call | `undecided` | `undecided` | TTS PCM direct to buffer/media egress | C4 local boundary + architecture | Real RTP playback/barge-in and stale queued audio require implementation/test stand integration |
| Fake operator | `001-S` local peer/transfer scenario | `pass` as test infrastructure | Separate local peer process | Peer-managed | SIP control/RTP direct to product SIP boundary | `001-S` transfer evidence | Not a production operator service and not a real PBX implementation |

## Baseline promotion rules

1. Main-process baseline означает `CPython 3.14.7t` без автоматического возврата GIL на проверенных стадиях.
2. C1/C2/C4 можно переносить в основной процесс только вместе с exact patch/build constraints; непатченные native
   wheels не являются эквивалентным baseline.
3. C3 переносится только как `main controller + isolated local inference server + HTTP IPC`.
4. Dispatcher получает semantic control and lifecycle events, но не является транспортом для аудио или больших
   текстовых payload.
5. Ни один текущий результат не закрывает concurrent ASR+LLM+TTS VRAM, full end-to-end latency, application callback
   affinity или production readiness.
