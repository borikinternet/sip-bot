"""Deterministic tests for the single-source runtime configuration."""

from dataclasses import FrozenInstanceError
import inspect

from config import constants
from sip_bot.config import RuntimeConfig


def test_runtime_config_is_an_explicit_snapshot_of_constants() -> None:
    config = RuntimeConfig.from_constants()

    assert config.application_name == constants.APPLICATION_NAME
    assert config.require_free_threaded is constants.REQUIRE_FREE_THREADED
    assert config.max_concurrent_calls == 1
    assert config.sip_codec == "PCMU"
    assert config.sip_sample_rate_hz == 8000
    assert config.sip_channels == 1
    assert config.media_ptime_policy == "negotiated-per-call"
    assert config.conversation_root == constants.CONVERSATION_ROOT
    assert config.default_skill_id == constants.DEFAULT_SKILL_ID
    assert config.rag_unknown_answer_policy == "offer-transfer"
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
