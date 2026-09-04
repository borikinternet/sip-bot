# 005-C closeout

Дата: `2026-09-04`  
Статус: `complete`

`005-C` полностью исполнен. Source-aware AI path и source-selection playback boundary проверены без добавления
нового delivery owner, без обхода Dispatcher для control plane и без изменения protected model/runtime baseline.

Подтверждено:

- `6 passed` target deterministic tests для typed source modes, bounded TTS output, pacing, stale generation и
  barge-in cancellation;
- real positive/negative RAG на согласованном natural-science corpus; negative prompt допускает только
  `offer_transfer`;
- real Qwen3.5-9B Q4_K_M через Ollama `0.33.1`, structured `answer`, target no-GIL runtime;
- pre-call warmup для embeddings, LLM и XTTS; один sequential GPU gate, fallback не запускался;
- real XTTS output: 11 chunks, `155308` PCM bytes, `8 kHz/mono/S16LE`, WAV доступен для прослушивания:
  [`tts-answer-sample.wav`](target-20260904-r1/tts-answer-sample.wav);
- полный target regression: `147 passed, 2 skipped`.
- clean live-path after source-mode correction: `6/6` scenarios pass; negotiated PCMU/8000/mono RTP, no callback,
  dropped or stale errors; `egress_underruns=0`, `tts_startup_wait=132`, `intentional_silence_frames=4629`;

Latency observation retained honestly: final phrase → first useful LLM output `488.600 ms`, final phrase → first PCM
`1785.090 ms`. Поэтому evidence доказывает работоспособность и разложение задержки, но не выдаёт этот run за достижение
общей end-to-end цели `200–500 ms`. Наблюдение передано в `005-D` для clean rehearsal/report и последующей оценки
оптимизации prompt/model path.

Ограничение cancellation: XTTS подтверждает generator close, но не предоставляет независимый native cancellation token;
это не blocker для согласованного MVP process boundary и явно отражено в evidence.

Evidence: [`commands.md`](commands.md), [`map005-c-ai-gate.json`](target-20260904-r1/map005-c-ai-gate.json),
[`tts-answer-sample.wav`](target-20260904-r1/tts-answer-sample.wav),
[`j4-full-live.json`](target-live-20260904-r1/j4-full-live.json),
[`plan-005-C`](../../../../docs/plans/plan-005-C-ai-quality-latency-resources.md).
