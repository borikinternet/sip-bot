"""Typed access to the static MVP configuration."""

from dataclasses import dataclass
from pathlib import Path

from config import constants


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Immutable application configuration copied from ``config.constants``.

    The explicit mapping is intentional.  It makes the configuration surface
    reviewable and prevents a hidden environment/configuration fallback from
    being introduced by a caller.
    """

    application_name: str
    application_version: str
    python_min_version: tuple[int, int]
    python_runtime_label: str
    require_free_threaded: bool
    max_concurrent_calls: int
    sip_bind_host: str
    sip_bind_port: int
    sip_transport: str
    rtp_bind_host: str
    rtp_port_start: int
    rtp_port_end: int
    sip_codec: str
    sip_sample_rate_hz: int
    sip_channels: int
    operator_target: str
    media_profile_source: str
    media_ptime_policy: str
    pcm_sample_format: str
    pcm_frame_size_policy: str
    asr_model_path: Path
    llm_model_path: Path
    tts_model_path: Path
    asr_device: str
    llm_device: str
    tts_device: str
    gpu_name: str
    gpu_vram_gb: int
    knowledge_corpus_path: Path
    knowledge_index_path: Path
    conversation_root: Path
    vad_speech_threshold: float
    endpoint_soft_ms: int
    endpoint_hard_ms: int
    min_speech_ms: int
    internal_pcm_frame_size_samples: int
    asr_chunk_ms: int
    asr_chunk_flush_ms: int
    audio_input_buffer_capacity_frames: int
    audio_output_buffer_capacity_frames: int
    control_event_buffer_capacity: int
    tts_output_tail_ms: int
    llm_http_endpoint: str
    llm_chat_model: str
    llm_embedding_model: str
    llm_connect_timeout_s: float
    llm_read_timeout_s: float
    llm_max_request_chars: int
    llm_max_response_chars: int
    llm_cancellation_mode: str
    llm_thinking_enabled: bool
    llm_temperature: float
    llm_max_generation_tokens: int
    default_skill_id: str
    prompt_template_id: str
    prompt_template_version: str
    generation_profile_id: str
    generation_profile_version: str
    output_schema_id: str
    max_answer_chars: int
    user_text_delimiter: str
    rag_corpus_version: str
    rag_embedding_model: str
    rag_top_k: int
    rag_relevance_threshold: float
    rag_max_context_chars: int
    rag_unknown_answer_policy: str
    transcript_stable_prefix_min_chars: int
    rtp_media_budget_ms: int
    latency_target_min_ms: int
    latency_target_max_ms: int
    log_level: str
    log_format: str
    log_date_format: str

    @classmethod
    def from_constants(cls) -> "RuntimeConfig":
        """Build a typed snapshot from the one authoritative constants file."""

        return cls(
            application_name=constants.APPLICATION_NAME,
            application_version=constants.APPLICATION_VERSION,
            python_min_version=constants.PYTHON_MIN_VERSION,
            python_runtime_label=constants.PYTHON_RUNTIME_LABEL,
            require_free_threaded=constants.REQUIRE_FREE_THREADED,
            max_concurrent_calls=constants.MAX_CONCURRENT_CALLS,
            sip_bind_host=constants.SIP_BIND_HOST,
            sip_bind_port=constants.SIP_BIND_PORT,
            sip_transport=constants.SIP_TRANSPORT,
            rtp_bind_host=constants.RTP_BIND_HOST,
            rtp_port_start=constants.RTP_PORT_START,
            rtp_port_end=constants.RTP_PORT_END,
            sip_codec=constants.SIP_CODEC,
            sip_sample_rate_hz=constants.SIP_SAMPLE_RATE_HZ,
            sip_channels=constants.SIP_CHANNELS,
            operator_target=constants.OPERATOR_TARGET,
            media_profile_source=constants.MEDIA_PROFILE_SOURCE,
            media_ptime_policy=constants.MEDIA_PTIME_POLICY,
            pcm_sample_format=constants.PCM_SAMPLE_FORMAT,
            pcm_frame_size_policy=constants.PCM_FRAME_SIZE_POLICY,
            asr_model_path=constants.ASR_MODEL_PATH,
            llm_model_path=constants.LLM_MODEL_PATH,
            tts_model_path=constants.TTS_MODEL_PATH,
            asr_device=constants.ASR_DEVICE,
            llm_device=constants.LLM_DEVICE,
            tts_device=constants.TTS_DEVICE,
            gpu_name=constants.GPU_NAME,
            gpu_vram_gb=constants.GPU_VRAM_GB,
            knowledge_corpus_path=constants.KNOWLEDGE_CORPUS_PATH,
            knowledge_index_path=constants.KNOWLEDGE_INDEX_PATH,
            conversation_root=constants.CONVERSATION_ROOT,
            vad_speech_threshold=constants.VAD_SPEECH_THRESHOLD,
            endpoint_soft_ms=constants.ENDPOINT_SOFT_MS,
            endpoint_hard_ms=constants.ENDPOINT_HARD_MS,
            min_speech_ms=constants.MIN_SPEECH_MS,
            internal_pcm_frame_size_samples=constants.INTERNAL_PCM_FRAME_SIZE_SAMPLES,
            asr_chunk_ms=constants.ASR_CHUNK_MS,
            asr_chunk_flush_ms=constants.ASR_CHUNK_FLUSH_MS,
            audio_input_buffer_capacity_frames=constants.AUDIO_INPUT_BUFFER_CAPACITY_FRAMES,
            audio_output_buffer_capacity_frames=constants.AUDIO_OUTPUT_BUFFER_CAPACITY_FRAMES,
            control_event_buffer_capacity=constants.CONTROL_EVENT_BUFFER_CAPACITY,
            tts_output_tail_ms=constants.TTS_OUTPUT_TAIL_MS,
            llm_http_endpoint=constants.LLM_HTTP_ENDPOINT,
            llm_chat_model=constants.LLM_CHAT_MODEL,
            llm_embedding_model=constants.LLM_EMBEDDING_MODEL,
            llm_connect_timeout_s=constants.LLM_CONNECT_TIMEOUT_S,
            llm_read_timeout_s=constants.LLM_READ_TIMEOUT_S,
            llm_max_request_chars=constants.LLM_MAX_REQUEST_CHARS,
            llm_max_response_chars=constants.LLM_MAX_RESPONSE_CHARS,
            llm_cancellation_mode=constants.LLM_CANCELLATION_MODE,
            llm_thinking_enabled=constants.LLM_THINKING_ENABLED,
            llm_temperature=constants.LLM_TEMPERATURE,
            llm_max_generation_tokens=constants.LLM_MAX_GENERATION_TOKENS,
            default_skill_id=constants.DEFAULT_SKILL_ID,
            prompt_template_id=constants.PROMPT_TEMPLATE_ID,
            prompt_template_version=constants.PROMPT_TEMPLATE_VERSION,
            generation_profile_id=constants.GENERATION_PROFILE_ID,
            generation_profile_version=constants.GENERATION_PROFILE_VERSION,
            output_schema_id=constants.OUTPUT_SCHEMA_ID,
            max_answer_chars=constants.MAX_ANSWER_CHARS,
            user_text_delimiter=constants.USER_TEXT_DELIMITER,
            rag_corpus_version=constants.RAG_CORPUS_VERSION,
            rag_embedding_model=constants.RAG_EMBEDDING_MODEL,
            rag_top_k=constants.RAG_TOP_K,
            rag_relevance_threshold=constants.RAG_RELEVANCE_THRESHOLD,
            rag_max_context_chars=constants.RAG_MAX_CONTEXT_CHARS,
            rag_unknown_answer_policy=constants.RAG_UNKNOWN_ANSWER_POLICY,
            transcript_stable_prefix_min_chars=constants.TRANSCRIPT_STABLE_PREFIX_MIN_CHARS,
            rtp_media_budget_ms=constants.RTP_MEDIA_BUDGET_MS,
            latency_target_min_ms=constants.LATENCY_TARGET_MIN_MS,
            latency_target_max_ms=constants.LATENCY_TARGET_MAX_MS,
            log_level=constants.LOG_LEVEL,
            log_format=constants.LOG_FORMAT,
            log_date_format=constants.LOG_DATE_FORMAT,
        )
