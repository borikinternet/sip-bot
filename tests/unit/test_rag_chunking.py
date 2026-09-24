from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sip_bot.retrieval import CorpusChunker, CorpusNormalizer, CorpusPackage, ingest_corpus, load_corpus


PROJECT_ROOT = Path(__file__).parents[2]
SCIENCE = PROJECT_ROOT / "data" / "knowledge" / "corpus"
WORKSHOP = PROJECT_ROOT / "config" / "workshops" / "rag" / "corpus"


def test_normalization_is_deterministic_and_preserves_words() -> None:
    source = "# Заголовок\r\n\r\nСтрока с пробелами.   \r\n\r\n\r\nВторая строка.\r\n"
    expected = "# Заголовок\n\nСтрока с пробелами.\n\nВторая строка.\n"

    assert CorpusNormalizer.normalize(source) == expected
    assert CorpusNormalizer.normalize(expected) == expected


def test_workshop_ingestion_is_byte_stable_and_source_aware() -> None:
    first = ingest_corpus(WORKSHOP)
    second = ingest_corpus(WORKSHOP)

    assert first.valid is True
    assert first.to_dict() == second.to_dict()
    assert len(first.sources) == 6
    assert len(first.chunks) == 12
    assert first.accepted_source_ids == tuple(source.source_id for source in first.sources)
    assert first.skipped_source_ids == ()
    assert len(first.content_sha256) == 64
    assert all(chunk.source_id in first.accepted_source_ids for chunk in first.chunks)
    assert all(chunk.source_version == "1.0.0" for chunk in first.chunks)
    assert all(chunk.content_sha256 and chunk.chunk_id.endswith(chunk.content_sha256[:12]) for chunk in first.chunks)


def test_science_compatibility_loader_keeps_two_semantic_chunks_per_source() -> None:
    sources, chunks = load_corpus(SCIENCE)

    assert len(sources) == 3
    assert len(chunks) == 6
    assert {chunk.source_id for chunk in chunks} == {source.source_id for source in sources}
    assert all(chunk.chunk_id.startswith(f"{chunk.source_id}-{chunk.ordinal:03d}-") for chunk in chunks)


def test_heading_is_carried_into_each_paragraph_chunk() -> None:
    document = CorpusPackage.load(WORKSHOP).documents[-1]
    chunks = CorpusChunker(max_chars=1200).chunk(document)

    assert len(chunks) == 2
    assert all(chunk.text.startswith("Услуги компании «СервисПлюс»\n") for chunk in chunks)


def test_long_paragraph_is_split_deterministically_with_stable_ids() -> None:
    document = CorpusPackage.load(WORKSHOP).documents[-1]
    long_text = "# Проверка\n\n" + " ".join(f"Предложение номер {number}." for number in range(40))
    modified = replace(document, text=long_text)
    chunker = CorpusChunker(max_chars=220)

    first = chunker.chunk(modified)
    second = chunker.chunk(modified)

    assert first == second
    assert len(first) > 1
    assert all(len(chunk.text) <= 220 for chunk in first)
    assert [chunk.ordinal for chunk in first] == list(range(1, len(first) + 1))
    assert all(chunk.content_sha256 and chunk.chunk_id.endswith(chunk.content_sha256[:12]) for chunk in first)
