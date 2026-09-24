"""aiohttp entry point for the conference web-demo."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import ssl
import sys
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web
from config import constants

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sip_bot.llm import LlmFacade, OllamaHttpClient  # noqa: E402

from .models import HEARTBEAT_INTERVAL_SECONDS, MAX_UPLOAD_BYTES  # noqa: E402
from .rag import (  # noqa: E402
    EmbeddingFacadeProvider,
    OllamaMetadataProvider,
    RagPreparationCoordinator,
    verified_questions,
)
from .registry import SessionNotFound, SessionRegistry  # noqa: E402
from sip_bot.retrieval.index import LocalKnowledgeIndex  # noqa: E402


LOG = logging.getLogger("conference-demo")
FRONTEND_ROOT = PROJECT_ROOT / "demo-web" / "frontend"
RUNTIME_ROOT = PROJECT_ROOT / "demo-web" / "runtime"
ARTIFACT_ROOT = RUNTIME_ROOT / "corpora"
REGISTRY_ROOT = RUNTIME_ROOT / "registry"
BASELINE_MANIFEST = PROJECT_ROOT / "data" / "knowledge" / "corpus" / "manifest.json"
BASELINE_INDEX = PROJECT_ROOT / constants.KNOWLEDGE_INDEX_PATH
BASELINE_METADATA_CACHE = RUNTIME_ROOT / "baseline-metadata.json"


def load_baseline_metadata(
    *,
    metadata_provider: Any,
    embedding_provider: Any,
    manifest_path: Path = BASELINE_MANIFEST,
    index_path: Path = BASELINE_INDEX,
    cache_path: Path = BASELINE_METADATA_CACHE,
) -> dict[str, Any]:
    """Generate and cache examples from the actual baseline corpus and index."""

    manifest_bytes = manifest_path.read_bytes()
    raw = json.loads(manifest_bytes)
    sources = raw.get("sources", [])
    documents = [
        (source["title"], (manifest_path.parent / source["file"]).read_text(encoding="utf-8"))
        for source in sources
    ]
    fingerprint = hashlib.sha256(
        b"baseline-metadata-v2"
        + manifest_bytes
        + b"".join(text.encode("utf-8") for _, text in documents)
        + index_path.read_bytes()
    ).hexdigest()
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("fingerprint") == fingerprint:
            return cached["metadata"]

    index = LocalKnowledgeIndex.load(index_path)
    generated = metadata_provider.generate(
        text="\n\n".join(f"# {title}\n{text}" for title, text in documents),
        filename="базовый корпус",
        corpus_id=raw["corpus_id"],
    )
    topics = sorted({topic for source in sources for topic in source.get("topics", [])})
    metadata = {
        "title": raw["title"],
        "topic": ", ".join(topics),
        "description": generated.description,
        "questions": list(verified_questions(generated.questions, index, embedding_provider)),
        "corpus_id": raw["corpus_id"],
        "baseline": True,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"fingerprint": fingerprint, "metadata": metadata}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(cache_path)
    return metadata


def create_app(
    *,
    artifact_root: Path = ARTIFACT_ROOT,
    registry_root: Path = REGISTRY_ROOT,
    frontend_root: Path = FRONTEND_ROOT,
    embedding_provider: Any | None = None,
    metadata_provider: Any | None = None,
    baseline_metadata: dict[str, Any] | None = None,
) -> web.Application:
    """Create an app with injectable RAG providers for deterministic tests."""

    artifact_root.mkdir(parents=True, exist_ok=True)
    registry_root.mkdir(parents=True, exist_ok=True)
    if embedding_provider is None:
        facade = LlmFacade(
            OllamaHttpClient(
                endpoint="http://127.0.0.1:11434",
                timeout_s=30.0,
            )
        )
        embedding_provider = EmbeddingFacadeProvider(facade)
    metadata_provider = metadata_provider or OllamaMetadataProvider()
    coordinator = RagPreparationCoordinator(
        artifact_root=artifact_root,
        registry_root=registry_root,
        embedding_provider=embedding_provider,
        metadata_provider=metadata_provider,
    )
    registry = SessionRegistry(
        artifact_root=artifact_root,
        registry_root=registry_root,
        baseline_metadata=baseline_metadata or load_baseline_metadata(
            metadata_provider=metadata_provider,
            embedding_provider=embedding_provider,
        ),
    )
    app = web.Application(client_max_size=MAX_UPLOAD_BYTES + 64 * 1024)
    app["registry"] = registry
    app["coordinator"] = coordinator
    app["frontend_root"] = frontend_root
    app["preparation_tasks"] = set()

    app.router.add_get("/api/session", create_session)
    app.router.add_get("/api/session/{session_id}", get_session)
    app.router.add_post("/api/session/{session_id}/upload", upload_file)
    app.router.add_post("/api/session/{session_id}/call/started", call_started)
    app.router.add_post("/api/session/{session_id}/call/ended", call_ended)
    app.router.add_get("/ws/{session_id}", websocket)
    app.router.add_get("/", serve_index)
    app.router.add_static("/assets", str(frontend_root / "assets"), name="assets")
    app.router.add_static("/static", str(frontend_root), name="static")
    app.on_startup.append(start_sweeper)
    app.on_cleanup.append(stop_sweeper)
    return app


async def create_session(request: web.Request) -> web.Response:
    session = await request.app["registry"].create()
    return web.json_response(_with_baseline(request.app["registry"], session))


async def get_session(request: web.Request) -> web.Response:
    try:
        payload = await request.app["registry"].snapshot(request.match_info["session_id"])
    except SessionNotFound:
        raise web.HTTPNotFound(text="unknown session")
    return web.json_response(_with_baseline(request.app["registry"], payload))


def _with_baseline(registry: SessionRegistry, value: Any) -> dict[str, Any]:
    payload = registry._snapshot(value) if hasattr(value, "session_id") else dict(value)
    if payload["state"] == "baseline" and payload["metadata"] is None:
        payload["metadata"] = registry.baseline_metadata
    return payload


async def upload_file(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    registry: SessionRegistry = request.app["registry"]
    try:
        session = await registry.require(session_id)
    except SessionNotFound:
        raise web.HTTPNotFound(text="unknown session")
    if session.active_call:
        raise web.HTTPConflict(text="cannot upload during an active call")

    reader = await request.multipart()
    part = await reader.next()
    if part is None or part.name != "file":
        raise web.HTTPBadRequest(text="multipart field 'file' is required")
    filename = Path(part.filename or "uploaded.md").name
    suffix = Path(filename).suffix.casefold()
    if suffix not in {".md", ".txt", ".pdf"}:
        raise web.HTTPUnsupportedMediaType(text="only .md, .txt and text-based .pdf files are accepted")
    data = bytearray()
    while True:
        chunk = await part.read_chunk(size=64 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > MAX_UPLOAD_BYTES:
            raise web.HTTPRequestEntityTooLarge(
                max_size=MAX_UPLOAD_BYTES,
                actual_size=len(data),
            )
    if not data:
        raise web.HTTPBadRequest(text="uploaded file is empty")

    await registry.begin_preparation(session_id)
    await registry.broadcast(session_id, {"type": "rag_preparing", "status": await registry.snapshot(session_id)})
    task = asyncio.create_task(
        _prepare_upload(
            request.app,
            session_id=session_id,
            caller_id=session.caller_id,
            filename=filename,
            data=bytes(data),
        )
    )
    request.app["preparation_tasks"].add(task)
    task.add_done_callback(request.app["preparation_tasks"].discard)
    return web.json_response(await registry.snapshot(session_id), status=202)


async def _prepare_upload(
    app: web.Application,
    *,
    session_id: str,
    caller_id: str,
    filename: str,
    data: bytes,
) -> None:
    registry: SessionRegistry = app["registry"]
    try:
        prepared = await asyncio.to_thread(
            app["coordinator"].prepare,
            session_id=session_id,
            caller_id=caller_id,
            filename=filename,
            data=data,
        )
        await registry.mark_ready(
            session_id,
            artifact_dir=prepared.artifact_dir,
            metadata=prepared.metadata,
            registry_payload=prepared.registry_payload,
        )
    except Exception as exc:  # noqa: BLE001 - status boundary must preserve failure
        LOG.exception("RAG preparation failed for %s", session_id)
        try:
            await registry.mark_failed(session_id, str(exc) or exc.__class__.__name__)
        except SessionNotFound:
            return


async def websocket(request: web.Request) -> web.StreamResponse:
    session_id = request.match_info["session_id"]
    registry: SessionRegistry = request.app["registry"]
    try:
        await registry.require(session_id)
    except SessionNotFound:
        raise web.HTTPNotFound(text="unknown session")
    ws = web.WebSocketResponse(autoping=True, autoclose=True)
    await ws.prepare(request)
    await registry.register_socket(session_id, ws)
    await ws.send_json({"type": "snapshot", "status": await registry.snapshot(session_id)})
    ping_task = asyncio.create_task(_application_ping(ws))
    try:
        async for message in ws:
            if message.type is WSMsgType.TEXT:
                try:
                    payload = json.loads(message.data)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("type") == "pong":
                    await registry.heartbeat(session_id)
            elif message.type is WSMsgType.PONG:
                await registry.heartbeat(session_id)
            elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                break
    finally:
        ping_task.cancel()
        await registry.unregister_socket(session_id, ws)
    return ws


async def _application_ping(ws: web.WebSocketResponse) -> None:
    try:
        while not ws.closed:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            if not ws.closed:
                await ws.send_json({"type": "ping"})
    except (asyncio.CancelledError, ConnectionError):
        return


async def call_started(request: web.Request) -> web.Response:
    try:
        payload = await request.app["registry"].mark_call_started(request.match_info["session_id"])
    except SessionNotFound:
        raise web.HTTPNotFound(text="unknown session")
    except RuntimeError as exc:
        raise web.HTTPConflict(text=str(exc))
    return web.json_response(payload)


async def call_ended(request: web.Request) -> web.Response:
    try:
        payload = await request.app["registry"].mark_call_ended(request.match_info["session_id"])
    except SessionNotFound:
        raise web.HTTPNotFound(text="unknown session")
    return web.json_response(_with_baseline(request.app["registry"], payload))


async def serve_index(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(Path(request.app["frontend_root"]) / "index.html")


async def start_sweeper(app: web.Application) -> None:
    async def run() -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                await app["registry"].sweep()
        except asyncio.CancelledError:
            return

    app["sweeper"] = asyncio.create_task(run())


async def stop_sweeper(app: web.Application) -> None:
    task = app.get("sweeper")
    if task is not None:
        task.cancel()
        await task
    tasks = tuple(app["preparation_tasks"])
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    host = os.environ.get("DEMO_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("DEMO_WEB_PORT", "8080"))
    cert_path = os.environ.get("DEMO_WEB_TLS_CERT")
    key_path = os.environ.get("DEMO_WEB_TLS_KEY")
    tls_port = int(os.environ.get("DEMO_WEB_TLS_PORT", "8443"))

    async def serve() -> None:
        runner = web.AppRunner(create_app())
        await runner.setup()
        try:
            await web.TCPSite(runner, host=host, port=port).start()
            LOG.info("HTTP listening on %s:%s", host, port)
            if cert_path and key_path:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert_path, key_path)
                await web.TCPSite(runner, host=host, port=tls_port, ssl_context=context).start()
                LOG.info("HTTPS listening on %s:%s", host, tls_port)
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
