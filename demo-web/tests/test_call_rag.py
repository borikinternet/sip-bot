from __future__ import annotations

import json
from pathlib import Path

from backend.call_rag import CallScopedRagController
from backend.rag import RagPreparationCoordinator, StaticMetadataProvider
from sip_bot.retrieval import DeterministicEmbeddingBackend, LocalKnowledgeIndex


def test_call_scoped_controller_publishes_then_releases_custom_index(tmp_path: Path) -> None:
    prepared = RagPreparationCoordinator(
        artifact_root=tmp_path / "corpora",
        registry_root=tmp_path / "registry",
        embedding_provider=DeterministicEmbeddingBackend(16),
        embedding_model="fake-demo-v1",
        metadata_provider=StaticMetadataProvider(),
    ).prepare(
        session_id="session-one",
        caller_id="demo-caller-one",
        filename="notes.txt",
        data="# Океан\n\nВода покрывает большую часть поверхности Земли.".encode(),
    )
    registry_root = tmp_path / "registry"
    registry_root.mkdir(exist_ok=True)
    (registry_root / "demo-caller-one.json").write_text(
        json.dumps(prepared.registry_payload, ensure_ascii=False), encoding="utf-8"
    )
    target = LocalKnowledgeIndex.load(prepared.index_path, expected_embedding_model="fake-demo-v1")
    baseline = LocalKnowledgeIndex.load(prepared.index_path, expected_embedding_model="fake-demo-v1")
    controller = CallScopedRagController(
        target_index=target,
        baseline_index=baseline,
        registry_root=registry_root,
        index_loader=lambda path, _payload: LocalKnowledgeIndex.load(path),
    )

    metadata = controller.prepare("demo-caller-one")
    assert metadata["title"] == "Океан"
    assert controller.active_caller_id == "demo-caller-one"

    assert controller.release("demo-caller-one") is True
    assert controller.active_caller_id is None
    assert not (registry_root / "demo-caller-one.json").exists()
    assert not prepared.artifact_dir.exists()
