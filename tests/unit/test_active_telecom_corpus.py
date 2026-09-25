from pathlib import Path
import re

from config import constants
from sip_bot.retrieval import LocalKnowledgeIndex, ingest_corpus


PROJECT_ROOT = Path(__file__).parents[2]


def test_active_telecom_corpus_matches_published_index() -> None:
    corpus_root = PROJECT_ROOT / constants.KNOWLEDGE_CORPUS_PATH
    index_path = PROJECT_ROOT / constants.KNOWLEDGE_INDEX_PATH
    ingestion = ingest_corpus(corpus_root)
    assert ingestion.valid is True
    assert ingestion.manifest is not None
    assert ingestion.manifest.title == "Технологии и голосовые помощники"
    assert ingestion.content_sha256 == constants.RAG_CORPUS_SHA256
    assert len(ingestion.chunks) >= 20

    document = (corpus_root / "voice-assistants.md").read_text(encoding="utf-8")
    words = re.findall(r"(?u)\b[А-Яа-яЁёA-Za-z0-9]+(?:[-][А-Яа-яЁёA-Za-z0-9]+)*\b", document)
    assert 2000 <= len(words) <= 3000

    index = LocalKnowledgeIndex.load(
        index_path,
        expected_index_version=constants.RAG_INDEX_VERSION,
        expected_corpus_version=constants.RAG_CORPUS_VERSION,
        expected_embedding_model=constants.RAG_EMBEDDING_MODEL,
        expected_dimension=constants.RAG_INDEX_DIMENSION,
        expected_chunking_policy=constants.RAG_CHUNKING_POLICY_VERSION,
        expected_corpus_sha256=constants.RAG_CORPUS_SHA256,
    )
    assert index.item_count == len(ingestion.chunks)
    assert index.metadata.corpus_id == ingestion.manifest.corpus_id
