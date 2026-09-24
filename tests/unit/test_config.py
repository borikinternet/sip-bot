"""Deterministic tests for the single-source runtime configuration."""

from dataclasses import FrozenInstanceError
import inspect

import pytest

from config import constants
from sip_bot.config import RegistrationProfile, RuntimeConfig


def test_runtime_config_is_an_explicit_snapshot_of_constants() -> None:
    config = RuntimeConfig.from_constants()

    assert config.application_name == constants.APPLICATION_NAME
    assert config.require_free_threaded is constants.REQUIRE_FREE_THREADED
    assert config.max_concurrent_calls == 1
    assert config.sip_codec == "PCMU"
    assert config.sip_sample_rate_hz == 8000
    assert config.sip_channels == 1
    assert config.media_ptime_policy == "negotiated-per-call"
    assert config.registration_profile.enabled is constants.SIP_REGISTRATION_ENABLED is True
    assert config.registration_profile.registrar_uri == constants.SIP_REGISTRAR_URI
    assert config.registration_profile.identity_uri == constants.SIP_REGISTRATION_IDENTITY_URI
    assert config.registration_profile.username == constants.SIP_REGISTRATION_USERNAME
    assert config.registration_profile.expires_seconds == constants.SIP_REGISTRATION_EXPIRES_SECONDS
    assert config.conversation_root == constants.CONVERSATION_ROOT
    assert config.vad_mode == constants.VAD_MODE == 2
    assert config.vad_energy_gate_enabled is constants.VAD_ENERGY_GATE_ENABLED is True
    assert config.vad_energy_min_dbfs == constants.VAD_ENERGY_MIN_DBFS == -42.0
    assert config.vad_energy_noise_margin_db == constants.VAD_ENERGY_NOISE_MARGIN_DB == 10.0
    assert config.vad_energy_near_end_bootstrap_dbfs == constants.VAD_ENERGY_NEAR_END_BOOTSTRAP_DBFS == -26.0
    assert config.vad_energy_near_end_confirmation_ms == constants.VAD_ENERGY_NEAR_END_CONFIRMATION_MS == 200
    assert config.vad_energy_near_end_percentile == constants.VAD_ENERGY_NEAR_END_PERCENTILE == 0.70
    assert config.vad_energy_near_end_margin_db == constants.VAD_ENERGY_NEAR_END_MARGIN_DB == 12.0
    assert config.vad_energy_barge_in_margin_db == constants.VAD_ENERGY_BARGE_IN_MARGIN_DB == 8.0
    assert config.vad_energy_barge_in_minimum_dbfs == constants.VAD_ENERGY_BARGE_IN_MINIMUM_DBFS == -26.0
    assert config.asr_no_speech_threshold == constants.ASR_NO_SPEECH_THRESHOLD == 0.60
    assert config.asr_segment_end_tolerance_ms == constants.ASR_SEGMENT_END_TOLERANCE_MS == 500.0
    assert config.endpoint_soft_ms == 300
    assert config.endpoint_hard_ms == constants.ENDPOINT_HARD_MS == 360
    assert config.tts_stream_chunk_size == constants.TTS_STREAM_CHUNK_SIZE == 5
    assert config.tts_stream_overlap_wav_len == constants.TTS_STREAM_OVERLAP_WAV_LEN == 1024
    assert config.sip_media_no_vad is constants.SIP_MEDIA_NO_VAD is True
    assert config.comfort_noise_level_dbov_magnitude == constants.COMFORT_NOISE_LEVEL_DBOV_MAGNITUDE == 50
    assert config.default_skill_id == constants.DEFAULT_SKILL_ID
    assert config.default_skill_version == constants.DEFAULT_SKILL_VERSION == "2"
    assert config.default_skill_instruction.startswith("Отвечай коротко.")
    assert config.prompt_template_text == constants.PROMPT_TEMPLATE_TEXT
    assert config.prompt_template_version == constants.PROMPT_TEMPLATE_VERSION == "3"
    assert config.call_greeting_text == constants.CALL_GREETING_TEXT == "Алло."
    assert config.rag_unknown_answer_policy == "offer-transfer"
    assert config.knowledge_index_path.suffix == ".json"
    assert config.rag_index_schema_version == "rag-index-v1"
    assert config.rag_index_version == "natural-science-embeddinggemma-v1"
    assert config.rag_chunking_policy_version == "markdown-semantic-v1"
    assert config.rag_index_dimension == 768
    assert len(config.rag_corpus_sha256) == 64
    assert config.llm_thinking_enabled is False
    assert config.llm_max_generation_tokens == 192


def test_configuration_has_no_environment_fallback() -> None:
    source = inspect.getsource(constants)

    assert "os.getenv" not in source
    assert "os.environ" not in source
    assert "dotenv" not in source


def test_runtime_config_is_immutable() -> None:
    config = RuntimeConfig.from_constants()

    try:
        config.application_name = "changed"  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("RuntimeConfig must be immutable")


def test_registration_profile_hides_demo_password_from_diagnostics() -> None:
    profile = RegistrationProfile.from_constants()

    assert constants.SIP_REGISTRATION_PASSWORD not in repr(profile)
    assert constants.SIP_REGISTRATION_PASSWORD not in repr(RuntimeConfig.from_constants())
    assert "password" not in profile.public_view()
    assert profile.public_view()["enabled"] is True


def test_disabled_registration_profile_does_not_require_registrar_fields() -> None:
    profile = RegistrationProfile.disabled()

    assert profile.enabled is False
    assert profile.public_view() == {
        "enabled": False,
        "registrar_uri": "",
        "identity_uri": "",
        "username": "",
        "expires_seconds": 0,
    }


def test_enabled_registration_profile_accepts_complete_values() -> None:
    profile = RegistrationProfile(
        enabled=True,
        registrar_uri="sip:127.0.0.1:5060",
        identity_uri="sip:tester@127.0.0.1",
        username="tester",
        password="demo",
        expires_seconds=300,
    )

    assert profile.enabled is True
    assert profile.expires_seconds == 300
    assert profile.public_view()["username"] == "tester"


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("registrar_uri", "", "registrar_uri"),
        ("identity_uri", "", "identity_uri"),
        ("username", "", "username"),
        ("password", "", "password"),
        ("expires_seconds", 0, "positive expires_seconds"),
    ],
)
def test_enabled_registration_profile_rejects_incomplete_values(
    field_name: str, value: object, message: str
) -> None:
    values: dict[str, object] = {
        "enabled": True,
        "registrar_uri": "sip:127.0.0.1:5060",
        "identity_uri": "sip:tester@127.0.0.1",
        "username": "tester",
        "password": "demo",
        "expires_seconds": 300,
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=message):
        RegistrationProfile(**values)  # type: ignore[arg-type]
