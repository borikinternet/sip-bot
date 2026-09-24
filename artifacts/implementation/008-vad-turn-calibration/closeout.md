# Map-008 execution closeout

Статус: `complete`  
Дата: `2026-09-13`

Map-008 полностью исполнена по APG в порядке `008-A → 008-B → 008-C`.

## Принятое техническое решение

- `VAD_MODE=2` выбран сравнением всех modes `0..3` на immutable corpus
  пяти русских фраз одного XTTS-голоса после PCMU conditioning;
- `ENDPOINT_SOFT_MS=300`, `MIN_SPEECH_MS=80` сохранены;
- `ENDPOINT_HARD_MS=520` — минимальная evidence-based настройка, которая
  устраняет split на фактически 480-ms intra-turn pause при 20-ms frame
  clock и сохраняет разделение 620/700-ms межходовых пауз;
- authoritative typed path не менялся: `PcmFrame → VadProcessor →
  VadDecision → TurnDetector → EndpointEvent/FinalUserTurn`;
- новый `VadSmoother`, semantic detector, queue, IPC или production owner
  не добавлялись.

## Child evidence

- [`008-A closeout`](008-A/closeout.md): corpus SHA-256
  `a031570e9954d249851997f33252ccc783dc27f0511cee3bb427a1d32579f5c8`,
  mode sweep pass, target `gil_enabled=false`;
- [`008-B closeout`](008-B/closeout.md): threshold baseline/corrective
  evidence, selected 520 ms, 3/3 authoritative boundaries, deterministic
  replay;
- [`008-C closeout`](008-C/closeout.md): I1 и J4 clean-start live pass,
  negotiated PCMU, downstream ASR/RAG/LLM/TTS, barge-in/transfer/report.

## Финальный audit

Host и target regression pass; source-map подтверждает отсутствие обхода
владельцев и PCM через Dispatcher/Event Bus. Красные результаты были
сохранены и исправлены в разрешённых write-set; category-4 blocker не
возник. Registry/backlog/roadmap/architecture/ТЗ синхронизированы после
изменений.

Ограничение результата: controlled single-voice TTS baseline. Human/noise
generalization и production precision/recall остаются отдельной будущей
работой и не маскируются этим closeout.
