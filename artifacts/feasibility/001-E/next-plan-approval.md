# Пакет согласования карты 4

Дата подготовки: `2026-09-02`  
Статус: `Map-002 и Map-002-I согласованы владельцем 2026-09-02; child plans созданы и ожидают отдельных owner reviews`

Этот файл — пакет передачи на согласование, а не разрешение на исполнение. Предлагаемый документ является map-level
картой реализации, а не единым child plan на весь MVP. Внутри карты сначала должна быть согласована обязательная под
карта взаимодействий и boundary-контрактов.

## Предлагаемый map-файл

- **Имя:** `plan-002-mvp-media-and-speech-integration.md`
- **Уровень:** `map` — карта 4 дорожной supermap.
- **Родительская supermap:** [`docs/roadmap.md`](../../../docs/roadmap.md).
- **Цель:** разложить реализацию основной логики на self-contained child plans и довести их до первого рабочего
  application baseline на принятых SIP/media, ASR, LLM и TTS boundaries.
- **Обязательная первая под карта:** `plan-002-I-boundary-interaction-map.md` — topology, циклы, типы на рёбрах и
  итерационный propagation contract-типов.
- **Предлагаемый корень evidence:** `artifacts/implementation/002-mvp-media-and-speech-integration/`.
- **Зависимости:** `001-A`–`001-E`, `001-S`, точные патчи C1/C2/C4, одобренная владельцем граница C3 Ollama HTTP;
  для answer path — отдельная проверка локального RAG/embedding baseline.

## Почему требуется карта, а не единый plan

Бывший «срез 4» объединяет независимые execution boundaries: runtime/bootstrap, SIP/media, speech ingress,
Dispatcher/Dialogue FSM, context, Skill & Prompt Manager, LLM Facade, TTS/playback, transfer/reporting и сквозную интеграцию. Для каждого направления
нужны собственные владелец поведения, write-set, lifecycle, cancellation, acceptance, blocker register и closeout.

Поэтому `plan-002` должен сначала зафиксировать структуру и порядок дочерних планов. Создание или согласование карты не
разрешает исполнение всех её пунктов.

## Состав карты

Карта предлагает следующую под карту и child plans:

`002-I` boundary interaction map → `002-A` runtime skeleton → `002-B` SIP/media adapter → `002-C` audio boundary
buffering;  
`002-D` speech ingress и `002-E` Dispatcher/Dialogue FSM → `002-F` Skill & Prompt Manager/context → `002-G` LLM
Facade/answer → `002-H` TTS output buffering/playback/barge-in → `002-J` transfer/report/integration.

Drafting, read-only analysis, fixtures и тесты с непересекающимся write-set могут готовиться параллельно. Зависимые
execution gates и GPU-heavy прогоны выполняются последовательно. Каждый child plan получает отдельный APG и owner review.

## Что проверяет owner review

- уровень документа `map`, а не `child plan`;
- границы карты и её соответствие обязательному demo-flow;
- состав, зависимости и порядок child plans;
- сохранение PJSUA2/PJMEDIA, `001-S`, PCMU, no-GIL/isolation и Ollama HTTP baseline;
- разделение control plane и data plane;
- наличие отдельной `Map-002-I` с topology, циклическими связями, contract registry и правилами его итерационного обновления;
- наличие отдельного `Skill & Prompt Manager` между FSM/context и LLM Facade, включая версионируемые prompt/profile и
  typed `LlmRequest`;
- обязательный RAG-контур: подготовленный локальный корпус, индекс, retrieval через source-aware `KnowledgeContext`,
  проверка `/api/embed` и сценарий unknown-answer при отсутствии достаточного контекста;
- map-level gates, blocker register и отдельные evidence roots;
- календарную границу карты и переход к карте тестирования после её closeout.

После согласования этого пакета, карты 4 и `Map-002-I` можно создавать остальные child plan-файлы. Их execution stage
начинается только после отдельного owner review каждого файла и актуальной ревизии contract registry.

## Требуется согласование

Карта 4, её child plan graph, topology/contract rules, зависимости, календарная граница и protected baseline
согласованы владельцем 2026-09-02. `Map-002-I` также согласована владельцем. `M-G4` карты 001 закрыт, а child plans
карты 002 продолжают проходить отдельные owner reviews и execution gates.
