# 001-D process/thread boundary matrix

Дата: `2026-08-27`  
Статус: `synthesis complete; undecided/deferred items explicit`

## Правило интерпретации

`main` означает процесс, в котором соответствующий tested path действительно был проверен. Это не означает, что
thread/task affinity уже выбрана для будущего приложения. `isolated` означает отдельный процесс с явной границей.
`undecided` сохраняется, если child evidence показывает operation, но не доказывает конкретную affinity или интегрированный
lifecycle приложения.

| Компонент / capability | Process boundary | Thread/task boundary | Control-plane owner | Data-plane owner и направление | Evidence | Итог |
|---|---|---|---|---|---|---|
| Main Dispatcher / Dialogue FSM | `main` | Serialized owner execution; конкретный executor ещё не выбран | Dispatcher/FSM | Не является транзитным владельцем payload | `architecture.md`, ADR-001 | Protected invariant; implementation deferred |
| SIP adapter: PJSUA2/PJMEDIA | `main` в tested patched path | `undecided`; PJSIP/native callback affinity не сведена к app scheduler | SIP adapter для protocol callbacks; Dispatcher для semantic events | SIP/media adapter owns RTP boundary; PCM channels direct | C1 manifest, patched lifecycle, `001-S` | `pass` within C1 limits |
| Mandatory SIP protocol reaction | Тот же SIP process | SIP stack callback/native context; exact application affinity `undecided` | SIP adapter отвечает немедленно на обязательную транзакцию; Dispatcher получает normalized semantic event при необходимости | Нет payload transfer | C1 BYE evidence как минимальный пример | Protocol responsiveness boundary pass for tested BYE case; broader transaction matrix deferred |
| Media ingress/egress | Внутри SIP/media process | `undecided`; callback-to-channel handoff not integrated | Media lifecycle owner + Dispatcher for open/close | PCMU ↔ PCM direct to/from bounded channels | C1 PCMU evidence, `001-S` | Boundary pass; channel implementation deferred |
| VAD | `main` candidate path, в составе ASR runtime | `undecided`; отдельная VAD operation не выполнялась | Turn Detector/Dispatcher получает flags/events | PCM frames direct from media ingress | C2 import of `faster_whisper.vad`; architecture contract | Candidate import only; operation deferred |
| Streaming ASR: faster-whisper | `main` free-threaded CPython with patched CTranslate2 | `undecided`; generator/worker scheduling not promoted to app contract | ASR owns operation; Dispatcher receives finality/cancel metadata | PCM → ASR; partial/final text → Transcript Assembler direct | C2 import, operation, partial-final, cancel | `pass` tested candidate path |
| Transcript Assembler | `main` planned component | `undecided` | Owns revision/stable-prefix and finalization metadata | ASR partials → current hypothesis/final text direct | Architecture; C2 observation only | Not implemented; deferred to speech pipeline |
| Turn Detector / endpointing | `main` planned component | `undecided` | Owns pause/soft/hard endpoint events | VAD flags direct; no large payload through Dispatcher | Architecture/requirements | Not implemented; deferred to speech pipeline |
| LLM adapter/controller | `main` free-threaded CPython; stdlib HTTP only | `undecided`; request task/worker model to be chosen in implementation | Dispatcher owns action validation and cancellation command | Final turn/context to adapter; HTTP carries prompt/result to local server | C3 import/controller evidence, architecture | Main controller pass |
| LLM native inference server | `isolated` local Ollama process | Native runner-managed; not claimed as Python affinity | LLM adapter owns request lifecycle; Dispatcher does not enter server | HTTP request/stream result direct between adapter and server | C3 manifest, closeout, owner decision | `pass_with_isolation` |
| Retrieval/RAG | `undecided` | `undecided` | Dialogue/LLM pipeline owner | Retrieval context direct to LLM adapter | Requirements/ADR-002 only | Not tested; deferred |
| TTS: XTTS-v2 | `main` free-threaded CPython with exact patched dependencies | `undecided`; generator stream can be wrapped by a future worker/task | TTS/playback lifecycle obeys Dispatcher cancel/close | Approved answer text → TTS; PCM → playback direct | C4 import/operation/cancel/PCMU evidence | `pass` tested patched path |
| Playback buffer/media egress | `main` candidate path | `undecided`; real barge-in channel not integrated | Dispatcher opens/closes playback; media owner drains buffer | TTS PCM → playback → PCMU/RTP direct | C4 local boundary + architecture | Local boundary pass; integration deferred |
| Local fake operator / VoIP peer | Separate test process, outside product main process | Peer-managed | Stand control protocol | RTP/PCMU direct to SIP adapter | `001-S` lifecycle/PCMU/BYE/transfer | Approved test infrastructure; not product boundary |

## Component promotion rules

- C1, C2 и C4 могут быть размещены в основном no-GIL-процессе только с зафиксированными patch/build constraints;
  использование непатченных binary wheels не является эквивалентным baseline.
- C3 размещается в отдельном процессе. В основной процесс не импортируется native inference module; HTTP на loopback —
  существующий IPC, не новый Dispatcher path.
- Ни один child closeout не доказал конкретную thread/task affinity callback-ов приложения. Поэтому D не выбирает
  `asyncio`, worker thread или отдельный app thread как факт; это implementation decision следующего плана.
- `pass`/`pass_with_isolation` здесь означает только component feasibility. Он не означает concurrent GPU fit,
  сквозную отмену native kernel или production readiness.
