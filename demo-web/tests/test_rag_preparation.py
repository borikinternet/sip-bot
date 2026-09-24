from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.rag import RagPreparationCoordinator, RagPreparationError, StaticMetadataProvider, verified_questions
from sip_bot.retrieval import DeterministicEmbeddingBackend, LocalKnowledgeIndex


def _pdf_with_text(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii"))
        document.extend(payload)
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    document.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(document)


def _coordinator(tmp_path: Path) -> RagPreparationCoordinator:
    return RagPreparationCoordinator(
        artifact_root=tmp_path / "corpora",
        registry_root=tmp_path / "registry",
        embedding_provider=DeterministicEmbeddingBackend(16),
        embedding_model="fake-demo-v1",
        metadata_provider=StaticMetadataProvider(),
    )


def test_prepare_publishes_loadable_index_and_registry(tmp_path: Path) -> None:
    prepared = _coordinator(tmp_path).prepare(
        session_id="session-one",
        caller_id="demo-caller-one",
        filename="notes.txt",
        data="# Океан\n\nВода покрывает большую часть поверхности Земли.".encode(),
    )
    assert prepared.artifact_dir.exists()
    assert prepared.metadata["title"] == "Океан"
    assert prepared.registry_payload["caller_id"] == "demo-caller-one"
    loaded = LocalKnowledgeIndex.load(prepared.index_path, expected_embedding_model="fake-demo-v1")
    assert loaded.item_count == 1
    assert (prepared.artifact_dir / "manifest.json").exists()
    assert (prepared.artifact_dir / "registry.json").exists()


def test_prepare_rejects_larger_than_640_kib_before_publication(tmp_path: Path) -> None:
    with pytest.raises(RagPreparationError, match="640 KiB"):
        _coordinator(tmp_path).prepare(
            session_id="session-two",
            caller_id="demo-caller-two",
            filename="too-large.md",
            data=b"x" * (640 * 1024 + 1),
        )
    assert list((tmp_path / "corpora").glob("*")) == []


def test_prepare_extracts_selectable_pdf_into_normalized_markdown(tmp_path: Path) -> None:
    prepared = _coordinator(tmp_path).prepare(
        session_id="session-pdf",
        caller_id="demo-caller-pdf",
        filename="brief.pdf",
        data=_pdf_with_text("PDF demo body"),
    )

    assert prepared.metadata["title"] == "PDF demo body"
    assert prepared.metadata["original_filename"] == "brief.pdf"
    assert (prepared.artifact_dir / "uploaded-document.md").read_text(encoding="utf-8").strip() == "PDF demo body"


def test_only_retrievable_example_questions_are_published() -> None:
    class Index:
        def query(self, query, provider, **kwargs):
            return SimpleNamespace(sufficient="голубым" in query.authoritative_text)

    assert verified_questions(
        ("Почему у Марса меняется цвет поверхности?", "Почему небо кажется голубым?"),
        Index(),
        object(),
    ) == ("Почему небо кажется голубым?",)


def test_examples_cover_distinct_sources_before_repeating_one() -> None:
    class Index:
        def query(self, query, provider, **kwargs):
            source = "mars" if "Марс" in query.authoritative_text else "water" if "Вода" in query.authoritative_text else "sky"
            return SimpleNamespace(sufficient=True, hits=(SimpleNamespace(source_id=source),))

    questions = ("Марс — что это?", "Марс — где он?", "Вода — что это?", "Небо — какое оно?")
    assert verified_questions(questions, Index(), object()) == (questions[0], questions[2], questions[3])
