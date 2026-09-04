"""Application bootstrap and runtime-owned lifecycle coordination."""

from dataclasses import dataclass
import sys
import sysconfig
import time
from collections.abc import Iterable, Mapping
from typing import Callable

from .config import RuntimeConfig
from .control.events import (
    CallClose,
    CallOpen,
    ChannelClose,
    ChannelOpen,
    ControlEvent,
    ControlEventKind,
    ControlEventSink,
    Terminal,
)
from .control.lifecycle import CallScope, ChannelHandle, LifecycleError, LifecycleRegistry
from .logging_setup import configure_logging


@dataclass(frozen=True, slots=True)
class RuntimeProbe:
    """Observed interpreter facts; it never claims no-GIL from a filename."""

    executable: str
    implementation: str
    version: tuple[int, int, int]
    py_gil_disabled: int | None
    gil_enabled: bool | None

    @property
    def is_free_threaded(self) -> bool:
        return self.py_gil_disabled == 1 and self.gil_enabled is False

    def meets(self, config: RuntimeConfig) -> bool:
        return (
            self.implementation == "cpython"
            and self.version[:2] >= config.python_min_version
            and (not config.require_free_threaded or self.is_free_threaded)
        )


def probe_runtime() -> RuntimeProbe:
    """Capture actual runtime state for startup and evidence."""

    gil_probe = getattr(sys, "_is_gil_enabled", None)
    gil_enabled = bool(gil_probe()) if gil_probe is not None else None
    py_gil_disabled = sysconfig.get_config_var("Py_GIL_DISABLED")
    if py_gil_disabled is not None:
        py_gil_disabled = int(py_gil_disabled)
    return RuntimeProbe(
        executable=sys.executable,
        implementation=sys.implementation.name,
        version=(sys.version_info.major, sys.version_info.minor, sys.version_info.micro),
        py_gil_disabled=py_gil_disabled,
        gil_enabled=gil_enabled,
    )


class RuntimeCompatibilityError(RuntimeError):
    """Raised when startup is attempted on a non-conforming interpreter."""


@dataclass(frozen=True, slots=True)
class WarmupStageResult:
    """Evidence for one sequential pre-call readiness stage."""

    name: str
    elapsed_ms: float
    details: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "elapsed_ms": self.elapsed_ms, "details": dict(self.details)}


@dataclass(frozen=True, slots=True)
class WarmupReport:
    """Successful model/data readiness report for one application process."""

    started_at_ns: int
    completed_at_ns: int
    stages: tuple[WarmupStageResult, ...]

    @property
    def elapsed_ms(self) -> float:
        return (self.completed_at_ns - self.started_at_ns) / 1_000_000

    def as_dict(self) -> dict[str, object]:
        return {
            "started_at_ns": self.started_at_ns,
            "completed_at_ns": self.completed_at_ns,
            "elapsed_ms": self.elapsed_ms,
            "stages": [stage.as_dict() for stage in self.stages],
        }


class RuntimeWarmupError(RuntimeError):
    """Raised when a pre-call readiness stage cannot be completed."""


class RuntimeCoordinator:
    """Runtime owner for one call scope and its scoped control handles."""

    def __init__(
        self,
        config: RuntimeConfig,
        event_sink: ControlEventSink,
        *,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.config = config
        self._event_sink = event_sink
        self._clock_ns = clock_ns
        self._sequence = 0
        self.lifecycle = LifecycleRegistry()
        self.logger = configure_logging(config)

    @property
    def next_sequence(self) -> int:
        return self._sequence + 1

    def open_call(
        self,
        call_id: str,
        *,
        before_publish: Callable[[CallScope], None] | None = None,
    ) -> CallScope:
        scope = self.lifecycle.open_call(call_id)
        if before_publish is not None:
            before_publish(scope)
        self._publish(ControlEventKind.CALL_OPEN, call_id, CallOpen(call_id))
        self.logger.info("call opened call_id=%s", call_id)
        return scope

    def open_channel(self, call_id: str, channel_id: str, channel_kind: str) -> ChannelHandle:
        scope = self.lifecycle.get_call(call_id)
        handle = scope.open_channel(channel_id, channel_kind)
        self._publish(
            ControlEventKind.CHANNEL_OPEN,
            call_id,
            ChannelOpen(call_id, channel_id, channel_kind, handle.generation),
            channel_id=channel_id,
            channel_generation=handle.generation,
        )
        self.logger.info(
            "channel opened call_id=%s channel_id=%s generation=%d",
            call_id,
            channel_id,
            handle.generation,
        )
        return handle

    def close_channel(self, call_id: str, channel_id: str, reason: str) -> bool:
        scope = self.lifecycle.get_call(call_id)
        handle, changed = scope.close_channel(channel_id, reason)
        self._publish(
            ControlEventKind.CHANNEL_CLOSE,
            call_id,
            ChannelClose(
                call_id,
                handle.channel_id,
                handle.channel_kind,
                handle.generation,
                reason,
                already_closed=not changed,
            ),
            channel_id=handle.channel_id,
            channel_generation=handle.generation,
        )
        self.logger.info(
            "channel closed call_id=%s channel_id=%s generation=%d changed=%s",
            call_id,
            channel_id,
            handle.generation,
            changed,
        )
        return changed

    def close_call(self, call_id: str, reason: str) -> bool:
        scope = self.lifecycle.get_call(call_id)
        was_open = scope.is_open
        closed_channels = scope.close(reason)
        for handle in closed_channels:
            self._publish(
                ControlEventKind.CHANNEL_CLOSE,
                call_id,
                ChannelClose(
                    call_id,
                    handle.channel_id,
                    handle.channel_kind,
                    handle.generation,
                    reason,
                    already_closed=False,
                ),
                channel_id=handle.channel_id,
                channel_generation=handle.generation,
            )
        # ``scope.close`` has already transitioned the scope.  Preserve the
        # pre-close state so a first close with zero channels is still visible
        # as a state change, while a re-close remains idempotent.
        already_closed = not was_open
        self._publish(
            ControlEventKind.CALL_CLOSE,
            call_id,
            CallClose(call_id, reason, already_closed=already_closed),
        )
        self.logger.info("call closed call_id=%s changed=%s", call_id, not already_closed)
        return not already_closed

    def terminate_call(self, call_id: str, reason: str) -> None:
        """Publish terminal first, then close all scoped channels idempotently."""

        self.lifecycle.get_call(call_id)
        self._publish(ControlEventKind.TERMINAL, call_id, Terminal(call_id, reason))
        self.close_call(call_id, reason)

    def dispatch_to_channel(
        self,
        handle: ChannelHandle,
        event: ControlEvent,
        consumer: Callable[[ControlEvent], None],
    ) -> bool:
        """Use a scoped control handle; stale generations are dropped."""

        return handle.dispatch(event, consumer)

    def _publish(
        self,
        kind: ControlEventKind,
        call_id: str,
        payload: CallOpen | CallClose | ChannelOpen | ChannelClose | Terminal,
        *,
        channel_id: str | None = None,
        channel_generation: int | None = None,
    ) -> ControlEvent:
        self._sequence += 1
        event = ControlEvent(
            kind=kind,
            call_id=call_id,
            sequence=self._sequence,
            timestamp_ns=self._clock_ns(),
            payload=payload,
            channel_id=channel_id,
            channel_generation=channel_generation,
        )
        self._event_sink.publish(event)
        return event


class ApplicationRuntime:
    """Strict bootstrap shell; model/SIP initialization is deliberately absent."""

    def __init__(self, config: RuntimeConfig, event_sink: ControlEventSink | None = None) -> None:
        self.config = config
        if event_sink is None:
            # Keep imports lazy: sip_media imports this module for runtime
            # probes, so importing the application composition at module load
            # time would recreate the existing cycle.
            from .control import Dispatcher
            from .dialogue import DialogueFSM

            event_sink = Dispatcher(DialogueFSM(operator_target=config.operator_target))
        self.event_sink = event_sink
        self.dispatcher = event_sink if hasattr(event_sink, "open_session") else None
        self.logger = configure_logging(config)
        self.coordinator = RuntimeCoordinator(config, event_sink)
        self.started = False
        self.probe: RuntimeProbe | None = None
        self.warmup_report: WarmupReport | None = None

    @property
    def ready(self) -> bool:
        """Whether the process completed its mandatory pre-call warmup."""

        return self.started and self.warmup_report is not None

    @classmethod
    def from_constants(cls, event_sink: ControlEventSink | None = None) -> "ApplicationRuntime":
        return cls(RuntimeConfig.from_constants(), event_sink)

    def compose_call(
        self,
        call_id: str,
        owners: object,
        *,
        components: tuple[object, ...] = (),
        command_sink: Callable[[object], None] | None = None,
    ) -> object:
        """Create one CallComposition around the existing Dispatcher/FSM.

        ``owners`` is intentionally imported and validated by the composition
        module.  The runtime only coordinates the scope-before-CALL_OPEN
        ordering needed to bind the same lifecycle object to session and FSM.
        """

        if not self.started:
            raise RuntimeError("application runtime must be started before opening a call")
        dispatcher = self.dispatcher
        if dispatcher is None:
            raise RuntimeError("application composition requires a Dispatcher event sink")
        from .runtime_composition import CallComposition, CallOwners

        if not isinstance(owners, CallOwners):
            raise TypeError("owners must be CallOwners")
        composition_holder: list[CallComposition] = []

        def prepare(scope: CallScope) -> None:
            session = dispatcher.open_session(
                call_id,
                scope=scope,
                components=components,  # type: ignore[arg-type]
                bindings=owners.bindings(),
            )
            composition_holder.append(
                CallComposition(
                    dispatcher,
                    session,
                    owners,
                    command_sink=command_sink,  # type: ignore[arg-type]
                )
            )

        self.coordinator.open_call(call_id, before_publish=prepare)
        dispatcher.drain()
        return composition_holder[0]

    def create_call_wiring(
        self,
        composition: object,
        *,
        sip_media: object,
        speech: object,
        asr: object,
        pipeline: object,
    ) -> object:
        """Create procedural live wiring for the current main asyncio loop.

        The returned object does not own dialogue or delivery semantics.  It
        only invokes the typed input methods of the supplied existing owners;
        call ``run``/``step`` from the application's main asyncio loop.
        """

        from .runtime_composition import CallComposition
        from .runtime_wiring import CallRuntimeWiring

        if not isinstance(composition, CallComposition):
            raise TypeError("composition must be CallComposition")
        if composition.dispatcher is not self.dispatcher:
            raise ValueError("composition must belong to this runtime dispatcher")
        return CallRuntimeWiring(
            composition,
            sip_media=sip_media,
            speech=speech,
            asr=asr,
            pipeline=pipeline,
            config=self.config,
        )

    def start(self) -> RuntimeProbe:
        probe = probe_runtime()
        self.probe = probe
        if not probe.meets(self.config):
            raise RuntimeCompatibilityError(
                "application requires CPython >= 3.14 free-threaded runtime; "
                f"observed version={probe.version} Py_GIL_DISABLED={probe.py_gil_disabled} "
                f"gil_enabled={probe.gil_enabled}"
            )
        self.started = True
        self.logger.info("application runtime started version=%s", self.config.application_version)
        return probe

    def warmup(self, stages: Iterable[tuple[str, Callable[[], object]]]) -> WarmupReport:
        """Run all heavy readiness stages before SIP call admission.

        Stages are intentionally sequential: the MVP shares one GPU and a
        native/runtime stage must finish before the next one is started.  A
        failed or incomplete stage leaves the runtime not-ready, so a caller
        must not start/accept a SIP call after that failure.
        """

        if not self.started:
            raise RuntimeWarmupError("application runtime must be started before warmup")
        self.warmup_report = None
        started_at_ns = time.monotonic_ns()
        results: list[WarmupStageResult] = []
        for name, action in stages:
            if not name or not callable(action):
                raise ValueError("warmup stages require a name and callable action")
            stage_started_ns = time.monotonic_ns()
            try:
                value = action()
            except BaseException as exc:
                raise RuntimeWarmupError(f"warmup stage {name!r} failed: {exc}") from exc
            results.append(
                WarmupStageResult(
                    name=name,
                    elapsed_ms=(time.monotonic_ns() - stage_started_ns) / 1_000_000,
                    details=self._warmup_details(value),
                )
            )
        report = WarmupReport(started_at_ns, time.monotonic_ns(), tuple(results))
        self.warmup_report = report
        self.logger.info("application warmup completed elapsed_ms=%.3f stages=%d", report.elapsed_ms, len(results))
        return report

    @staticmethod
    def _warmup_details(value: object) -> dict[str, object]:
        if hasattr(value, "as_dict") and callable(value.as_dict):
            mapped = value.as_dict()
            if isinstance(mapped, Mapping):
                return {str(key): item for key, item in mapped.items()}
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
        return {"result": repr(value)}

    def shutdown(self, reason: str = "runtime_shutdown") -> None:
        active_session = self.dispatcher.active_session if self.dispatcher is not None else None
        if active_session is not None:
            active_session.close(reason)
        self.started = False
        self.warmup_report = None


def main() -> int:
    """Run the non-invasive bootstrap/runtime probe entrypoint."""

    config = RuntimeConfig.from_constants()
    logger = configure_logging(config)
    probe = probe_runtime()
    logger.info(
        "runtime probe implementation=%s version=%s executable=%s "
        "Py_GIL_DISABLED=%s gil_enabled=%s",
        probe.implementation,
        ".".join(str(part) for part in probe.version),
        probe.executable,
        probe.py_gil_disabled,
        probe.gil_enabled,
    )
    if not probe.meets(config):
        logger.error("runtime preflight failed: free-threaded CPython is required")
        return 2
    logger.info("runtime preflight passed")
    return 0
