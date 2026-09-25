from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from backend.rag import RagMetadata, StaticMetadataProvider
from backend.server import _corpus_example_questions, create_app, load_baseline_metadata
from backend.url_fetch import DownloadedDocument
from sip_bot.retrieval import DeterministicEmbeddingBackend


async def _wait_for_type(ws, expected: str) -> dict:
    for _ in range(20):
        message = await asyncio.wait_for(ws.receive(), timeout=2.0)
        if message.type.name == "TEXT":
            payload = __import__("json").loads(message.data)
            if payload.get("type") == expected:
                return payload
    raise AssertionError(f"did not receive websocket event {expected!r}")


def test_http_upload_emits_rag_ready_and_enables_call(tmp_path: Path) -> None:
    async def run() -> None:
        app = create_app(
            artifact_root=tmp_path / "corpora",
            registry_root=tmp_path / "registry",
            frontend_root=Path(__file__).resolve().parents[1] / "frontend",
            embedding_provider=DeterministicEmbeddingBackend(16),
            metadata_provider=StaticMetadataProvider(),
            baseline_metadata={"title": "Тестовый базовый корпус", "questions": []},
        )
        async with TestClient(TestServer(app)) as client:
            initial = await (await client.get("/api/session")).json()
            assert initial["call_enabled"] is True
            ws = await client.ws_connect(f"/ws/{initial['session_id']}")
            await _wait_for_type(ws, "snapshot")
            form = FormData()
            form.add_field("file", "# Лес\n\nВ документе описан лес.".encode(), filename="forest.md", content_type="text/markdown")
            response = await client.post(f"/api/session/{initial['session_id']}/upload", data=form)
            assert response.status == 202
            ready = await _wait_for_type(ws, "rag_ready")
            assert ready["status"]["state"] == "ready"
            assert ready["status"]["call_enabled"] is True
            await ws.close()

    asyncio.run(run())


def test_url_import_uses_same_ready_flow(tmp_path: Path, monkeypatch) -> None:
    async def fake_download(url: str) -> DownloadedDocument:
        assert url == "https://example.org/article"
        return DownloadedDocument(
            "article.html",
            b"<main><h1>SIP and RTP</h1><p>The voice assistant answers calls.</p></main>",
            url,
        )

    monkeypatch.setattr("backend.server.download_document", fake_download)

    async def run() -> None:
        app = create_app(
            artifact_root=tmp_path / "corpora",
            registry_root=tmp_path / "registry",
            frontend_root=Path(__file__).resolve().parents[1] / "frontend",
            embedding_provider=DeterministicEmbeddingBackend(16),
            metadata_provider=StaticMetadataProvider(),
            baseline_metadata={"title": "Base", "questions": []},
        )
        async with TestClient(TestServer(app)) as client:
            initial = await (await client.get("/api/session")).json()
            rejected = await client.post(
                f"/api/session/{initial['session_id']}/import-url",
                json={"url": "http://127.0.0.1:11434/api/tags"},
            )
            assert rejected.status == 400
            unchanged = await (await client.get(f"/api/session/{initial['session_id']}")).json()
            assert unchanged["state"] == "baseline"
            ws = await client.ws_connect(f"/ws/{initial['session_id']}")
            await _wait_for_type(ws, "snapshot")
            response = await client.post(
                f"/api/session/{initial['session_id']}/import-url",
                json={"url": "https://example.org/article"},
            )
            assert response.status == 202
            ready = await _wait_for_type(ws, "rag_ready")
            assert ready["status"]["state"] == "ready"
            assert ready["status"]["call_enabled"] is True
            assert ready["status"]["metadata"]["source_url"] == "https://example.org/article"
            await ws.close()

    asyncio.run(run())


def test_baseline_metadata_tracks_corpus_changes_and_filters_questions(tmp_path: Path, monkeypatch) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    document = corpus / "science.md"
    document.write_text("Небо кажется голубым из-за рассеяния света.", encoding="utf-8")
    manifest = corpus / "manifest.json"
    manifest.write_text(json.dumps({
        "title": "Наука",
        "corpus_id": "science",
        "sources": [{"title": "Небо", "file": "science.md", "topics": ["оптика"]}],
    }, ensure_ascii=False), encoding="utf-8")
    index = tmp_path / "index.json"
    index.write_text("index-v1", encoding="utf-8")

    class Provider:
        calls = 0

        def generate(self, *, text, filename, corpus_id):
            self.calls += 1
            return RagMetadata("Наука", "оптика", f"Источник: {text[-50:]}", (
                "Почему у Марса меняется цвет поверхности?",
                "Почему небо кажется голубым?",
            ))

    class FakeIndex:
        def query(self, query, provider, **kwargs):
            return SimpleNamespace(sufficient="небо" in query.authoritative_text.casefold())

    monkeypatch.setattr("backend.server.LocalKnowledgeIndex.load", lambda path: FakeIndex())
    provider = Provider()
    options = dict(
        metadata_provider=provider,
        embedding_provider=object(),
        manifest_path=manifest,
        index_path=index,
        cache_path=tmp_path / "baseline-cache.json",
    )
    first = load_baseline_metadata(**options)
    assert first["questions"] == ["Почему небо кажется голубым?"]
    assert provider.calls == 1
    assert load_baseline_metadata(**options) == first
    assert provider.calls == 1
    document.write_text("Небо голубое из-за рассеяния Рэлея.", encoding="utf-8")
    changed = load_baseline_metadata(**options)
    assert provider.calls == 2
    assert changed["description"] != first["description"]


def test_explicit_baseline_questions_cover_different_sections() -> None:
    documents = [("Guide", "\n\n".join(
        f"Вопрос: Тема {number}? Ответ: Подробный ответ {number}."
        for number in range(1, 9)
    ))]

    assert _corpus_example_questions(documents)[:3] == (
        "Тема 1?", "Тема 5?", "Тема 8?",
    )
