# 001-E map-gate matrix

Дата: `2026-08-27`  
Статус карты: `complete`

## 1. Map-level gates

| Gate | Условие открытия | Evidence / result | Статус |
|---|---|---|---|
| `M-G1 decomposition review` | Owner review структуры `001-A`–`001-E` | Map-001 review принят; child plans и APG-связи созданы | `closed 2026-08-26` |
| `M-G2 runtime gate` | `001-A` и `001-B` имеют evidence | Ubuntu/WSL2 environment и CPython `3.14.7t` free-threaded/no-GIL подтверждены; три probe run exit `0` | `closed 2026-08-27` |
| `M-G3 component gate` | `001-C` и `001-C1`–`001-C4` закрыты | PJSUA2/PJMEDIA, faster-whisper, Qwen/Ollama и XTTS-v2 имеют component decision; C3 — owner-approved isolation | `closed 2026-08-27` |
| `M-G4 feasibility closeout` | `001-D` имеет accepted evidence | E baseline, evidence index, blocker register и next-plan approval package созданы; Map-002 и Map-002-I получили owner review | `closed 2026-09-02` |

`M-G4` закрыт после отдельного owner review следующей карты. Это закрывает feasibility/handoff scope Map-001;
реализация Map-002 и исполнение её child plans остаются отдельной работой.

## 2. Child status reconciliation

| Plan | Result | Evidence | Handoff |
|---|---|---|---|
| `001-A` | `complete` | `artifacts/feasibility/001-A-environment-baseline/closeout.md` | Runtime setup |
| `001-B` | `complete` (runtime decision: `pass`) | `artifacts/feasibility/001-B/closeout.md` | Native compatibility map |
| `001-S` | `complete` (stand result: `pass`) | `artifacts/feasibility/001-S-voip-test-stand/closeout.md` | Approved local peer/fake operator |
| `001-C1` | `complete` (candidate decision: `pass`) | `artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/closeout.md` | Patched SIP/media candidate |
| `001-C2` | `complete` (candidate decision: `pass`) | `artifacts/feasibility/001-C2/closeout.md` | Patched ASR candidate |
| `001-C3` | `complete` (candidate decision: `pass_with_isolation`) | `artifacts/feasibility/001-C3-llm-primary/closeout.md` | Main HTTP controller + local Ollama process |
| `001-C4` | `complete` (candidate decision: `pass`) | `artifacts/feasibility/001-C4-tts-primary/closeout.md` | Patched TTS candidate and WAV artifact |
| `001-D` | `complete` (synthesis result: `pass`) | `artifacts/feasibility/001-D/closeout.md` | Process/control/data baseline |
| `001-E` | `complete` | `artifacts/feasibility/001-E/closeout.md` | Map-002 hand-off accepted; integration deferred to Map-002 |

## 3. Calendar and scope

На дату исполнения E, `2026-08-27`, deadline `2026-09-25` не пропущен. Feasibility evidence frozen without silently
добавленных кандидатов. После 31 августа действуют ограничения roadmap: новые компоненты и режимы не добавляются,
если они не закрывают обязательный demo-flow или конкретный зарегистрированный blocker.

Следующий календарный переход — implementation plan для media/speech/application integration. Его acceptance обязан
перенести в execution только уже принятые C/D boundaries и использовать существующий `001-S`, а не создавать новый
необоснованный VoIP stack.
