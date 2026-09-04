# Publication checklist

Статус: подготовлен для будущей публикации; release не выполнялся.

| Материал | Требование | Состояние |
|---|---|---|
| Исходный код | Выбрать и добавить project `LICENSE` | `open — решение владельца нужно перед release` |
| Dependencies | Название, версия, source и license каждого используемого пакета | Baseline собран в feasibility closeouts; перед release нужен полный inventory |
| LLM | Ссылка на модель, revision/quantization, backend и license | Qwen3.5-9B Q4_K_M/Ollama зафиксированы; notices проверить |
| ASR | faster-whisper/CTranslate2 patch, model revision и license | Зафиксированы в C2 candidate freeze; включить patch notice |
| TTS | XTTS-v2 license и права на reference voice | Coqui license указана; voice/source проверить отдельно |
| Knowledge base | Wikimedia source, attribution и ShareAlike obligations | Указаны в `docs/knowledge-base.md`; перенести attribution в release materials |
| Weights | Не включать веса в GitHub source tree без отдельного решения | Соблюдается |
| Outputs | Для опубликованных WAV/text/screenshots указывать provenance и applicable license | Требуется при формировании финальных материалов |
| README | Описать demo-only scope, one-call limitation, no production claim и local model setup | Подготовить перед release |
| Conference slides | Ссылаться на source-index и не выдавать latency target за достигнутый | Draft claims готовы |
| Legal status | Финальная проверка не является частью технического Map-006 closeout | Не объявлять release-ready автоматически |

## Основные источники

- [`docs/licensing-policy.md`](../../docs/licensing-policy.md)
- [`docs/knowledge-base.md`](../../docs/knowledge-base.md)
- [`docs/requirements.md`](../../docs/requirements.md)
- [`docs/decisions/ADR-002-llm-model-selection.md`](../../docs/decisions/ADR-002-llm-model-selection.md)
- [`001-C3 closeout`](../feasibility/001-C3-llm-primary/closeout.md)
- [`001-C4 closeout`](../feasibility/001-C4-tts-primary/closeout.md)
