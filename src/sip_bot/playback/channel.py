"""Cancellable direct media playback channel with generation isolation."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from time import monotonic_ns

from sip_bot.sip_media.models import PcmFrame
from sip_bot.tts.media_pacer import MediaPacer

from .contracts import PlaybackCloseReason, PlaybackEvent, PlaybackEventKind


class PlaybackChannel:
    """Own one non-reusable playback generation.

    ``send_frame`` is the direct data-plane egress callback.  It must be
    short/non-blocking; no Dispatcher or control bus is involved.
    """

    def __init__(
        self,
        *,
        call_id: str,
        channel_id: str,
        generation: int,
        pacer: MediaPacer,
        send_frame: Callable[[PcmFrame], None],
        on_event: Callable[[PlaybackEvent], None] | None = None,
        cancel_producer: Callable[[str], None] | None = None,
        clock_ns: Callable[[], int] = monotonic_ns,
    ) -> None:
        if not call_id or not channel_id or generation < 1:
            raise ValueError("playback channel identity is required")
        self.call_id = call_id
        self.channel_id = channel_id
        self.generation = generation
        self.pacer = pacer
        self.send_frame = send_frame
        self.on_event = on_event
        self.cancel_producer = cancel_producer
        self.clock_ns = clock_ns
        self._closed = False
        self._started = False
        self._lock = RLock()
        self.events: list[PlaybackEvent] = []

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def open(self) -> PlaybackEvent:
        with self._lock:
            return self._emit_locked(PlaybackEventKind.OPENED)

    def pump(self, now_ns: int | None = None) -> PcmFrame | None:
        """Deliver at most one ready frame without waiting on the producer."""
        with self._lock:
            if self._closed:
                return None
            frame = self.pacer.next_ready(now_ns)
            if frame is None:
                return None
            if not self._matches(frame):
                self._emit_locked(PlaybackEventKind.STALE_DROPPED, sequence=frame.sequence)
                return None
            if not self._started:
                self._started = True
                self._emit_locked(PlaybackEventKind.STARTED)
            try:
                self.send_frame(frame)
            except Exception:
                self._emit_locked(PlaybackEventKind.FAILED, reason="egress_failed", sequence=frame.sequence)
                self._close_locked(PlaybackCloseReason.FAILED)
                raise
            self._emit_locked(PlaybackEventKind.FRAME_SENT, sequence=frame.sequence)
            return frame

    def submit(self, frame: PcmFrame) -> bool:
        """Accept a paced frame; stale/closed frames are silently dropped."""
        with self._lock:
            if self._closed or not self._matches(frame):
                self._emit_locked(PlaybackEventKind.STALE_DROPPED, sequence=getattr(frame, "sequence", None))
                return False
            # The pacer owns ordering.  A direct submit is intentionally not
            # supported because it would bypass media-clock pacing.
            raise TypeError("submit is not a direct egress API; push into the output boundary")

    def close(self, reason: PlaybackCloseReason | str = PlaybackCloseReason.COMPLETED) -> bool:
        with self._lock:
            if self._closed:
                return False
            self._close_locked(PlaybackCloseReason(reason))
            return True

    def cancel(self, reason: str = "cancelled") -> bool:
        with self._lock:
            if self._closed:
                return False
            self.pacer.output.cancel()
            if self.cancel_producer is not None:
                self.cancel_producer(reason)
            self._close_locked(PlaybackCloseReason.CANCELLED, reason_text=reason)
            return True

    def barge_in(self) -> bool:
        return self.cancel(reason=PlaybackCloseReason.BARGE_IN.value)

    def _matches(self, frame: PcmFrame) -> bool:
        return (isinstance(frame, PcmFrame) and frame.call_id == self.call_id
                and frame.channel_id == self.channel_id and frame.generation == self.generation)

    def _close_locked(self, reason: PlaybackCloseReason, *, reason_text: str = "") -> None:
        self._closed = True
        self.pacer.output.cancel()
        self._emit_locked(
            PlaybackEventKind.CANCELLED if reason in {PlaybackCloseReason.CANCELLED, PlaybackCloseReason.BARGE_IN,
                                                      PlaybackCloseReason.CALL_ENDED} else PlaybackEventKind.CLOSED,
            reason=reason_text or reason.value,
        )

    def _emit_locked(
        self,
        kind: PlaybackEventKind,
        *,
        reason: str = "",
        sequence: int | None = None,
    ) -> PlaybackEvent:
        event = PlaybackEvent(self.call_id, self.channel_id, self.generation, kind, self.clock_ns(), reason, sequence)
        self.events.append(event)
        if self.on_event is not None:
            self.on_event(event)
        return event


__all__ = ["PlaybackChannel"]
