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
SIP_BIND_PORT: Final[int] = 5060
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
KNOWLEDGE_CORPUS_PATH: Final[Path] = Path("data/knowledge/corpus")
KNOWLEDGE_INDEX_PATH: Final[Path] = Path("data/knowledge/index")
CONVERSATION_ROOT: Final[Path] = Path("data/dialogues")

# Speech and bounded-channel policies used by later boundary plans.
VAD_SPEECH_THRESHOLD: Final[float] = 0.5
ENDPOINT_SOFT_MS: Final[int] = 300
ENDPOINT_HARD_MS: Final[int] = 500
MIN_SPEECH_MS: Final[int] = 80
INTERNAL_PCM_FRAME_SIZE_SAMPLES: Final[int] = 160
ASR_CHUNK_MS: Final[int] = 1000
ASR_CHUNK_FLUSH_MS: Final[int] = 1000
AUDIO_INPUT_BUFFER_CAPACITY_FRAMES: Final[int] = 50
AUDIO_OUTPUT_BUFFER_CAPACITY_FRAMES: Final[int] = 50
CONTROL_EVENT_BUFFER_CAPACITY: Final[int] = 256
TTS_OUTPUT_TAIL_MS: Final[int] = 0

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
PROMPT_TEMPLATE_ID: Final[str] = "mvp-answer-ru"
PROMPT_TEMPLATE_VERSION: Final[str] = "2"
GENERATION_PROFILE_ID: Final[str] = "mvp-short-answer"
GENERATION_PROFILE_VERSION: Final[str] = "2"
OUTPUT_SCHEMA_ID: Final[str] = "structured-dialogue-decision-v1"
MAX_ANSWER_CHARS: Final[int] = 1000
USER_TEXT_DELIMITER: Final[str] = "<user_text>"

# Retrieval contract identifiers and limits.
RAG_CORPUS_VERSION: Final[str] = "ru-natural-science-demo-v1"
RAG_EMBEDDING_MODEL: Final[str] = "embeddinggemma"
RAG_TOP_K: Final[int] = 3
RAG_RELEVANCE_THRESHOLD: Final[float] = 0.35
RAG_MAX_CONTEXT_CHARS: Final[int] = 6000
RAG_UNKNOWN_ANSWER_POLICY: Final[str] = "offer-transfer"
TRANSCRIPT_STABLE_PREFIX_MIN_CHARS: Final[int] = 12
QUERY_POLICY_VERSION: Final[str] = "ru-natural-science-v1"
QUERY_MAX_CONTEXT_CHARS: Final[int] = 1800
QUERY_MAX_PHRASE_TOKENS: Final[int] = 4
RAG_INDEX_VERSION: Final[str] = "ollama-embeddinggemma-2026-09-03"
RAG_EMBEDDING_OPERATION: Final[str] = "typed-llm-facade-embed"
RAG_CONTEXT_ID_PREFIX: Final[str] = "knowledge-context"

# Observability and latency targets.
RTP_MEDIA_BUDGET_MS: Final[int] = 30
LATENCY_TARGET_MIN_MS: Final[int] = 200
LATENCY_TARGET_MAX_MS: Final[int] = 500
LOG_LEVEL: Final[str] = "INFO"
LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S%z"
