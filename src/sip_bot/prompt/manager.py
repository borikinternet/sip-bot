"""Application-owned skill and prompt manager.

This module prepares a typed request only.  It does not call Ollama, make SIP
decisions, publish to the event bus or silently rewrite the final user text.
"""

from __future__ import annotations

from dataclasses import dataclass

from sip_bot.context.store import ContextSnapshot
from sip_bot.retrieval.contracts import KnowledgeContext
from sip_bot.speech.contracts import FinalUserTurn


@dataclass(frozen=True, slots=True)
class SkillSpec:
    skill_id: str
    version: str
    instruction: str


@dataclass(frozen=True, slots=True)
class PromptSpec:
    template_id: str
    version: str
    template: str


@dataclass(frozen=True, slots=True)
class GenerationProfile:
    profile_id: str
    version: str
    max_tokens: int
    temperature: float


@dataclass(frozen=True, slots=True)
class PromptDiagnostics:
    skill_id: str
    skill_version: str
    template_id: str
    template_version: str
    profile_id: str
    profile_version: str
    knowledge_context_id: str
    source_ids: tuple[str, ...]
    sufficient: bool


@dataclass(frozen=True, slots=True)
class LlmRequest:
    call_id: str
    turn_id: str
    skill_id: str
    skill_version: str
    prompt_template_id: str
    prompt_template_version: str
    generation_profile_id: str
    generation_profile_version: str
    output_schema_id: str
    final_user_text: str
    prompt: str
    knowledge_context: KnowledgeContext
    authoritative: bool
    answer_mode: str
    allowed_actions: tuple[str, ...]
    diagnostics: PromptDiagnostics

    def __post_init__(self) -> None:
        if not self.call_id or not self.turn_id or not self.final_user_text.strip():
            raise ValueError("LLM request identity and exact user text are required")
        if self.answer_mode not in {"rag_answer", "unknown_answer"}:
            raise ValueError("unsupported answer mode")
        if not self.authoritative:
            raise ValueError("F only builds authoritative final-turn requests")


class InsufficientKnowledgeContext(ValueError):
    """Raised when a caller asks for an answer request without RAG evidence."""


class SkillPromptManager:
    def __init__(
        self,
        *,
        skill: SkillSpec,
        prompt: PromptSpec,
        profile: GenerationProfile,
        output_schema_id: str,
        max_context_chars: int = 6000,
    ) -> None:
        self.skill = skill
        self.prompt_spec = prompt
        self.profile = profile
        self.output_schema_id = output_schema_id
        self.max_context_chars = max_context_chars

    def prepare(
        self,
        *,
        call_id: str,
        turn_id: str,
        final_user_text: str,
        snapshot: ContextSnapshot,
        knowledge_context: KnowledgeContext,
    ) -> LlmRequest:
        if not final_user_text.strip():
            raise ValueError("final user text must be non-empty")
        context_text = "\n".join(f"[{turn.role}] {turn.text}" for turn in snapshot.turns)
        evidence_text = "\n\n".join(
            f"[source_id={hit.source_id}; score={hit.score:.4f}; chunk_id={hit.chunk_id}]\n{hit.text}"
            for hit in knowledge_context.hits
        )
        context_text = context_text[-self.max_context_chars :]
        evidence_text = evidence_text[-self.max_context_chars :]
        sufficient = knowledge_context.sufficient and bool(knowledge_context.hits)
        answer_mode = "rag_answer" if sufficient else "unknown_answer"
        allowed_actions = ("answer", "clarify") if sufficient else ("offer_transfer",)
        instruction = self.skill.instruction if sufficient else (
            "Недостаточно подтверждённых фрагментов локальной базы. Сообщи об этом и предложи подключить оператора."
        )
        rendered = self.prompt_spec.template.format(
            instruction=instruction,
            context=context_text or "(пусто)",
            knowledge=evidence_text or "(релевантный контекст не найден)",
            user_text=final_user_text,
        )
        diagnostics = PromptDiagnostics(
            self.skill.skill_id,
            self.skill.version,
            self.prompt_spec.template_id,
            self.prompt_spec.version,
            self.profile.profile_id,
            self.profile.version,
            knowledge_context.context_id,
            knowledge_context.source_ids,
            sufficient,
        )
        return LlmRequest(
            call_id=call_id,
            turn_id=turn_id,
            skill_id=self.skill.skill_id,
            skill_version=self.skill.version,
            prompt_template_id=self.prompt_spec.template_id,
            prompt_template_version=self.prompt_spec.version,
            generation_profile_id=self.profile.profile_id,
            generation_profile_version=self.profile.version,
            output_schema_id=self.output_schema_id,
            final_user_text=final_user_text,
            prompt=rendered,
            knowledge_context=knowledge_context,
            authoritative=True,
            answer_mode=answer_mode,
            allowed_actions=allowed_actions,
            diagnostics=diagnostics,
        )

    def prepare_for_turn(
        self,
        *,
        final_turn: FinalUserTurn,
        snapshot: ContextSnapshot,
        knowledge_context: KnowledgeContext,
    ) -> LlmRequest:
        """Prepare a request from the authoritative direct speech payload."""

        if not isinstance(final_turn, FinalUserTurn):
            raise TypeError("final_turn must be the authoritative FinalUserTurn payload")
        return self.prepare(
            call_id=final_turn.call_id,
            turn_id=final_turn.turn_id,
            final_user_text=final_turn.text,
            snapshot=snapshot,
            knowledge_context=knowledge_context,
        )
