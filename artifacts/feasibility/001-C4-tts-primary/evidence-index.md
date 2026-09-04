# 001-C4 TTS primary — evidence index

Состояние на `2026-08-27`: candidate-specific GPU feasibility path выполнен; C4 имеет `pass` для проверенного
disposable main-process runtime. Production-интеграция и full end-to-end не заявляются.

| Evidence ID | Срез | Файл | Статус | Что доказано |
|---|---|---|---|---|
| `E-C4-ENV-001` | preflight | `preflight.md`, `environment.json` | observed | Ubuntu-24.04/WSL2, CPython 3.14.7t, target package baseline |
| `E-C4-SELECT-001` | C4-S0 | `manifest.json`, `asset-manifest.json` | pass | XTTS-v2 v2.0.3 exact revision, complete weights, voice provenance и license |
| `E-C4-PATCH-001` | C4-S1 | `torchaudio-free-threading.patch`, `tokenizers-free-threading.patch`, `monotonic-alignment-search-free-threading.patch`, `patch-build.md` | pass | Три узких no-GIL patch-а, исходники/сборка и хэши exact patched binaries зафиксированы; patched binaries использованы в runtime |
| `E-C4-IMPORT-001` | C4-S1 | `import.json` | pass | Все manifest-listed imports tested path оставляют `GIL=False` |
| `E-C4-PCM-001` | C4-S2 | `operation.json` | pass | XTTS streaming дал 4 PCM fragments; first PCM и timing зафиксированы |
| `E-C4-LATENCY-001` | C4-S2 | `operation.json` | observed | Final phrase → first PCM `1308.4 ms`; final phrase → complete `1776.8 ms` |
| `E-C4-AUDIO-001` | C4-S2 | `tts-sample.wav`, `operation.json` | pass | WAV создан из того же operation, metadata и SHA-256 совпадают |
| `E-C4-PCMU-001` | C4-S3 | `pcmu-boundary.json` | pass | PCM16 mono 24 kHz преобразован в непустой PCMU/G.711 mu-law 8 kHz mono |
| `E-C4-CANCEL-001` | C4-S4 | `cancellation.json` | pass with limitation | generator close после первого fragment; stale output отсутствует; native token отсутствует |
| `E-C4-COMMANDS-001` | all | `commands.md`, `operation.stdout.json`, `operation.stderr.txt`, `pcmu-boundary.stdout.json`, `cancellation.stdout.json` | pass | Команды, stdout/stderr и exit codes сохранены |

## Правило sample

`tts-sample.wav` не является записью разговора. Это полный короткий synthetic ответ из того же успешного
operation, который дал `first_pcm`; sample rate, channels, duration, bytes и SHA-256 записаны в `operation.json`.
Исходный raw `.pcm` и live conversation audio не сохранялись.

## Explicit non-claims

Прямой `torchcodec` не импортируется в tested path из-за несовместимого `libnvrtc.so.13`; Triton отключён как
необязательный backend. Это не fallback-кандидаты и не автоматическое process isolation. Их возврат требует нового
candidate/runtime evidence. Full SIP/RTP, real barge-in, concurrency и MOS остаются вне C4.
