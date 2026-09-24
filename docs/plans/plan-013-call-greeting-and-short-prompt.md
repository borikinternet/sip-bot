# Карта 013: приветствие при ответе и короткий LLM-ответ

Уровень: `map`  
Идентификатор: `Map-013`  
Статус: `complete`  
Дата: `2026-09-22`

## 1. Цель и проверяемый результат

После установленного входящего вызова бот самостоятельно произносит настраиваемое «Алло.», одновременно оставляя
speech ingress открытым для barge-in. Все authoritative live/demo paths используют один версионируемый prompt package,
содержащий явную инструкцию «Отвечай коротко.» и хранящийся в `config/constants.py`.

Проверяемый результат:

1. `CALL_ANSWERED` приводит к `PLAY_GREETING`, TTS playback и затем к `LISTENING`;
2. речь пользователя во время приветствия отменяет greeting playback через существующий barge-in path;
3. приветствие не вызывает LLM/RAG и не меняет SIP admission/readiness;
4. prompt text и skill instruction больше не дублируются в live/probe runner'ах;
5. prompt diagnostics получают новую версию, а exact final user text сохраняется;
6. targeted FSM/pipeline/config/prompt tests и affected regression lane проходят без упрощений.

## 2. Почему это карта

Есть два самостоятельных acceptance boundary: конфигурационный prompt package и изменение call-answer dialogue lifecycle.
Они разделены на `013-A` и `013-B`; общий `config/constants.py` изменяется последовательно главным executor.

## 3. Применимые правила

| Источник | Материализованное правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| [`technical-specification.md`](../technical-specification.md) §2.3, §3 | Шаблоны/skills версионируются, принадлежат приложению и хранятся именованными константами; ответ краткий, русский, без Markdown | Один default prompt package в constants и factory в `prompt/` | prompt/config tests, отсутствие literals в runners | Два расходящихся authoritative шаблона |
| [`architecture.md`](../architecture.md) §3.2 | Prompt policy принадлежит `Skill & Prompt Manager`, не LLM Facade | Facade не меняется; factory создаёт существующего owner | source/diff audit | Шаблон переносится в Ollama/facade |
| [`architecture.md`](../architecture.md) §3, §5 | FSM принимает dialogue/control решение; TTS payload идёт напрямую, Dispatcher не переносит аудио | FSM выдаёт компактный `PLAY_GREETING`, pipeline вызывает TTS, wiring принимает PCM | FSM/pipeline/barge-in tests | TTS/PCM проходит через Dispatcher |
| [`development-guidelines.md`](../development-guidelines.md) §1–§3, §6–§9 | Typed-first, существующий owner, тест до closeout, ошибки scope исправляются, только бинарный closeout | Новый typed command; без нового delivery owner; targeted + regression | test output и closeout | Непроверенное изменение FSM или частичный closeout |
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | User-scenario/FSM change требует полного gate и отдельных узких plan-files | `013-A`/`013-B`, blocker register и closeout | APG audit | Открытый category-4 gap |

## 4. Граница и source-map

```text
Входит:
  default skill instruction/template/version в config/constants.py;
  единая factory SkillPromptManager;
  конфигурируемый greeting text;
  CALL_ANSWERED → greeting playback → LISTENING;
  barge-in/cancel/stale protection и tests;
  синхронизация user guide/ТЗ/registry/backlog.

Не входит:
  смена LLM/TTS модели, RAG policy, SIP registration/admission;
  новый event bus, очередь или playback component;
  динамические prompt-файлы и production config store;
  подбор другого голоса или текста приветствия.

Protected baseline:
  один call, существующие Dispatcher/FSM/TTS owners, direct PCM path,
  обязательный RAG/unknown-answer, 180 → readiness → 200.

Рабочее дерево:
  содержит незакоммиченные результаты предыдущих карт; unrelated diff сохраняется.
```

| Область | Текущее поведение | Целевое поведение | Owner |
|---|---|---|---|
| Prompt config | В constants только IDs; текст продублирован в tools | Текст/инструкция/версии в constants; runners вызывают factory | Skill & Prompt Manager |
| Answer lifecycle | После `CALL_ANSWERED` сразу `LISTENING` | Input открывается, greeting playback, затем `LISTENING` | Dialogue FSM |
| Greeting audio | Отсутствует | Существующий ConversationPipeline/TTS direct path | ConversationPipeline + TTS owner |

## 5. Owner review

| Вопрос | Решение | Статус |
|---|---|---|
| Что произносить | Конфигурационная реплика `Алло.` | `resolved by owner 2026-09-22` |
| Как ускорять ответ | В default skill явно добавить точную инструкцию `Отвечай коротко.` | `resolved by owner 2026-09-22` |
| Нужен ли LLM для приветствия | Нет; статический approved TTS text | `resolved by architecture and owner request` |
| Нужно ли отдельное согласование child plans | Нет открытых вариантов; действуют ранее принятые правила группового execution | `resolved` |

## 6. Граф исполнения

```text
013-A prompt package centralization
    ↓ shared constants propagated
013-B greeting FSM/TTS integration
    ↓
targeted tests → affected regression → docs/registry closeout
```

## 7. Blocker register

| ID | Trigger | Категория | Состояние |
|---|---|---|---|
| B-013-001 | Greeting требует нового media/delivery owner вместо существующего playback path | 4 | `open on trigger` |
| B-013-002 | Exact concise prompt ломает structured JSON/RAG/unknown-answer contract | 1/4 после corrective pass | `open on trigger` |
| B-013-003 | Greeting нельзя отменить существующим barge-in generation contract | 1/4 после corrective pass | `open on trigger` |

Текущий фактический blocker: `none`.

## 8. Closeout gate

Карта получает `complete` только после полного закрытия `013-A` и `013-B`, зелёных тестов, проверки реального
authoritative runner prompt package и синхронизации документов. `foundation complete` и частичное закрытие запрещены.

## 9. Результат исполнения

Карта полностью закрыта 2026-09-22. `013-A` и `013-B` получили собственное acceptance evidence; открытых blocker и
owner-review вопросов нет.

- единый default package хранится в `config/constants.py`, а live/probe runners создают его через
  `build_default_prompt_manager()`;
- instruction содержит точную фразу `Отвечай коротко.`, версии skill/template/profile подняты до `2/3/3`;
- `CALL_ANSWERED` один раз запускает настраиваемое `Алло.` через существующий TTS/playback path, без LLM/RAG;
- unit/integration regression: `243 passed, 5 skipped`; target free-threaded lane: `38 passed`, GIL остаётся выключен;
- real AI gate `013-A/target-20260922-r4`: first usable LLM output `176.215 ms`, final structured decision
  `884.254 ms` от начала request;
- authoritative registered RAG call `013-B/registered-rag-live-20260922-r3`: общий `status=pass`, все восемь workshop
  checks true, greeting является первой assistant turn, barge-in/unknown-answer/transfer/report прошли, RTP
  underrun/drop/callback error равны нулю.

Closeout: [`artifacts/implementation/013-call-greeting-and-short-prompt/closeout.md`](../../artifacts/implementation/013-call-greeting-and-short-prompt/closeout.md).
