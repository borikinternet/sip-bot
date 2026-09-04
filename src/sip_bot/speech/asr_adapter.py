"""Streaming adapter around the accepted C2 faster-whisper baseline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Iterator, Protocol

from sip_bot.control.lifecycle import CancelToken

from sip_bot.media.asr_chunker import FlushReason

from .contracts import AsrAudioChunk, AsrHypothesis, coerce_backend_hypothesis


class AsrAdapterError(RuntimeError):
    """Raised when the streaming ASR boundary is invalid."""


class AsrBackend(Protocol):
    def transcribe_chunk(self, chunk: AsrAudioChunk) -> Iterable[Any]:
        ...


@dataclass(slots=True)
class AsrOperation:
    """Cancellation and generation scope for one streaming operation."""

    call_id: str
    channel_id: str
    generation: int
    operation_id: str
    cancel_token: CancelToken
    closed: bool = False

    def cancel(self) -> bool:
        self.closed = True
        return self.cancel_token.cancel()


class StreamingAsrAdapter:
    """Map chunked C2 backend output to lifecycle-safe application hypotheses."""

    def __init__(self, backend: AsrBackend) -> None:
        self.backend = backend
        self._active: AsrOperation | None = None
        self._closed = False
        self._revision = 0
        self._operation_number = 0

    def open_operation(self, *, call_id: str, channel_id: str, generation: int) -> AsrOperation:
        if self._closed:
            raise AsrAdapterError("ASR adapter is closed")
        if self._active is not None:
            self._active.cancel()
        reset = getattr(self.backend, "reset", None)
        if callable(reset):
            reset()
        self._operation_number += 1
        operation = AsrOperation(
            call_id=call_id,
            channel_id=channel_id,
            generation=generation,
            operation_id=f"{call_id}:asr-{self._operation_number}",
            cancel_token=CancelToken(),
        )
        self._active = operation
        self._revision = 0
        return operation

    def _is_current(self, operation: AsrOperation) -> bool:
        return (
            not self._closed
            and self._active is operation
            and not operation.closed
            and not operation.cancel_token.is_cancelled
        )

    def stream(
        self,
        operation: AsrOperation,
        chunks: Iterable[AsrAudioChunk],
    ) -> Iterator[AsrHypothesis]:
        """Yield only current-generation hypotheses; late backend items vanish."""

        for chunk in chunks:
            if not self._is_current(operation):
                return
            if (chunk.call_id, chunk.channel_id, chunk.generation) != (
                operation.call_id,
                operation.channel_id,
                operation.generation,
            ):
                raise AsrAdapterError("ASR chunk lifecycle metadata does not match operation")
            self._revision += 1
            try:
                backend_items = self.backend.transcribe_chunk(chunk)
                for item in backend_items:
                    if not self._is_current(operation):
                        return
                    hypothesis = coerce_backend_hypothesis(
                        item,
                        call_id=operation.call_id,
                        channel_id=operation.channel_id,
                        generation=operation.generation,
                        revision=self._revision,
                        timestamp_ns=chunk.timestamp_ns,
                    )
                    if chunk.is_final or chunk.flush_reason is FlushReason.HARD_ENDPOINT:
                        hypothesis = replace(hypothesis, is_final=True)
                    self._revision = max(self._revision, hypothesis.revision)
                    yield hypothesis
            except AsrAdapterError:
                raise
            except Exception as exc:
                raise AsrAdapterError(f"ASR backend operation failed: {exc}") from exc

    def cancel(self, operation: AsrOperation) -> bool:
        return operation.cancel()

    def close(self) -> None:
        self._closed = True
        if self._active is not None:
            self._active.cancel()
        reset = getattr(self.backend, "reset", None)
        if callable(reset):
            reset()


class FasterWhisperC2Backend:
    """Lazy C2 backend using the tested faster-whisper family.

    Construction does not import or load the model.  The model factory may be
    injected for deterministic tests; real model creation is intentionally
    left to the controlled target-runtime execution path.
    """

    def __init__(
        self,
        model_path: str,
        *,
        language: str = "ru",
        device: str = "cuda",
        compute_type: str = "float16",
        model_factory: Any | None = None,
    ) -> None:
        if not model_path:
            raise ValueError("model_path must not be empty")
        self.model_path = model_path
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model_factory = model_factory
        self._model: Any | None = None
        self._turn_scope: tuple[str, str, int] | None = None
        self._turn_pcm = bytearray()
        self._last_chunk_sequence = 0

    MODEL_SAMPLE_RATE_HZ = 16_000

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._model_factory is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-not-found]
            except ImportError as exc:
                raise AsrAdapterError(
                    "faster-whisper/CTranslate2 is not installed in the selected runtime"
                ) from exc
            self._model = WhisperModel(
                self.model_path,
                device=self.device,
                compute_type=self.compute_type,
            )
        else:
            self._model = self._model_factory(
                self.model_path,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe_chunk(self, chunk: AsrAudioChunk) -> Iterable[dict[str, Any]]:
        """Run one bounded chunk and expose segment text as a partial result."""

        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AsrAdapterError("numpy is required by the faster-whisper operation boundary") from exc
        if chunk.profile.channels != 1:
            raise AsrAdapterError("faster-whisper input must be mono")
        scope = (chunk.call_id, chunk.channel_id, chunk.generation)
        if self._turn_scope != scope:
            self.reset()
            self._turn_scope = scope
        if chunk.sequence <= self._last_chunk_sequence:
            raise AsrAdapterError("ASR chunk sequence must increase within one operation")
        self._last_chunk_sequence = chunk.sequence
        self._turn_pcm.extend(chunk.pcm_s16le)
        samples = np.frombuffer(bytes(self._turn_pcm), dtype=np.int16).astype(np.float32) / 32768.0
        samples = self._resample_to_model_rate(samples, chunk.profile.sample_rate_hz, np)
        segments, _info = self._load_model().transcribe(
            samples,
            language=self.language,
            vad_filter=False,
            beam_size=1,
            # The input is the complete current-turn prefix.  Carrying the
            # model's own previous-text state across independent calls would
            # duplicate/retain text outside the authoritative assembler.
            condition_on_previous_text=False,
        )
        text = " ".join(str(getattr(segment, "text", "")).strip() for segment in segments).strip()
        reset_after_result = chunk.is_final or chunk.flush_reason is FlushReason.HARD_ENDPOINT
        if reset_after_result:
            self.reset()
        yield {"text": text, "is_final": False, "source": "faster-whisper-c2"}

    def reset(self) -> None:
        """Discard the current audio prefix without unloading the model."""

        self._turn_pcm.clear()
        self._turn_scope = None
        self._last_chunk_sequence = 0

    def warmup(self, *, input_sample_rate_hz: int = 8_000, duration_ms: int = 1000) -> dict[str, object]:
        """Load CTranslate2 and execute one real inference before call admission.

        ``faster-whisper`` consumes 16 kHz mono samples.  The call boundary is
        negotiated PCMU/8 kHz, so the warmup uses the same model input rate as
        ``transcribe_chunk`` and forces the lazy segment iterator to execute.
        """

        if input_sample_rate_hz < 1 or duration_ms < 1:
            raise ValueError("warmup sample rate and duration must be positive")
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AsrAdapterError("numpy is required by the faster-whisper warmup") from exc
        source_samples = max(1, round(input_sample_rate_hz * duration_ms / 1000))
        source = np.zeros(source_samples, dtype=np.float32)
        samples = self._resample_to_model_rate(source, input_sample_rate_hz, np)
        started_model = self._model is None
        segments, _info = self._load_model().transcribe(
            samples,
            language=self.language,
            vad_filter=False,
            beam_size=1,
            condition_on_previous_text=True,
        )
        tuple(segments)
        return {
            "model_path": self.model_path,
            "model_sample_rate_hz": self.MODEL_SAMPLE_RATE_HZ,
            "input_sample_rate_hz": input_sample_rate_hz,
            "input_duration_ms": duration_ms,
            "model_loaded_by_warmup": started_model,
        }

    def _resample_to_model_rate(self, samples: Any, source_rate_hz: int, np: Any) -> Any:
        if source_rate_hz < 1:
            raise AsrAdapterError("ASR input sample rate must be positive")
        if source_rate_hz == self.MODEL_SAMPLE_RATE_HZ:
            return samples
        if samples.size == 0:
            return samples.astype(np.float32)
        output_count = max(1, round(samples.size * self.MODEL_SAMPLE_RATE_HZ / source_rate_hz))
        source_positions = np.arange(samples.size, dtype=np.float64)
        target_positions = np.arange(output_count, dtype=np.float64) * source_rate_hz / self.MODEL_SAMPLE_RATE_HZ
        return np.interp(target_positions, source_positions, samples).astype(np.float32, copy=False)
