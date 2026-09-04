# APG-аудит supermap, карт и plan-файлов

Дата: `2026-09-04`

## Объём проверки

Проверены `docs/architectural-planning-gate.md`, `docs/development-guidelines.md`,
`docs/roadmap.md`, `docs/plans/`, `docs/document-registry.md`, `docs/task-backlog.md`,
а также closeout/evidence для `001-*`, `002-A`–`002-J`, `002-I.0` и `002-I.1`.

## Результат

- APG соответствует целевому смыслу: он описывает применение документов второго типа
  к operational-документам первого типа, а не владеет предметными правилами разработки.
- Устойчивые правила разработки находятся в `docs/development-guidelines.md`.
  В APG не обнаружен оставшийся самостоятельный каталог правил второго типа, который
  требовал бы переноса; оставшиеся разделы APG являются процедурой gate, шаблоном и
  требованиями к evidence.
- У всех исполненных child plans итоговый статус бинарен: `complete`. Частично
  исполненных child plans со статусом `foundation`, `partial` или `arch-ready` не найдено.
- Исполненные планы `001-*` и `002-A`–`002-J`, включая `002-I.0` и `002-I.1`, имеют
  бинарный итоговый статус `complete`; частичные child-plan статусы не используются.
  Map-002 и Map-I также закрыты собственными map-level gates; supermap остаётся
  `in_progress`, потому что карта 5, доклад и rehearsal ещё не закрыты.
- `python tools/check_document_registry.py`: `actual=40`, `registry_rows=40`, `missing=0`,
  `extra=0`, `duplicate_paths=0`, PASS.
- `python tools/check_task_backlog.py`: после синхронизации `TASK-007`/`TASK-008`
  показал `rows=8`, `unique_ids=8`, PASS.

## Исправления по результату аудита

- Принят и проверен handoff субагента J1–J3: `6` targeted, `88` unit/contract до
  main rerun; итоговый совместный main rerun — `94 passed` на Windows и target no-GIL.
- Исправлен фактический RAG configuration gap: `RAG_RELEVANCE_THRESHOLD` приведён к
  принятому real-provider evidence `0.35`; добавлена contract-проверка положительного
  и отрицательного порога.
- После H закрыта Map-I propagation revision 8; J4 preflight выпустил revision 9 с
  зарегистрированным gap, но не назначил новые узлы/рёбра без owner decision.
- Owner decision `2026-09-03` подтвердил single-call MVP с отдельными объектами
  существующих `Dispatcher` и `DialogueFSM` и новым `CallSession`; PJSUA2/PJMEDIA
  capacity preflight показал `maxCalls=4` в target default. Map-I обновлена до
  revision 11, а successor plan оформлен как `002-I.0`, не `002-K`.
- Бывший deferred `TASK-002` о no-GIL проверке выбранных native-зависимостей
  промотирован в `done`: evidence есть для C1–C4 и application lanes.
- После красного live-прогона r19 исправлена ошибка Transcript Assembler: случайный
  общий префикс соседних partial ASR-гипотез больше не объявляется stable без явного
  `stable_prefix` от backend. Исправление покрыто targeted/regression tests и
  повторным live gate r20; r19 сохранён как raw diagnostic evidence.
- После корректировки текущих runtime/prompt constants повторно выполнен главный
  full live gate: r20 дал `6/6` scenario checks, `errors=[]`, SIP/RTP PCMU,
  source-aware RAG, barge-in, transfer и report на одном вызове.

## Открытые вопросы и следующий gate

Открытых блокеров по закрытой карте 4 нет. Наблюдаемые остатки — качество/длина
русского XTTS-ответа относительно tokenizer limit `182`, высокий счётчик paced-output
`egress_underruns`, а также расширенная проверка latency/VRAM и протокольных failure
paths; они переданы следующей карте, а не замаскированы под pass.

Следующий рабочий документ — карта 5 системного тестирования и исправлений. Она
получит собственный owner review и child-plan decomposition по APG; supermap до её
closeout остаётся `in_progress`.
