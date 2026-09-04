"""Media-clock pacing for the TTS output boundary."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns
from typing import Callable

from sip_bot.sip_media.models import PcmFrame

from .output_buffer import TtsOutputBuffer


@dataclass(slots=True)
class PacerStats:
    emitted_frames: int = 0
    not_ready: int = 0
    dropped_after_cancel: int = 0


class MediaPacer:
    """Expose exact media frames on the negotiated clock with a small lead.

    The lead lets the application pre-fill the direct media egress buffer by
    one frame before the PJMEDIA callback's next tick.  It is bounded and does
    not change the frame cadence or make the callback wait for TTS.
    """

    def __init__(
        self,
        output: TtsOutputBuffer,
        *,
        clock_ns: Callable[[], int] = monotonic_ns,
        lookahead_ns: int | None = None,
    ) -> None:
        self.output = output
        self.clock_ns = clock_ns
        default_lookahead_ns = min(10_000_000, output.profile.frame_time_usec * 1000 // 2)
        self.lookahead_ns = default_lookahead_ns if lookahead_ns is None else lookahead_ns
        if self.lookahead_ns < 0:
            raise ValueError("pacer lookahead must be non-negative")
        self.stats = PacerStats()

    def next_ready(self, now_ns: int | None = None) -> PcmFrame | None:
        now = self.clock_ns() if now_ns is None else now_ns
        if now < 0:
            raise ValueError("pacer timestamp must be non-negative")
        if self.output.cancelled:
            self.stats.dropped_after_cancel += 1
            return None
        frame = self.output.peek_frame()
        if frame is None:
            return None
        lookahead = self.lookahead_ns if self.stats.emitted_frames else 0
        if now + lookahead < frame.timestamp_ns:
            self.stats.not_ready += 1
            return None
        emitted = self.output.next_frame()
        if emitted is not None:
            self.stats.emitted_frames += 1
        return emitted


__all__ = ["MediaPacer", "PacerStats"]
