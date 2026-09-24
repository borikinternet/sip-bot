"""Typed access to the static MVP configuration."""

from dataclasses import dataclass, field
from pathlib import Path

from config import constants


@dataclass(frozen=True, slots=True)
class RegistrationProfile:
    """Immutable SIP registrar profile forwarded to the SIP adapter.

    The password is intentionally excluded from ``repr`` and from the public
    view used by diagnostics.  The profile is a value object only; registration
    lifecycle and PJSUA2 account setup belong to the SIP adapter child plan.
    """

    enabled: bool
    registrar_uri: str
    identity_uri: str
    username: str
    password: str = field(repr=False)
    expires_seconds: int

    @classmethod
    def disabled(cls) -> "RegistrationProfile":
        """Return an explicit no-registration profile for direct-URI callers."""

        return cls(
            enabled=False,
            registrar_uri="",
            identity_uri="",
            username="",
            password="",
            expires_seconds=0,
        )

    @classmethod
    def from_constants(cls) -> "RegistrationProfile":
        """Build the profile from the sole authoritative constants module."""

        return cls(
            enabled=constants.SIP_REGISTRATION_ENABLED,
            registrar_uri=constants.SIP_REGISTRAR_URI,
            identity_uri=constants.SIP_REGISTRATION_IDENTITY_URI,
            username=constants.SIP_REGISTRATION_USERNAME,
            password=constants.SIP_REGISTRATION_PASSWORD,
            expires_seconds=constants.SIP_REGISTRATION_EXPIRES_SECONDS,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("registration enabled flag must be bool")
        for name in ("registrar_uri", "identity_uri", "username", "password"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"registration {name} must be str")
        if not isinstance(self.expires_seconds, int) or isinstance(self.expires_seconds, bool):
            raise TypeError("registration expires_seconds must be int")
        if not self.enabled:
            return
        for name in ("registrar_uri", "identity_uri", "username", "password"):
            if not getattr(self, name).strip():
                raise ValueError(f"enabled registration requires non-empty {name}")
        if self.expires_seconds <= 0:
            raise ValueError("enabled registration requires positive expires_seconds")

    def public_view(self) -> dict[str, object]:
        """Return diagnostics-safe profile data without the password."""

        return {
            "enabled": self.enabled,
            "registrar_uri": self.registrar_uri,
            "identity_uri": self.identity_uri,
            "username": self.username,
            "expires_seconds": self.expires_seconds,
        }


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
    registration_profile: RegistrationProfile
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
    vad_mode: int
    vad_speech_threshold: float
    vad_energy_gate_enabled: bool
    vad_energy_min_dbfs: float
    vad_energy_noise_margin_db: float
    vad_energy_initial_noise_floor_dbfs: float
    vad_energy_history_ms: int
    vad_energy_bootstrap_ms: int
    vad_energy_noise_percentile: float
    vad_energy_max_noise_rise_db_per_s: float
    vad_energy_noise_fall_alpha: float
    vad_energy_speech_level_alpha: float
    vad_energy_confirmation_ms: int
    vad_energy_near_end_bootstrap_dbfs: float
    vad_energy_near_end_confirmation_ms: int
    vad_energy_near_end_percentile: float
    vad_energy_near_end_margin_db: float
    vad_energy_barge_in_margin_db: float
    vad_energy_barge_in_minimum_dbfs: float
    endpoint_soft_ms: int
    endpoint_hard_ms: int
    min_speech_ms: int
    internal_pcm_frame_size_samples: int
    asr_chunk_ms: int
    asr_chunk_flush_ms: int
    asr_no_speech_threshold: float
    asr_segment_end_tolerance_ms: float
    audio_input_buffer_capacity_frames: int
    audio_output_buffer_capacity_frames: int
    control_event_buffer_capacity: int
    tts_output_tail_ms: int
    tts_stream_chunk_size: int
    tts_stream_overlap_wav_len: int
    sip_media_no_vad: bool
    comfort_noise_level_dbov_magnitude: int
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
    default_skill_version: str
    default_skill_instruction: str
    prompt_template_id: str
    prompt_template_version: str
    prompt_template_text: str
    generation_profile_id: str
    generation_profile_version: str
    output_schema_id: str
    max_answer_chars: int
    user_text_delimiter: str
    call_greeting_text: str
    transfer_confirmation_text: str
    rag_corpus_version: str
    rag_embedding_model: str
    rag_index_schema_version: str
    rag_index_version: str
    rag_chunking_policy_version: str
    rag_corpus_sha256: str
    rag_index_dimension: int
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
            registration_profile=RegistrationProfile.from_constants(),
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
            vad_mode=constants.VAD_MODE,
            vad_speech_threshold=constants.VAD_SPEECH_THRESHOLD,
            vad_energy_gate_enabled=constants.VAD_ENERGY_GATE_ENABLED,
            vad_energy_min_dbfs=constants.VAD_ENERGY_MIN_DBFS,
            vad_energy_noise_margin_db=constants.VAD_ENERGY_NOISE_MARGIN_DB,
            vad_energy_initial_noise_floor_dbfs=constants.VAD_ENERGY_INITIAL_NOISE_FLOOR_DBFS,
            vad_energy_history_ms=constants.VAD_ENERGY_HISTORY_MS,
            vad_energy_bootstrap_ms=constants.VAD_ENERGY_BOOTSTRAP_MS,
            vad_energy_noise_percentile=constants.VAD_ENERGY_NOISE_PERCENTILE,
            vad_energy_max_noise_rise_db_per_s=constants.VAD_ENERGY_MAX_NOISE_RISE_DB_PER_S,
            vad_energy_noise_fall_alpha=constants.VAD_ENERGY_NOISE_FALL_ALPHA,
            vad_energy_speech_level_alpha=constants.VAD_ENERGY_SPEECH_LEVEL_ALPHA,
            vad_energy_confirmation_ms=constants.VAD_ENERGY_CONFIRMATION_MS,
            vad_energy_near_end_bootstrap_dbfs=constants.VAD_ENERGY_NEAR_END_BOOTSTRAP_DBFS,
            vad_energy_near_end_confirmation_ms=constants.VAD_ENERGY_NEAR_END_CONFIRMATION_MS,
            vad_energy_near_end_percentile=constants.VAD_ENERGY_NEAR_END_PERCENTILE,
            vad_energy_near_end_margin_db=constants.VAD_ENERGY_NEAR_END_MARGIN_DB,
            vad_energy_barge_in_margin_db=constants.VAD_ENERGY_BARGE_IN_MARGIN_DB,
            vad_energy_barge_in_minimum_dbfs=constants.VAD_ENERGY_BARGE_IN_MINIMUM_DBFS,
            endpoint_soft_ms=constants.ENDPOINT_SOFT_MS,
            endpoint_hard_ms=constants.ENDPOINT_HARD_MS,
            min_speech_ms=constants.MIN_SPEECH_MS,
            internal_pcm_frame_size_samples=constants.INTERNAL_PCM_FRAME_SIZE_SAMPLES,
            asr_chunk_ms=constants.ASR_CHUNK_MS,
            asr_chunk_flush_ms=constants.ASR_CHUNK_FLUSH_MS,
            asr_no_speech_threshold=constants.ASR_NO_SPEECH_THRESHOLD,
            asr_segment_end_tolerance_ms=constants.ASR_SEGMENT_END_TOLERANCE_MS,
            audio_input_buffer_capacity_frames=constants.AUDIO_INPUT_BUFFER_CAPACITY_FRAMES,
            audio_output_buffer_capacity_frames=constants.AUDIO_OUTPUT_BUFFER_CAPACITY_FRAMES,
            control_event_buffer_capacity=constants.CONTROL_EVENT_BUFFER_CAPACITY,
            tts_output_tail_ms=constants.TTS_OUTPUT_TAIL_MS,
            tts_stream_chunk_size=constants.TTS_STREAM_CHUNK_SIZE,
            tts_stream_overlap_wav_len=constants.TTS_STREAM_OVERLAP_WAV_LEN,
            sip_media_no_vad=constants.SIP_MEDIA_NO_VAD,
            comfort_noise_level_dbov_magnitude=constants.COMFORT_NOISE_LEVEL_DBOV_MAGNITUDE,
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
            default_skill_version=constants.DEFAULT_SKILL_VERSION,
            default_skill_instruction=constants.DEFAULT_SKILL_INSTRUCTION,
            prompt_template_id=constants.PROMPT_TEMPLATE_ID,
            prompt_template_version=constants.PROMPT_TEMPLATE_VERSION,
            prompt_template_text=constants.PROMPT_TEMPLATE_TEXT,
            generation_profile_id=constants.GENERATION_PROFILE_ID,
            generation_profile_version=constants.GENERATION_PROFILE_VERSION,
            output_schema_id=constants.OUTPUT_SCHEMA_ID,
            max_answer_chars=constants.MAX_ANSWER_CHARS,
            user_text_delimiter=constants.USER_TEXT_DELIMITER,
            call_greeting_text=constants.CALL_GREETING_TEXT,
            transfer_confirmation_text=constants.TRANSFER_CONFIRMATION_TEXT,
            rag_corpus_version=constants.RAG_CORPUS_VERSION,
            rag_embedding_model=constants.RAG_EMBEDDING_MODEL,
            rag_index_schema_version=constants.RAG_INDEX_SCHEMA_VERSION,
            rag_index_version=constants.RAG_INDEX_VERSION,
            rag_chunking_policy_version=constants.RAG_CHUNKING_POLICY_VERSION,
            rag_corpus_sha256=constants.RAG_CORPUS_SHA256,
            rag_index_dimension=constants.RAG_INDEX_DIMENSION,
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
