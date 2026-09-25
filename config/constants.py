"""MVP configuration constants.

This module is the single configuration source for the application runtime.
Values are intentionally static: changing a value takes effect after restart.
No environment variables, implicit defaults, or external configuration stores
are consulted by the application.
"""

from pathlib import Path
from typing import Final


APPLICATION_NAME: Final[str] = "sip-bot"
APPLICATION_VERSION: Final[str] = "0.1.0"

# Runtime baseline.  The exact installed patch release is captured by the
# runtime probe; the application process must still be free-threaded.
PYTHON_MIN_VERSION: Final[tuple[int, int]] = (3, 14)
PYTHON_RUNTIME_LABEL: Final[str] = "CPython >= 3.14 free-threaded"
REQUIRE_FREE_THREADED: Final[bool] = True
MAX_CONCURRENT_CALLS: Final[int] = 1

# Signalling/media values that are stable at the MVP boundary.  Per-call
# ptime, payload type, and frame size are negotiated by the SIP/media plan.
SIP_BIND_HOST: Final[str] = "127.0.0.1"
SIP_BIND_PORT: Final[int] = 5070
SIP_TRANSPORT: Final[str] = "udp"
RTP_BIND_HOST: Final[str] = "127.0.0.1"
RTP_PORT_START: Final[int] = 40000
RTP_PORT_END: Final[int] = 40100
SIP_CODEC: Final[str] = "PCMU"
SIP_SAMPLE_RATE_HZ: Final[int] = 8000
SIP_CHANNELS: Final[int] = 1
OPERATOR_TARGET: Final[str] = "sip:operator@127.0.0.1:5090"
MEDIA_PROFILE_SOURCE: Final[str] = "per-call-sdp-pjmedia"
MEDIA_PTIME_POLICY: Final[str] = "negotiated-per-call"
PCM_SAMPLE_FORMAT: Final[str] = "S16LE"
PCM_FRAME_SIZE_POLICY: Final[str] = "negotiated-per-call"

# Optional local-registrar profile for the workshop.  The feature is
# deliberately disabled in the default demo path, while the public password
# is kept in the committed sample configuration so the workshop is
# reproducible.  This is not a production credential or a secret-store policy.
SIP_REGISTRATION_ENABLED: Final[bool] = True
SIP_REGISTRAR_URI: Final[str] = "sip:172.16.15.72:15062"
SIP_REGISTRATION_IDENTITY_URI: Final[str] = "sip:1002@192.168.1.74"
SIP_REGISTRATION_USERNAME: Final[str] = "1002"
SIP_REGISTRATION_PASSWORD: Final[str] = "Workshop-2026!"
SIP_REGISTRATION_EXPIRES_SECONDS: Final[int] = 300

# Local model/runtime locations.  This foundation records the owners of these
# settings but does not import or initialize any model runtime.
ASR_MODEL_PATH: Final[Path] = Path("models/asr")
LLM_MODEL_PATH: Final[Path] = Path("models/llm")
TTS_MODEL_PATH: Final[Path] = Path("models/tts")
ASR_DEVICE: Final[str] = "cuda:0"
LLM_DEVICE: Final[str] = "cuda:0"
TTS_DEVICE: Final[str] = "cuda:0"
GPU_NAME: Final[str] = "NVIDIA RTX 5060 Ti"
GPU_VRAM_GB: Final[int] = 16

# Runtime persistence and retrieval locations.
KNOWLEDGE_CORPUS_PATH: Final[Path] = Path("data/knowledge/telecom-corpus")
KNOWLEDGE_INDEX_PATH: Final[Path] = Path("data/knowledge/index/telecom-voice-assistants-v1.json")
CONVERSATION_ROOT: Final[Path] = Path("data/dialogues")

# Speech and bounded-channel policies used by later boundary plans.
# WebRTC VAD aggressiveness mode: 0 is least aggressive, 3 most aggressive.
# Endpointing remains owned by TurnDetector and is configured independently.
VAD_MODE: Final[int] = 2
VAD_SPEECH_THRESHOLD: Final[float] = 0.5
# WebRTC VAD exposes only a boolean through the Python binding.  The live
# processor confirms positive decisions against a per-call adaptive RMS gate
# so low-level codec noise and acoustic return do not become user turns.
VAD_ENERGY_GATE_ENABLED: Final[bool] = True
VAD_ENERGY_MIN_DBFS: Final[float] = -42.0
VAD_ENERGY_NOISE_MARGIN_DB: Final[float] = 10.0
VAD_ENERGY_INITIAL_NOISE_FLOOR_DBFS: Final[float] = -60.0
VAD_ENERGY_HISTORY_MS: Final[int] = 10_000
VAD_ENERGY_BOOTSTRAP_MS: Final[int] = 500
VAD_ENERGY_NOISE_PERCENTILE: Final[float] = 0.20
VAD_ENERGY_MAX_NOISE_RISE_DB_PER_S: Final[float] = 5.0
VAD_ENERGY_NOISE_FALL_ALPHA: Final[float] = 0.20
VAD_ENERGY_SPEECH_LEVEL_ALPHA: Final[float] = 0.20
VAD_ENERGY_CONFIRMATION_MS: Final[int] = 80
# A per-call near-end reference is established only by a clearly energetic
# frame.  Before that point the ordinary VAD may still accept quieter speech,
# while barge-in uses its stricter explicit bootstrap floor.
VAD_ENERGY_NEAR_END_BOOTSTRAP_DBFS: Final[float] = -26.0
VAD_ENERGY_NEAR_END_CONFIRMATION_MS: Final[int] = 200
VAD_ENERGY_NEAR_END_PERCENTILE: Final[float] = 0.70
VAD_ENERGY_NEAR_END_MARGIN_DB: Final[float] = 12.0
VAD_ENERGY_BARGE_IN_MARGIN_DB: Final[float] = 8.0
VAD_ENERGY_BARGE_IN_MINIMUM_DBFS: Final[float] = -26.0
ENDPOINT_SOFT_MS: Final[int] = 300
# The authoritative endpoint must stay inside the owner's 300-400 ms budget.
# 360 ms leaves two 20-ms telephone frames of scheduling/quantization margin.
# It supersedes the historical 520-ms Map-008 policy, which preserved one
# synthetic 480-ms intra-turn pause at the cost of unacceptable live latency.
ENDPOINT_HARD_MS: Final[int] = 360
MIN_SPEECH_MS: Final[int] = 80
INTERNAL_PCM_FRAME_SIZE_SAMPLES: Final[int] = 160
ASR_CHUNK_MS: Final[int] = 1000
ASR_CHUNK_FLUSH_MS: Final[int] = 1000
# Production faster-whisper hypotheses carry model speech evidence.  A final
# hypothesis at or above this no-speech probability closes its turn without
# creating authoritative user text. Segment timeline tolerance is diagnostic.
ASR_NO_SPEECH_THRESHOLD: Final[float] = 0.60
ASR_SEGMENT_END_TOLERANCE_MS: Final[float] = 500.0
AUDIO_INPUT_BUFFER_CAPACITY_FRAMES: Final[int] = 50
AUDIO_OUTPUT_BUFFER_CAPACITY_FRAMES: Final[int] = 50
CONTROL_EVENT_BUFFER_CAPACITY: Final[int] = 256
TTS_OUTPUT_TAIL_MS: Final[int] = 0
# XTTS emits its first waveform only after this many autoregressive acoustic
# tokens have been accumulated.  Plan-018 selected 5 over the original 20 on
# a 30-run multi-phrase target sweep: materially lower TTFA, zero simulated
# producer underruns and full-generation RTF below 0.55.
TTS_STREAM_CHUNK_SIZE: Final[int] = 5
TTS_STREAM_OVERLAP_WAV_LEN: Final[int] = 1024
# Application media stays on the negotiated PCMU clock while no TTS payload is
# available.  The level is a tunable MVP engineering value in dBov magnitude;
# it is not an absolute standards default.
SIP_MEDIA_NO_VAD: Final[bool] = True
COMFORT_NOISE_LEVEL_DBOV_MAGNITUDE: Final[int] = 50

# Local Ollama IPC settings.  The runtime skeleton does not connect to it.
LLM_HTTP_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
LLM_CHAT_MODEL: Final[str] = "c3-qwen35-9b-q4km:latest"
LLM_EMBEDDING_MODEL: Final[str] = "embeddinggemma"
LLM_CONNECT_TIMEOUT_S: Final[float] = 1.0
LLM_READ_TIMEOUT_S: Final[float] = 30.0
LLM_MAX_REQUEST_CHARS: Final[int] = 12000
LLM_MAX_RESPONSE_CHARS: Final[int] = 4000
LLM_CANCELLATION_MODE: Final[str] = "close-request-stream"
LLM_THINKING_ENABLED: Final[bool] = False
LLM_TEMPERATURE: Final[float] = 0.1
LLM_MAX_GENERATION_TOKENS: Final[int] = 192

# Prompt/skill contract identifiers.  They are data for later plans, not an
# implementation of prompt composition.
DEFAULT_SKILL_ID: Final[str] = "answer-ru"
DEFAULT_SKILL_VERSION: Final[str] = "2"
DEFAULT_SKILL_INSTRUCTION: Final[str] = (
    "Отвечай коротко. Отвечай только на основании найденных источников."
)
PROMPT_TEMPLATE_ID: Final[str] = "mvp-answer-ru"
PROMPT_TEMPLATE_VERSION: Final[str] = "3"
PROMPT_TEMPLATE_TEXT: Final[str] = (
    "Отвечай только валидным JSON без Markdown и рассуждений. "
    "Допустимые action: answer, clarify, offer_transfer. Для action=answer "
    "дай не более двух коротких предложений в поле text.\n"
    "{instruction}\nКонтекст:\n{context}\nЗнания:\n{knowledge}\n"
    "Вопрос пользователя:\n{user_text}"
)
GENERATION_PROFILE_ID: Final[str] = "mvp-short-answer"
GENERATION_PROFILE_VERSION: Final[str] = "3"
OUTPUT_SCHEMA_ID: Final[str] = "structured-dialogue-decision-v1"
MAX_ANSWER_CHARS: Final[int] = 1000
USER_TEXT_DELIMITER: Final[str] = "<user_text>"

# A static first replica is synthesized through the normal TTS/playback path.
# It never invokes retrieval or LLM and remains interruptible by barge-in.
CALL_GREETING_TEXT: Final[str] = "Алло."
# Static re-confirmation after a compound positive turn. It uses the normal
# TTS/playback path but never invokes answer LLM or retrieval.
TRANSFER_CONFIRMATION_TEXT: Final[str] = "Подключить оператора?"

# Retrieval contract identifiers and limits.
RAG_CORPUS_VERSION: Final[str] = "ru-telecom-voice-assistants-demo-v1"
RAG_EMBEDDING_MODEL: Final[str] = "embeddinggemma"
RAG_TOP_K: Final[int] = 3
RAG_RELEVANCE_THRESHOLD: Final[float] = 0.35
RAG_MAX_CONTEXT_CHARS: Final[int] = 6000
RAG_UNKNOWN_ANSWER_POLICY: Final[str] = "offer-transfer"
TRANSCRIPT_STABLE_PREFIX_MIN_CHARS: Final[int] = 12
QUERY_POLICY_VERSION: Final[str] = "ru-technical-acronyms-v3"
QUERY_MAX_CONTEXT_CHARS: Final[int] = 1800
QUERY_MAX_PHRASE_TOKENS: Final[int] = 4
RAG_INDEX_SCHEMA_VERSION: Final[str] = "rag-index-v1"
RAG_INDEX_VERSION: Final[str] = "telecom-voice-assistants-embeddinggemma-v1"
RAG_CHUNKING_POLICY_VERSION: Final[str] = "markdown-semantic-v1"
RAG_CORPUS_SHA256: Final[str] = "9064796f84c103c31942e41ee6a08180aa3bd57c388cce3ba2971ca5e5abb111"
RAG_INDEX_DIMENSION: Final[int] = 768
RAG_EMBEDDING_OPERATION: Final[str] = "typed-llm-facade-embed"
RAG_CONTEXT_ID_PREFIX: Final[str] = "knowledge-context"

# Observability and latency targets.
RTP_MEDIA_BUDGET_MS: Final[int] = 30
LATENCY_TARGET_MIN_MS: Final[int] = 200
LATENCY_TARGET_MAX_MS: Final[int] = 500
LOG_LEVEL: Final[str] = "INFO"
LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S%z"
