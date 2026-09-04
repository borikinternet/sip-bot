# 001-D control/data plane map

Дата: `2026-08-27`  
Статус: `synthesis complete`

## 1. Общие правила

- Dispatcher владеет control plane, semantic state и lifecycle каналов.
- Аудио и большие текстовые payload идут напрямую между producer и consumer и не проходят через Dispatcher.
- В control events передаются небольшие метаданные: `call_id`, `turn_id`, `generation_id`, тип события, состояние и
  ссылки/handles на payload. Эти идентификаторы не заменяют close semantics.
- При закрытии канала данные старого поколения отбрасываются; late/stale result не публикуется. Для C3 HTTP client
  close подтверждён, но отдельного native cancellation acknowledgement нет.

## 2. Control plane

| Event/command | Producer | Consumer / owner | Wait policy | Cancel/close policy | Status / evidence |
|---|---|---|---|---|---|
| Incoming `INVITE`, answer/decline lifecycle | SIP adapter | Dispatcher/FSM; SIP adapter выполняет обязательные protocol callbacks | Dispatcher не ждёт AI | Call lifecycle owns close | C1 lifecycle; semantic integration deferred |
| SIP protocol event / transaction | SIP adapter/native SIP callback | SIP adapter immediately sends mandatory response or applies protocol/media reaction; Dispatcher receives a normalized semantic event when the application state is affected | No wait for Dispatcher/AI | Apply event-specific channel/lifecycle policy; terminal events close all call channels | C1 BYE pass as minimum example; broader `CANCEL`/`OPTIONS`/`re-INVITE`/RTP matrix is integration work |
| `speech_started`, `pause_candidate`, `soft_endpoint`, `speech_resumed`, `hard_endpoint` | VAD/Turn Detector | Dispatcher/FSM for lifecycle; Turn Detector owns heuristic | Event enqueue must be bounded/non-blocking | Close speculative/current channel on resume/finalization | Architecture contract; implementation deferred |
| `utterance_final` metadata | Transcript Assembler | Dispatcher receives finality metadata; LLM adapter receives full text directly | No large text through Dispatcher | Turn close invalidates old generation | C2 final evidence + architecture; direct channel implementation deferred |
| ASR/LLM/TTS error and timeout | Component owner | Dispatcher/FSM | Event-based, bounded timeout | Close affected generation/channel | Child cancellation evidence; integrated policy deferred |
| LLM structured action `{action, ...}` | LLM adapter | Dispatcher/FSM validates and applies | Dispatcher does not block on LLM | Old result rejected after generation close | ADR-001 + C3 structured result |
| `answer`, `clarify`, `offer_transfer`, `transfer`, `hangup` commands | Dispatcher/FSM | TTS and/or SIP adapter | Commands are state transitions, not long-running payload calls | Idempotent close; transfer target from config | ADR-001/requirements; full implementation deferred |
| `tts_open`, `tts_close`, `barge_in` | Dispatcher/FSM | TTS/playback owner | No wait for synthesis completion | Close playback immediately; discard queued old PCM | Architecture/C4 local cancel evidence; RTP integration deferred |
| `cancel_asr`, `cancel_llm`, `cancel_tts` | Dispatcher | Corresponding component adapter | Send signal, do not wait for native kernel | Candidate close semantics; no hard native cancel claim | C2/C3/C4 cancellation evidence |
| `transfer` target | Config/constants + Dispatcher | SIP adapter | Dispatcher resolves configured target; model never supplies SIP address | Call state owns transfer completion/failure | Requirements/ADR-001/`001-S` stand coverage |
| Dialogue context checkpoint/report | Dialogue manager | Per-call context/report writer | Must not block SIP callback | Write/update per-call file; finalize post-call | Requirements/technical spec; runtime implementation deferred |

## 3. Data plane

| Payload | Producer | Consumer | Format / boundary | Boundedness and close | Status / evidence |
|---|---|---|---|---|---|
| Inbound RTP audio | SIP peer / SIP adapter | Media ingress | PCMU/G.711 mu-law, 8 kHz, mono | RTP/media owner; call close stops delivery | C1/`001-S` PCMU pass |
| Internal inbound PCM | Media ingress | VAD and ASR fan-out | PCM S16LE, mono, 8 kHz | Bounded channel; overflow policy to be selected in implementation | Architecture + C1 boundary; integrated channel not tested |
| VAD frame flags | VAD | Turn Detector | Small immutable frame decisions | Drop/close with corresponding audio generation | VAD operation deferred |
| ASR partial hypotheses | Streaming ASR | Transcript Assembler | Revisioned text events, direct data path | Replaceable current hypothesis; old revision discarded | C2 partial/final pass; assembler implementation deferred |
| Final user-turn text | Transcript Assembler | LLM adapter | UTF-8 Russian text, authoritative final only | Close previous generation on new turn/call end | C2 final observation; direct app channel deferred |
| Retrieval context | Retrieval | LLM adapter | Compact immutable text fragments | Bounded context; retrieval policy not yet implemented | ADR-002 only; deferred |
| LLM prompt/result over IPC | Main LLM adapter | Local Ollama native server and back | HTTP over `127.0.0.1`; streamed/structured JSON | Client stream close suppresses stale result; native ack unavailable | C3 owner-approved existing IPC |
| Structured action metadata | LLM adapter | Dispatcher | Small validated JSON/action envelope | Reject after generation close; text payload split from action ownership | ADR-001 + C3 result pass |
| Approved answer text | LLM adapter | TTS | Direct bounded UTF-8 text channel; no Dispatcher transit | Dispatcher opens/closes generation; stale answer discarded | Architecture invariant; implementation deferred |
| TTS PCM | TTS | Playback buffer/media egress | Candidate PCM stream; convert to agreed internal PCM | Close on barge-in/call end; queued old data discarded | C4 first PCM/cancel pass; real playback deferred |
| Outbound RTP audio | Media egress/SIP adapter | Remote SIP peer | PCMU/G.711 mu-law, 8 kHz, mono | Call lifecycle owns close | C1/`001-S` PCMU boundary pass |

## 4. Explicit non-transit rule

Dispatcher does not carry RTP frames, PCM frames, ASR partial text, final answer text or retrieval fragments. It carries
only lifecycle/control metadata and the validated semantic action. The C3 HTTP process boundary is direct adapter-to-
inference-service IPC and is not a hidden queue or a replacement for Dispatcher ownership.
