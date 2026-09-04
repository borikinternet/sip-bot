"""One-call and one-way channel lifecycle ownership."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock

from .events import ControlEvent


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation violates the one-way contract."""


class CallState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ChannelState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class CancelToken:
    """Thread-safe, idempotent cancellation marker for one scoped operation."""

    __slots__ = ("_cancelled", "_lock")

    def __init__(self) -> None:
        self._cancelled = False
        self._lock = RLock()

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def cancel(self) -> bool:
        with self._lock:
            if self._cancelled:
                return False
            self._cancelled = True
            return True


@dataclass(frozen=True, slots=True)
class ChannelLease:
    call_id: str
    channel_id: str
    generation: int


class ChannelHandle:
    """A non-reopenable scoped control-channel handle.

    A new generation gets a new handle.  The old handle can never dispatch a
    control event after close, which is the stale-result guard for this slice.
    """

    __slots__ = (
        "_close_reason",
        "_lock",
        "_state",
        "call_id",
        "cancel_token",
        "channel_id",
        "channel_kind",
        "generation",
    )

    def __init__(self, call_id: str, channel_id: str, channel_kind: str, generation: int) -> None:
        self.call_id = call_id
        self.channel_id = channel_id
        self.channel_kind = channel_kind
        self.generation = generation
        self.cancel_token = CancelToken()
        self._state = ChannelState.OPEN
        self._lock = RLock()
        self._close_reason: str | None = None

    @property
    def state(self) -> ChannelState:
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state is ChannelState.OPEN

    @property
    def close_reason(self) -> str | None:
        with self._lock:
            return self._close_reason

    def lease(self) -> ChannelLease:
        return ChannelLease(self.call_id, self.channel_id, self.generation)

    def close(self, reason: str) -> bool:
        if not reason or len(reason) > 160:
            raise ValueError("reason must be a non-empty string of at most 160 characters")
        with self._lock:
            if self._state is ChannelState.CLOSED:
                return False
            self._state = ChannelState.CLOSED
            self._close_reason = reason
            self.cancel_token.cancel()
            return True

    def accepts(self, event: ControlEvent) -> bool:
        with self._lock:
            return (
                self._state is ChannelState.OPEN
                and event.is_channel_scoped
                and event.call_id == self.call_id
                and event.channel_id == self.channel_id
                and event.channel_generation == self.generation
            )

    def dispatch(self, event: ControlEvent, consumer: Callable[[ControlEvent], None]) -> bool:
        """Deliver only a current event; return false for stale/closed input.

        The callback runs under the re-entrant channel gate, so close and
        delivery have a deterministic linearization point without introducing
        an unbounded queue or moving payload through the control boundary.
        """

        with self._lock:
            if not self.accepts(event):
                return False
            consumer(event)
            return True


class CallScope:
    """Owner of all channel handles belonging to one call."""

    __slots__ = ("_cancel_token", "_channels", "_generations", "_lock", "_state", "call_id")

    def __init__(self, call_id: str) -> None:
        if not call_id or len(call_id) > 128:
            raise ValueError("call_id must be a non-empty string of at most 128 characters")
        self.call_id = call_id
        self._state = CallState.OPEN
        self._cancel_token = CancelToken()
        self._channels: dict[str, ChannelHandle] = {}
        self._generations: dict[str, int] = {}
        self._lock = RLock()

    @property
    def state(self) -> CallState:
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state is CallState.OPEN

    @property
    def cancel_token(self) -> CancelToken:
        return self._cancel_token

    def open_channel(self, channel_id: str, channel_kind: str) -> ChannelHandle:
        if not channel_id or len(channel_id) > 128:
            raise ValueError("channel_id must be a non-empty string of at most 128 characters")
        if not channel_kind or len(channel_kind) > 128:
            raise ValueError("channel_kind must be a non-empty string of at most 128 characters")
        with self._lock:
            if self._state is CallState.CLOSED:
                raise LifecycleError("cannot open a channel on a closed call")
            current = self._channels.get(channel_id)
            if current is not None and current.is_open:
                raise LifecycleError(f"channel is already open: {channel_id}")
            generation = self._generations.get(channel_id, 0) + 1
            handle = ChannelHandle(self.call_id, channel_id, channel_kind, generation)
            self._generations[channel_id] = generation
            self._channels[channel_id] = handle
            return handle

    def get_channel(self, channel_id: str) -> ChannelHandle:
        with self._lock:
            try:
                return self._channels[channel_id]
            except KeyError as exc:
                raise LifecycleError(f"unknown channel: {channel_id}") from exc

    def channels(self, *, open_only: bool = False) -> tuple[ChannelHandle, ...]:
        """Return a stable snapshot for channel orchestration and diagnostics."""

        with self._lock:
            values = tuple(self._channels.values())
        return tuple(handle for handle in values if handle.is_open) if open_only else values

    def close_channel(self, channel_id: str, reason: str) -> tuple[ChannelHandle, bool]:
        handle = self.get_channel(channel_id)
        return handle, handle.close(reason)

    def close(self, reason: str) -> tuple[ChannelHandle, ...]:
        if not reason or len(reason) > 160:
            raise ValueError("reason must be a non-empty string of at most 160 characters")
        with self._lock:
            if self._state is CallState.CLOSED:
                return ()
            closed_channels = tuple(handle for handle in self._channels.values() if handle.is_open)
            for handle in closed_channels:
                handle.close(reason)
            self._state = CallState.CLOSED
            self._cancel_token.cancel()
            return closed_channels


class LifecycleRegistry:
    """Registry enforcing one active call and non-reused call identities."""

    __slots__ = ("_active", "_calls", "_lock")

    def __init__(self) -> None:
        self._active: CallScope | None = None
        self._calls: dict[str, CallScope] = {}
        self._lock = RLock()

    @property
    def active_call(self) -> CallScope | None:
        with self._lock:
            return self._active

    def open_call(self, call_id: str) -> CallScope:
        with self._lock:
            if not call_id or len(call_id) > 128:
                raise ValueError("call_id must be a non-empty string of at most 128 characters")
            if self._active is not None and self._active.is_open:
                raise LifecycleError("MVP runtime permits only one active call")
            if call_id in self._calls:
                raise LifecycleError(f"call identity cannot be reused: {call_id}")
            scope = CallScope(call_id)
            self._calls[call_id] = scope
            self._active = scope
            return scope

    def get_call(self, call_id: str) -> CallScope:
        with self._lock:
            try:
                return self._calls[call_id]
            except KeyError as exc:
                raise LifecycleError(f"unknown call: {call_id}") from exc
