# Plan-013-B: приветствие через существующий FSM/TTS playback

Статус: `complete`  
Родитель: [`Map-013`](plan-013-call-greeting-and-short-prompt.md)

## Цель и write-set

После `CALL_ANSWERED` открыть speech ingress и один раз синтезировать конфигурационное `Алло.` существующим TTS path.
После физического drain перейти в `LISTENING`; barge-in отменяет текущую generation так же, как обычный ответ.

Допустимый write-set: `src/sip_bot/dialogue/actions.py`, `src/sip_bot/dialogue/fsm.py`, `src/sip_bot/runtime.py`,
`src/sip_bot/conversation_pipeline.py`, live runner construction, связанные tests и документы Map-013. SIP adapter,
readiness, media buffer/framer/pacer и TTS model adapter защищены.

## Typed boundary и ownership

```text
SipEvent(CALL_ANSWERED)
  → DialogueFSM: OPEN speech_ingress + PLAY_GREETING control command
  → ConversationPipeline.play configured approved text
  → existing TTS stream → existing audio_sink/TtsOutputBuffer/PJMEDIA
  → PlaybackEvent(PRODUCER_COMPLETED/COMPLETED)
  → DialogueFSM(LISTENING)
```

`PLAY_GREETING` — компактный control command без PCM. Текст принадлежит application config/pipeline, не LLM. Новый
delivery owner, event bus topic или media queue не создаются.

## Срезы и acceptance

1. Добавить typed `PLAY_GREETING` и idempotent per-call greeting transition.
2. Добавить static-text TTS operation в pipeline с session/generation cancellation.
3. Доказать complete → listening, barge-in cancel, no LLM/RAG invocation и single greeting per call.
4. Запустить targeted FSM/pipeline/wiring tests и affected regression lane.

Stop conditions: greeting блокирует SIP callback/main loop, проходит через Dispatcher как PCM, переживает barge-in или
повторно запускается на duplicate `CALL_ANSWERED`. Blocker: `none`, если corrective pass остаётся в write-set.

## Результат

Выполнено 2026-09-22. Добавлен typed `PLAY_GREETING`; FSM открывает speech ingress до воспроизведения, запускает
приветствие один раз на звонок и использует существующий cancel/barge-in contract. Pipeline синтезирует статический
configured text без LLM/RAG и сохраняет его отдельным assistant turn. Registered RAG live gate
`registered-rag-live-20260922-r3` прошёл полностью; в trace присутствуют `call_open → call_greeting → playback_finished`,
в context первая реплика — `Алло.`, RTP/media counters чистые.
