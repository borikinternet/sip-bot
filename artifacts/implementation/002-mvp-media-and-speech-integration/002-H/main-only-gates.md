# 002-H main-only gates

Эти проверки не считаются выполненными deterministic tests и должны быть запущены главным executor
последовательно на целевом runtime с сохранением stdout/stderr, exit code и фактических версий.

## `H-GPU-001`: реальный XTTS-v2

- использовать именно C4 baseline XTTS-v2 v2.0.3, revision `6b8036b35d787cf43d18d640587956b9db8fd1b8`;
- использовать обязательные C4 no-GIL patches для `torchaudio`, `tokenizers`, `monotonic_alignment_search`, не включать
  неподтверждённые Triton/torchcodec paths;
- запускать в `/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/bin/python` или актуальном executable, записанном в evidence;
- проверить import/no-GIL до/после import, model load, first PCM, completion;
- подать approved русский ответ, проверить первый и последующий PCM chunks, отсутствие пустого chunk, operation time и
  нормализацию к активному `NegotiatedMediaProfile`;
- проверить `generator.close()`/candidate cancellation и stale suppression, не заявляя hard native cancellation;
- не перезаписывать C4 artifacts; сохранить H-specific operation/latency/cancellation records в этом каталоге.

Promotion: только после успешного operation и no-GIL evidence H2/H5 могут быть отмечены пройденными.

## `H-RTP-001`: SIP/RTP playback и barge-in

- использовать локальный стенд `001-S`, согласовать SDP и получить фактический per-call `NegotiatedMediaProfile`;
- проверить как минимум один non-20-ms profile или явно доказать, что SDP/fixture использует иной `ptime`, если стенд
  это поддерживает;
- передать paced `PcmFrame` через media layer в PCMU/RTP egress и проверить размер/timestamp/ptime;
- во время TTS generation и во время playback подать новое пользовательское speech event;
- проверить немедленное закрытие старого playback channel, отмену producer, отсутствие stale audio и продолжение
  входящего media/ASR path;
- сохранить RTP counters, PCMU payload checks, ptime, event trace и exit code.

Promotion: только после успешного RTP playback и barge-in; failure классифицируется по APG 6.1 и не обходится
ослаблением deterministic assertions.

## Результат

`B-002-H-003` закрыт после обоих main-only gates. Deterministic boundary evidence, XTTS/GPU и RTP/playback evidence
сведены в H closeout; child plan `002-H` может иметь бинарный статус `complete`.
