"""Typed session and RAG lifecycle values for the conference demo."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import Any


MAX_UPLOAD_BYTES = 640 * 1024
HEARTBEAT_INTERVAL_SECONDS = 5.0
HEARTBEAT_TIMEOUT_SECONDS = 15.0
PRE_ANSWER_RAG_TIMEOUT_SECONDS = 15.0


class SessionState(StrEnum):
    BASELINE = "baseline"
    PREPARING = "preparing"
    READY = "ready"
    ACTIVE_CALL = "active_call"
    FAILED = "failed"
    STALE = "stale"


@dataclass(slots=True)
class WebSession:
    session_id: str
    caller_id: str
    state: SessionState = SessionState.BASELINE
    created_at: float = field(default_factory=monotonic)
    last_heartbeat: float = field(default_factory=monotonic)
    metadata: dict[str, Any] | None = None
    artifact_dir: Path | None = None
    error: str | None = None
    active_call: bool = False
    websocket_count: int = 0
    sockets: set[Any] = field(default_factory=set, repr=False)


def state_is_call_enabled(state: SessionState) -> bool:
    return state in {SessionState.BASELINE, SessionState.READY}
