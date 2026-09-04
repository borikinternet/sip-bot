"""Process-local, bounded control-plane event fan-out.

The bus deliberately accepts only small control values.  Audio bytes, PCM
frames, and other data-plane payloads must use their specialised channels.
Publishing is always non-blocking: a slow subscriber loses the newest event
and exposes that loss through :class:`DeliveryReport` and counters.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, fields, is_dataclass
from queue import Empty, Full, Queue
from threading import RLock
from typing import Any

_CLOSE_SENTINEL = object()


class EventBusClosedError(RuntimeError):
    """Raised when an operation is attempted on a closed bus."""


class SubscriptionClosedError(RuntimeError):
    """Raised when a closed subscription is read or used."""


class ControlPayloadError(TypeError):
    """Raised when a data-plane payload is submitted to the control bus."""


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    """Result of one non-blocking publication."""

    delivered: int
    dropped: int
    subscribers: int

    def __bool__(self) -> bool:
        return self.dropped == 0


def _validate_control_value(value: Any, *, text_limit: int, seen: set[int] | None = None) -> None:
    """Reject bytes and unbounded text recursively without requiring a base class."""

    if getattr(value, "__data_plane__", False):
        raise ControlPayloadError("data-plane payloads are not allowed on the control event bus")
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ControlPayloadError("audio and binary payloads are not allowed on the control event bus")
    if isinstance(value, str) and len(value) > text_limit:
        raise ControlPayloadError(f"control text exceeds the {text_limit}-character limit")
    if value is None or isinstance(value, (int, float, bool, str, type, bytes)):
        return
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    if is_dataclass(value):
        for field in fields(value):
            _validate_control_value(getattr(value, field.name), text_limit=text_limit, seen=seen)
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_control_value(key, text_limit=text_limit, seen=seen)
            _validate_control_value(item, text_limit=text_limit, seen=seen)
    elif isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            _validate_control_value(item, text_limit=text_limit, seen=seen)


class ControlSubscription:
    """A bounded FIFO subscription with explicit close/unsubscribe semantics."""

    __slots__ = ("_closed", "_dropped", "_lock", "_predicate", "_queue", "call_id", "subscription_id")

    def __init__(
        self,
        subscription_id: int,
        capacity: int,
        *,
        call_id: str | None = None,
        predicate: Callable[[Any], bool] | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("subscription capacity must be positive")
        self.subscription_id = subscription_id
        self.call_id = call_id
        self._queue: Queue[Any] = Queue(maxsize=capacity)
        self._predicate = predicate
        self._lock = RLock()
        self._closed = False
        self._dropped = 0

    @property
    def capacity(self) -> int:
        return self._queue.maxsize

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def matches(self, event: Any) -> bool:
        if self.call_id is not None and getattr(event, "call_id", None) != self.call_id:
            return False
        return self._predicate(event) if self._predicate is not None else True

    def _offer(self, event: Any) -> bool:
        with self._lock:
            if self._closed:
                return False
            try:
                self._queue.put_nowait(event)
            except Full:
                self._dropped += 1
                return False
            return True

    def get_nowait(self) -> Any:
        with self._lock:
            if self._closed:
                raise SubscriptionClosedError("subscription is closed")
        return self._queue.get_nowait()

    def get(self, timeout: float | None = None) -> Any:
        with self._lock:
            if self._closed:
                raise SubscriptionClosedError("subscription is closed")
        item = self._queue.get(timeout=timeout)
        if item is _CLOSE_SENTINEL:
            raise SubscriptionClosedError("subscription is closed")
        return item

    def drain(self, limit: int | None = None) -> list[Any]:
        result: list[Any] = []
        while limit is None or len(result) < limit:
            try:
                result.append(self.get_nowait())
            except Empty:
                return result
        return result

    def close(self) -> None:
        with self._lock:
            self._closed = True
            while True:
                try:
                    self._queue.get_nowait()
                except Empty:
                    break
            # Wake a consumer blocked in get().  A closed subscription still
            # rejects all subsequent reads before this marker is observed.
            self._queue.put_nowait(_CLOSE_SENTINEL)

    def __iter__(self) -> Iterator[Any]:
        while not self.closed:
            try:
                yield self.get()
            except (SubscriptionClosedError, Empty):
                return


class ControlEventBus:
    """Thread-safe process-local control event bus.

    ``publish`` never waits for a subscriber.  ``close_call`` is useful during
    terminal/re-entry handling and closes all scoped subscriptions atomically.
    """

    __slots__ = ("_closed", "_dropped", "_lock", "_next_id", "_subscriptions", "capacity", "text_limit")

    def __init__(self, capacity: int = 256, *, text_limit: int = 4096) -> None:
        if capacity < 1:
            raise ValueError("bus capacity must be positive")
        if text_limit < 1:
            raise ValueError("text_limit must be positive")
        self.capacity = capacity
        self.text_limit = text_limit
        self._lock = RLock()
        self._closed = False
        self._next_id = 0
        self._subscriptions: dict[int, ControlSubscription] = {}
        self._dropped = 0

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def subscribe(
        self,
        *,
        call_id: str | None = None,
        predicate: Callable[[Any], bool] | None = None,
        capacity: int | None = None,
    ) -> ControlSubscription:
        with self._lock:
            if self._closed:
                raise EventBusClosedError("event bus is closed")
            self._next_id += 1
            subscription = ControlSubscription(
                self._next_id,
                self.capacity if capacity is None else capacity,
                call_id=call_id,
                predicate=predicate,
            )
            self._subscriptions[subscription.subscription_id] = subscription
            return subscription

    def unsubscribe(self, subscription: ControlSubscription | int) -> bool:
        subscription_id = subscription if isinstance(subscription, int) else subscription.subscription_id
        with self._lock:
            current = self._subscriptions.pop(subscription_id, None)
        if current is None:
            return False
        current.close()
        return True

    def publish(self, event: Any) -> DeliveryReport:
        if not is_dataclass(event):
            if isinstance(event, (bytes, bytearray, memoryview)):
                raise ControlPayloadError("audio and binary payloads are not allowed on the control event bus")
            raise ControlPayloadError("control bus accepts typed dataclass events only; text payload is not an event")
        if getattr(event, "__data_plane__", False):
            raise ControlPayloadError("data-plane payloads are not allowed on the control event bus")
        _validate_control_value(event, text_limit=self.text_limit)
        with self._lock:
            if self._closed:
                raise EventBusClosedError("event bus is closed")
            subscriptions = tuple(self._subscriptions.values())
        delivered = 0
        dropped = 0
        for subscription in subscriptions:
            if not subscription.matches(event):
                continue
            if subscription._offer(event):
                delivered += 1
            else:
                dropped += 1
        if dropped:
            with self._lock:
                self._dropped += dropped
        return DeliveryReport(delivered, dropped, len(subscriptions))

    def close_call(self, call_id: str) -> int:
        with self._lock:
            selected = [s for s in self._subscriptions.values() if s.call_id == call_id]
            for subscription in selected:
                self._subscriptions.pop(subscription.subscription_id, None)
        for subscription in selected:
            subscription.close()
        return len(selected)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            subscriptions = tuple(self._subscriptions.values())
            self._subscriptions.clear()
        for subscription in subscriptions:
            subscription.close()


_DEFAULT_BUS: ControlEventBus | None = None
_DEFAULT_BUS_LOCK = RLock()


def get_control_event_bus() -> ControlEventBus:
    """Return the process-local singleton used by the MVP runtime."""

    global _DEFAULT_BUS
    with _DEFAULT_BUS_LOCK:
        if _DEFAULT_BUS is None or _DEFAULT_BUS.closed:
            _DEFAULT_BUS = ControlEventBus()
        return _DEFAULT_BUS


def reset_control_event_bus() -> None:
    """Close and forget the singleton; intended for deterministic tests."""

    global _DEFAULT_BUS
    with _DEFAULT_BUS_LOCK:
        if _DEFAULT_BUS is not None:
            _DEFAULT_BUS.close()
        _DEFAULT_BUS = None


EventBus = ControlEventBus
Subscription = ControlSubscription
