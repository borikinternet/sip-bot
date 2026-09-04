# 001-D gaps и deferred findings

Дата: `2026-08-27`  
Статус: `no blocking unexpected architecture gap; known limitations are classified explicitly`

## 1. Unexpected gaps

| Gap ID | Наблюдение | Класс | Влияние на D | Решение / владелец | Статус |
|---|---|---|---|---|---|
| `GAP-001D-001` | В подготовительном C2 `runtime-manifest.json` поле `ctranslate2.patch.operation_gate` ранее сохраняло `pending`, тогда как stage-specific `operation.json`, `partial-final.json` и closeout фиксировали выполненный pass | Документная несинхронность подготовительного manifest | Не блокировал: D использовал stage-specific operation evidence и closeout как более поздние записи | Синхронизировать C2 manifest; owner: project owner | `resolved 2026-08-27; operation_gate=pass` |

Иных неожиданных архитектурных gaps в границах D не обнаружено. В частности, новый IPC для C3 не потребовался:
owner-approved HTTP IPC на `127.0.0.1` уже существует и принят как process boundary.

## 2. Известные ограничения, не являющиеся неожиданными gaps

| ID | Ограничение | Классификация | Что делать дальше |
|---|---|---|---|
| `DEFER-001D-THREAD-001` | Child evidence не доказывает application-level thread/task affinity всех SIP/native callbacks и stream workers | `deferred`, ожидаемо для synthesis stage | Выбрать affinity в implementation plan и подтвердить callback/lifecycle smoke |
| `DEFER-001D-IPC-001` | C3 HTTP client close не даёт отдельного native cancellation acknowledgement | Known component limitation | Сохранить generation/close semantics; не заявлять hard native cancellation; проверить bounded adapter behavior |
| `DEFER-001D-CHANNEL-001` | Сквозные direct channels, overflow, close/re-close и stale suppression между всеми компонентами не реализованы | `deferred`, out-of-scope C1–C4 | Реализовать channels и barge-in в последующем integration plan |
| `DEFER-001D-GPU-001` | Совместная работа ASR+LLM+TTS на одной RTX 5060 Ti не измерялась | `deferred`, out-of-scope component feasibility | Измерить в отдельном integration/GPU contention slice |
| `DEFER-001D-SPEECH-001` | VAD operation, Transcript Assembler и Turn Detector ещё не имеют runtime evidence | `deferred`, следующий speech pipeline scope | Согласовать и выполнить отдельный speech pipeline plan |
| `DEFER-001D-RAG-001` | Retrieval и проверка естественно-научной базы знаний не реализованы | `deferred`, out-of-scope C1–C4 | Добавить локальную KB/RAG в implementation plan |

## 3. Unexpected-gap protocol result

- `B-001D-004`: не triggered — synthesis использует существующие ownership rules и не создаёт новый queue/facade/IPC.
- `B-001D-005`: не закрывается как runtime pass; channel-level integration deferred отдельным plan.
- `B-001D-006`: не triggered — synthesized decisions не противоречат ADR/architecture.
- `B-001D-008`: не triggered — все обязательные component contours имеют `pass` или owner-approved
  `pass_with_isolation`; fallback не нужен.
