# C3 backend A/B check: Ollama vs direct llama.cpp

Дата: `2026-08-27`

## Цель

Проверить утверждение, что прямой запуск llama.cpp существенно быстрее Ollama, на той же машине и с тем же
квантизованным GGUF. Основной C3 baseline не заменяется этим экспериментом автоматически.

## Общие условия

- GPU: NVIDIA GeForce RTX 5060 Ti, 16 311 MiB;
- модель: `Qwen3.5-9B-Q4_K_M.gguf`;
- SHA-256: `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`;
- context: `8192`;
- один слот/параллельный запрос;
- temperature `0.2`, top-p `0.95`, top-k `20`;
- reasoning выключен;
- один и тот же русский вопрос: `Почему небо днём кажется голубым?`;
- structured JSON-контракт `action=answer`, непустой `text`;
- fallback не использовался.

## Direct upstream llama.cpp

Использован официальный контейнер:

```text
ghcr.io/ggml-org/llama.cpp:server-cuda13-b10524
image digest: sha256:c0d2e9b796d5b75213146db37e620a7bbfae23ceeafd0d4bb418224b5954e2ee
build: 10524, commit 9ee9fc04c
```

Основные параметры запуска:

```text
-m /models/Qwen3.5-9B-Q4_K_M.gguf -ngl 999 -c 8192 -np 1
--reasoning off --flash-attn auto
```

Runner подтвердил:

- `33/33` слоёв выгружены на GPU;
- CUDA model buffer: `4861.28 MiB`;
- CPU-mapped model buffer: `545.62 MiB`;
- KV cache: `256 MiB`;
- RTX 5060 Ti распознана как CUDA0.

### Результат

При `--flash-attn auto`:

- first useful stream chunk: `195.425 ms`;
- полный streaming response: `2025.267 ms`;
- non-stream response: `1776.731 ms`;
- generation: `97` токенов за `1542.741 ms`, то есть `62.227 tok/s`.

При `--flash-attn off` выполнены три тёплых запроса:

| Run | Generation tokens/s | Generation time | Wall time |
|---:|---:|---:|---:|
| 1 | 61.751 | 1732.778 ms | 2093.143 ms |
| 2 | 63.520 | 1401.141 ms | 1929.754 ms |
| 3 | 62.483 | 1728.478 ms | 2247.332 ms |

Среднее generation throughput: `62.585 tok/s`. Существенной разницы с `flash-attn auto` не обнаружено.
Ответы были валидным JSON с `finish_reason=stop`.

## Ollama baseline

Использован:

```text
Ollama 0.33.1
```

По собственному логу Ollama запустила внутренний `llama-server` на базе llama.cpp:

```text
build 1, commit d222767c7
--flash-attn auto -b 1024 -ub 1024 --context-shift --keep 4
```

Внутренний runner также подтвердил:

- `33/33` слоёв выгружены на GPU;
- CUDA model buffer: `4861.28 MiB`;
- CPU-mapped model buffer: `545.62 MiB`;
- KV cache: `256 MiB`;
- один слот, context `8192`, `n_threads=6`.

### Результат

Повтор C3 probe с тем же `/api/chat`, `think=false` и JSON schema:

- first useful output: `176.710 ms`;
- first valid structured response: `2082.608 ms`;
- статус: `gpu_inference_completed`.

Три тёплых non-stream запроса через Ollama API:

| Run | Generation tokens/s | Generation time | Wall time |
|---:|---:|---:|---:|
| 1 | 62.600 | 1549.515 ms | 8688.408 ms |
| 2 | 63.841 | 1817.009 ms | 1989.523 ms |
| 3 | 61.924 | 1647.174 ms | 1786.276 ms |

В первом запросе `load_duration` составил `6797 ms`; следующие запросы использовали уже загруженную модель.
Средняя скорость generation для двух полностью тёплых запросов: `62.883 tok/s`.

## Вывод

На этой конфигурации утверждение о существенном преимуществе прямого llama.cpp не подтвердилось:

- direct llama.cpp: примерно `62.2–62.6 tok/s`;
- Ollama: примерно `61.9–63.8 tok/s`;
- оба runner-а выгрузили `33/33` слоя на RTX 5060 Ti;
- память model buffer и KV cache практически одинаковы;
- first-useful и full-response latency также находятся в одном диапазоне.

Прямой runner не оказался быстрее в данном A/B-тесте, но имеет преимущество в прозрачности и явном контроле
параметров. Ollama не является здесь CPU-only или явно неоптимизированным путём.

## Ограничения проверки

- Это один короткий prompt и несколько тёплых запусков, не статистический benchmark.
- Direct llama.cpp запускался в CUDA 13 контейнере с моделью на `D:`, Ollama — в WSL runtime с собственным model store;
  поэтому сравнение startup/storage latency не является чистым.
- Direct и Ollama использовали разные сборки llama.cpp и немного разные batch-параметры.
- Проверена генерация, но не полный SIP/RTP pipeline, совместная загрузка ASR/LLM/TTS или реальная cancellation.
- Эксперимент не меняет текущий C3 owner-gated вопрос о допустимости внешнего native-процесса.
