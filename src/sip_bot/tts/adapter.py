"""Backend-neutral XTTS-v2 adapter boundary.

The real patched XTTS runtime is injected by the main executor.  This module
owns only the typed lifecycle and normalization boundary; it never imports
the heavy model at package import time.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from threading import Event
from typing import Protocol

from sip_bot.sip_media.models import NegotiatedMediaProfile

from .contracts import ApprovedTextChunk, TtsPcmChunk


@dataclass(frozen=True, slots=True)
class EngineAudioChunk:
    """PCM16 output of the injected XTTS provider before normalization."""

    pcm_s16le: bytes
    sample_rate_hz: int
    channels: int = 1

    def __post_init__(self) -> None:
        if not self.pcm_s16le or self.sample_rate_hz < 1 or self.channels < 1:
            raise ValueError("invalid engine audio chunk")
        if len(self.pcm_s16le) % (self.channels * 2):
            raise ValueError("engine PCM is not aligned")


class XttsEngine(Protocol):
    def stream(self, text: str, cancel: Event) -> Iterable[EngineAudioChunk]: ...


class TtsAdapterError(RuntimeError):
    pass


def _resample_pcm16_mono(payload: bytes, source_rate_hz: int, target_rate_hz: int) -> bytes:
    """Deterministic linear resampling for the narrow mono PCM boundary."""

    if source_rate_hz == target_rate_hz:
        return payload
    if source_rate_hz < 1 or target_rate_hz < 1:
        raise ValueError("sample rates must be positive")
    values = [int.from_bytes(payload[index:index + 2], "little", signed=True)
              for index in range(0, len(payload), 2)]
    if not values:
        return b""
    output_count = max(1, round(len(values) * target_rate_hz / source_rate_hz))
    result = bytearray()
    for output_index in range(output_count):
        source_position = output_index * source_rate_hz / target_rate_hz
        left = min(int(source_position), len(values) - 1)
        right = min(left + 1, len(values) - 1)
        fraction = source_position - left
        sample = round(values[left] + (values[right] - values[left]) * fraction)
        result.extend(int(max(-32768, min(32767, sample))).to_bytes(2, "little", signed=True))
    return bytes(result)


class XttsV2Adapter:
    """Wrap the accepted C4 XTTS-v2 candidate behind a typed stream."""

    def __init__(
        self,
        engine: XttsEngine,
        *,
        operation_id_factory: Callable[[], str],
    ) -> None:
        self.engine = engine
        self.operation_id_factory = operation_id_factory

    def stream(
        self,
        text: str,
        *,
        call_id: str,
        channel_id: str,
        turn_id: str,
        generation: int,
        profile: NegotiatedMediaProfile,
        cancel: Event | None = None,
    ) -> Iterator[TtsPcmChunk]:
        if not text.strip():
            raise ValueError("TTS text must not be blank")
        if profile.channels != 1:
            raise TtsAdapterError("XTTS MVP adapter supports mono output only")
        cancel_event = cancel or Event()
        operation_id = self.operation_id_factory()
        sequence = 1
        try:
            for engine_chunk in self.engine.stream(text, cancel_event):
                if cancel_event.is_set():
                    return
                if engine_chunk.channels != 1:
                    raise TtsAdapterError("XTTS engine output must be mono")
                pcm = _resample_pcm16_mono(
                    engine_chunk.pcm_s16le,
                    engine_chunk.sample_rate_hz,
                    profile.sample_rate_hz,
                )
                if not pcm:
                    continue
                yield TtsPcmChunk(
                    operation_id=operation_id,
                    call_id=call_id,
                    channel_id=channel_id,
                    generation=generation,
                    sequence=sequence,
                    pcm_s16le=pcm,
                    profile=profile,
                )
                sequence += 1
        except Exception as exc:
            if cancel_event.is_set():
                return
            if isinstance(exc, TtsAdapterError):
                raise
            raise TtsAdapterError("XTTS stream failed") from exc

    def stream_approved_text(
        self,
        chunks: Iterable[ApprovedTextChunk],
        *,
        channel_id: str,
        profile: NegotiatedMediaProfile,
        cancel: Event | None = None,
    ) -> Iterator[TtsPcmChunk]:
        """Consume one approved text stream without accepting arbitrary text."""

        collected: list[str] = []
        last: ApprovedTextChunk | None = None
        for chunk in chunks:
            if not isinstance(chunk, ApprovedTextChunk):
                raise TypeError("TTS accepts ApprovedTextChunk only")
            if last is not None and (chunk.call_id != last.call_id or chunk.turn_id != last.turn_id
                                     or chunk.generation != last.generation):
                raise ValueError("approved text stream mixes lifecycle identities")
            collected.append(chunk.text)
            last = chunk
        if last is None:
            return
        yield from self.stream(
            "".join(collected),
            call_id=last.call_id,
            channel_id=channel_id,
            turn_id=last.turn_id,
            generation=last.generation,
            profile=profile,
            cancel=cancel,
        )

    def warmup(
        self,
        *,
        profile: NegotiatedMediaProfile,
        text: str = "Проверка готовности.",
        call_id: str = "warmup-call",
        channel_id: str = "warmup-call:tts",
        turn_id: str = "warmup-call:turn-1",
        generation: int = 1,
    ) -> dict[str, object]:
        """Execute and consume the first real XTTS stream chunk pre-call."""

        stream = self.stream(
            text,
            call_id=call_id,
            channel_id=channel_id,
            turn_id=turn_id,
            generation=generation,
            profile=profile,
        )
        try:
            first = next(stream, None)
            if first is None:
                raise TtsAdapterError("XTTS warmup produced no PCM chunk")
            return {
                "sample_rate_hz": first.profile.sample_rate_hz,
                "channels": first.profile.channels,
                "first_chunk_bytes": len(first.pcm_s16le),
            }
        finally:
            stream.close()


__all__ = ["EngineAudioChunk", "TtsAdapterError", "XttsEngine", "XttsV2Adapter"]
