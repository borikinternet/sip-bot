"""Synchronous bridge from a SIP caller-id to a published RAG artifact.

The web process publishes one immutable JSON record per prepared session.  The
single-session bot reads that record only after it has received the queued
call's provisional 180 response, loads the complete index off the event loop,
and publishes it into the stable in-memory index handle used by the existing
conversation pipeline.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from threading import RLock
from typing import Any, Callable


class CallRagError(RuntimeError):
    """The caller-id does not resolve to a usable prepared artifact."""


class CallScopedRagController:
    """Load and release one published index at a time."""

    _CALLER_ID = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")

    def __init__(
        self,
        *,
        target_index: Any,
        baseline_index: Any,
        registry_root: Path,
        index_loader: Callable[[Path, dict[str, Any]], Any],
        baseline_metadata: dict[str, Any] | None = None,
    ) -> None:
        if not callable(index_loader):
            raise TypeError("index_loader must be callable")
        self.target_index = target_index
        self.baseline_index = baseline_index
        self.registry_root = Path(registry_root)
        self.index_loader = index_loader
        self.baseline_metadata = dict(baseline_metadata or {})
        self._active_caller_id: str | None = None
        self._active_payload: dict[str, Any] | None = None
        self._lock = RLock()

    @property
    def active_caller_id(self) -> str | None:
        with self._lock:
            return self._active_caller_id

    def prepare(self, caller_id: str) -> dict[str, Any]:
        """Resolve and publish a complete index, or raise without mutation."""

        payload = self._read_payload(caller_id)
        if payload.get("state") == "baseline":
            loaded = self.baseline_index
        else:
            index_path = self._required_path(payload, "index_path")
            loaded = self.index_loader(index_path, payload)
        with self._lock:
            if self._active_caller_id is not None:
                raise CallRagError("another caller-id already owns the bot index")
            self.target_index.replace_from(loaded)
            self._active_caller_id = caller_id
            self._active_payload = payload
        metadata = payload.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}

    def release(self, caller_id: str | None = None) -> bool:
        """Restore baseline retrieval and remove the published artifact."""

        with self._lock:
            active = self._active_caller_id
            if active is None:
                return False
            if caller_id is not None and caller_id != active:
                return False
            payload = self._active_payload or {}
            self.target_index.replace_from(self.baseline_index)
            self._active_caller_id = None
            self._active_payload = None

        if payload.get("state") != "baseline":
            self._remove_published_files(active, payload)
        return True

    def _read_payload(self, caller_id: str) -> dict[str, Any]:
        if not isinstance(caller_id, str) or self._CALLER_ID.fullmatch(caller_id) is None:
            raise CallRagError("caller-id has an invalid format")
        path = self.registry_root / f"{caller_id}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return self._baseline_fallback(caller_id)
        if not isinstance(payload, dict) or payload.get("state") not in {"ready", "baseline"}:
            return self._baseline_fallback(caller_id)
        if payload.get("caller_id") != caller_id:
            return self._baseline_fallback(caller_id)
        return payload

    def _baseline_fallback(self, caller_id: str) -> dict[str, Any]:
        return {
            "schema_version": "conference-rag-registry-v1",
            "caller_id": caller_id,
            "state": "baseline",
            "metadata": dict(self.baseline_metadata),
            "baseline": True,
        }

    @staticmethod
    def _required_path(payload: dict[str, Any], field: str) -> Path:
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise CallRagError(f"registry field {field!r} is missing")
        path = Path(value)
        if not path.is_file():
            raise CallRagError(f"published {field} is missing")
        return path

    def _remove_published_files(self, caller_id: str, payload: dict[str, Any]) -> None:
        registry_path = self.registry_root / f"{caller_id}.json"
        # The browser may POST call/ended concurrently with SIP terminal
        # cleanup.  Never remove a newer baseline record published by the web
        # session owner while deleting the old custom artifact.
        try:
            current = json.loads(registry_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            current = None
        if (
            isinstance(current, dict)
            and current.get("state") == "ready"
            and current.get("caller_id") == caller_id
            and current.get("artifact_dir") == payload.get("artifact_dir")
        ):
            registry_path.unlink(missing_ok=True)
        value = payload.get("artifact_dir")
        if isinstance(value, str) and value:
            artifact_dir = Path(value)
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)


__all__ = ["CallRagError", "CallScopedRagController"]
