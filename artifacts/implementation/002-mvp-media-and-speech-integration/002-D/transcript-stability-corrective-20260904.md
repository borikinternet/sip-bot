# 002-D corrective evidence: transcript stability

Дата: `2026-09-04`

## Обнаружение

Full live gate `002-J/j4-full-live-20260904-r19` завершился красным результатом на первой фразе с
`TranscriptContractError: ASR revision contradicts the already stable prefix`. Две ранние partial-гипотезы ASR
случайно имели длинный общий префикс, и прежний assembler ошибочно объявил его стабильным. Следующая, более точная
гипотеза этот префикс исправила.

Это была ошибка реализации в существующем approved speech-ingress scope (APG 6.1 category 1), а не архитектурный gap.
Raw failure сохранён в `002-J/j4-full-live-20260904-r19/j4-full-live.json`.

## Исправление

`TranscriptAssembler` теперь продвигает `stable_prefix` только если он явно передан backend-ом в
`AsrHypothesis.stable_prefix`. При отсутствии этого поля partial-гипотеза остаётся полностью изменяемой. Так сохраняется
защита от накопления исправленных фрагментов и не вводится новый компонент или fallback.

Добавлен deterministic regression:
`tests/unit/test_speech_ingress.py::test_transcript_assembler_does_not_freeze_an_early_common_asr_prefix`.
Существующая проверка русской `ё/е` переведена на явный backend stable prefix.

## Проверка

- targeted speech/wiring host tests: `23 passed, 2 skipped`, exit `0`;
- target CPython 3.14.7t full regression: `127 passed, 2 skipped`, exit `0`;
- full live gate `002-J/j4-full-live-20260904-r20`: `status=pass`, `6/6` scenario checks, `errors=[]`, exit `0`.

Изменение не меняет typed boundary: `AsrHypothesis`, `TranscriptUpdate` и `FinalUserTurn` сохранены; изменена только
политика доверия к optional stable-prefix metadata.
