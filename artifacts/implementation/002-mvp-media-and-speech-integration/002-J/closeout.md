# J1–J4 execution audit и blocker

Статус исполнения child plan: `complete` — J1–J3, изолированные J4
component/composition lanes, полный live SIP-driven J4 и J5 closeout приняты.
Базовый live path принят в `live-gate-20260903-r4`, полная сценарная матрица
принята в `j4-full-live-20260904-r20`; `B-002-J-004` закрыт.

Главный executor принял handoff J1–J3, реализовал и принял I.0 composition,
после чего выполнил J4 clean-start evidence-runner. Category-4 blocker
`B-002-J-005` снят после закрытия I.0. Исторический gap отсутствовавшего
production/application driver закрыт successor plan I.1; подробный audit и
его resolution находятся в
[`j4-integration-gap.md`](j4-integration-gap.md).

## Выполнено

- `src/sip_bot/transfer/` получил typed `TransferCommand`, который принимает
  только существующий `DialogueCommand(kind=TRANSFER)`, и адаптер
  `TransferOrchestrator` с детерминированным `FakeOperator`.
- Результатом адаптера остаётся существующий typed `TransferResult`; новый
  contract revision и ownership не вводились.
- `src/sip_bot/report/` получил `ReportInput`, детерминированный Markdown
  `ReportBuilder` и идемпотентный `ReportFinalizer`.
- Report содержит состояние/причину завершения FSM, текстовый context,
  source-aware RAG diagnostics, transfer outcome и явное отсутствие
  аудиозаписи.
- `tests/scenarios/j_harness.py` создаёт чистый per-test call/context/operator
  и ведёт сценарий только через FSM boundary.
- `tests/integration/test_transfer_report.py` покрывает J1–J3 и отрицательные
  проверки обхода FSM.
- `tools/j4_clean_start_probe.py` последовательно запускает target regression,
  real answer composition и real media/transfer composition с отдельными
  stdout/stderr логами и fresh output roots.

## Изменённые файлы

- `src/sip_bot/transfer/contracts.py`
- `src/sip_bot/transfer/fake_operator.py`
- `src/sip_bot/transfer/__init__.py`
- `src/sip_bot/report/builder.py`
- `src/sip_bot/report/__init__.py`
- `tests/scenarios/j_harness.py`
- `tests/integration/test_transfer_report.py`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/manifest.json`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/deterministic-results.json`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/commands.md`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/closeout.md`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/j4-preflight.md`
- `artifacts/implementation/002-mvp-media-and-speech-integration/002-J/next-plan-approval.md`

## Diff summary

Добавлены 5 production/test modules, 1 clean-start harness, 6 integration
tests и 4 evidence-файла. Upstream `001-*`, `002-A`–`002-H`, Map-I, parent
map, registry/backlog, общие constants и contract revision не изменялись.

## Проверки

Подробные команды и exit codes находятся в `commands.md` и
`deterministic-results.json`:

- targeted: `6 passed`, exit `0`;
- unit/contract regression: `88 passed`, exit `0`;
- compileall: exit `0`;
- target CPython 3.14.7 free-threaded (`gil_enabled=False`): targeted `6
  passed`, compileall exit `0`.
- После I.0 corrective pass: Windows `109 passed, 3 skipped` (Baresip отсутствует
  на host), target `112 passed`, включая live SIP/RTP component tests.
- J4 clean-start runner: все 3 команды завершились с exit code `0`;
  target regression — `112 passed`, real answer composition — RAG/source-aware
  answer → LLM → XTTS → report, real media composition — real ASR/VAD/
  endpointing → RAG-negative → LLM offer-transfer → XTTS → fake operator →
  report.
- Исторические три lane сами по себе не доказывали единый live Baresip→ASR→LLM→TTS→Baresip вызов; это ограничение
  закрыто отдельным full live gate r20.
- Target runtime: CPython 3.14.7t, `Py_GIL_DISABLED=1`,
  `gil_enabled=False`; real composition processes также сохранили
  `gil_enabled=False`.
- Evidence manifest: [`j4-evidence.json`](j4-clean-start-20260903-r2/j4-evidence.json).

## Pre-existing и out-of-scope

- Windows-only Baresip отсутствует, поэтому 3 live SIP/RTP проверки на host
  имеют явный skip; canonical target их выполняет.
- Реальный composition использует offline Common Voice fixture на media input,
  а не аудиозапись разговора и не внешний PBX. This is a test input, not
  a production recording path.

## Blocker history

`B-002-J-005` был снят: `002-I.0` добавил production-level one-call
composition вокруг существующих Dispatcher/DialogueFSM и отдельного
CallSession. `ContextStore` ведёт внутренний `conversation.jsonl`, а
обязательный итоговый артефакт `report.md` имеет отдельного владельца-
финализатора. Отсутствие `state.json` не является дефектом: такой файл не
входит в требования проекта.

Это был APG 6.1 category 4, а не ошибка J1–J3 и не повод ослаблять тесты.
Owner decision разделил существующие Dispatcher и DialogueFSM и назначил
отдельный successor plan `002-I.0`; его implementation/evidence приняты.

На момент исторического closeout blocker `B-002-J-006` — также APG 6.1 category 4. В тогдашних
production modules нет владельца, который читает
`SipMediaAdapter.next_ingress_frame()`, запускает per-turn speech/ASR
processing, отправляет `FinalUserTurn` в `ConversationPipeline` и прокачивает
`TtsOutputBuffer → MediaPacer → PlaybackChannel →
SipMediaAdapter.enqueue_egress_frame()`. Добавление такого узла меняет
application boundary и write-set, поэтому до owner review он не вводится.

## J4 full live и J5 closeout

`j4-full-live-20260904-r20/j4-full-live.json` имеет `status=pass` и exit code
`0`. Один чистый Baresip call доказал SIP/RTP PCMU/8000/mono, два связанных
вопроса с контекстом, barge-in с отменой старого playback, source-aware RAG,
unknown-answer с предложением оператора, подтверждение `Да.` с переходом FSM
в `transferring`, SIP transfer с ответами `100/200`, и итоговый `report.md`.
Проверены все 6 scenario checks; `errors=[]`, `stale_hypotheses=0`,
`asr_chunks_dropped=0`, `callback_errors=0`, `gil_enabled=false`.

Перед r20 прогон r19 выявил ошибку реализации Transcript Assembler: общий префикс двух последовательных partial ASR
гипотез ошибочно считался стабильным, хотя обе гипотезы могли содержать одну и ту же раннюю ошибку. Исправление
ограничило продвижение stable prefix явно переданным backend полем; без него гипотеза остаётся изменяемой. После
исправления targeted speech checks и target full regression стали зелёными, затем r20 повторно прошёл полный live gate.
Raw r19 сохранён и не считается acceptance evidence.

J5 завершён после синхронизации Map-I revision 21, parent Map-002, I.1/J4
evidence, document registry и task backlog. Производственные hardening/load/MOS
и TTS quality observations явно оставлены карте 5/backlog.

## Следующий шаг

Исторические blockers `B-002-J-006` и `B-002-J-004` сняты evidence r4/r20.
Карта 4 закрыта; дальнейший рабочий переход — карта 5 системного тестирования
и исправлений по roadmap. Этот closeout не объявляет MVP production-ready.
