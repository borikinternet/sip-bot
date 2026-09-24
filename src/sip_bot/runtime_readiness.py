"""Runtime-scoped, single-flight readiness coordination.

The coordinator deliberately has no call identity.  A SIP call may request
readiness, but it never owns the warmup operation and cancelling that call
must not cancel the shared runtime preparation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import inspect
from threading import RLock
import time
from typing import Any

from .control.event_bus import ControlEventBus, EventBusClosedError


class RuntimeReadinessState(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RuntimeReadinessEvent:
    """Small control-plane notification; the coordinator remains canonical."""

    runtime_id: str
    state: RuntimeReadinessState
    sequence: int
    timestamp_ns: int
    error_type: str | None = None

    def __post_init__(self) -> None:
        if not self.runtime_id or len(self.runtime_id) > 128:
            raise ValueError("runtime_id must be a non-empty string of at most 128 characters")
        if self.sequence < 1:
            raise ValueError("readiness event sequence must be positive")
        if self.timestamp_ns < 0:
            raise ValueError("readiness event timestamp must not be negative")
        if self.error_type is not None and (not self.error_type or len(self.error_type) > 160):
            raise ValueError("readiness event error_type must be empty or at most 160 characters")


@dataclass(frozen=True, slots=True)
class RuntimeReadinessSnapshot:
    runtime_id: str
    state: RuntimeReadinessState
    sequence: int
    started_at_ns: int | None
    completed_at_ns: int | None
    error_type: str | None
    error_message: str | None


class RuntimeReadinessCoordinator:
    """Own one runtime warmup operation shared by all waiting callers."""

    def __init__(
        self,
        warmup: Callable[[], object],
        *,
        runtime_id: str = "application",
        event_bus: ControlEventBus | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if not callable(warmup):
            raise TypeError("warmup must be callable")
        if not runtime_id or len(runtime_id) > 128:
            raise ValueError("runtime_id must be a non-empty string of at most 128 characters")
        self._warmup = warmup
        self.runtime_id = runtime_id
        self.event_bus = event_bus
        self._clock_ns = clock_ns
        self._lock = RLock()
        self._state = RuntimeReadinessState.NOT_STARTED
        self._sequence = 0
        self._started_at_ns: int | None = None
        self._completed_at_ns: int | None = None
        self._error_type: str | None = None
        self._error_message: str | None = None
        self._report: object | None = None
        self._task: asyncio.Task[object] | None = None
        self._closed = False

    @property
    def state(self) -> RuntimeReadinessState:
        with self._lock:
            return self._state

    @property
    def ready(self) -> bool:
        return self.state is RuntimeReadinessState.READY

    @property
    def warmup_running(self) -> bool:
        return self.state is RuntimeReadinessState.RUNNING

    @property
    def report(self) -> object | None:
        with self._lock:
            return self._report

    @property
    def error_type(self) -> str | None:
        with self._lock:
            return self._error_type

    @property
    def error_message(self) -> str | None:
        with self._lock:
            return self._error_message

    @property
    def task(self) -> asyncio.Task[object] | None:
        with self._lock:
            return self._task

    def snapshot(self) -> RuntimeReadinessSnapshot:
        with self._lock:
            return RuntimeReadinessSnapshot(
                runtime_id=self.runtime_id,
                state=self._state,
                sequence=self._sequence,
                started_at_ns=self._started_at_ns,
                completed_at_ns=self._completed_at_ns,
                error_type=self._error_type,
                error_message=self._error_message,
            )

    def start_background(self) -> asyncio.Task[object] | None:
        """Start the shared operation once; never execute warmup inline."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError("runtime warmup must be triggered from the main asyncio loop") from exc
        with self._lock:
            if self._closed:
                raise RuntimeError("runtime readiness coordinator is closed")
            if self._state is RuntimeReadinessState.READY:
                return None
            if self._state is RuntimeReadinessState.FAILED:
                raise RuntimeWarmupError(f"runtime warmup previously failed: {self._error_type or 'unknown'}")
            if self._state is RuntimeReadinessState.RUNNING:
                return self._task
            self._state = RuntimeReadinessState.RUNNING
            self._sequence += 1
            self._started_at_ns = self._clock_ns()
            self._completed_at_ns = None
            self._error_type = None
            self._error_message = None
            self._report = None
            self._publish_locked()
            task = loop.create_task(self._run(), name=f"runtime-warmup-{self.runtime_id}")
            self._task = task
            return task

    async def ensure_ready(self) -> object:
        """Return the shared result, starting it only when no operation exists."""

        task = self.start_background()
        if task is None:
            report = self.report
            if report is None:
                raise RuntimeWarmupError("runtime readiness is READY without a warmup report")
            return report
        # A cancelled incoming call must not cancel the process-wide warmup.
        return await asyncio.shield(task)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            task = self._task
            self._task = None
        if task is not None and not task.done():
            task.cancel()

    async def _run(self) -> object:
        try:
            result = await asyncio.to_thread(self._warmup)
            if inspect.isawaitable(result):
                result = await result
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            with self._lock:
                self._state = RuntimeReadinessState.FAILED
                self._sequence += 1
                self._completed_at_ns = self._clock_ns()
                self._error_type = type(exc).__name__
                self._error_message = str(exc)[:512] or None
                self._report = None
                self._task = None
                self._publish_locked()
            raise RuntimeWarmupError(f"runtime warmup failed: {exc}") from exc
        with self._lock:
            if self._closed:
                self._task = None
                return result
            self._state = RuntimeReadinessState.READY
            self._sequence += 1
            self._completed_at_ns = self._clock_ns()
            self._error_type = None
            self._report = result
            self._task = None
            self._publish_locked()
        return result

    def _publish_locked(self) -> None:
        if self.event_bus is None:
            return
        event = RuntimeReadinessEvent(
            runtime_id=self.runtime_id,
            state=self._state,
            sequence=self._sequence,
            timestamp_ns=self._clock_ns(),
            error_type=self._error_type,
        )
        try:
            self.event_bus.publish(event)
        except EventBusClosedError:
            # The state/snapshot is authoritative; a closed observer bus must
            # not turn a successful warmup into a failed runtime.
            return


class RuntimeWarmupError(RuntimeError):
    """Raised when the shared runtime readiness operation fails."""


__all__ = [
    "RuntimeReadinessCoordinator",
    "RuntimeReadinessEvent",
    "RuntimeReadinessSnapshot",
    "RuntimeReadinessState",
    "RuntimeWarmupError",
]
