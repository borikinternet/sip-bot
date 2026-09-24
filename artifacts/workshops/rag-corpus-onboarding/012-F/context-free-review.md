# 012-F independent context-free review

Статус: `PASS`

Дата: `2026-09-21`

Исполнитель: независимый субагент без истории текущей задачи

Ограничение: read-only review; heavy GPU inference и live SIP не запускались повторно.

## Первый проход

Первый verdict был `FAIL`: reviewer сопоставил формально зелёный `live-r3` с `conversation.jsonl`/`report.md` и обнаружил,
что при `sufficient=false` LLM произнесла нерелевантный совет про утечку газа. Старый wrapper проверял FSM action, но не
смысл текста offer-transfer. Замечание принято как defect категории 1/2 в текущем scope, а не как внешний blocker.

Дополнительно reviewer указал три дефекта воспроизводимости runbook: повторное использование `$PY`/`$RUN` без shell
preamble, возможную гонку `docker compose up`/`fs_cli` и отсутствие post-rollback runtime probe.

## Corrective pass

- При insufficient низкорелевантные hits больше не подаются LLM как знания; prompt требует явный текст ограничения и
  предложения оператора.
- Wrapper проверяет positive, live follow-up, insufficient old-science turn, смысл unknown-answer, отсутствие `wiki-*`
  leakage и source IDs в report.
- Short elliptical `Сколько ...?` получает dialogue context; однословный ASR-фрагмент его автоматически не получает.
- Runbook повторяет shell preamble, использует Docker `--wait --wait-timeout 60` и требует probe после rollback.

## Повторный verdict

`PASS`, blockers отсутствуют. Reviewer проверил `live-r5`, текущий wrapper, runbook и 41 deterministic test:

- positive и follow-up sufficient и используют `company-pricing-and-terms`;
- old science turn insufficient;
- unknown-answer сообщает об ограничении и предлагает оператора;
- `wiki-*` leakage отсутствует;
- registration, RTP continuity, transfer и recording checks проходят;
- исправления shell/Docker/rollback присутствуют.

Non-blocking notes: positional assertions допустимы только для зафиксированного fixture; substring-проверка текста не
заменяет общий semantic evaluator; точные суммы в свободном LLM-ответе отдельно не валидируются wrapper-ом, хотя в
`live-r5` корректны (`1500` и `2250` рублей).
