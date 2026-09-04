"""Backend-neutral LLM facade and the existing Ollama HTTP boundary."""

from .facade import ChatOperation, LlmFacade
from .ollama_client import (
    MalformedResponseError,
    OllamaHttpClient,
    OllamaTimeoutError,
    OllamaTransportError,
)
from .telemetry import LatencyTrace
from .types import (
    CancelRequest,
    InferenceStatus,
    InferenceStatusKind,
    LlmStreamEvent,
    StreamEventKind,
)

__all__ = [
    "CancelRequest",
    "ChatOperation",
    "InferenceStatus",
    "InferenceStatusKind",
    "LatencyTrace",
    "LlmFacade",
    "LlmStreamEvent",
    "MalformedResponseError",
    "OllamaHttpClient",
    "OllamaTimeoutError",
    "OllamaTransportError",
    "StreamEventKind",
]
