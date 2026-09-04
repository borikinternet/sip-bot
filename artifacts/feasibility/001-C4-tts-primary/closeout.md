# 001-C4 TTS primary — GPU execution closeout

Дата: `2026-08-27`

Статус исполнения child plan: `complete`  
Candidate decision: `pass`

## Итог

`pass для проверенного main-process MVP пути; owner review production-интеграции не подразумевается`.

Единственный frozen primary — XTTS-v2 v2.0.3 на revision
`6b8036b35d787cf43d18d640587956b9db8fd1b8`. Полные веса скачаны и проверены по SHA-256. Реальный русский
GPU operation выполнен в `CPython 3.14.7t` с отключённым GIL; WAV-результат сохранён для ручного прослушивания.
Fallback-кандидат не выбирался и не запускался.

## Выполнено

- Установлены и проверены `coqui-tts==0.27.5`, `torch==2.10.0+cu128`, `torchaudio==2.10.0+cu128`,
  `tokenizers==0.22.2`, `transformers==4.57.5`, `librosa==0.11.0`, `soundfile==0.14.0`.
- `torchaudio`, `tokenizers` и `monotonic_alignment_search` пересобраны с узкими no-GIL patch-ами:
  `torchaudio-free-threading.patch`, `tokenizers-free-threading.patch` и
  `monotonic-alignment-search-free-threading.patch`. SHA-256 patch-файлов и бинарей сохранены в текущем
  evidence root/командах.
- Необязательный Triton отключён в disposable runtime: XTTS operation его не требует, а его `libtriton`
  включал GIL при широком импорте `TTS`.
- Прямой `torchcodec` не включён в operation path: его бинарь ожидал `libnvrtc.so.13`; reference voice
  загружается через `soundfile`, а resampling выполняется patched `torchaudio.functional.resample`.
- Clean-process import gate прошёл для всех модулей tested path; после каждого импорта GIL оставался `False`.
- Model load и operation прошли на CUDA; GIL оставался `False` после model load, первого PCM-фрагмента и
  завершения operation.

## Operation evidence

- Input: `Вода кипит при ста градусах Цельсия.`
- Model load: `8.138 s`.
- XTTS streaming: 4 непустых PCM-фрагмента, первый через `1308.4 ms` от получения конечной фразы,
  полный результат через `1776.8 ms`.
- Первый fragment: `float32`, mono, 24 kHz, 21 248 samples.
- Прослушиваемый результат того же operation:
  `tts-sample.wav`, WAV/PCM16, mono, 24 kHz, 70 144 samples, `140332` bytes,
  длительность `2922.7 ms`, SHA-256
  `42eb21016a4ab147738c06b69c43d67752856008a2985a0feadc6ccf1f7920bd`.
- PCMU boundary: PCM16 mono 24 kHz → resample 8 kHz → PCMU/G.711 mu-law, непустой результат `23382` bytes.

Источники фактов: `import.json`, `operation.json`, `pcmu-boundary.json`, `cancellation.json` и сохранённые
stdout/stderr records.

## Cancellation limitation

`XTTS-v2 inference_stream` не предоставляет отдельного native cancellation token. Проверена candidate-owned
граница `generator.close()` после первого PCM-фрагмента: close наблюдается, после close элементов нет,
stale PCM не принимается, GIL не включается. Это подтверждает MVP-семантику «отобрать трубу», но не обещает
немедленное прерывание уже выполняющегося native CUDA kernel. Hard native cancellation не заявляется.

## Blockers

| ID | Статус | Evidence/решение |
|---|---|---|
| `B-C4-003` | resolved for tested path | exact no-GIL patches + import/model/operation checkpoints; unpatched binaries недопустимы |
| `B-C4-004` | resolved | `pcmu-boundary.json` подтверждает PCMU 8 kHz mono boundary |
| `B-C4-005` | resolved with explicit limitation | generator close и stale suppression проходят; native cancel token отсутствует |
| `B-C4-006` | resolved | candidate output и boundary conversion зафиксированы, без скрытого внешнего API |
| `B-C4-007` | resolved | exact model weights присутствуют, hashes совпадают, operation выполнен |
| `B-C4-008` | none triggered | нет внешнего API, записи разговора или fallback |

## Ограничения closeout

Этот closeout закрывает только feasibility boundary `001-C4`. Он не доказывает production-поток, субъективное
качество голоса, одновременную работу всех AI-контуров, полный SIP/RTP call, barge-in через реальный RTP,
перевод звонка или full end-to-end latency. WAV — синтетический образец ответа, не запись разговора.

Следующий узкий шаг: перенести подтверждённые candidate/runtime invariants в implementation plan `001-D` и
сохранить no-GIL patches как обязательную часть C4 runtime setup; не использовать unpatched wheels и не
возвращать Triton/torchcodec в tested import path без отдельного evidence.
