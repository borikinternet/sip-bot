import asyncio
from threading import Event

from sip_bot.control.event_bus import ControlEventBus
from sip_bot.runtime_readiness import (
    RuntimeReadinessCoordinator,
    RuntimeReadinessEvent,
    RuntimeReadinessState,
    RuntimeWarmupError,
)


def test_runtime_warmup_is_single_flight_and_emits_typed_state_events() -> None:
    async def scenario() -> None:
        started = Event()
        release = Event()
        calls = 0

        def warmup() -> str:
            nonlocal calls
            calls += 1
            started.set()
            release.wait(1.0)
            return "warmup-report"

        bus = ControlEventBus()
        subscription = bus.subscribe(predicate=lambda event: isinstance(event, RuntimeReadinessEvent))
        coordinator = RuntimeReadinessCoordinator(warmup, runtime_id="test-runtime", event_bus=bus)

        first = coordinator.start_background()
        second = coordinator.start_background()
        assert first is second
        assert coordinator.state is RuntimeReadinessState.RUNNING
        await asyncio.to_thread(started.wait, 1.0)
        release.set()
        assert await coordinator.ensure_ready() == "warmup-report"
        assert await coordinator.ensure_ready() == "warmup-report"
        assert calls == 1
        assert coordinator.state is RuntimeReadinessState.READY
        assert [event.state for event in subscription.drain()] == [
            RuntimeReadinessState.RUNNING,
            RuntimeReadinessState.READY,
        ]

    asyncio.run(scenario())


def test_runtime_warmup_failure_is_shared_and_does_not_retry_implicitly() -> None:
    async def scenario() -> None:
        calls = 0

        def warmup() -> None:
            nonlocal calls
            calls += 1
            raise ValueError("broken model")

        coordinator = RuntimeReadinessCoordinator(warmup)
        first = coordinator.start_background()
        assert first is not None
        for _ in range(2):
            try:
                await coordinator.ensure_ready()
            except RuntimeWarmupError:
                pass
            else:
                raise AssertionError("failed warmup must raise")
        assert calls == 1
        assert coordinator.state is RuntimeReadinessState.FAILED
        assert coordinator.error_type == "ValueError"

    asyncio.run(scenario())
