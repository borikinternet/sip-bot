"""Specialized bounded PCM fan-out for direct data-plane consumers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock

from .types import PcmFrame


@dataclass(slots=True)
class FanOutStats:
    """Observable delivery counters; audio payload is never retained here."""

    published: int = 0
    delivered: int = 0
    dropped_overflow: int = 0
    dropped_stale: int = 0
    dropped_closed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {field: int(getattr(self, field)) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Per-publish outcome without exposing control-plane events."""

    accepted: bool
    delivered_to: tuple[str, ...] = ()
    overflowed: tuple[str, ...] = ()
    stale_for: tuple[str, ...] = ()
    closed_for: tuple[str, ...] = ()


class PcmFanOutSubscription:
    """One independent bounded consumer channel owned by ``PcmFanOut``."""

    def __init__(self, owner: "PcmFanOut", name: str, capacity: int) -> None:
        self._owner = owner
        self.name = name
        self.capacity = capacity
        self._frames: deque[PcmFrame] = deque()
        self._closed = False
        self._lock = RLock()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def get_nowait(self) -> PcmFrame | None:
        with self._lock:
            if not self._frames:
                return None
            return self._frames.popleft()

    def qsize(self) -> int:
        with self._lock:
            return len(self._frames)

    def close(self) -> bool:
        return self._owner.close_subscription(self.name)

    def _put(self, frame: PcmFrame) -> bool:
        with self._lock:
            if self._closed or len(self._frames) >= self.capacity:
                return False
            self._frames.append(frame)
            return True

    def _close(self) -> None:
        with self._lock:
            self._frames.clear()
            self._closed = True


class PcmFanOut:
    """Fan out each PCM frame into independent bounded non-blocking queues.

    The ingress producer never waits for a consumer.  A slow consumer loses
    only its own frame, while the other subscriptions continue receiving data.
    """

    def __init__(self, *, capacity_frames: int, generation: int | None = None) -> None:
        if capacity_frames < 1:
            raise ValueError("capacity_frames must be positive")
        if generation is not None and generation < 1:
            raise ValueError("generation must be positive")
        self.capacity_frames = capacity_frames
        self.generation = generation
        self.stats = FanOutStats()
        self._subscriptions: dict[str, PcmFanOutSubscription] = {}
        self._closed = False
        self._lock = RLock()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def subscribe(self, name: str) -> PcmFanOutSubscription:
        if not name:
            raise ValueError("subscription name must be non-empty")
        with self._lock:
            if self._closed:
                raise RuntimeError("fan-out is closed")
            if name in self._subscriptions:
                raise ValueError(f"subscription already exists: {name!r}")
            subscription = PcmFanOutSubscription(self, name, self.capacity_frames)
            self._subscriptions[name] = subscription
            return subscription

    def close_subscription(self, name: str) -> bool:
        with self._lock:
            subscription = self._subscriptions.get(name)
            if subscription is None or subscription.closed:
                return False
            subscription._close()
            return True

    def publish(self, frame: PcmFrame) -> PublishResult:
        if not isinstance(frame, PcmFrame):
            raise TypeError("fan-out accepts PcmFrame only")
        with self._lock:
            if self._closed:
                self.stats.dropped_closed += 1
                return PublishResult(False, closed_for=tuple(self._subscriptions))
            self.stats.published += 1
            delivered: list[str] = []
            overflowed: list[str] = []
            stale: list[str] = []
            closed: list[str] = []
            for name, subscription in self._subscriptions.items():
                if subscription.closed:
                    closed.append(name)
                    self.stats.dropped_closed += 1
                elif self.generation is not None and frame.generation != self.generation:
                    stale.append(name)
                    self.stats.dropped_stale += 1
                elif subscription._put(frame):
                    delivered.append(name)
                    self.stats.delivered += 1
                else:
                    overflowed.append(name)
                    self.stats.dropped_overflow += 1
            return PublishResult(
                bool(delivered),
                tuple(delivered),
                tuple(overflowed),
                tuple(stale),
                tuple(closed),
            )

    def close(self) -> bool:
        with self._lock:
            if self._closed:
                return False
            self._closed = True
            for subscription in self._subscriptions.values():
                subscription._close()
            return True


__all__ = ["FanOutStats", "PcmFanOut", "PcmFanOutSubscription", "PublishResult"]
