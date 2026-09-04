"""PJSUA2 AudioMediaPort bridge and bounded direct PCM handoff."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
import time
from typing import Any, Callable

from .models import NegotiatedMediaProfile, PcmFrame


class EgressSourceMode(StrEnum):
    """Source selected by the media-clock callback for one call."""

    IDLE = "idle"
    PREROLL = "preroll"
    PLAYING = "playing"
    DRAINING = "draining"
    CANCELLED = "cancelled"
    CLOSED = "closed"


@dataclass(slots=True)
class MediaPortStats:
    """Counters suitable for evidence without retaining audio payloads."""

    ingress_frames: int = 0
    ingress_bytes: int = 0
    egress_frames: int = 0
    egress_bytes: int = 0
    ingress_dropped_closed: int = 0
    ingress_dropped_overflow: int = 0
    egress_dropped_closed: int = 0
    egress_dropped_overflow: int = 0
    egress_underruns: int = 0
    tts_startup_wait: int = 0
    intentional_silence_frames: int = 0
    source_mode_transitions: int = 0
    callback_errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            name: int(getattr(self, name))
            for name in (
                "ingress_frames",
                "ingress_bytes",
                "egress_frames",
                "egress_bytes",
                "ingress_dropped_closed",
                "ingress_dropped_overflow",
                "egress_dropped_closed",
                "egress_dropped_overflow",
                "egress_underruns",
                "tts_startup_wait",
                "intentional_silence_frames",
                "source_mode_transitions",
                "callback_errors",
            )
        }


class PcmFrameQueue:
    """A bounded, non-blocking producer queue for decoded media frames."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._frames: deque[PcmFrame] = deque()
        self._closed = False
        self._lock = RLock()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def put_nowait(self, frame: PcmFrame) -> bool:
        with self._lock:
            if self._closed or len(self._frames) >= self.capacity:
                return False
            self._frames.append(frame)
            return True

    def get_nowait(self) -> PcmFrame | None:
        with self._lock:
            if not self._frames:
                return None
            return self._frames.popleft()

    def close(self) -> int:
        with self._lock:
            discarded = len(self._frames)
            self._frames.clear()
            self._closed = True
            return discarded

    def qsize(self) -> int:
        with self._lock:
            return len(self._frames)


class PcmOutputBuffer:
    """Bounded PCM byte buffer read at the exact size requested by PJMEDIA."""

    def __init__(self, profile: NegotiatedMediaProfile, capacity_frames: int) -> None:
        if capacity_frames < 1:
            raise ValueError("capacity_frames must be positive")
        self.profile = profile
        self.capacity_bytes = profile.frame_bytes * capacity_frames
        self._bytes = bytearray()
        self._closed = False
        self._lock = RLock()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def put_nowait(self, frame: PcmFrame) -> bool:
        if frame.profile != self.profile:
            raise ValueError("egress frame profile does not match the active call profile")
        with self._lock:
            if self._closed or len(self._bytes) + len(frame.pcm_s16le) > self.capacity_bytes:
                return False
            self._bytes.extend(frame.pcm_s16le)
            return True

    def read_nowait(self, capacity: int) -> bytes | None:
        if capacity < 0:
            raise ValueError("capacity must not be negative")
        with self._lock:
            if self._closed:
                return None
            if not self._bytes:
                return None
            size = min(capacity, len(self._bytes))
            payload = bytes(self._bytes[:size])
            del self._bytes[:size]
            return payload

    def close(self) -> int:
        with self._lock:
            discarded = len(self._bytes)
            self._bytes.clear()
            self._closed = True
            return discarded

    def qsize_bytes(self) -> int:
        with self._lock:
            return len(self._bytes)


class PcmAudioBridge:
    """Owns one bidirectional application ``AudioMediaPort`` for one call."""

    def __init__(
        self,
        *,
        pjsua2_module: Any,
        call_id: str,
        channel_id: str,
        generation: int,
        profile: NegotiatedMediaProfile,
        capacity_frames: int,
        output_capacity_frames: int | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        failure_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.pjsua2 = pjsua2_module
        self.call_id = call_id
        self.channel_id = channel_id
        self.generation = generation
        self.profile = profile
        self.clock_ns = clock_ns
        self.failure_callback = failure_callback
        self.ingress = PcmFrameQueue(capacity_frames)
        self.egress = PcmOutputBuffer(profile, capacity_frames if output_capacity_frames is None else output_capacity_frames)
        self.stats = MediaPortStats()
        self._ingress_sequence = 0
        self._closed = False
        self._source_mode = EgressSourceMode.IDLE
        self._lock = RLock()
        self.port = self._create_port()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def egress_source_mode(self) -> EgressSourceMode:
        with self._lock:
            return self._source_mode

    def set_egress_source_mode(self, mode: EgressSourceMode | str) -> bool:
        """Select the non-blocking source used by the PJMEDIA callback."""

        selected = EgressSourceMode(mode)
        with self._lock:
            if self._source_mode is selected:
                return False
            self._source_mode = selected
            self.stats.source_mode_transitions += 1
            return True

    def _create_port(self) -> Any:
        bridge = self
        pjsua2 = self.pjsua2

        class BridgePort(pjsua2.AudioMediaPort):  # type: ignore[misc]
            def __init__(self) -> None:
                super().__init__()

            def onFrameReceived(self, frame: Any) -> None:
                bridge._on_frame_received(frame)

            def onFrameRequested(self, frame: Any) -> None:
                bridge._on_frame_requested(frame)

        port = BridgePort()
        fmt = pjsua2.MediaFormatAudio()
        fmt.type = pjsua2.PJMEDIA_TYPE_AUDIO
        fmt.clockRate = self.profile.sample_rate_hz
        fmt.channelCount = self.profile.channels
        fmt.bitsPerSample = self.profile.pcm_bits_per_sample
        fmt.frameTimeUsec = self.profile.frame_time_usec
        port.createPort(f"sip-media-{self.call_id}", fmt)
        return port

    def _on_frame_received(self, frame: Any) -> None:
        with self._lock:
            if self._closed:
                self.stats.ingress_dropped_closed += 1
                return
        try:
            size = int(frame.buf.size())
            payload = bytearray(size)
            frame.buf.copy_to_bytearray(payload)
            with self._lock:
                self._ingress_sequence += 1
                sequence = self._ingress_sequence
            pcm = PcmFrame(
                call_id=self.call_id,
                channel_id=self.channel_id,
                generation=self.generation,
                sequence=sequence,
                timestamp_ns=self.clock_ns(),
                pcm_s16le=bytes(payload),
                profile=self.profile,
            )
        except Exception as exc:
            with self._lock:
                self.stats.callback_errors += 1
            self._failure(f"media_ingress_callback:{type(exc).__name__}:{exc}")
            return

        if not self.ingress.put_nowait(pcm):
            with self._lock:
                if self._closed:
                    self.stats.ingress_dropped_closed += 1
                    return
                self.stats.ingress_dropped_overflow += 1
            self._failure("media_ingress_overflow")
            return
        with self._lock:
            self.stats.ingress_frames += 1
            self.stats.ingress_bytes += len(payload)

    def _on_frame_requested(self, frame: Any) -> None:
        try:
            capacity = int(frame.size)
            if capacity <= 0:
                frame.type = self.pjsua2.PJMEDIA_FRAME_TYPE_NONE
                frame.size = 0
                return
            with self._lock:
                mode = self._source_mode
            if mode is EgressSourceMode.PLAYING:
                payload = self.egress.read_nowait(capacity)
                if payload is None:
                    with self._lock:
                        self.stats.egress_underruns += 1
                    payload = bytes(capacity)
            elif mode is EgressSourceMode.PREROLL:
                payload = self.egress.read_nowait(capacity)
                if payload is None:
                    with self._lock:
                        self.stats.tts_startup_wait += 1
                    payload = bytes(capacity)
            elif mode is EgressSourceMode.DRAINING:
                payload = self.egress.read_nowait(capacity)
                if payload is None:
                    with self._lock:
                        # The TTS generation is complete and the media
                        # egress buffer has drained.  Switch to the normal
                        # idle source atomically with the first expected
                        # silent frame; this prevents the PJMEDIA clock from
                        # reporting a false PLAYING underrun at the tail.
                        if self._source_mode is EgressSourceMode.DRAINING:
                            self._source_mode = EgressSourceMode.IDLE
                            self.stats.source_mode_transitions += 1
                        self.stats.intentional_silence_frames += 1
                    payload = bytes(capacity)
            else:
                with self._lock:
                    self.stats.intentional_silence_frames += 1
                payload = bytes(capacity)
            if len(payload) < capacity:
                payload = payload + bytes(capacity - len(payload))
            frame.type = self.pjsua2.PJMEDIA_FRAME_TYPE_AUDIO
            frame.buf.assign_from_bytes(payload[:capacity])
            frame.size = min(len(payload), capacity)
            with self._lock:
                self.stats.egress_frames += 1
                self.stats.egress_bytes += frame.size
        except Exception as exc:
            with self._lock:
                self.stats.callback_errors += 1
            self._failure(f"media_egress_callback:{type(exc).__name__}:{exc}")
            try:
                frame.type = self.pjsua2.PJMEDIA_FRAME_TYPE_NONE
                frame.size = 0
            except Exception:
                pass

    def _failure(self, reason: str) -> None:
        if self.failure_callback is not None:
            self.failure_callback(reason)

    def enqueue(self, frame: PcmFrame) -> bool:
        with self._lock:
            if self._closed:
                self.stats.egress_dropped_closed += 1
                return False
        try:
            accepted = self.egress.put_nowait(frame)
        except ValueError:
            self._failure("media_egress_profile_mismatch")
            raise
        if not accepted:
            with self._lock:
                if self._closed:
                    self.stats.egress_dropped_closed += 1
                else:
                    self.stats.egress_dropped_overflow += 1
            self._failure("media_egress_overflow")
        elif self.egress_source_mode is EgressSourceMode.IDLE:
            self.set_egress_source_mode(EgressSourceMode.PREROLL)
        return accepted

    def next_ingress(self) -> PcmFrame | None:
        return self.ingress.get_nowait()

    def close(self) -> bool:
        with self._lock:
            if self._closed:
                return False
            self._closed = True
            self._source_mode = EgressSourceMode.CLOSED
        self.ingress.close()
        self.egress.close()
        return True

    def release_port(self) -> Any | None:
        """Release the native conference port while PJMEDIA is still alive.

        The callback class closes over this bridge, while the bridge owns the
        port, so retaining ``port`` until interpreter teardown can leave a
        reference cycle.  The adapter calls this after stopping both media
        directions and before destroying the PJSUA2 endpoint.  A direct
        ``close()`` intentionally keeps the proxy available for stale-frame
        callback tests; releasing the native resource is an explicit owner
        lifecycle step.
        """

        with self._lock:
            port = self.port
            self.port = None
            return port
