"""Non-blocking serialized dispatcher for control-plane events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread
from typing import TYPE_CHECKING, Any, Protocol

from .event_bus import ControlEventBus, ControlSubscription, get_control_event_bus
from .events import ControlEvent, ControlEventKind
from .lifecycle import CallScope, CallState, CancelToken, ChannelHandle, LifecycleError

if TYPE_CHECKING:
    from ..dialogue.events import PlaybackEvent, SpeechEvent, StructuredDecision, TransferResult
    from ..sip_media.protocol_events import NormalizedSipEvent, SipEventKind

    DialogueControlMessage = NormalizedSipEvent | SpeechEvent | StructuredDecision | PlaybackEvent | TransferResult
    ControlMessage = ControlEvent | DialogueControlMessage
else:
    # Runtime classes are resolved lazily below to avoid the existing
    # sip_media -> runtime -> control package import cycle.
    DialogueControlMessage = Any
    ControlMessage = Any


def _control_message_types() -> tuple[type[Any], ...]:
    from ..dialogue.events import PlaybackEvent, SpeechEvent, StructuredDecision, TransferResult
    from ..sip_media.protocol_events import NormalizedSipEvent

    return (ControlEvent, NormalizedSipEvent, SpeechEvent, StructuredDecision, PlaybackEvent, TransferResult)


def _is_control_message(value: object) -> bool:
    return isinstance(value, _control_message_types())


def _is_call_started(value: object) -> bool:
    from ..sip_media.protocol_events import NormalizedSipEvent, SipEventKind

    return isinstance(value, NormalizedSipEvent) and value.kind is SipEventKind.CALL_STARTED


@dataclass(frozen=True, slots=True)
class DispatcherStats:
    submitted: int
    processed: int
    rejected: int
    handler_errors: int


class SessionComponent(Protocol):
    """Minimal lifecycle hook for a component owned by one call session."""

    def close(self, reason: str) -> None:
        """Stop the component's session-scoped resources without blocking."""


class EventHandler(Protocol):
    """Typed owner boundary used by Dispatcher and CallSession."""

    def handle(self, event: object) -> None:
        """Handle one already-validated event without blocking."""


@dataclass(frozen=True, slots=True)
class SessionBindings:
    """Named per-call owners held by ``CallSession``.

    The bindings are references only: each component keeps ownership of its
    own data and behavior.  ``CallSession`` uses them to coordinate lifecycle
    and never routes their audio, text, or stream payload through Dispatcher.
    """

    sip_media: object | None = None
    speech: object | None = None
    context: object | None = None
    retrieval: object | None = None
    prompt: object | None = None
    llm: object | None = None
    tts: object | None = None
    transfer: object | None = None
    report: object | None = None


@dataclass(frozen=True, slots=True)
class SessionLease:
    """Typed identity carried by direct data-plane producers/consumers."""

    call_id: str
    generation: int

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ValueError("session lease call_id must be non-empty")
        if self.generation < 1:
            raise ValueError("session lease generation must be positive")


class CallSession:
    """Per-call composition object around an existing FSM and call scope.

    The session owns only composition/lifecycle identity.  It does not make
    dialogue decisions and intentionally exposes no method for moving audio,
    text, or other large payloads through the Dispatcher.
    """

    __slots__ = (
        "_closed_callback",
        "_components",
        "_bindings",
        "_generation",
        "_fsm_lock",
        "_lock",
        "_scope",
        "_control_opened",
        "call_id",
        "fsm",
    )

    def __init__(
        self,
        call_id: str,
        fsm: EventHandler,
        *,
        generation: int,
        scope: CallScope | None = None,
        components: tuple[SessionComponent, ...] = (),
        bindings: SessionBindings | None = None,
        closed_callback: Callable[["CallSession"], None] | None = None,
    ) -> None:
        if not call_id or len(call_id) > 128:
            raise ValueError("call_id must be a non-empty string of at most 128 characters")
        if generation < 1:
            raise ValueError("session generation must be positive")
        if not hasattr(fsm, "handle"):
            raise TypeError("session FSM must provide handle(event)")
        self.call_id = call_id
        self.fsm = fsm
        self._generation = generation
        self._scope = scope or CallScope(call_id)
        if self._scope.call_id != call_id:
            raise ValueError("session scope call_id must match session call_id")
        bind_scope = getattr(fsm, "bind_scope", None)
        if bind_scope is not None:
            if not callable(bind_scope):
                raise TypeError("session FSM bind_scope must be callable")
            bind_scope(self._scope)
        self._components = components
        self._bindings = bindings or SessionBindings()
        self._closed_callback = closed_callback
        self._fsm_lock = RLock()
        self._lock = RLock()
        self._control_opened = False

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def scope(self) -> CallScope:
        return self._scope

    @property
    def bindings(self) -> SessionBindings:
        return self._bindings

    @property
    def cancel_token(self) -> CancelToken:
        return self._scope.cancel_token

    @property
    def state(self) -> CallState:
        return self._scope.state

    @property
    def is_open(self) -> bool:
        return self._scope.is_open

    def lease(self) -> SessionLease:
        return SessionLease(self.call_id, self.generation)

    def accepts(self, lease: SessionLease) -> bool:
        """Return whether a direct data-plane producer still targets this session."""

        return self.is_open and lease == self.lease()

    def open_channel(self, channel_id: str, channel_kind: str) -> ChannelHandle:
        """Open a typed session-scoped control handle; payload stays direct."""

        return self._scope.open_channel(channel_id, channel_kind)

    def dispatch_control(self, event: ControlMessage) -> bool:
        """Route only a typed control event to the existing FSM.

        This method is deliberately not a generic payload router.  Audio,
        text, and stream objects must use their direct data-plane channels.
        """

        if not _is_control_message(event):
            raise TypeError("CallSession control route accepts typed control messages only")
        with self._fsm_lock:
            if event.call_id != self.call_id or not self.is_open:
                return False
            if isinstance(event, ControlEvent) and event.kind is ControlEventKind.CALL_OPEN:
                if self._control_opened:
                    return True
                self._control_opened = True
            elif _is_call_started(event):
                if self._control_opened:
                    return True
                self._control_opened = True
            self.fsm.handle(event)
            if isinstance(event, ControlEvent) and event.kind in {ControlEventKind.CALL_CLOSE, ControlEventKind.TERMINAL}:
                self.close(event.payload.reason)
            elif getattr(self.fsm, "is_terminal", False):
                reason = getattr(event, "reason", None) or getattr(getattr(event, "kind", None), "value", None)
                self.close(str(reason or "dialogue_terminal"))
            return True

    def dispatch_data(self, lease: SessionLease, consumer: Callable[[], None]) -> bool:
        """Run a direct-payload consumer serialized with control transitions.

        The payload itself never enters Dispatcher.  The short callback only
        updates its direct owner and, when needed, the existing FSM; long
        retrieval/inference/TTS work must be started after this handoff.
        """

        if not isinstance(lease, SessionLease):
            raise TypeError("direct data route requires SessionLease")
        if not callable(consumer):
            raise TypeError("direct data consumer must be callable")
        with self._fsm_lock:
            if not self.accepts(lease):
                return False
            consumer()
            return True

    def close(self, reason: str) -> bool:
        """Close the session and all owned hooks exactly once."""

        with self._lock:
            if not self.is_open:
                return False
            self._scope.close(reason)
            components = self._components
            self._components = ()
            callback = self._closed_callback
            self._closed_callback = None
        for component in components:
            component.close(reason)
        if callback is not None:
            callback(self)
        return True


class Dispatcher:
    """Serialize FSM mutations while keeping publishers non-blocking.

    The handler is expected to be a fast state transition.  Inference, SIP
    waits, TTS and ASR work return later as events and are never called here.
    """

    __slots__ = (
        "_handler_errors",
        "_lock",
        "_closed_call_ids",
        "_active_session",
        "_session_generation",
        "_processed",
        "_queue",
        "_rejected",
        "_stop",
        "_submitted",
        "_subscription",
        "_thread",
        "bus",
        "capacity",
        "fsm",
        "on_error",
    )

    def __init__(
        self,
        fsm: EventHandler,
        *,
        bus: ControlEventBus | None = None,
        capacity: int = 256,
        on_error: Callable[[BaseException, Any], None] | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("dispatcher capacity must be positive")
        self.fsm = fsm
        self.bus = bus or get_control_event_bus()
        self.capacity = capacity
        self._queue: Queue[Any] = Queue(maxsize=capacity)
        self._lock = RLock()
        self._closed_call_ids: set[str] = set()
        self._active_session: CallSession | None = None
        self._session_generation = 0
        self._stop = Event()
        self._thread: Thread | None = None
        self._subscription: ControlSubscription | None = None
        self._submitted = self._processed = self._rejected = self._handler_errors = 0
        self.on_error = on_error

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stats(self) -> DispatcherStats:
        with self._lock:
            return DispatcherStats(self._submitted, self._processed, self._rejected, self._handler_errors)

    @property
    def active_session(self) -> CallSession | None:
        """Return the current session, or ``None`` when the slot is free."""

        with self._lock:
            session = self._active_session
            return session if session is not None and session.is_open else None

    def open_session(
        self,
        call_id: str,
        *,
        fsm: EventHandler | None = None,
        scope: CallScope | None = None,
        components: tuple[SessionComponent, ...] = (),
        bindings: SessionBindings | None = None,
    ) -> CallSession:
        """Create the single active per-call composition object."""

        with self._lock:
            active = self._active_session
            if active is not None and active.is_open:
                raise LifecycleError("MVP dispatcher permits only one active call")
            if call_id in self._closed_call_ids:
                raise LifecycleError(f"call identity cannot be reused: {call_id}")
            self._session_generation += 1
            session = CallSession(
                call_id,
                self.fsm if fsm is None else fsm,
                generation=self._session_generation,
                scope=scope,
                components=components,
                bindings=bindings,
                closed_callback=self._on_session_closed,
            )
            self._active_session = session
            return session

    def close_session(self, reason: str) -> bool:
        """Close the active session without waiting for inference or SIP."""

        session = self.active_session
        return session.close(reason) if session is not None else False

    def _on_session_closed(self, session: CallSession) -> None:
        with self._lock:
            self._closed_call_ids.add(session.call_id)

    def _process_control_message(self, event: ControlMessage) -> None:
        session = self.active_session
        if isinstance(event, ControlEvent) and event.kind is ControlEventKind.CALL_OPEN:
            if event.call_id in self._closed_call_ids:
                return
            if session is not None:
                if session.call_id == event.call_id:
                    session.dispatch_control(event)
                    return
                raise LifecycleError("MVP dispatcher permits only one active call")
            session = self.open_session(event.call_id)
            session.dispatch_control(event)
            return
        if session is None:
            if event.call_id in self._closed_call_ids:
                return
            if _is_call_started(event):
                session = self.open_session(event.call_id)
                session.dispatch_control(event)
            else:
                self.fsm.handle(event)
            return
        if event.call_id != session.call_id:
            if event.call_id in self._closed_call_ids:
                return
            raise LifecycleError("control event call_id does not match active session")
        session.dispatch_control(event)

    def submit(self, event: Any) -> bool:
        """Queue an event without waiting; return false when bounded queue is full."""

        # Once application composition owns an active call, payload events
        # must use their direct data-plane channel.  Keep the old generic
        # handler behavior for a Dispatcher that has not entered session mode.
        if self.active_session is not None and not _is_control_message(event):
            with self._lock:
                self._rejected += 1
            return False
        try:
            self._queue.put_nowait(event)
        except Full:
            with self._lock:
                self._rejected += 1
            return False
        with self._lock:
            self._submitted += 1
        return True

    publish = submit
    dispatch = submit

    def process_one(self) -> bool:
        try:
            event = self._queue.get_nowait()
        except Empty:
            return False
        try:
            if _is_control_message(event):
                self._process_control_message(event)
            elif self.active_session is not None:
                # Covers a race where a legacy event was queued before the
                # session opened.  It cannot cross the control boundary.
                with self._lock:
                    self._rejected += 1
            else:
                self.fsm.handle(event)
        except BaseException as exc:
            with self._lock:
                self._handler_errors += 1
            if self.on_error is not None:
                self.on_error(exc, event)
            else:
                raise
        finally:
            with self._lock:
                self._processed += 1
        return True

    def drain(self, limit: int | None = None) -> int:
        processed = 0
        while limit is None or processed < limit:
            if not self.process_one():
                break
            processed += 1
        return processed

    def attach(self, *, call_id: str | None = None, capacity: int | None = None) -> ControlSubscription:
        """Subscribe to a bus and enqueue received events via ``pump``."""

        if self._subscription is not None:
            raise RuntimeError("dispatcher is already attached")
        self._subscription = self.bus.subscribe(call_id=call_id, capacity=capacity)
        return self._subscription

    def pump(self, limit: int | None = None) -> int:
        """Move at most ``limit`` bus events to the local dispatcher queue."""

        if self._subscription is None:
            return 0
        moved = 0
        for event in self._subscription.drain(limit):
            if self.submit(event):
                moved += 1
        return moved

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="sip-bot-dispatcher", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.pump()
            if not self.process_one():
                self._stop.wait(0.001)

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.0, timeout))
        self._thread = None
        if self._subscription is not None:
            self.bus.unsubscribe(self._subscription)
            self._subscription = None
