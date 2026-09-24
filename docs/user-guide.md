# Пользовательский гайд SIP-бота

Статус: `active`  
Актуально для: `Ubuntu 24.04/WSL2`, `CPython 3.14.7t`, `RTX 5060 Ti`, один параллельный звонок  
Назначение: запуск текущего локального демонстратора и проверка его результата

## 1. Важное ограничение текущей версии

В репозитории уже есть рабочий сквозной демонстрационный путь, но пока нет упакованного сервиса, который можно
зарегистрировать на произвольной PBX и запустить одной командой как постоянного SIP-абонента.

Сегодня используются два разных входа:

| Вход | Что делает |
|---|---|
| `python -m sip_bot` | Только проверяет target runtime и no-GIL preflight; живой звонок не запускает |
| `tools/map005_rehearsal_gate.py` | Запускает полный локальный demo-run: warmup AI, Baresip peer, fake operator, SIP/RTP-вызов и формирование артефактов |

Поэтому настоящий пользовательский путь текущего MVP — это технический оператор демонстрации. Внешний абонент пока
не настраивает PBX на готовый daemon: это следующий слой упаковки runtime, а не скрытая возможность текущего кода.

## 2. Роли

- **Абонент** — говорит с ботом через SIP; ему не нужны Python, Ollama или сведения о RAG.
- **Оператор демонстрации** — запускает WSL, Ollama и accepted rehearsal command, затем проверяет отчёт и запись.
- **Интегратор** — в будущем подключает SIP-адрес бота к PBX и задаёт маршрут оператора; для этого потребуется отдельный
  service launcher и конфигурация учётных данных/регистратора.

## 3. Что должно быть установлено

Минимальная проверенная конфигурация:

- Windows с WSL2 и дистрибутивом `Ubuntu-24.04`;
- GPU NVIDIA RTX 5060 Ti, доступная из WSL;
- не менее 20 ГБ свободного места на диске, где лежат проект, кэши и артефакты;
- target free-threaded CPython:
  `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`;
- combined runtime для live AI/SIP gate:
  `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python`;
- patched `webrtcvad-wheels 2.0.14`, patched CTranslate2 binding, PJSUA2/PJMEDIA и Baresip;
- локальный Ollama `0.33.1`;
- подготовленные модели:
  - ASR `Systran/faster-whisper-large-v3` в `/home/sipbot/.local/models/faster-whisper-large-v3-edaa852e`;
  - LLM `Qwen3.5-9B`, GGUF `Q4_K_M`, модель Ollama `c3-qwen35-9b-q4km:latest`;
  - embeddings `embeddinggemma:latest`;
  - TTS XTTS-v2 в `/home/sipbot/.cache/sip-bot-c4-xtts-v2-model`.

Проверенные provenance, patches и версии находятся в feasibility/implementation evidence и не заменяются этим кратким
гайдом. Если какого-либо runtime или веса нет, запуск нужно остановить на этапе подготовки: demo-runner не должен
молча переходить на другой Python, модель, квантизацию или CPU-fallback.

## 4. Где находятся настройки

### 4.1. Основная конфигурация приложения

Единственный источник статических application constants — [`config/constants.py`](../config/constants.py). После
изменения требуется перезапуск процесса. Основные группы настроек:

| Группа | Примеры |
|---|---|
| SIP/media | `SIP_BIND_HOST`, `SIP_BIND_PORT`, `RTP_PORT_START`, `RTP_PORT_END`, `SIP_CODEC`, `OPERATOR_TARGET` |
| Модели и устройства | `ASR_MODEL_PATH`, `LLM_MODEL_PATH`, `TTS_MODEL_PATH`, `ASR_DEVICE`, `LLM_DEVICE`, `TTS_DEVICE` |
| Речь | `VAD_MODE=2`, `ENDPOINT_SOFT_MS=300`, `ENDPOINT_HARD_MS=360`, `MIN_SPEECH_MS=80` |
| Буферизация | `ASR_CHUNK_MS=1000`, capacities audio/control buffers |
| Потоковый TTS | `TTS_STREAM_CHUNK_SIZE=5`, `TTS_STREAM_OVERLAP_WAV_LEN=1024` |
| Ollama | `LLM_HTTP_ENDPOINT`, `LLM_CHAT_MODEL`, `LLM_EMBEDDING_MODEL`, timeouts и generation profile |
| RAG | corpus/index path, `RAG_TOP_K`, `RAG_RELEVANCE_THRESHOLD`, `RAG_MAX_CONTEXT_CHARS` |
| Prompt/skill | `DEFAULT_SKILL_INSTRUCTION`, `PROMPT_TEMPLATE_TEXT`, их ID/version и generation profile |
| Приветствие | `CALL_GREETING_TEXT` (`"Алло."` по умолчанию; пустая строка отключает greeting) |

`config/constants.py` — владельцы настроек приложения. Документы [`technical-specification.md`](technical-specification.md)
и [`architecture.md`](architecture.md) описывают их смысл, но не являются вторым конфигурационным файлом.

Штатное место редактирования формулировки ответа — `DEFAULT_SKILL_INSTRUCTION`; именно здесь находится инструкция
`Отвечай коротко.`. Структуру полного запроса, JSON-ограничения и placeholders `{instruction}`, `{context}`, `{knowledge}`
и `{user_text}` меняют в `PROMPT_TEMPLATE_TEXT`. После смыслового изменения нужно поднять соответствующую
`DEFAULT_SKILL_VERSION`, `PROMPT_TEMPLATE_VERSION` или `GENERATION_PROFILE_VERSION` и перезапустить runtime. Factory в
`src/sip_bot/prompt/defaults.py` материализует эти constants, а `src/sip_bot/prompt/manager.py` подставляет данные;
копировать шаблон в live runner или редактировать Ollama для этого не нужно.

`TTS_STREAM_CHUNK_SIZE` управляет внутренним размером первой порции XTTS, а не SIP/RTP `ptime`: PJMEDIA по-прежнему
получает кадры по согласованному для звонка media clock. Чем меньше значение, тем раньше появляется первый PCM, но тем
чаще XTTS выполняет декодирование и тем меньше запас producer buffer. Текущий baseline `5` выбран на десяти запусках
пяти русских фраз для каждого кандидата `20/10/5`; менять его по одному услышанному ответу не следует. Повторная
проверка выполняется `tools/tts_stream_latency_probe.py`, а live-разложение задержки —
`tools/tts_latency_audit.py` по результату registered full rehearsal.

### 4.2. Тестовый SIP-стенд

Шаблоны Baresip находятся в
[`artifacts/feasibility/001-S-voip-test-stand/config/`](../artifacts/feasibility/001-S-voip-test-stand/config/):

- `peer-5080/` — пользовательский тестовый peer;
- `operator-5090/` — fake operator для проверки transfer;
- `config/` — базовые файлы стенда.

`j4` и `rehearsal` создают рабочие копии конфигураций в новом evidence root. Рабочие копии не редактируются вручную
после запуска и не должны использоваться как постоянная конфигурация PBX.

### 4.3. База знаний и результаты

- active workshop corpus: [`config/workshops/rag/corpus/`](../config/workshops/rag/corpus/);
- science regression corpus: [`data/knowledge/corpus/`](../data/knowledge/corpus/);
- готовые локальные indexes: [`data/knowledge/index/`](../data/knowledge/index/);
- контекст текущего звонка и итоговый текстовый отчёт — внутри выбранного output root;
- исходные и stereo-записи live-теста создаёт Baresip, а не application runtime.

Текущие live tools частично используют зафиксированные пути approved environments для ASR/TTS. Поэтому изменение только
`ASR_MODEL_PATH` или `TTS_MODEL_PATH` в constants пока не перенастраивает `tools/live_i1_gate.py` и
`tools/j4_full_live_gate.py`. Это известный packaging gap; до появления launcher следует пользоваться accepted командами
и их окружениями.

## 5. Проверка перед запуском

Команды ниже выполняются из PowerShell или из WSL. Путь `/mnt/c/devel/sip-bot` соответствует текущему checkout в
`C:\devel\sip-bot`.

### 5.1. WSL, диск и GPU

```powershell
wsl.exe -l -v
wsl.exe -d Ubuntu-24.04 -- bash -lc 'df -h /mnt/c; nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader,nounits'
```

До единственного тяжёлого запуска нужно убедиться, что:

- свободно не менее 20 ГБ;
- GPU не занята другой моделью или игрой;
- в выводе видна RTX 5060 Ti.

### 5.2. Target Python и no-GIL

```powershell
wsl.exe -d Ubuntu-24.04 -u sipbot -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "import sys,sysconfig; print(sys.executable); print(sys.version); print(sysconfig.get_config_var('Py_GIL_DISABLED')); print(sys._is_gil_enabled())"
```

Ожидается `Py_GIL_DISABLED=1` и `False` в последней строке. Windows Python и обычный WSL Python 3.12 не являются
target runtime для live inference.

### 5.3. Ollama

Проверить версию и доступность сервера:

```bash
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama --version
curl -fsS http://127.0.0.1:11434/api/tags
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama list
```

В списке должны присутствовать `c3-qwen35-9b-q4km:latest` и `embeddinggemma:latest`. Если сервер не запущен, в
отдельном WSL-терминале запустить его и оставить этот терминал открытым:

```bash
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama serve
```

Если `127.0.0.1:11434` уже отвечает, второй экземпляр Ollama запускать не нужно.

Быстрая проверка именно тех API, которые использует фасад:

```bash
curl -fsS http://127.0.0.1:11434/api/embed \
  -H 'Content-Type: application/json' \
  -d '{"model":"embeddinggemma","input":"Проверка готовности индекса."}'

curl -fsS http://127.0.0.1:11434/api/show \
  -H 'Content-Type: application/json' \
  -d '{"name":"c3-qwen35-9b-q4km:latest"}'
```

Эти проверки могут сами загрузить Ollama-модели в память. Полный demo-run всё равно выполняет собственный warmup по
рабочему typed boundary.

## 6. Порядок запуска

На текущем MVP порядок такой:

1. Освободить GPU и проверить диск.
2. Запустить Ollama или убедиться, что он уже слушает `127.0.0.1:11434`.
3. Проверить target CPython и наличие моделей.
4. Запустить accepted rehearsal command из нового пустого output root.
5. Дождаться окончания runtime readiness и полного SIP/RTP сценария.
6. Проверить `status`, scenario checks, report и stereo WAV.

### 6.1. Что именно прогревается

В полном rehearsal прогрев выполняется runtime-scoped coordinator-ом последовательно, потому что GPU общая. Для
registered incoming режима `ApplicationRuntime.start()` остаётся быстрым: launcher сначала отправляет `180 Ringing`, а
затем либо использует уже готовый runtime, либо ждёт/запускает одну общую readiness-операцию до финального допуска:

1. `RAG/embeddings` — готовый versioned index загружается и проверяется, затем выполняется один warm query; corpus
   embeddings на startup/call path не вычисляются;
2. `LLM chat` — выполняется structured non-thinking request через `LlmFacade`;
3. `ASR` — выполняется операция на входном 8 kHz PCM с модельным путём 16 kHz;
4. `TTS initialize` — загружается XTTS и готовятся conditioning latents;
5. `TTS stream` — получается первый реальный PCM chunk;
6. `fixture` — для blocking demo-run формируется тестовый многосценарный WAV; registered workshop path использует
   заранее подготовленный fixture.

Это не import-only smoke: warmup использует те же typed owners и операции, что и рабочий путь. При рестарте процесса
его нужно повторить. В финальном cold registered evidence r15 warmup занял `26,303.471 ms`; это стоимость подготовки runtime,
а не задержка уже готового диалога. Входящий вызов, пришедший во время `RUNNING`, ожидает ту же операцию; отдельный
per-call warmup не создаётся.

Отдельной команды `sip-bot warmup` пока нет. В библиотечном коде эквивалентная последовательность —
`ApplicationRuntime.start()` → `runtime.configure_warmup(...)` → явный `start_background()` либо fallback
`IncomingCallReadinessGate.ensure_ready()` → финальный `SipMediaAdapter.answer()` с `200 OK`. Для live incoming режима
адаптер сначала локально отправляет `180 Ringing`; readiness coordinator выполняет warmup вне native callback и не
блокирует основной `asyncio` loop. Ошибка warmup завершается явным `503`, а не direct/CPU fallback. Готового внешнего
daemon-launcher вокруг этой процедуры пока ещё нет.

### 6.2. Полный локальный demo-run

Команда ниже — текущий воспроизводимый путь. В `--output-root` каждый раз указывается новый каталог или пустой
каталог: runner не перезаписывает исторические результаты.

```powershell
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/map005_rehearsal_gate.py --output-root /mnt/c/devel/sip-bot/artifacts/user-runs/20260913-r1 --timeout-s 240 --post-report-grace-s 3'
```

Команда сама:

- выполняет warmup;
- создаёт локальные Baresip peer и fake operator;
- устанавливает SIP/RTP-вызов с PCMU/8000/mono;
- прогоняет follow-up, barge-in, unknown-answer/offer-transfer и transfer;
- формирует текстовый отчёт;
- сохраняет raw `enc`/`dec` и stereo derivative записи на стороне Baresip.

Это демонстрационный сценарий с заранее сгенерированным голосовым fixture, а не разговор человека с ботом.

### 6.3. Зарегистрированный режим для мастер-класса

Для отдельной проверки optional SIP registration используется локальный FreeSWITCH fixture. Это воспроизводимый
тестовый стенд, а не production PBX. В типовой конфигурации registration выключена; `registered_call_probe.py` явно
создаёт enabled-профиль с публичными demo credentials для этого сценария.

Чистый запуск стенда и зарегистрированного вызова:

```powershell
docker.exe compose -f tools/freeswitch_workshop/docker-compose.yml down --remove-orphans
docker.exe compose -f tools/freeswitch_workshop/docker-compose.yml up -d --wait --wait-timeout 60 --force-recreate
docker.exe exec sip-bot-freeswitch-workshop fs_cli -x status
docker.exe exec sip-bot-freeswitch-workshop fs_cli -x "show registrations"
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cublas/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cudnn/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/freeswitch_workshop/registered_call_probe.py --output artifacts/user-runs/registered-20260913-r1.json --timeout-seconds 30'
```

В результате должны быть `status=pass`, успешные регистрации `tester` и `peer`, порядок `180 → readiness handoff →
200`, negotiated `PCMU/8000/mono` и отсутствие overflow/native abort. Машинный результат сохраняется в
`artifacts/user-runs/registered-20260913-r1.json`; перед повтором выбирается новый output path. Команда probe сама
завершает Baresip peer, но контейнер FreeSWITCH можно остановить отдельно:

```powershell
docker.exe compose -f tools/freeswitch_workshop/docker-compose.yml down --remove-orphans
```

Полный registered full-AI replay запускается после подготовки стенда и использует cold runtime readiness:

```powershell
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cublas/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cudnn/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}; export PYTHONNOUSERSITE=1; export PYTHONPATH=/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages; cd /mnt/c/devel/sip-bot; /home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python tools/freeswitch_workshop/registered_full_rehearsal.py --output-root artifacts/user-runs/registered-full-20260913-r1 --timeout-s 300 --post-report-grace-s 5 --fixture-leading-silence-s 45'
```

Эта команда сама не запускает целенаправленный прогрев при старте: readiness coordinator начинает одну общую операцию
по запросу сценария, а входящий вызов сначала получает `180`. Воспроизводимый cold run r15 занял `26,303.471 ms` до
готовности runtime и завершился с полным AI/report результатом. Для мастер-класса можно заранее вызвать тот же сценарий
с `--prewarm`; повторный per-call warmup при этом не создаётся.

Пароль `PUBLIC-DEMO-SIP-PASSWORD` намеренно является опубликованным demo credential из типового конфига; его нельзя
использовать в реальной PBX. Полноценный постоянно работающий внешний launcher остаётся отдельным packaging scope.

### 6.4. Смена документов и RAG-мастер-класс

Активный демонстрационный corpus — синтетические документы компании «СервисПлюс», а готовый index загружается без
повторной векторизации корпуса. Самодостаточный процесс «подготовить Markdown/manifest → проверить → построить index →
оценить retrieval → активировать → выполнить зарегистрированный звонок → rollback» описан в
[`workshops/rag-corpus-onboarding-runbook.md`](workshops/rag-corpus-onboarding-runbook.md).

Пользовательский RAG workflow не требует переобучения Qwen. Он использует `embeddinggemma` через тот же typed
`LLM Facade`, локальный `rag-index-v1` и существующий Qwen/Ollama answer path. В live gate обязательно проверяются
positive, follow-up, смена темы, unknown-answer с явным предложением оператора, transfer, source IDs и отсутствие
`wiki-*` leakage.

## 7. Что проверять после запуска

В каталоге, указанном в `--output-root`, должны появиться:

- `registered-j4-full-live.json` — общий machine-readable результат registered full-AI replay;
- `recordings/conversation-stereo.wav` — левый канал `user_to_bot`, правый `bot_to_user`;
- `recordings/raw/*-enc.wav` и `*-dec.wav` — первичные дорожки Baresip;
- `recordings/recording-manifest.json` — mapping, hashes, timestamps старта дорожек и выравнивание каналов по окну
  `200 OK → BYE`;
- `context/call-in-0/conversation.jsonl` — текстовый контекст текущего звонка;
- `reports/call-in-0/report.md` — обязательный итоговый отчёт.

Минимальная проверка результата без дополнительных утилит:

```bash
cd /mnt/c/devel/sip-bot
grep -E '"status"|"scenario_checks"|"warmup"|"audio_recording"' artifacts/user-runs/registered-full-20260913-r1/registered-j4-full-live.json
```

Для Map-010 в JSON дополнительно проверяется объект `rtp_continuity`. Приёмка непрерывности использует answered-call
window от события `200 OK` на `INVITE` до `BYE`/`media_stopped`, negotiated `ptime`, число egress-кадров адаптера и
счётчики приёма/потерь RTP на Baresip peer. В успешном target r4 окно составило `125618.477 ms` при `ptime=20 ms`:
ожидалось `6281`, adapter egress и peer receive дали `6281`, loss/underrun/callback errors/egress drops равны нулю.
Длительности raw `enc`/`dec` WAV и стереозаписи проверяются отдельно как recording diagnostic; они не заменяют RTP
continuity и не используются как его proxy.

Сначала прослушать `conversation-stereo.wav`, затем сверить mapping и hashes в manifest. Старые r1/r2/r3/r6/r7/r10
артефакты не следует выдавать за результат нового запуска.

## 8. Завершение и повторный запуск

- После успешного run Baresip peer и fake operator завершаются самим runner.
- Ollama можно оставить запущенным для следующего run; при остановке нажать `Ctrl+C` в его терминале.
- Повторный run получает новый output root, например `artifacts/user-runs/20260913-r2`.
- Если runner был прерван, перед повтором проверить, что старые Baresip-процессы не остались висеть, и выбрать новый
  output root.
- Не удалять model caches ради ускорения следующего запуска: это снова вызовет длительный дисковый I/O и cold start.

## 9. Типовые проблемы

| Симптом | Проверка/действие |
|---|---|
| `connection refused` на `11434` | Запустить Ollama в отдельном WSL-терминале; проверить `/api/tags` |
| Модель не найдена | Проверить `ollama list`; не подменять модель автоматически, восстановить approved model/runtime |
| Ошибка про free-threaded CPython | Запущен не тот executable; использовать именно combined command выше |
| Недостаточно места | Освободить место до 20 ГБ; не начинать heavy run |
| GPU занята или OOM | Завершить внешний GPU-процесс и повторить preflight; не включать CPU/fallback молча |
| Output root не пуст | Выбрать новый каталог; исторические результаты не перезаписывать |
| Долгая загрузка диска в начале | Это cold start/warmup; при incoming SIP caller сначала получает `180`, а `200` отправляется только после готовности |
| Lock-файл пакетного менеджера при подготовке окружения | Подождать случайный интервал и повторить операцию; не считать lock сам по себе блокером |

## 10. Что нужно добавить, чтобы гайд стал пользовательским для внешнего интегратора

Для использования с произвольной PBX потребуется отдельный прикладной launcher, который:

1. читает `RuntimeConfig` и SIP/PBX settings;
2. создаёт owners и существующие boundary bindings;
3. проверяет readiness и при cold start запускает warmup вне native callback/event-loop blocking;
4. запускает основной `asyncio` loop, отвечает `180` на входящий звонок и отправляет `200` только после readiness;
5. корректно завершает runtime по SIP/media events;
6. предоставляет понятные `start/stop/status/warmup` команды и журнал ошибок.

До реализации этого launcher настоящий внешний пользователь должен считать `map005_rehearsal_gate.py` инструментом
локальной демонстрации и регрессионного прогона, а не production-сервисом.
