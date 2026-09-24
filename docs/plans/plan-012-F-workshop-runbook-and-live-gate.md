# План 012-F: runbook мастер-класса и live SIP gate

Уровень: `child plan`  
Идентификатор: `012-F`  
Статус owner review: `accepted by Map-012 and explicit execution instruction 2026-09-21`  
Статус исполнения: `complete 2026-09-21`  
Родитель: [`Map-012`](plan-012-rag-corpus-onboarding-workshop.md)  
Зависимость: `012-A`–`012-E complete`  
Evidence root: `artifacts/workshops/rag-corpus-onboarding/012-F/`

## Цель и результат

Опубликовать self-contained русскоязычный runbook для пустого агента/участника: подготовить документы, проверить
package, построить и активировать index, запустить готовность и зарегистрированный FreeSWITCH/SIP-сценарий, проверить
source-aware report и unknown-answer/transfer. Затем выполнить clean repeat по инструкции.

## Материализованные правила

- Runbook использует только обычные повторяемые команды и не полагается на историю чата или скрытый ручной patch.
- Existing FreeSWITCH Map-011, registration Map-009 и media/speech baseline не переписываются.
- До heavy run проверяются 20 GiB, target no-GIL runtime, GPU и Ollama/model readiness.
- Index строится offline; startup загружает artifact, corpus embeddings в call path равны нулю.
- Live scenarios: positive, follow-up, negative/offer-transfer + confirmation; old science question не получает active
  source-aware answer; report содержит workshop source IDs.
- Главный executor выполняет heavy GPU и final live gate; независимый агент делает context-free review без правок общего
  config/registry.

## Source-map/write-set

Разрешено: `docs/workshops/rag-corpus-onboarding-runbook.md`, scoped workshop config/fixtures/tools,
`docs/user-guide.md`, `tools/freeswitch_workshop/registered_full_rehearsal.py` или новый thin workshop wrapper,
tests/evidence и этот plan. Owner docs/roadmap/registry/backlog обновляет главный executor после фактического результата.

Protected: SIP/RTP/ASR/VAD/TTS/FSM semantics, Map-011 runbook/evidence, historical artifacts and previous index builds.

## Slices

1. `F1`: draft context-free runbook from tested commands, including rollback to previous index.
2. `F2`: deterministic dry/clean build-load-evaluation repeat into fresh artifact root.
3. `F3`: registered FreeSWITCH live call using workshop index and report/source assertions.
4. `F4`: independent context-free review; correct only reproducibility defects.
5. `F5`: owner-doc/status/registry/backlog synchronization and map closeout audit.

## Blockers/tests/fallback

| ID | Trigger | Status |
|---|---|---|
| `B-012-F-001` | Clean executor cannot repeat workflow or live call lacks required source/unknown/report evidence | `resolved 2026-09-21 by live-r5 and independent context-free PASS` |

Audio recording remains diagnostic; acceptance is based on typed/event/results plus report, not subjective audio alone.
No hot reload, external vector DB, OCR/importer, alternate model or fabricated live evidence. Child closes only complete or
concrete blocked after corrective pass and preserved raw output.

## Closeout

Исполнено полностью. Опубликован
[`rag-corpus-onboarding-runbook.md`](../workshops/rag-corpus-onboarding-runbook.md); clean repeat воспроизвёл index SHA-256
`9a2e0937cf2bcf3a2533b4762410490c0e40420f64a29483cf2e487b56d2b579`, evaluation `12/12` и runtime load с нулём
corpus embeddings. Финальный registered `live-r5` прошёл все workshop/scenario/RTP/recording checks: positive и
follow-up используют pricing context, самостоятельный старый science-вопрос insufficient, unknown-answer явно сообщает
об ограничении и предлагает оператора, подтверждение приводит к transfer, `wiki-*` leakage отсутствует.

Corrective runs сохранены, а assertions не ослаблены: r1 выявил context contamination/non-audio callback/tolerance;
r2 — ошибочное наследование истории однословным ASR-фрагментом; r3 — false-positive проверки текста offer-transfer;
r4 — неучтённый эллиптический follow-up. r5 закрыл все эти проверки. Независимый агент без истории сначала воспроизвёл
дефект r3, затем после исправлений дал PASS без blockers. Evidence:
[`012-F/closeout.md`](../../artifacts/workshops/rag-corpus-onboarding/012-F/closeout.md).
