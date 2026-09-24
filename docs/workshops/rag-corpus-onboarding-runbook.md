# Мастер-класс: настраиваем SIP-ассистента на документы компании

Статус: `verified by deterministic clean repeat, independent context-free review and registered live gate`

Целевая среда: `Windows 11 + WSL2 Ubuntu 24.04 + CPython 3.14.7t + RTX 5060 Ti`

Сценарий: новый UTF-8 Markdown corpus → проверка → embeddings → атомарный index → evaluation → зарегистрированный
SIP-звонок через FreeSWITCH.

## 1. Что получится

Участник заменит демонстрационную базу естественных наук документами условной компании «СервисПлюс», не обучая
Qwen заново. Веса LLM не меняются: `embeddinggemma` строит векторы документов и вопросов, локальный index выбирает
релевантные фрагменты, а Qwen получает вопрос вместе с найденным контекстом.

На выходе должны быть:

- проверенный versioned corpus package;
- воспроизводимый index `small-service-company-embeddinggemma-v1` (`12 × 768`);
- evaluation `12/12`, включая перефразирование, follow-up и отрицательные запросы;
- зарегистрированный звонок через FreeSWITCH с ответами по новому corpus;
- `report.md` с `company-*` source IDs и без `wiki-*` leakage;
- stereo-запись разговора от Baresip.

Это MVP: Markdown/JSON готовятся вручную, поиск линейный in-memory, hot reload, OCR, PDF/DOCX importer, ACL и
распределённая vector DB не входят.

## 2. Предварительные условия и stop conditions

Общий runtime бота должен быть подготовлен по [`../user-guide.md`](../user-guide.md). FreeSWITCH-часть можно
предварительно повторить по [`freeswitch-callcenter-runbook.md`](freeswitch-callcenter-runbook.md); автоматический live
gate ниже использует локальный workshop fixture FreeSWITCH и Baresip.

Из PowerShell:

```powershell
wsl.exe -l -v
wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc 'df -BG / /mnt/c; nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader,nounits'
wsl.exe -d Ubuntu-24.04 -u sipbot -- /home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -c "import sys,sysconfig; print(sys.version); print(sysconfig.get_config_var('Py_GIL_DISABLED')); print(sys._is_gil_enabled())"
```

Продолжать можно только при свободных `>=20 GiB`, доступной RTX 5060 Ti, `Py_GIL_DISABLED=1` и
`sys._is_gil_enabled() == False`. Если GPU занята другим процессом, освободить её; CPU fallback не включать.

Проверить Ollama в Ubuntu:

```bash
curl -fsS http://127.0.0.1:11434/api/version
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama list
```

Нужны `embeddinggemma:latest` и `c3-qwen35-9b-q4km:latest`. Если endpoint не отвечает, в отдельном WSL-терминале:

```bash
/home/sipbot/src/c3-ollama/v0.33.1/bin/ollama serve
```

Остановиться, если corpus содержит документы без понятного права использования, validator красный, build не
сохраняет старый index при ошибке, evaluation не проходит полностью либо runtime принимает несовместимый artifact.

## 3. Как подготовить документы

Corpus — отдельный каталог. В корне лежит `manifest.json`, а каждый источник — отдельный UTF-8 Markdown-файл.
Готовый пример: [`../../config/workshops/rag/corpus/`](../../config/workshops/rag/corpus/).

Обязательные поля manifest:

```json
{
  "schema_version": "rag-corpus-v1",
  "corpus_id": "small-service-company-demo",
  "corpus_version": "small-service-company-demo-v1",
  "title": "Синтетическая база знаний компании «СервисПлюс»",
  "language": "ru",
  "license": "CC0-1.0",
  "sources": [
    {
      "source_id": "company-services",
      "file": "services.md",
      "title": "Услуги компании",
      "origin": "Синтетический материал проекта sip-bot",
      "license": "CC0-1.0",
      "attribution": "Синтетическая база знаний «СервисПлюс», версия 1.0.0",
      "owner": "Проект sip-bot",
      "version": "1.0.0",
      "effective_date": "2026-09-21",
      "priority": 100,
      "topics": ["бытовые услуги", "ремонт"],
      "audiences": ["диспетчер", "клиент"]
    }
  ]
}
```

Правила:

- один устойчивый `source_id` на логический документ;
- относительный `.md` path без `..`, абсолютных путей и symlink escape;
- заголовки описывают разделы, абзацы — самостоятельные небольшие смысловые фрагменты;
- дата — ISO `YYYY-MM-DD`, priority — целое `0..1000`;
- конфликтующие инструкции получают явную дату/версию/priority, а не оставляются на выбор LLM;
- пароль, персональные данные и внутренние секреты в публичный workshop corpus не помещаются;
- PDF/DOCX/HTML на этом этапе вручную приводятся к Markdown; OCR не имитируется.

## 4. Проверка, построение и оценка

Все команды выполняются в Ubuntu от `sipbot`:

```bash
cd /mnt/c/devel/sip-bot
export PYTHONPATH=/mnt/c/devel/sip-bot/src:/mnt/c/devel/sip-bot
PY=/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
RUN=artifacts/user-runs/rag-onboarding-01

$PY tools/knowledge/rag_index.py validate \
  --corpus config/workshops/rag/corpus \
  --report $RUN/validation.json

$PY tools/knowledge/rag_index.py build \
  --corpus config/workshops/rag/corpus \
  --output $RUN/small-service-company-v1.json \
  --index-version small-service-company-embeddinggemma-v1 \
  --embedding-model embeddinggemma \
  --report $RUN/build.json

$PY tools/knowledge/evaluate_rag.py \
  --index $RUN/small-service-company-v1.json \
  --suite config/workshops/rag/evaluation.json \
  --output $RUN/evaluation.json
```

Ожидается: validation `valid=true`; build `status=pass`, `item_count=12`, `dimension=768`; evaluation `status=pass`,
`passed_cases=12`, `total_cases=12`. Повторная сборка неизменного corpus должна дать тот же artifact SHA-256.

Builder вызывает Ollama только через typed `LlmFacade`, пишет temporary sibling, сам загружает и проверяет candidate,
после чего публикует его `os.replace`. Ошибка до publish не должна менять старый файл.

## 5. Активация индекса и rollback

Runtime имеет единственный источник статической конфигурации — [`../../config/constants.py`](../../config/constants.py).
Для workshop-профиля должны быть заданы:

```python
KNOWLEDGE_CORPUS_PATH = Path("config/workshops/rag/corpus")
KNOWLEDGE_INDEX_PATH = Path("data/knowledge/index/small-service-company-v1.json")
RAG_CORPUS_VERSION = "small-service-company-demo-v1"
RAG_INDEX_VERSION = "small-service-company-embeddinggemma-v1"
RAG_CORPUS_SHA256 = "9f6c1fb70792d6a44e3c098f920bf5895b1fa03503aac13d14897ea833e707ff"
RAG_INDEX_DIMENSION = 768
```

Скопировать проверенный artifact из `$RUN` в заданный path разрешается только после полного build/evaluation gate.
Текущий репозиторий уже содержит идентичный опубликованный artifact. После изменения constants процесс перезапускается;
hot reload во время разговора запрещён.

Проверить active artifact и один warm query:

```bash
cd /mnt/c/devel/sip-bot
export PYTHONPATH=/mnt/c/devel/sip-bot/src:/mnt/c/devel/sip-bot
PY=/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
RUN=artifacts/user-runs/rag-onboarding-01

$PY tools/knowledge/runtime_index_probe.py \
  --output $RUN/runtime-index-probe.json
```

Ожидается `corpus_embedding=0`, `warm_query_embedding=1`: startup загружает готовые векторы и не индексирует документы.

Rollback — вернуть пять science-значений и перезапустить runtime:

```text
KNOWLEDGE_CORPUS_PATH=data/knowledge/corpus
KNOWLEDGE_INDEX_PATH=data/knowledge/index/natural-science-v1.json
RAG_CORPUS_VERSION=ru-natural-science-demo-v1
RAG_INDEX_VERSION=natural-science-embeddinggemma-v1
RAG_CORPUS_SHA256=531d177f8f77611faaad32cf08c0a9b172e1f2cb2c8a0d3d26667a210f0e33ee
```

После rollback перезапустить runtime и повторить `runtime_index_probe.py`; probe должен показать science metadata,
`corpus_embedding=0` и ровно один `warm_query_embedding`.

## 6. Подготовка голосового fixture

Это тяжёлый шаг с XTTS; выполнить один раз до звонка. Он не является прогревом по входящему вызову:

```bash
cd /mnt/c/devel/sip-bot
RUN=artifacts/user-runs/rag-onboarding-01
export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cublas/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cudnn/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}
export PYTHONNOUSERSITE=1

/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python \
  tools/knowledge/build_rag_workshop_fixture.py \
  --output $RUN/input-scenario.wav \
  --manifest $RUN/input-scenario.json
```

Fixture содержит positive, follow-up, barge-in, старый science-вопрос и подтверждение transfer. WAV — голос тестового
абонента, а не запись разговора.

## 7. Зарегистрированный звонок через FreeSWITCH

Из PowerShell запустить локальный fixture FreeSWITCH:

```powershell
docker.exe compose -f C:\devel\sip-bot\tools\freeswitch_workshop\docker-compose.yml down --remove-orphans
docker.exe compose -f C:\devel\sip-bot\tools\freeswitch_workshop\docker-compose.yml up -d --wait --wait-timeout 60 --force-recreate
docker.exe exec sip-bot-freeswitch-workshop fs_cli -x status
```

В Ubuntu выполнить полный сценарий. Указать новый пустой output root:

```bash
cd /mnt/c/devel/sip-bot
export LD_LIBRARY_PATH=/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/ctranslate2.libs:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cublas/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cudnn/lib:/home/sipbot/.local/c2-faster-whisper-1.2.1t/lib/python3.14t/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}
export PYTHONNOUSERSITE=1

/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python \
  tools/knowledge/registered_rag_workshop_rehearsal.py \
  --fixture-source artifacts/user-runs/rag-onboarding-01/input-scenario.wav \
  --output-root artifacts/user-runs/rag-onboarding-live-01 \
  --timeout-s 300
```

Runner запускает общий prewarm до вызова. Если вызов приходит до READY, бот отвечает `180`, ждёт ту же single-flight
операцию и отправляет `200` только после успешной загрузки index, warm query, LLM, ASR и TTS. Per-call warmup не
создаётся.

## 8. Проверка результата

В `artifacts/user-runs/rag-onboarding-live-01/` проверить:

- `rag-workshop-full-live.json`: общий `status=pass`, все `rag_workshop.checks=true`;
- `reports/call-in-0/report.md`: positive и follow-up используют `company-pricing-and-terms`, нет `wiki-*`, science-вопрос
  insufficient, а ответ явно сообщает о недостатке знаний и предлагает оператора;
- `context/call-in-0/conversation.jsonl`: пять пользовательских ходов и ответы;
- `recordings/conversation-stereo.wav`: слева пользователь, справа бот;
- `recordings/raw/*-enc.wav`, `*-dec.wav` и `recording-manifest.json`;
- RTP continuity, barge-in, transfer и registration checks в JSON.

Нельзя принимать run только по субъективному прослушиванию: machine-readable typed/event checks и итоговый report
обязательны. После проверки контейнер можно остановить:

```powershell
docker.exe compose -f C:\devel\sip-bot\tools\freeswitch_workshop\docker-compose.yml down --remove-orphans
```

## 9. Типовые ошибки

| Симптом | Действие |
|---|---|
| Validator показывает path/encoding/schema error | Исправить corpus; не пропускать документ молча |
| Build не видит Ollama | Запустить один `ollama serve`, проверить `/api/version` |
| Index model/dimension/hash mismatch | Пересобрать штатной CLI-командой; не отключать проверку |
| Evaluation меньше `12/12` | Сохранить raw report, классифицировать retrieval gap; не удалять неудобный case |
| В report появились `wiki-*` | Остановить приёмку: активирован старый или смешанный index |
| Science-вопрос получил подтверждённый ответ | Остановить приёмку: нарушен insufficient/offer-transfer path |
| Output root не пуст | Выбрать новый каталог, исторические evidence не перезаписывать |
| 100% disk на cold start | Дождаться подготовки до звонка, не удалять model cache между runs |
| GPU OOM/занята | Освободить GPU и повторить; не включать скрытый CPU fallback |

## 10. Что масштабировать после MVP

При росте корпуса линейный JSON index заменяется отдельной vector DB только по измеренному gap. Импорт PDF/DOCX,
OCR, incremental indexing, ACL, multi-tenant corpus и hot activation требуют отдельных контрактов и evaluation; они
не являются скрытыми возможностями этого мастер-класса.
