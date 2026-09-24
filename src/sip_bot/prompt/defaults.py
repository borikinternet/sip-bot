"""Build the single constants-backed MVP prompt package."""

from __future__ import annotations

from sip_bot.config import RuntimeConfig

from .manager import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec


def build_default_prompt_manager(config: RuntimeConfig | None = None) -> SkillPromptManager:
    """Materialize the versioned default package from the sole config source."""

    selected = config or RuntimeConfig.from_constants()
    return SkillPromptManager(
        skill=SkillSpec(
            selected.default_skill_id,
            selected.default_skill_version,
            selected.default_skill_instruction,
        ),
        prompt=PromptSpec(
            selected.prompt_template_id,
            selected.prompt_template_version,
            selected.prompt_template_text,
        ),
        profile=GenerationProfile(
            selected.generation_profile_id,
            selected.generation_profile_version,
            selected.llm_max_generation_tokens,
            selected.llm_temperature,
        ),
        output_schema_id=selected.output_schema_id,
        max_context_chars=selected.rag_max_context_chars,
    )


__all__ = ["build_default_prompt_manager"]
