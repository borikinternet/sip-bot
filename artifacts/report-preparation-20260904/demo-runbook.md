# Map-006: runbook воспроизводимой демонстрации

Дата: `2026-09-05`  
Target: Ubuntu 24.04 в WSL2, CPython `3.14.7t`, RTX 5060 Ti, один локальный Baresip peer и fake operator

Статус: `complete по техническому scope`. `005-E`/r10 остаётся upstream evidence целостности TTS, а текущим
acceptance evidence Map-006 является corrective `006-D/target-20260905-r6`; r7 сохранён только как исторический
diagnostic baseline.

## 1. Предварительные условия

- Windows и WSL имеют не менее 20 ГБ свободного места.
- GPU свободна от чужих процессов; проверка выполняется перед единственным тяжёлым запуском.
- Веса ASR/LLM/TTS, Ollama и patched no-GIL dependencies уже установлены в утверждённых disposable environments.
- Нельзя принимать call до завершения реального warmup RAG embeddings, LLM chat, ASR и TTS.
- Для нового прогона используется новый пустой evidence root; исторические `r7` artifacts не перезаписываются.

## 2. Проверка target runtime

```bash
cd /mnt/c/devel/sip-bot
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c \
  'import sys; print(sys.version); print("gil_enabled=", sys._is_gil_enabled())'
```

Ожидается free-threading CPython `3.14.7t` и `gil_enabled=False`. Host Python разрешён для document registry audit,
но не заменяет target для inference/live claims.

## 3. Clean-start rehearsal (принятый corrective 006-D r6)

Команда принятого main-executor прогона r6:

```bash
cd /mnt/c/devel/sip-bot
export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}
/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python -I tools/map005_rehearsal_gate.py \
  --output-root /mnt/c/devel/sip-bot/artifacts/report-preparation-20260904/006-D/target-20260905-r6 \
  --timeout-s 240 --post-report-grace-s 3
```

Для повторного прогона заменить только output root на новый каталог. Команда не должна запускаться одновременно с
другим GPU-heavy процессом. Runner выполняет test-only in-memory `pjsua2.EpConfig().medConfig.noVad=True`, чтобы
Baresip `sndfile` decode track сохранял временную ось idle RTP; application source и production recording этим не
изменяются.

## 4. Ожидаемый сценарий

1. локальный SIP/RTP call с PCMU/8000/mono устанавливается и принимается;
2. пользователь задаёт вопрос по естественным наукам;
3. задаёт follow-up с использованием контекста;
4. перебивает ответ новым вопросом;
5. задаёт вопрос вне curated KB, получает честное предложение оператора;
6. отвечает «Да», вызов переводится на fake operator;
7. terminal lifecycle создаёт текстовый `report.md`;
8. Baresip test peer сохраняет raw `enc`/`dec`, после чего строится stereo derivative.

## 5. Артефакты для проверки

- [`map005-d-rehearsal.json`](006-D/target-20260905-r6/map005-d-rehearsal.json) — machine-readable result, 7/7 checks;
- [`requirement-matrix.md`](006-D/target-20260905-r6/requirement-matrix.md) — scenario matrix;
- [`conversation-stereo.wav`](006-D/target-20260905-r6/recordings/conversation-stereo.wav) — left user→bot, right bot→user;
- [`recording-manifest.json`](006-D/target-20260905-r6/recordings/recording-manifest.json) — raw paths, hashes, mapping and explicit alignment;
- [`audio-audit.md`](006-D/target-20260905-r6/audio-audit.md) — read-only audit of active speech regions and TTS gaps;
- [`report.md`](006-D/target-20260905-r6/reports/j4-full-live-call/report.md) — dialogue report;
- [`freeze-checklist.md`](006-D/target-20260905-r6/freeze-checklist.md) — D closeout checklist.

При ручной проверке нужно сначала прослушать stereo, затем сверить mapping и hashes в manifest. Raw tracks не удаляются.

## 6. Cleanup и troubleshooting

- После завершения убедиться, что Baresip peers завершены и RTP/SIP processes не остались висеть.
- Если GPU занята, не менять model/runtime и не запускать fallback: завершить внешний процесс и повторить preflight.
- Если свободного места меньше 20 ГБ, остановить heavy run, освободить место и повторить preflight.
- Если пакетный менеджер занят lock-файлом, это не повод менять зависимости: повторить подготовительную операцию после
  случайной задержки.
- `r1` и `r3` — исторические прогоны, остановленные внешним условием Ollama;
- `r4` и `r5` — исторические прогоны с неполным сценарием и неисполненными transfer-проверками;
- `r6` — текущий полностью успешный corrective run Map-006, использовать его для current claims;
- `r7` и `r10` — upstream historical evidence; `r10` сохраняет значение для TTS integrity baseline.

## 7. Честные ограничения демонстрации

Warmup не показывается как latency ответа. Общая задержка final phrase→first PCM выше ориентира 200–500 ms и должна
быть озвучена в докладе. Один clean-start run не является доказательством production readiness, масштабирования или
MOS/SLO.
