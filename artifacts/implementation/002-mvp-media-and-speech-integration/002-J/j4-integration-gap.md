# J4 integration gap: live SIP-to-AI wiring

Дата аудита: 2026-09-03  
Статус исторического аудита: `resolved`. Первоначальный runtime-wiring gap закрыт по `live-gate-20260903-r4`, а
полная J4 scenario matrix закрыта единым clean-start прогоном
[`j4-full-live-20260904-r20`](j4-full-live-20260904-r20/j4-full-live.json); `B-002-J-004` resolved.

Этот файл фиксирует gap, обнаруженный до исполнения successor plan `002-I.1`. Он сохранён как traceability evidence;
его conclusion о первоначально отсутствовавшем runtime driver superseded свежим live gate.

## Наблюдение

J4 clean-start runner завершился с exit code `0` по всем трём своим lane:

- target regression: `112 passed`, включая live SIP/RTP component checks;
- real answer composition: RAG → LLM → XTTS → report;
- real media/transfer composition: faster-whisper → VAD/endpointing →
  `FinalUserTurn` → RAG → LLM → XTTS → fake operator → report.

Это было историческое наблюдение до materialization runtime wiring. Оно проверяло component boundaries и composition
contracts, но не доказывало одного живого Baresip-вызова, в котором RTP из `SipMediaAdapter` проходит через
ASR/LLM/TTS и сгенерированный звук возвращается в тот же SIP/RTP media path. Этот пробел закрыт свежим r20 ниже.

## Resolution

Главный executor выполнил clean-start full live gate после pre-call warmup. Один Baresip SIP/RTP вызов прошёл через
`PcmFrame → PcmFanOut → VAD/endpointing → Streaming ASR → FinalUserTurn → RAG/Skill & Prompt/LLM Facade →
XTTS/TtsOutputBuffer/MediaPacer/PlaybackChannel → SipMediaAdapter` и локальный fake-operator transfer.
Все шесть обязательных scenario checks имеют значение `true`, `errors=[]`, `stale_hypotheses=0`,
`asr_chunks_dropped=0`, `callback_errors=0`, target runtime — CPython `3.14.7t`, `gil_enabled=false`.

Три корректирующие boundary-проблемы были исправлены и проверены тестами/evidence: late ASR hard-end commit и
speech-only input без hallucinated silence, benign `ё/е` revision, а также сохранение FSM confirmation state до
authoritative `FinalUserTurn`. Дополнительно лимит structured LLM generation поднят до 192 токенов после evidence
обрезания ответа на прежнем лимите 96.

В промежуточном r19 (сохранённом отдельно) full gate остановился на ошибке реализации Transcript Assembler: без
явного `stable_prefix` он фиксировал общий префикс последовательных гипотез и отвергал последующую корректировку.
После corrective pass продвижение stable prefix разрешено только по backend-provided полю; targeted и полный target
regression прошли, затем r20 повторил live acceptance.

## Evidence-backed gap

Статический audit исходного дерева показывает:

- `SipMediaAdapter` предоставляет `next_ingress_frame()` и
  `enqueue_egress_frame()`, но ни один production/demo runtime не связывает
  эти методы с `ConversationPipeline`;
- `ConversationPipeline` принимает уже готовый authoritative `FinalUserTurn`
  и имеет абстрактный `audio_sink`, но не владеет SIP polling, speech-session
  creation, per-turn `TranscriptAssembler`, ASR chunk draining или playback
  pacing;
- текущие real probes подают synthetic/offline fixture frames или готовый
  `FinalUserTurn`, а TTS сохраняют в WAV через диагностический sink. Они не
  используют `TtsOutputBuffer → MediaPacer → PlaybackChannel →
  SipMediaAdapter.enqueue_egress_frame()`;
- при этом J4 plan требует full PCMU SIP flow, а `requirements.md` требует
  для MVP позвонить на SIP-бота, задать голосовой вопрос и получить голосовой
  ответ.

Следовательно, J4 component/composition evidence принят как проверенный
поднабор, но acceptance полного live SIP-driven demo не выполнен. Это не
ошибка тестового assertion и не разрешается изменением порогов или заменой
SIP входа fixture-ом.

## Исторический blocker

На момент аудита `B-002-J-006` — category 4 по APG 6.1: в application runtime не выполнено
wiring существующих typed input-методов live SIP/media, speech/AI и playback.
Это не отсутствие нового semantic owner и не разрешение создавать отдельный
delivery-компонент. Вызов input-метода получателя является materialization
in-process edge; execution loop и его queue bridges являются процедурной частью
application runtime.

Блокируется:

- полное J4 acceptance;
- J5 closeout;
- закрытие Map-002 и объявление MVP рабочим SIP-демонстратором.

## Требуемое owner decision

Для исправления подготовлен отдельный узкий successor child plan
[`plan-002-I.1-live-call-asyncio-wiring.md`](../../../docs/plans/plan-002-I.1-live-call-asyncio-wiring.md), который
сначала фиксирует exact input methods и asyncio/thread boundaries, а затем
реализует и проверяет:

1. основной `asyncio` loop с Dispatcher и control bus как его задачами;
2. SIP event/media polling без ожидания AI;
3. вызов существующих speech input methods, ASR chunk drain и создание нового
   transcript scope для каждого хода;
4. direct `FinalUserTurn` → `ConversationPipeline`;
5. approved TTS output buffering/pacing и direct SIP egress;
6. cancellation/barge-in/terminal/transfer propagation;
7. один fresh live Baresip scenario с сохранённым report и без audio recording.

Межпоточный обмен ограничивается bounded thread-safe queues; `asyncio.Queue`
используется только внутри основного event loop. До начала и в ходе исполнения
этого plan не вводились новые semantic components, новый bus, новый IPC или
fallback. Owner review `002-I.1` принят `2026-09-03`; его execution и J4
acceptance закрыты r20.
