# Map-006: source index и traceability

Дата: `2026-09-04`  
Назначение: factual source index для доклада и demo package

Индекс не является новым владельцем требований, архитектуры или конфигурации. Он связывает тезисы доклада с
документами-владельцами и фактическими evidence.

> Map-006 technical package завершён target `006-D/target-20260905-r6`. Upstream corrective plan [`005-E`](../../docs/plans/plan-005-E-tts-playback-integrity-corrective.md)
> закрыт и r10 сохраняется как baseline TTS integrity. Прослушивание r7 выявило mid-stream потерю TTS; r6 подтвердил
> полный сценарный прогон, stereo recording и отсутствие playback underruns. Исторические ссылки и raw artifacts не
> перезаписываются; юридическая публикация отдельно.

## 1. Требования и архитектура

| Claim | Владелец | Evidence | Статус |
|---|---|---|---|
| MVP — один русский SIP-разговор с PCMU, локальными ASR/LLM/TTS, RAG, context, barge-in, transfer и report | [`requirements.md`](../../docs/requirements.md) | Map-005 requirement matrix | подтверждено как scope |
| Dispatcher/DialogueFSM владеют control plane; audio и крупный text payload идут напрямую | [`architecture.md`](../../docs/architecture.md) | Map-002-I rev21, Map-005 APG audit | подтверждено |
| SIP protocol reactions не ждут AI; LLM не получает произвольный SIP API | [`architecture.md`](../../docs/architecture.md), [`ADR-001`](../../docs/decisions/ADR-001-llm-and-dialogue-manager.md) | A/J4 protocol and FSM evidence | подтверждено |
| Один звонок, no-GIL target и pre-call warmup | [`technical-specification.md`](../../docs/technical-specification.md), [`ADR-003`](../../docs/decisions/ADR-003-free-threaded-python.md) | Map-005 r10 runtime/warmup metadata | подтверждено для MVP |
| Mandatory RAG с source IDs и unknown-answer policy | [`requirements.md`](../../docs/requirements.md), [`knowledge-base.md`](../../docs/knowledge-base.md) | 005-C real positive/negative RAG; r7 has 5 RAG contexts | подтверждено |

## 2. Выбранный baseline

| Контур | Baseline | Source/evidence | License/notice |
|---|---|---|---|
| SIP/media | PJSUA2/PJMEDIA `2.17`, PCMU payload type 0, 8000 Hz, mono, negotiated ptime 20 ms | [`001-C1 closeout`](../feasibility/001-C1-sip-pjsua2-pjmedia/closeout.md), r7 `adapter_profile` | PJSIP/PJMEDIA notice требуется |
| ASR | `faster-whisper==1.2.1`, `Systran/faster-whisper-large-v3`, patched CTranslate2 binding для no-GIL | [`C2 candidate freeze`](../feasibility/001-C2/candidate-freeze.md), [`005-B closeout`](../implementation/002-system-testing-and-demo-readiness/005-B/closeout.md) | MIT и patch/source notice |
| LLM | `Qwen3.5-9B-Q4_K_M.gguf` через локальный Ollama `0.33.1`/HTTP IPC | [`C3 closeout`](../feasibility/001-C3-llm-primary/closeout.md), [`005-C closeout`](../implementation/002-system-testing-and-demo-readiness/005-C/closeout.md) | Model/backend notices; ADR-002 остаётся proposed |
| TTS | XTTS-v2 `2.0.3`, streaming output, patched no-GIL tested path | [`C4 closeout`](../feasibility/001-C4-tts-primary/closeout.md), [`005-C closeout`](../implementation/002-system-testing-and-demo-readiness/005-C/closeout.md) | Coqui Public Model License и voice/source notice |
| Corpus/RAG | Curated Russian natural-science corpus, local embeddings/index/retrieval | [`knowledge-base.md`](../../docs/knowledge-base.md), 005-C evidence | Wikimedia attribution/ShareAlike review |
| Runtime | Ubuntu 24.04/WSL2, CPython `3.14.7t`, `gil_enabled=false`, RTX 5060 Ti | [`ADR-003`](../../docs/decisions/ADR-003-free-threaded-python.md), r7 JSON | Runtime/dependency notices |

## 3. Rehearsal evidence

Источник для baseline: [`Map-005-D r7`](../implementation/002-system-testing-and-demo-readiness/005-D/target-20260904-r7/map005-d-rehearsal.json),
его [`requirement matrix`](../implementation/002-system-testing-and-demo-readiness/005-D/target-20260904-r7/requirement-matrix.md)

Upstream TTS integrity source: [`Map-005-E r10`](../implementation/002-system-testing-and-demo-readiness/005-E/target-20260904-r10/map005-d-rehearsal.json).
Текущий Map-006 corrective source: [`006-D target r6`](006-D/target-20260905-r6/map005-d-rehearsal.json), его
[`audio audit`](006-D/target-20260905-r6/audio-audit.md) и [`D closeout`](006-D/closeout.md).

| Claim | Фактическое значение | Статус |
|---|---:|---|
| Map-006 corrective rehearsal | `pass`, 7/7 scenario checks | подтверждено r6 |
| Диалог | Обязательные follow-up, barge-in, unknown-answer/offer-transfer, operator transfer и report checks пройдены; trace содержит 7 user final turns, 4 assistant answers, 6 RAG contexts | подтверждено r6 |
| Media | PCMU/8000/mono, ptime 20 ms; peer packets transmit `3880`, receive `4079` | подтверждено r6 |
| Runtime | CPython 3.14.7t, `gil_enabled=false` | подтверждено r6 |
| Warmup | `38332.304 ms` до SIP admission | подтверждено r6; не часть turn latency |
| Media counters | ingress/egress `4079`; drops `0`; `egress_underruns=0`; `tts_startup_wait=0`; intentional silence `2356`; callback errors `0` | подтверждено r6 |
| TTS output counters | accepted chunks `40`; accepted bytes `574298`; emitted frames `1723`; overflow bytes `0`; buffered/pending `0`; dropped tail `23574` | подтверждено r6; tail accounting отделён от overflow и underrun |
| Recording | raw `enc`/`dec`, stereo 2-channel PCM16/8000 Hz, `81.48 s`, left=`user_to_bot`, right=`bot_to_user` | подтверждено r6 |
| Alignment | target `651840` frames; shorter left track padded by `31040` frames; policy recorded in manifest | подтверждено r6; raw tracks preserved |

## 4. Latency evidence

Источник: [`005-C closeout`](../implementation/002-system-testing-and-demo-readiness/005-C/closeout.md) и его target AI gate.

| Metric | Value | Interpretation |
|---|---:|---|
| Final phrase → first useful LLM output | `488.600 ms` | component observation |
| Final phrase → valid structured LLM result | `1518.092 ms` | component observation |
| Final phrase → first XTTS PCM | `1785.090 ms` | user-facing MVP metric observation |
| Comfort orientation | `200–500 ms` | not achieved by this baseline; claim is not hidden |
| RTP budget | `30 ms` | fixed project assumption, not separately measured |

## 5. Limitations и not-demonstrated properties

### Known limitations

- Full final-phrase-to-first-PCM latency is above the project comfort orientation.
- XTTS generator cancellation is verified at Python generator boundary; independent native CUDA cancellation token is not
  claimed.
- Warmup is operationally mandatory and takes tens of seconds before a call; it is not charged to live turn latency.
- Baresip recording is a test-peer artifact, not bot-side production recording; unequal raw tails are explicitly padded
  only in the derived stereo file.
- r7 stereo review found audible mid-stream TTS loss despite `egress_underruns=0`; dynamic bounded accumulation,
  bounded lookahead and exact byte/frame accounting were implemented in `005-E` and accepted by r10. r7 remains
  historical diagnostic evidence and is not used as the current TTS completeness claim.
- Project source-code license has not been selected; this package does not perform a public release.

### Not demonstrated and not claimed

- production PBX integration or PBX-owned transfer semantics;
- more than one concurrent call;
- production HA, SLO, MOS/load campaign, security hardening or long-term audio retention;
- native Ubuntu outside the approved WSL2 target;
- final legal clearance for every dependency/model/voice/output before publication.
