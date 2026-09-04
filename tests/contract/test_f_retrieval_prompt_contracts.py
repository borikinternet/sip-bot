import json
from pathlib import Path

from sip_bot.context.store import ContextStore
from sip_bot.config import RuntimeConfig
from sip_bot.speech import EndpointEventKind, FinalUserTurn
from sip_bot.prompt.manager import GenerationProfile, PromptSpec, SkillPromptManager, SkillSpec
from sip_bot.retrieval.contracts import EmbeddingRequest, EmbeddingResponse
from sip_bot.retrieval.index import DeterministicEmbeddingBackend, LocalKnowledgeIndex, load_corpus
from sip_bot.retrieval.query_builder import KnowledgeQueryBuilder


def test_embedding_operation_is_typed_and_index_is_reproducible(tmp_path: Path):
    backend = DeterministicEmbeddingBackend()
    request = EmbeddingRequest("req-1", "Небо голубое", "fake-v1")
    response = backend.embed(request)
    assert isinstance(response, EmbeddingResponse)
    assert response.request_id == request.request_id
    assert response.model == request.model

    _, chunks = load_corpus(Path(__file__).parents[2] / "data" / "knowledge" / "corpus")
    first = LocalKnowledgeIndex.build(chunks, backend, index_version="repro-v1", embedding_model="fake-v1")
    second = LocalKnowledgeIndex.build(chunks, backend, index_version="repro-v1", embedding_model="fake-v1")
    first_path = tmp_path / "one" / "index.json"
    second_path = tmp_path / "two" / "index.json"
    first.save(first_path)
    second.save(second_path)
    assert first_path.read_bytes() == second_path.read_bytes()


def test_configured_rag_threshold_matches_real_provider_evidence():
    config = RuntimeConfig.from_constants()
    evidence_path = Path(__file__).parents[2] / "artifacts" / "implementation" / "002-mvp-media-and-speech-integration" / "002-G" / "real-provider-probe.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    positive = evidence["embedding"]["positive"]
    negative = evidence["embedding"]["negative"]

    assert positive["threshold"] == config.rag_relevance_threshold
    assert negative["threshold"] == config.rag_relevance_threshold
    assert positive["top_hit"]["score"] >= config.rag_relevance_threshold
    assert max(negative["top_scores"]) < config.rag_relevance_threshold


def test_f_answer_handoff_contains_rag_and_is_not_a_control_event(tmp_path: Path):
    store = ContextStore(tmp_path, "call-contract")
    snapshot = store.append_user("turn-1", "Почему небо голубое?")
    knowledge = __import__("sip_bot.retrieval.contracts", fromlist=["KnowledgeContext"]).KnowledgeContext(
        "ctx-1",
        "Почему небо голубое?",
        (),
        False,
        0.7,
        3,
        "index-v1",
        "embedding-v1",
    )
    manager = SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "answer"),
        prompt=PromptSpec("template", "1", "{instruction}:{user_text}"),
        profile=GenerationProfile("profile", "1", 128, 0.0),
        output_schema_id="schema-v1",
    )
    request = manager.prepare(
        call_id="call-contract",
        turn_id="turn-1",
        final_user_text="Почему небо голубое?",
        snapshot=snapshot,
        knowledge_context=knowledge,
    )
    assert request.knowledge_context.sufficient is False
    assert request.answer_mode == "unknown_answer"
    assert not hasattr(request, "kind")


def test_prompt_manager_accepts_authoritative_final_turn_directly(tmp_path: Path):
    store = ContextStore(tmp_path, "call-direct")
    snapshot = store.append_user("turn-1", "Почему небо голубое?")
    final_turn = FinalUserTurn(
        call_id="call-direct",
        channel_id="call-direct:audio",
        generation=1,
        turn_id="turn-1",
        text="Почему небо голубое?",
        revision=2,
        finalized_at_ns=500_000_000,
        boundary=EndpointEventKind.HARD_ENDPOINT,
    )
    knowledge = __import__("sip_bot.retrieval.contracts", fromlist=["KnowledgeContext"]).KnowledgeContext(
        "ctx-direct", final_turn.text, (), False, 0.7, 3, "index-v1", "embedding-v1"
    )
    manager = SkillPromptManager(
        skill=SkillSpec("answer-ru", "1", "answer"),
        prompt=PromptSpec("template", "1", "{instruction}:{user_text}"),
        profile=GenerationProfile("profile", "1", 128, 0.0),
        output_schema_id="schema-v1",
    )

    request = manager.prepare_for_turn(
        final_turn=final_turn,
        snapshot=snapshot,
        knowledge_context=knowledge,
    )
    assert request.call_id == final_turn.call_id
    assert request.turn_id == final_turn.turn_id
    assert request.final_user_text == final_turn.text
