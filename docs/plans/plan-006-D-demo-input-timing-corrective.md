# План 006-D: сокращение искусственных пауз demo input fixture

Уровень: `child plan`  
Идентификатор: `006-D`  
Родитель: [`plan-006-report-and-demo-preparation.md`](plan-006-report-and-demo-preparation.md)  
Дата: `2026-09-04`  
Статус owner review: `accepted by explicit owner instruction 2026-09-04`  
Статус исполнения: `complete — target r6 принят 2026-09-05`

## 1. Цель

Сократить лишние интервалы тишины в тестовой пользовательской записи, которую Baresip проигрывает через `aufile`,
сохранив смысл и порядок обязательного демонстрационного сценария: follow-up, barge-in, unknown-answer/offer-transfer,
подтверждение transfer и завершение звонка.

Это изменение относится только к test/demo fixture. Оно не изменяет runtime audio path, SIP/RTP contracts, TTS output,
запись разговора на стороне Baresip или production application source.

## 2. Применимые правила и решения

| Источник | Правило | Применение | Проверка | Stop condition |
|---|---|---|---|---|
| [`architectural-planning-gate.md`](../architectural-planning-gate.md) | Изменение защищённого инструмента оформляется отдельным узким plan-file и проверяется целевым тестом | Fixture timing вынесен в отдельный test-tool write-set | Plan, diff, unit и live gate | Потребовалось изменение runtime boundary |
| [`development-guidelines.md`](../development-guidelines.md) | Нельзя делать красную проверку зелёной удалением обязательного сценария или ослаблением assertion | Сокращаются только искусственные ожидательные окна; все пять user turns и сценарные проверки сохраняются | Fixture metadata и 7/7 live checks | Потерян обязательный turn или scenario edge |
| [`plan-005-system-testing-and-demo-readiness.md`](plan-005-system-testing-and-demo-readiness.md) | r10 — принятый upstream baseline; barge-in и Baresip stereo recording обязательны | Временная ось r10 используется как baseline; barge-in gap 2.5 s не сокращается | r10 comparison и новая stereo запись | Barge-in перестал воспроизводиться |
| [`technical-specification.md`](../technical-specification.md) | Baresip recording — test-peer artifact; runtime не создаёт audio recording | Меняется только input fixture, не recording owner | Manifest и source audit | Появилась bot-side запись |

## 3. Точный write-set

Разрешённые файлы:

- `tools/demo_fixture_timing.py` — чистая test-only таблица временных окон;
- `tools/j4_full_live_gate.py` — использование таблицы при генерации fixture;
- `tests/unit/test_demo_fixture_timing.py` — deterministic checks расписания;
- `artifacts/report-preparation-20260904/006-D/` — команды, target evidence и closeout;
- этот plan и map-level документы после фактического результата.

Запрещено изменять production `src/sip_bot/**`, SIP/RTP contracts, TTS buffer/pacer, модели, configuration constants,
Baresip recording implementation и исторические r7/r10 artifacts.

## 4. Timing profile

Исходные r10 интервалы сохраняются в историческом evidence. Новый профиль `compact-demo-v1`:

| Turn | Текст | Leading silence | Trailing silence | Назначение |
|---|---|---:|---:|---|
| 1 | Почему небо днём кажется голубым? | 1.5 s | 14.5 s | Дождаться первого ответа с небольшим запасом |
| 2 | А почему на закате оно становится красным? | 0 s | 1.0 s | Сохранить подготовку barge-in |
| 3 | Стоп, небо голубое? | 1.5 s | 11.0 s | Завершить interrupted answer перед следующим вопросом |
| 4 | Каков точный состав атмосферы на экзопланете Кеплер 786? | 11.0 s | 10.5 s | Дождаться unknown-answer offer без 34-секундного окна |
| 5 | Да | 10.5 s | 10.0 s | Достаточный хвост для transfer, без неиспользуемых 28 s |

Интервал между turn 2 и turn 3 остаётся `1.0 + 1.5 = 2.5 s`, поэтому turn 3 по-прежнему должен перебивать ответ.
Ожидаемый новый бюджет тишины — `71.5 s`; сокращение общей тишины относительно r10 — `39.5 s`; ожидаемая
длительность fixture — около `83.6 s`
вместо `123.1 s`, с поправкой на фактическую длительность синтезированных реплик.

## 5. Acceptance

- deterministic timing tests проходят;
- target CPython `3.14.7t`, `gil_enabled=false` и тот же warmup/model path используются для live gate;
- один чистый SIP/RTP-звонок проходит все `7/7` checks;
- сохраняются follow-up/context, barge-in, unknown-answer/transfer, operator transfer, report и stereo recording;
- fixture metadata содержит новый timing profile и не смешивается с conversation recording;
- TTS output не меняется по владельцу и не возвращаются прежние mid-stream gaps;
- новая stereo запись доступна для ручного прослушивания;
- document registry и backlog после изменения Markdown проходят аудит.

## 6. Blockers

| ID | Триггер | Действие | Статус |
|---|---|---|---|
| `B-006-D-001` | Сокращённый профиль нарушает обязательный сценарий или barge-in | Вернуть безопасное окно, выполнить corrective pass; не удалять сценарий | `none until triggered` |
| `B-006-D-002` | Для сокращения требуется изменение production/runtime boundary | Остановиться и оформить новый APG gap/owner review | `none until triggered` |
| `B-006-D-003` | Target live gate недоступен из-за GPU/disk/runtime внешнего условия | Повторить после устранения внешнего условия | `resolved 2026-09-05: disk preflight прошёл, target r6 pass` |

Ошибки test fixture или timing profile в разрешённом write-set являются corrective work, а не blocker. Частичный
результат не закрывает план.

## 7. Closeout

План получает `complete` после unit/target checks, новой записи и audio/manifest audit. Исторические r7/r10
artifacts не перезаписываются. После снятия `B-006-D-003` выполнен target r6: compact fixture, все 7 checks,
Baresip raw/stereo recording и audio audit прошли. Closeout сохранён в
`artifacts/report-preparation-20260904/006-D/closeout.md`.
