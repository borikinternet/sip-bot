from __future__ import annotations

import asyncio
from pathlib import Path

from backend.registry import SessionRegistry
from backend.models import SessionState


def test_session_registry_expires_waiting_artifact_but_not_active_call(tmp_path: Path) -> None:
    async def run() -> None:
        registry = SessionRegistry(
            artifact_root=tmp_path / "corpora",
            registry_root=tmp_path / "registry",
            baseline_metadata={"title": "base"},
            heartbeat_timeout=5.0,
        )
        session = await registry.create()
        await registry.begin_preparation(session.session_id)
        artifact = tmp_path / "corpora" / "artifact"
        artifact.mkdir(parents=True)
        await registry.mark_ready(
            session.session_id,
            artifact_dir=artifact,
            metadata={"title": "custom"},
            registry_payload={"caller_id": session.caller_id},
        )
        session.last_heartbeat = 0.0
        expired = await registry.sweep(now=6.0)
        assert expired == (session.session_id,)
        assert not artifact.exists()
        assert (await registry.snapshot(session.session_id))["state"] == SessionState.STALE.value

        active = await registry.create()
        await registry.mark_call_started(active.session_id)
        active.last_heartbeat = 0.0
        assert await registry.sweep(now=100.0) == ()
        assert (await registry.snapshot(active.session_id))["state"] == SessionState.ACTIVE_CALL.value

    asyncio.run(run())


def test_call_end_removes_custom_artifact_and_returns_to_baseline(tmp_path: Path) -> None:
    async def run() -> None:
        registry = SessionRegistry(
            artifact_root=tmp_path / "corpora",
            registry_root=tmp_path / "registry",
            baseline_metadata={"title": "base"},
        )
        session = await registry.create()
        artifact = tmp_path / "artifact"
        artifact.mkdir()
        await registry.mark_ready(
            session.session_id,
            artifact_dir=artifact,
            metadata={"title": "custom"},
            registry_payload={"caller_id": session.caller_id},
        )
        await registry.mark_call_started(session.session_id)
        result = await registry.mark_call_ended(session.session_id)
        assert result["state"] == SessionState.BASELINE.value
        assert result["call_enabled"] is True
        assert not artifact.exists()

    asyncio.run(run())


def test_expired_preparation_cannot_publish_after_heartbeat_death(tmp_path: Path) -> None:
    async def run() -> None:
        registry = SessionRegistry(
            artifact_root=tmp_path / "corpora",
            registry_root=tmp_path / "registry",
            baseline_metadata={"title": "base"},
            heartbeat_timeout=5.0,
        )
        session = await registry.create()
        await registry.begin_preparation(session.session_id)
        session.last_heartbeat = 0.0
        assert await registry.sweep(now=6.0) == (session.session_id,)
        artifact = tmp_path / "late-artifact"
        artifact.mkdir()
        try:
            await registry.mark_ready(
                session.session_id,
                artifact_dir=artifact,
                metadata={"title": "late"},
                registry_payload={"state": "ready", "caller_id": session.caller_id},
            )
        except KeyError:
            pass
        else:
            raise AssertionError("stale session published a late artifact")
        assert not artifact.exists()

    asyncio.run(run())
