# J4 preflight и blocker evidence

Дата: `2026-09-03`

## Что принято до J4

- `002-A`–`002-H`: `complete`, upstream contracts propagated through Map-I revision 8.
- J1–J3 deterministic handoff: принят главным executor после diff review.
- Windows: `94 passed` (`tests/integration/test_transfer_report.py`, `tests/unit`,
  `tests/contract`).
- Target CPython 3.14.7t: те же `94 passed`, `compileall` exit `0`.
- Target application import: все пакеты `sip_bot` импортированы, `gil_enabled=False`.
- Target existing integration lane: `10 passed` (`tests/integration`), включая live
  SIP/RTP tests текущего B/H слоя.
- Target runtime preflight: exit `0`, CPython 3.14.7t, `Py_GIL_DISABLED=1`,
  `gil_enabled=False`.

## Проверка J4

J4 остановлен до запуска heavy model/live full-flow gate после чтения фактического
write-set и запуска независимых предварительных проверок.

| Проверка | Результат |
|---|---|
| `ApplicationRuntime` и `sip_bot.__main__` | Только runtime probe/bootstrap; SIP, speech, RAG, LLM, TTS и FSM не собираются в call session |
| `XttsEngine` | Только Protocol; concrete XTTS engine в `src/sip_bot/` отсутствует |
| `FasterWhisperC2Backend` | Есть chunk adapter, но нет владельца worker/lifecycle, связывающего его с live media loop |
| `SipMediaAdapter` + FSM | Есть раздельные SIP/FSM owners и commands, но нет production command/event composition |
| `TransferOrchestrator` | Реализован deterministic `FakeOperator`, не SIP-backed transfer owner |
| `ContextStore` | Может вести внутренний `conversation.jsonl`; обязательный итоговый `report.md` имеет отдельный report owner |
| J4 clean-start full matrix | Не может быть честно запущена в утверждённом write-set без новой call-session orchestration boundary |

## Классификация

`B-002-J-005` — APG 6.1 category 4: непредусмотренный architectural/API gap.
Это не ошибка unit-теста и не красный результат реализации J1–J3. Исправление потребует
определить владельца нового call-session orchestration (или явно передать эту роль уже
существующему компоненту), новые рёбра/typed contracts и разрешённый write-set.
Поэтому J4 и Map-002 closeout остановлены до owner review successor plan.

Post-preflight owner decision (`2026-09-03`) подтвердил, что composition должна
быть представлена существующими отдельными классами/объектами `Dispatcher` и
`DialogueFSM` плюс новым per-call `CallSession` при сохранении single-call MVP.
Successor plan — `002-I.0`, а не `002-K`; второй Dispatcher или второй FSM не
создаются.

Запрещённые действия, которые не выполнялись: model-only demo вместо SIP-flow, обход FSM,
подмена SIP transfer fake-only evidence, скрытая запись аудио, lexical/model-only RAG
fallback, ослабление assertions и объявление J/Map-002 complete.
