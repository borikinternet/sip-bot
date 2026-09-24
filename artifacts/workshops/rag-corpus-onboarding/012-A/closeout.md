# 012-A closeout: corpus package contract

Статус: `complete`  
Дата: `2026-09-21`  
Contract revision: `rag-corpus-v1`

## Результат

- Добавлены typed `CorpusManifest`, расширенный `CorpusSource`, `CorpusDocument`, `CorpusValidationIssue/Report`.
- `CorpusPackage.validate/load` строго проверяет JSON/UTF-8, schema/unknown fields, stable IDs, provenance, license,
  versions/dates/priority/topics/audiences, duplicate source/file, confined relative Markdown path и non-empty document.
- Невалидный package не проходит `load()` и не может быть молча передан в build.
- Science corpus перенесён на schema v1 без изменения Markdown; valid, 3 sources/documents.
- Создан синтетический CC0 workshop corpus «СервисПлюс»; valid, 6 sources/documents: услуги, расписание,
  цены/условия, заявка, исключения и эскалация.

Manifest SHA-256:

- science: `BFCFC2A38B6493DA3B94B4A621499D0D1021A62541080A60A4AE98E3F1E0B5B0`;
- workshop: `40F09B2A63F6CA52371319933C6643226DA9F53A1516114957F32A4BDD7947BF`.

## Проверки

Target runtime: CPython 3.14.7t, `Py_GIL_DISABLED=1`, `sys._is_gil_enabled()=False`.

```text
wsl -d Ubuntu-24.04 -u sipbot -- bash -lc 'cd /mnt/c/devel/sip-bot &&
  export PYTHONPATH=/mnt/c/devel/sip-bot/src &&
  /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -m pytest -q
  tests/unit/test_rag_corpus.py tests/unit/test_context_retrieval_prompt.py
  tests/contract/test_f_retrieval_prompt_contracts.py'
```

Результат: `22 passed in 2.16s`, exit code `0`. Проверены unknown fields, duplicate IDs/files, traversal/absolute/Windows
paths, invalid UTF-8, empty documents, duplicate JSON keys и повторяемый report.

## Closeout

Scope выполнен полностью, открытых blocker/fallback нет. Authoritative handoff для 012-B: package
`CorpusPackage.documents` в source-id order, каждый document содержит typed source metadata, strict UTF-8 text и SHA-256.

