"""Bounded TTS PCM aggregation and media-ptime framing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock

from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame

from .contracts import TtsPcmChunk


class TtsOutputError(RuntimeError):
    pass


@dataclass(slots=True)
class TtsOutputStats:
    accepted_chunks: int = 0
    accepted_bytes: int = 0
    emitted_frames: int = 0
    emitted_bytes: int = 0
    flushed_tail_frames: int = 0
    dropped_tail_bytes: int = 0
    dropped_stale_chunks: int = 0
    dropped_closed_chunks: int = 0
    dropped_cancelled_chunks: int = 0
    dropped_overflow_bytes: int = 0


class TtsOutputBuffer:
    """Aggregate arbitrary TTS chunks while preserving a strict bound."""

    def __init__(
        self,
        *,
        profile: NegotiatedMediaProfile,
        call_id: str,
        channel_id: str,
        generation: int,
        max_buffer_bytes: int = 256_000,
        max_pending_frames: int | None = None,
        start_timestamp_ns: int = 0,
    ) -> None:
        if not call_id or not channel_id or generation < 1:
            raise ValueError("invalid TTS output lifecycle")
        if max_buffer_bytes < profile.frame_bytes:
            raise ValueError("output bounds are too small")
        if start_timestamp_ns < 0:
            raise ValueError("start timestamp must be non-negative")
        self.profile = profile
        self.call_id = call_id
        self.channel_id = channel_id
        self.generation = generation
        self.max_buffer_bytes = max_buffer_bytes
        # Kept as a source-compatible argument for existing callers.  Ready
        # frames are no longer capped separately: the dynamic accumulation
        # buffer is the single bounded high-water domain.
        if max_pending_frames is not None and max_pending_frames < 1:
            raise ValueError("pending frame compatibility bound must be positive")
        self.max_pending_frames = max_pending_frames
        self._start_timestamp_ns = start_timestamp_ns
        self._segments: deque[bytes] = deque()
        self._buffered_bytes = 0
        self._next_sequence = 1
        self._last_chunk_sequence = 0
        self._closed = False
        self._cancelled = False
        self._completed = False
        self._lock = RLock()
        self.stats = TtsOutputStats()

    @property
    def buffered_bytes(self) -> int:
        with self._lock:
            return self._buffered_bytes

    @property
    def pending_frames(self) -> int:
        with self._lock:
            complete_frames, remainder = divmod(self._buffered_bytes, self.profile.frame_bytes)
            tail = int(self._completed and remainder > 0)
            return complete_frames + tail

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def push(self, chunk: TtsPcmChunk) -> bool:
        if not isinstance(chunk, TtsPcmChunk):
            raise TypeError("TTS output accepts TtsPcmChunk only")
        with self._lock:
            if self._cancelled:
                self.stats.dropped_cancelled_chunks += 1
                return False
            if self._closed:
                self.stats.dropped_closed_chunks += 1
                return False
            if (chunk.call_id != self.call_id or chunk.channel_id != self.channel_id
                    or chunk.generation != self.generation or chunk.profile != self.profile
                    or chunk.sequence <= self._last_chunk_sequence):
                self.stats.dropped_stale_chunks += 1
                return False
            if self._buffered_bytes + len(chunk.pcm_s16le) > self.max_buffer_bytes:
                self.stats.dropped_overflow_bytes += len(chunk.pcm_s16le)
                raise TtsOutputError(
                    f"TTS output high-water exceeded: buffered={self._buffered_bytes} "
                    f"incoming={len(chunk.pcm_s16le)} limit={self.max_buffer_bytes}"
                )
            self._last_chunk_sequence = chunk.sequence
            self._segments.append(chunk.pcm_s16le)
            self._buffered_bytes += len(chunk.pcm_s16le)
            self.stats.accepted_chunks += 1
            self.stats.accepted_bytes += len(chunk.pcm_s16le)
            return True

    def complete(self) -> int:
        """Close production while retaining all accumulated PCM for playback."""
        with self._lock:
            if self._cancelled or self._completed:
                return 0
            tail = int(self._buffered_bytes % self.profile.frame_bytes > 0)
            if tail:
                self.stats.flushed_tail_frames += 1
            self._completed = True
            self._closed = True
            return tail

    def cancel(self) -> bool:
        with self._lock:
            if self._cancelled:
                return False
            self._cancelled = True
            self._closed = True
            self.stats.dropped_tail_bytes += self._buffered_bytes
            self._segments.clear()
            self._buffered_bytes = 0
            return True

    def close(self) -> bool:
        return self.complete()

    def next_frame(self) -> PcmFrame | None:
        with self._lock:
            payload = self._next_payload_locked()
            if payload is None:
                return None
            frame = self._make_frame_locked(payload)
            self._next_sequence += 1
            self.stats.emitted_frames += 1
            self.stats.emitted_bytes += len(payload)
            return frame

    def peek_frame(self) -> PcmFrame | None:
        with self._lock:
            payload = self._peek_payload_for_next_frame_locked()
            return self._make_frame_locked(payload) if payload is not None else None

    def _peek_payload_for_next_frame_locked(self) -> bytes | None:
        frame_bytes = self.profile.frame_bytes
        if self._buffered_bytes >= frame_bytes:
            return self._peek_bytes_locked(frame_bytes)
        if self._completed and self._buffered_bytes:
            return self._peek_bytes_locked(self._buffered_bytes) + b"\x00" * (frame_bytes - self._buffered_bytes)
        return None

    def _next_payload_locked(self) -> bytes | None:
        payload = self._peek_payload_for_next_frame_locked()
        if payload is None:
            return None
        consume = min(self.profile.frame_bytes, self._buffered_bytes)
        self._consume_bytes_locked(consume)
        return payload

    def _peek_bytes_locked(self, size: int) -> bytes:
        if size < 0 or size > self._buffered_bytes:
            raise TtsOutputError("invalid PCM peek size")
        remaining = size
        parts: list[bytes] = []
        for segment in self._segments:
            if remaining <= 0:
                break
            part = segment[:remaining]
            parts.append(part)
            remaining -= len(part)
        if remaining:
            raise TtsOutputError("PCM segment accounting mismatch")
        return b"".join(parts)

    def _consume_bytes_locked(self, size: int) -> None:
        if size < 0 or size > self._buffered_bytes:
            raise TtsOutputError("invalid PCM consume size")
        remaining = size
        while remaining and self._segments:
            segment = self._segments[0]
            if len(segment) <= remaining:
                remaining -= len(segment)
                self._segments.popleft()
            else:
                self._segments[0] = segment[remaining:]
                remaining = 0
        if remaining:
            raise TtsOutputError("PCM segment accounting mismatch")
        self._buffered_bytes -= size

    def _make_frame_locked(self, payload: bytes) -> PcmFrame:
        if len(payload) != self.profile.frame_bytes:
            raise TtsOutputError("internal frame is not exactly the negotiated media size")
        frame = PcmFrame(
            call_id=self.call_id,
            channel_id=self.channel_id,
            generation=self.generation,
            sequence=self._next_sequence,
            timestamp_ns=self._start_timestamp_ns + (self._next_sequence - 1) * self.profile.frame_time_usec * 1000,
            pcm_s16le=payload,
            profile=self.profile,
        )
        return frame


__all__ = ["TtsOutputBuffer", "TtsOutputError", "TtsOutputStats"]
