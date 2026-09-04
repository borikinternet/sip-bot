# 005-B closeout

Дата: `2026-09-04`  
Статус: `complete`

`005-B` полностью исполнен. Speech/audio acceptance закрыт без изменения protected baseline, typed contracts,
approved ASR candidate или runtime boundary.

Подтверждено:

- `9 passed` deterministic unit/integration matrix на target no-GIL runtime;
- PCMU-derived application path: 253 negotiated 20-ms frames, codec boundary, `PcmFrame`, bounded chunking,
  faster-whisper backend и один authoritative `FinalUserTurn`;
- 300-ms soft и 500-ms hard endpoint, partial revisions, cancellation/stale suppression;
- faster-whisper streaming и generator-close cancellation probes — pass, GIL не включался;
- полный target regression: `141 passed, 2 skipped`.

В процессе были две исправленные проблемы запуска evidence: неполный CUDA library path (category 3) и два дефекта
нового test runner-а (category 2). После corrective retry все обязательные проверки зелёные; product source defect,
architectural gap и fallback не обнаружены.

Важное ограничение: fixture smoke не является live SIP/RTP quality claim; live protocol/media claim закрыт `005-A`.
faster-whisper предоставляет generator close, но не отдельный native cancellation token.

Evidence: [`commands.md`](commands.md), [`target-20260904-r2`](target-20260904-r2/),
[`target-20260904-r4`](target-20260904-r4/), [`plan-005-B`](../../../../docs/plans/plan-005-B-speech-audio-resilience.md).
