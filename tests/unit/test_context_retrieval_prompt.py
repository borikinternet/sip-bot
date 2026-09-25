from pathlib import Path

from sip_bot.context.store import ContextStore
from sip_bot.prompt.manager import (
    GenerationProfile,
    SkillPromptManager,
    SkillSpec,
    PromptSpec,
)
from sip_bot.prompt import build_default_prompt_manager
from sip_bot.retrieval.contracts import KnowledgeContext, KnowledgeHit
from sip_bot.retrieval.index import (
    DeterministicEmbeddingBackend,
    LocalKnowledgeIndex,
    _eligible_lexical_terms,
    load_corpus,
)
from sip_bot.retrieval.query_builder import KnowledgeQueryBuilder, query_capabilities


def test_context_store_is_bounded_and_text_only(tmp_path: Path):
    store = ContextStore(tmp_path, "call-1", max_turns=2, max_chars=100)
    store.append_user("t1", "первый вопрос")
    store.append_assistant("t1", "первый ответ")
    snapshot = store.append_user("t2", "второй вопрос")

    assert [turn.turn_id for turn in snapshot.turns] == ["t1", "t2"]
    assert snapshot.turns[-1].role == "user"
    assert store.path.read_text(encoding="utf-8").count("\n") == 3
    assert '"audio"' not in store.path.read_text(encoding="utf-8")


def test_query_builder_preserves_authoritative_text_and_special_tokens():
    source = "Почему H2O не кипит при 0 °C без давления 10^3 Па?"
    query = KnowledgeQueryBuilder().build(source, context=(("t0", "Мы говорили о свойствах воды"),))

    assert query.authoritative_text == source
    assert "не" in query.lexical_terms
    assert any("h2o" in item for item in query.lexical_terms)
    assert any("10^3" in item for item in query.lexical_terms)
    assert any("°c" in item for item in query.lexical_terms)
    assert query.context_turn_ids == ("t0",)
    assert any(term.startswith("свойств") for term in query.lexical_terms)
    assert "Текущий вопрос:" in query.embedding_text
    assert query.policy_version == "ru-technical-acronyms-v3"


def test_technical_acronyms_are_retrieval_anchors() -> None:
    query = KnowledgeQueryBuilder().build("Чем SIP отличается от RTP?")

    assert "sip" in _eligible_lexical_terms(query)
    assert "rtp" in _eligible_lexical_terms(query)


def test_query_builder_capability_probe_is_non_blocking():
    capabilities = query_capabilities()
    assert set(capabilities) == {"razdel", "pymorphy3", "policy_version"}
    assert isinstance(capabilities["razdel"], bool)
    assert isinstance(capabilities["pymorphy3"], bool)


def test_query_builder_marks_only_dependent_turns_for_retrieval_context() -> None:
    builder = KnowledgeQueryBuilder()

    assert builder.requires_dialogue_context("А ночью сколько будет стоить?") is True
    assert builder.requires_dialogue_context("А почему на закате оно становится красным?") is True
    assert builder.requires_dialogue_context("Сколько будет стоить?") is True
    assert builder.requires_dialogue_context("Стоп, а какие данные нужны для заявки?") is False
    assert builder.requires_dialogue_context("Почему небо днём голубое?") is False
    assert builder.requires_dialogue_context("Голубое") is False
    assert builder.requires_dialogue_context("Да") is False


def test_local_index_returns_source_aware_hit_and_explicit_insufficient_context():
    root = Path(__file__).parents[2] / "data" / "knowledge" / "corpus"
    sources, chunks = load_corpus(root)
    backend = DeterministicEmbeddingBackend()
    index = LocalKnowledgeIndex.build(
        chunks, backend, index_version="test-index-v1", embedding_model="fake-v1"
    )
    builder = KnowledgeQueryBuilder()
    positive = index.query(
        builder.build("Почему небо днём кажется голубым?"),
        backend,
        top_k=2,
        threshold=0.10,
        context_id="ctx-positive",
    )
    negative = index.query(
        builder.build("Как устроен телескоп?"),
        backend,
        top_k=2,
        threshold=0.99,
        context_id="ctx-negative",
    )

    assert len(sources) == 3
    assert positive.sufficient is True
    assert positive.hits[0].source_id == "wiki-physics-rayleigh"
    assert positive.hits[0].score >= positive.threshold
    assert negative.sufficient is False
    assert positive.sufficiency_diagnostics is not None
    assert positive.sufficiency_diagnostics.reason in {
        "strong_semantic",
        "configured_semantic_with_lexical_support",
        "lexical_rescue_with_semantic_floor",
    }
    assert positive.sufficiency_diagnostics.configured_threshold == positive.threshold
    assert negative.source_ids
    assert all(hit.chunk_id for hit in positive.hits)

    unrelated = index.query(
        builder.build("Каков точный состав атмосферы экзопланеты Кеплер-786?"),
        backend,
        top_k=2,
        threshold=0.10,
        context_id="ctx-unrelated",
    )
    assert unrelated.sufficient is False


def test_retrieval_rejects_one_word_lexical_overlap_below_strong_semantic_threshold():
    root = Path(__file__).parents[2] / "data" / "knowledge" / "corpus"
    _, chunks = load_corpus(root)
    backend = DeterministicEmbeddingBackend()
    index = LocalKnowledgeIndex.build(
        chunks, backend, index_version="test-index-v1", embedding_model="fake-v1"
    )

    result = index.query(
        KnowledgeQueryBuilder().build("Голубое?"),
        backend,
        top_k=2,
        threshold=0.35,
        context_id="ctx-underspecified",
    )

    assert result.sufficient is False
    assert result.sufficiency_diagnostics is not None
    assert result.sufficiency_diagnostics.reason == "underspecified_query"


def test_prompt_manager_requires_rag_evidence_and_keeps_exact_user_text(tmp_path: Path):
    store = ContextStore(tmp_path, "call-2")
    snapshot = store.append_user("turn-1", "Почему небо голубое?")
    builder = KnowledgeQueryBuilder()
    backend = DeterministicEmbeddingBackend()
    _, chunks = load_corpus(Path(__file__).parents[2] / "data" / "knowledge" / "corpus")
    index = LocalKnowledgeIndex.build(chunks, backend, index_version="test-index-v1", embedding_model="fake-v1")
    knowledge = index.query(
        builder.build("Почему небо голубое?"), backend, top_k=2, threshold=0.1, context_id="ctx-1"
    )
    manager = SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "Отвечай кратко и только по переданным источникам."),
        prompt=PromptSpec(
            "mvp-answer-ru", "1", "{instruction}\nКонтекст:\n{context}\nЗнания:\n{knowledge}\nВопрос:\n<user_text>{user_text}</user_text>"
        ),
        profile=GenerationProfile("mvp-short-answer", "1", 256, 0.1),
        output_schema_id="structured-dialogue-decision-v1",
    )
    request = manager.prepare(
        call_id="call-2",
        turn_id="turn-1",
        final_user_text="Почему небо голубое?",
        snapshot=snapshot,
        knowledge_context=knowledge,
    )

    assert request.answer_mode == "rag_answer"
    assert request.final_user_text == "Почему небо голубое?"
    assert request.knowledge_context.source_ids[0] == "wiki-physics-rayleigh"
    assert "source_id=wiki-physics-rayleigh" in request.prompt


def test_default_prompt_package_is_constants_backed_and_explicitly_short(tmp_path: Path) -> None:
    snapshot = ContextStore(tmp_path, "call-default").append_user("turn-1", "Почему небо голубое?")
    knowledge = KnowledgeContext(
        "ctx-default",
        "Почему небо голубое?",
        (KnowledgeHit("chunk-1", "wiki-physics-rayleigh", "Небо голубое из-за рассеяния света.", 0.9),),
        True,
        0.35,
        3,
        "index-v1",
        "embeddinggemma",
    )

    request = build_default_prompt_manager().prepare(
        call_id="call-default",
        turn_id="turn-1",
        final_user_text="Почему небо голубое?",
        snapshot=snapshot,
        knowledge_context=knowledge,
    )

    assert "Отвечай коротко." in request.prompt
    assert request.final_user_text == "Почему небо голубое?"
    assert request.prompt_template_version == "3"
    assert request.generation_profile_version == "3"
    assert request.allowed_actions == ("answer", "clarify")


def test_prompt_manager_marks_model_only_path_as_unknown(tmp_path: Path):
    snapshot = ContextStore(tmp_path, "call-3").append_user("turn-1", "Как устроен телескоп?")
    knowledge = KnowledgeContext(
        "ctx-empty",
        "Как устроен телескоп?",
        (KnowledgeHit("irrelevant-1", "company-exceptions", "Аварийная утечка газа: звоните 112.", 0.2),),
        False,
        0.7,
        3,
        "v1",
        "fake-v1",
    )
    manager = SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "answer"),
        prompt=PromptSpec("template", "1", "{instruction}\n{knowledge}\n{user_text}"),
        profile=GenerationProfile("profile", "1", 128, 0.0),
        output_schema_id="schema-v1",
    )

    request = manager.prepare(
        call_id="call-3",
        turn_id="turn-1",
        final_user_text="Как устроен телескоп?",
        snapshot=snapshot,
        knowledge_context=knowledge,
    )

    assert request.answer_mode == "unknown_answer"
    assert request.allowed_actions == ("offer_transfer",)
    assert request.diagnostics.sufficient is False
    assert "дословно" in request.prompt
    assert "Подключить оператора?" in request.prompt
    assert "Аварийная утечка газа" not in request.prompt
