"""Session leases and the shared caller-ID-to-artifact registry."""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import uuid
from pathlib import Path
from time import monotonic
from typing import Any

from .models import (
    HEARTBEAT_TIMEOUT_SECONDS,
    SessionState,
    WebSession,
    state_is_call_enabled,
)


class SessionNotFound(KeyError):
    """The volatile web session is unknown or has expired."""


class SessionRegistry:
    """Own volatile web sessions and publish an atomic local routing registry."""

    def __init__(
        self,
        *,
        artifact_root: Path,
        registry_root: Path,
        baseline_metadata: dict[str, Any],
        heartbeat_timeout: float = HEARTBEAT_TIMEOUT_SECONDS,
    ) -> None:
        self.artifact_root = artifact_root
        self.registry_root = registry_root
        self.baseline_metadata = dict(baseline_metadata)
        self.heartbeat_timeout = heartbeat_timeout
        self._sessions: dict[str, WebSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> WebSession:
        session_id = uuid.uuid4().hex
        caller_id = f"demo-{secrets.token_hex(7)}"
        session = WebSession(session_id=session_id, caller_id=caller_id)
        async with self._lock:
            self._sessions[session_id] = session
        self._write_atomic_json(self.registry_root / f"{caller_id}.json", self._baseline_payload(session))
        return session

    async def require(self, session_id: str) -> WebSession:
        async with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise SessionNotFound(session_id) from exc

    async def snapshot(self, session_id: str) -> dict[str, Any]:
        session = await self.require(session_id)
        return self._snapshot(session)

    async def heartbeat(self, session_id: str) -> dict[str, Any]:
        session = await self.require(session_id)
        async with self._lock:
            session.last_heartbeat = monotonic()
            return self._snapshot(session)

    async def begin_preparation(self, session_id: str) -> dict[str, Any]:
        session = await self.require(session_id)
        async with self._lock:
            if session.state is SessionState.STALE:
                raise SessionNotFound(session_id)
            if session.active_call:
                raise RuntimeError("cannot replace RAG during an active call")
            if session.state is SessionState.PREPARING:
                raise RuntimeError("document preparation is already in progress")
            session.state = SessionState.PREPARING
            session.error = None
            session.metadata = None
            return self._snapshot(session)

    async def mark_ready(
        self,
        session_id: str,
        *,
        artifact_dir: Path,
        metadata: dict[str, Any],
        registry_payload: dict[str, Any],
    ) -> dict[str, Any]:
        session = await self.require(session_id)
        old_artifact: Path | None
        async with self._lock:
            if session.state is SessionState.STALE:
                self._remove_artifact(artifact_dir)
                raise SessionNotFound(session_id)
            self._write_atomic_json(self.registry_root / f"{session.caller_id}.json", registry_payload)
            old_artifact = session.artifact_dir
            session.state = SessionState.READY
            session.artifact_dir = artifact_dir
            session.metadata = dict(metadata)
            session.error = None
            result = self._snapshot(session)
        if old_artifact is not None and old_artifact != artifact_dir:
            self._remove_artifact(old_artifact)
        await self.broadcast(session_id, {"type": "rag_ready", "status": result})
        return result

    async def mark_failed(self, session_id: str, error: str) -> dict[str, Any]:
        session = await self.require(session_id)
        async with self._lock:
            if session.state is SessionState.STALE:
                return self._snapshot(session)
            session.state = SessionState.FAILED
            session.error = error[:500]
            result = self._snapshot(session)
        await self.broadcast(session_id, {"type": "rag_failed", "status": result})
        return result

    async def mark_call_started(self, session_id: str) -> dict[str, Any]:
        session = await self.require(session_id)
        async with self._lock:
            if not state_is_call_enabled(session.state):
                raise RuntimeError("session is not ready for a call")
            session.active_call = True
            session.state = SessionState.ACTIVE_CALL
            result = self._snapshot(session)
        await self.broadcast(session_id, {"type": "call_started", "status": result})
        return result

    async def mark_call_ended(self, session_id: str) -> dict[str, Any]:
        session = await self.require(session_id)
        async with self._lock:
            session.active_call = False
            artifact_dir = session.artifact_dir
            session.artifact_dir = None
            session.metadata = None
            session.state = SessionState.BASELINE
            result = self._snapshot(session)
        self._remove_registry_entry(session.caller_id)
        self._remove_artifact(artifact_dir)
        self._write_atomic_json(self.registry_root / f"{session.caller_id}.json", self._baseline_payload(session))
        await self.broadcast(session_id, {"type": "call_ended", "status": result})
        return result

    async def register_socket(self, session_id: str, socket: Any) -> dict[str, Any]:
        session = await self.require(session_id)
        async with self._lock:
            session.sockets.add(socket)
            session.websocket_count = len(session.sockets)
            session.last_heartbeat = monotonic()
            return self._snapshot(session)

    async def unregister_socket(self, session_id: str, socket: Any) -> None:
        try:
            session = await self.require(session_id)
        except SessionNotFound:
            return
        async with self._lock:
            session.sockets.discard(socket)
            session.websocket_count = len(session.sockets)

    async def broadcast(self, session_id: str, payload: dict[str, Any]) -> None:
        session = await self.require(session_id)
        message = json.dumps(payload, ensure_ascii=False)
        stale: list[Any] = []
        for socket in tuple(session.sockets):
            try:
                await socket.send_str(message)
            except Exception:  # noqa: BLE001 - a disconnected browser is a lease signal
                stale.append(socket)
        for socket in stale:
            await self.unregister_socket(session_id, socket)

    async def sweep(self, *, now: float | None = None) -> tuple[str, ...]:
        current = monotonic() if now is None else now
        expired: list[str] = []
        async with self._lock:
            for session_id, session in self._sessions.items():
                if session.active_call or session.state in {SessionState.STALE}:
                    continue
                if current - session.last_heartbeat > self.heartbeat_timeout:
                    session.state = SessionState.STALE
                    session.error = "websocket heartbeat expired"
                    expired.append(session_id)
        for session_id in expired:
            session = await self.require(session_id)
            artifact_dir = session.artifact_dir
            async with self._lock:
                session.artifact_dir = None
                session.metadata = None
            self._remove_registry_entry(session.caller_id)
            self._remove_artifact(artifact_dir)
            await self.broadcast(session_id, {"type": "session_stale", "status": self._snapshot(session)})
        return tuple(expired)

    @staticmethod
    def _snapshot(session: WebSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "caller_id": session.caller_id,
            "state": session.state.value,
            "call_enabled": state_is_call_enabled(session.state) and not session.active_call,
            "metadata": session.metadata,
            "error": session.error,
            "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
            "websocket_count": session.websocket_count,
        }

    def _baseline_payload(self, session: WebSession) -> dict[str, Any]:
        return {
            "schema_version": "conference-rag-registry-v1",
            "session_id": session.session_id,
            "caller_id": session.caller_id,
            "state": "baseline",
            "metadata": dict(self.baseline_metadata),
            "baseline": True,
        }

    def _remove_registry_entry(self, caller_id: str) -> None:
        (self.registry_root / f"{caller_id}.json").unlink(missing_ok=True)

    @staticmethod
    def _remove_artifact(artifact_dir: Path | None) -> None:
        if artifact_dir is not None and artifact_dir.exists():
            shutil.rmtree(artifact_dir)

    @staticmethod
    def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
