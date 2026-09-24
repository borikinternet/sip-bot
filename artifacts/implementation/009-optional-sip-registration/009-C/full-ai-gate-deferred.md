# 009-C C4 — full-AI gate: deferred

Статус: `deferred`, не pass.

Registered SIP/FreeSWITCH вызов нельзя объявить полноценным AI-gate: входящий
вызов доходит до зарегистрированного PJSUA2 endpoint, но текущий inbound-answer
path завершается нативным PJSIP abort (см. `registered-call-r2.json`). Поэтому
до запуска ASR/LLM/TTS RTP не доходит.

Дополнительно в текущем окружении не было разрешено запускать тяжёлый cold
GPU-inference. `ollama serve` доступен, однако отдельного доказанного warm
ASR+TTS pipeline для этого зарегистрированного вызова нет. Full-AI gate не
запускался и не маскировался stub-результатом.

Promotion condition:

1. исправить blocker `B-009-C-004` в разрешённом для этого исправления плане;
2. повторить регистрацию и входящий вызов;
3. выполнить full AI gate только на заранее прогретых ASR/LLM/TTS;
4. сохранить PCMU/RTP, speech, AI, report и recording evidence без credential.
