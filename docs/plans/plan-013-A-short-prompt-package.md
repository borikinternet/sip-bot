# Plan-013-A: единый короткий prompt package

Статус: `complete`  
Родитель: [`Map-013`](plan-013-call-greeting-and-short-prompt.md)

## Цель и write-set

Перенести default skill instruction и полный prompt template в единственный конфигурационный источник, добавить точную
инструкцию `Отвечай коротко.`, поднять версии package и перевести authoritative tools на общую factory.

Допустимый write-set: `config/constants.py`, `src/sip_bot/config.py`, `src/sip_bot/prompt/`, prompt-конструкторы в
`tools/*.py`, связанные tests и документы Map-013. LLM facade, retrieval ranking и output schema защищены.

## Локальные правила и boundary

- `SkillPromptManager` остаётся владельцем composition; factory только материализует constants-based default package.
- Exact user text не переписывается.
- RAG insufficient-context policy остаётся дословной и не ослабляется.
- Все live/demo runners обязаны использовать тот же package; test-specific custom prompts допустимы только в tests.
- Изменение получает новую template/profile/skill version и проверяется по rendered prompt.

## Срезы и acceptance

1. Добавить именованные constants и typed config mapping.
2. Добавить `build_default_prompt_manager()` и заменить duplicated production/probe literals.
3. Проверить exact phrase, IDs/versions, JSON/RAG policy и отсутствие authoritative duplicates.
4. Запустить targeted config/prompt tests и affected integration tests.

Stop conditions: structured decision перестал разбираться; unknown-answer утратил mandatory transfer wording; появился
второй runtime config source. Blocker: `none`, если corrective pass остаётся в write-set.

## Результат

Выполнено 2026-09-22. Default skill/template/profile централизованы в constants-backed factory, authoritative runners
переведены на неё. Real AI gate `target-20260922-r4` прошёл с версиями `2/3/3`: first usable output `176.215 ms`,
final structured decision `884.254 ms`; RAG/source-aware JSON-контракт сохранён. Исторические `r1`–`r3` оставлены как
evidence соответственно cold-timeout и двух исправленных дефектов test harness.
