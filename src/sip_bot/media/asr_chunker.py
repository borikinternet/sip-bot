"""Bounded, timer-aware PCM accumulator for the ASR data-plane boundary."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
import time
from typing import Callable

from .types import PcmFrame
from sip_bot.sip_media.models import NegotiatedMediaProfile


class FlushReason(StrEnum):
    TARGET = "target"
    TIMER = "timer"
    HARD_ENDPOINT = "hard_endpoint"
    MANUAL = "manual"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class AsrAudioChunk:
    """A bounded PCM chunk handed directly to the ASR component."""

    call_id: str
    channel_id: str
    generation: int
    turn_id: str
    sequence: int
    timestamp_ns: int
    pcm_s16le: bytes
    profile: NegotiatedMediaProfile
    flush_reason: FlushReason
    is_final: bool = False

    def __post_init__(self) -> None:
        if not self.call_id or not self.channel_id or not self.turn_id:
            raise ValueError("call_id, channel_id and turn_id must be non-empty")
        if self.generation < 1 or self.sequence < 1 or self.timestamp_ns < 0:
            raise ValueError("invalid ASR chunk lifecycle metadata")
        if not isinstance(self.pcm_s16le, bytes):
            raise ValueError("ASR chunk payload must be bytes")
        if not self.pcm_s16le and not (self.is_final and self.flush_reason is FlushReason.HARD_ENDPOINT):
            raise ValueError("ASR chunk payload must be non-empty unless it is a hard-endpoint marker")
        if len(self.pcm_s16le) % (self.profile.channels * 2):
            raise ValueError("ASR chunk payload is not PCM S16LE aligned")

    @property
    def sample_count(self) -> int:
        return len(self.pcm_s16le) // (self.profile.channels * 2)

    @property
    def duration_ms(self) -> float:
        return self.sample_count * 1000.0 / self.profile.sample_rate_hz

    def as_dict(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "channel_id": self.channel_id,
            "generation": self.generation,
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "timestamp_ns": self.timestamp_ns,
            "bytes": len(self.pcm_s16le),
            "sample_count": self.sample_count,
            "duration_ms": self.duration_ms,
            "flush_reason": self.flush_reason.value,
            "is_final": self.is_final,
            "profile": self.profile.as_dict(),
        }


@dataclass(slots=True)
class ChunkerStats:
    accepted_frames: int = 0
    accepted_bytes: int = 0
    emitted_chunks: int = 0
    emitted_bytes: int = 0
    flushed_timer: int = 0
    flushed_hard_endpoint: int = 0
    flushed_close: int = 0
    flushed_manual: int = 0
    dropped_stale: int = 0
    dropped_closed: int = 0
    dropped_cancelled: int = 0
    dropped_overflow: int = 0
    dropped_unscoped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {field: int(getattr(self, field)) for field in self.__dataclass_fields__}


class AsrChunker:
    """Accumulate frames without blocking the producer or growing unbounded.

    ``on_timer`` is the timer boundary: the application scheduler calls it
    with monotonic time.  No hidden thread is created, so close/cancel and
    deterministic tests have explicit ownership of timer execution.
    """

    def __init__(
        self,
        *,
        profile: NegotiatedMediaProfile,
        call_id: str,
        channel_id: str,
        generation: int,
        chunk_ms: int = 1000,
        flush_ms: int = 1000,
        max_pending_chunks: int = 2,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if not call_id or not channel_id:
            raise ValueError("call_id and channel_id must be non-empty")
        if generation < 1:
            raise ValueError("generation must be positive")
        if chunk_ms < 1 or flush_ms < 1 or max_pending_chunks < 1:
            raise ValueError("chunk, flush, and pending capacities must be positive")
        self.profile = profile
        self.call_id = call_id
        self.channel_id = channel_id
        self.generation = generation
        self.chunk_ms = chunk_ms
        self.flush_ms = flush_ms
        self.max_pending_chunks = max_pending_chunks
        self.clock_ns = clock_ns
        target_samples = profile.sample_rate_hz * chunk_ms / 1000
        if target_samples != int(target_samples):
            raise ValueError("chunk_ms does not produce a whole number of samples")
        self.target_bytes = int(target_samples) * profile.channels * 2
        self._buffer = bytearray()
        self._buffer_timestamp_ns: int | None = None
        self._last_audio_timestamp_ns: int | None = None
        self._turn_has_audio = False
        self._active_turn_id: str | None = None
        self._pending: deque[AsrAudioChunk] = deque()
        self._last_frame_sequence = 0
        self._next_chunk_sequence = 1
        self._closed = False
        self._cancelled = False
        self._lock = RLock()
        self.stats = ChunkerStats()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    @property
    def buffered_bytes(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def pending_chunks(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def active_turn_id(self) -> str | None:
        with self._lock:
            return self._active_turn_id

    def begin_turn(self, turn_id: str) -> bool:
        """Open the authoritative TurnDetector scope for following PCM frames."""

        if not turn_id:
            raise ValueError("turn_id must be non-empty")
        with self._lock:
            if self._closed or self._cancelled:
                return False
            if self._active_turn_id == turn_id:
                return False
            if self._active_turn_id is not None:
                raise ValueError(
                    f"cannot begin ASR turn {turn_id!r} before {self._active_turn_id!r} is finalized"
                )
            if self._buffer or self._turn_has_audio:
                raise RuntimeError("unscoped ASR audio exists before begin_turn")
            self._active_turn_id = turn_id
            return True

    def push(self, frame: PcmFrame) -> int:
        """Accept a frame and return the number of chunks emitted/queued."""

        if not isinstance(frame, PcmFrame):
            raise TypeError("ASR chunker accepts PcmFrame only")
        with self._lock:
            if self._closed:
                self.stats.dropped_closed += 1
                return 0
            if self._cancelled:
                self.stats.dropped_cancelled += 1
                return 0
            if frame.call_id != self.call_id or frame.channel_id != self.channel_id or frame.generation != self.generation:
                self.stats.dropped_stale += 1
                return 0
            if self._active_turn_id is None:
                self.stats.dropped_unscoped += 1
                return 0
            if frame.profile != self.profile or frame.sequence <= self._last_frame_sequence:
                self.stats.dropped_stale += 1
                return 0
            now_ns = frame.timestamp_ns
            self._flush_due_locked(now_ns)
            if self._buffer_timestamp_ns is None:
                self._buffer_timestamp_ns = frame.timestamp_ns
            self._last_frame_sequence = frame.sequence
            self._last_audio_timestamp_ns = frame.timestamp_ns
            self._turn_has_audio = True
            self._buffer.extend(frame.pcm_s16le)
            self.stats.accepted_frames += 1
            self.stats.accepted_bytes += len(frame.pcm_s16le)
            return self._emit_target_chunks_locked()

    def on_timer(self, now_ns: int | None = None) -> int:
        """Flush a partial chunk once its explicit timer deadline is reached."""

        with self._lock:
            if self._closed or self._cancelled or self._buffer_timestamp_ns is None:
                return 0
            now = self.clock_ns() if now_ns is None else now_ns
            if now - self._buffer_timestamp_ns < self.flush_ms * 1_000_000:
                return 0
            return self._flush_locked(FlushReason.TIMER, is_final=False)

    def flush(self, reason: FlushReason = FlushReason.MANUAL, *, is_final: bool = False) -> int:
        """Emit a short tail, if present, with an explicit reason."""

        if reason is FlushReason.TARGET:
            raise ValueError("TARGET is emitted by push(), not manual flush()")
        with self._lock:
            if self._closed or self._cancelled:
                return 0
            return self._flush_locked(reason, is_final=is_final)

    def hard_endpoint(self, turn_id: str) -> int:
        if not turn_id:
            raise ValueError("turn_id must be non-empty")
        with self._lock:
            if self._closed or self._cancelled:
                return 0
            if self._active_turn_id != turn_id:
                raise ValueError(
                    f"hard endpoint {turn_id!r} does not match active ASR turn {self._active_turn_id!r}"
                )
            emitted = self._flush_locked(FlushReason.HARD_ENDPOINT, is_final=True)
            self._active_turn_id = None
            return emitted

    def next_chunk(self) -> AsrAudioChunk | None:
        with self._lock:
            if not self._pending:
                return None
            return self._pending.popleft()

    def close(self) -> bool:
        """Gracefully flush the tail and close input; queued chunks remain drainable."""

        with self._lock:
            if self._closed:
                return False
            if not self._cancelled:
                self._flush_locked(FlushReason.CLOSE, is_final=True)
            self._closed = True
            return True

    def cancel(self) -> bool:
        """Discard the current generation so no stale tail reaches ASR."""

        with self._lock:
            if self._cancelled:
                return False
            self._cancelled = True
            self._buffer.clear()
            self._buffer_timestamp_ns = None
            self._last_audio_timestamp_ns = None
            self._turn_has_audio = False
            self._active_turn_id = None
            self._pending.clear()
            self.stats.dropped_cancelled += 1
            return True

    def _flush_due_locked(self, now_ns: int) -> None:
        if self._buffer_timestamp_ns is not None and now_ns - self._buffer_timestamp_ns >= self.flush_ms * 1_000_000:
            self._flush_locked(FlushReason.TIMER, is_final=False)

    def _emit_target_chunks_locked(self) -> int:
        emitted = 0
        while len(self._buffer) >= self.target_bytes:
            timestamp_ns = self._buffer_timestamp_ns
            assert timestamp_ns is not None
            payload = bytes(self._buffer[: self.target_bytes])
            del self._buffer[: self.target_bytes]
            if self._enqueue_locked(payload, timestamp_ns, FlushReason.TARGET, is_final=False):
                emitted += 1
            if self._buffer:
                self._buffer_timestamp_ns = timestamp_ns
            else:
                self._buffer_timestamp_ns = None
        return emitted

    def _flush_locked(self, reason: FlushReason, *, is_final: bool) -> int:
        if not self._buffer:
            if reason is FlushReason.HARD_ENDPOINT and self._turn_has_audio:
                timestamp_ns = self._last_audio_timestamp_ns
                assert timestamp_ns is not None
                emitted = int(self._enqueue_locked(b"", timestamp_ns, reason, is_final=True))
                if emitted:
                    self._turn_has_audio = False
                self.stats.flushed_hard_endpoint += 1
                return emitted
            return 0
        timestamp_ns = self._buffer_timestamp_ns
        assert timestamp_ns is not None
        payload = bytes(self._buffer)
        self._buffer.clear()
        self._buffer_timestamp_ns = None
        emitted = int(self._enqueue_locked(payload, timestamp_ns, reason, is_final=is_final))
        if emitted and reason is FlushReason.HARD_ENDPOINT:
            self._turn_has_audio = False
        if reason is FlushReason.TIMER:
            self.stats.flushed_timer += 1
        elif reason is FlushReason.HARD_ENDPOINT:
            self.stats.flushed_hard_endpoint += 1
        elif reason is FlushReason.CLOSE:
            self.stats.flushed_close += 1
        elif reason is FlushReason.MANUAL:
            self.stats.flushed_manual += 1
        return emitted

    def _enqueue_locked(
        self,
        payload: bytes,
        timestamp_ns: int,
        reason: FlushReason,
        *,
        is_final: bool,
    ) -> bool:
        if len(self._pending) >= self.max_pending_chunks:
            self.stats.dropped_overflow += 1
            return False
        chunk = AsrAudioChunk(
            call_id=self.call_id,
            channel_id=self.channel_id,
            generation=self.generation,
            turn_id=self._required_turn_id(),
            sequence=self._next_chunk_sequence,
            timestamp_ns=timestamp_ns,
            pcm_s16le=payload,
            profile=self.profile,
            flush_reason=reason,
            is_final=is_final,
        )
        self._next_chunk_sequence += 1
        self._pending.append(chunk)
        self.stats.emitted_chunks += 1
        self.stats.emitted_bytes += len(payload)
        return True

    def _required_turn_id(self) -> str:
        if self._active_turn_id is None:
            raise RuntimeError("ASR chunk cannot be emitted outside an authoritative turn")
        return self._active_turn_id


__all__ = ["AsrAudioChunk", "AsrChunker", "ChunkerStats", "FlushReason"]
