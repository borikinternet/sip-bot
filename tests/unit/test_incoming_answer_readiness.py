"""Incoming SIP provisional answer and asynchronous readiness gate contracts."""

from __future__ import annotations

import asyncio
from threading import Event
from types import SimpleNamespace

from sip_bot.runtime_wiring import IncomingCallReadinessGate
from sip_bot.runtime_readiness import RuntimeReadinessCoordinator
from sip_bot.sip_media.adapter import AdapterState, SipMediaAdapter, SipMediaConfig, caller_id_from_sip_uri
from sip_bot.sip_media.protocol_events import NormalizedSipEvent, SipEventKind


class _CallOpParam:
    def __init__(self) -> None:
        self.statusCode = 0


class _IncomingCall:
    instances: list["_IncomingCall"] = []

    def __init__(self, _account: object, _call_id: int) -> None:
        self.answers: list[_CallOpParam] = []
        self.__class__.instances.append(self)

    def getInfo(self) -> object:
        return SimpleNamespace(remoteUri="sip:peer@127.0.0.1")

    def answer(self, param: _CallOpParam) -> None:
        self.answers.append(param)


class _Account:
    pass


class _Pjsua:
    Call = _IncomingCall
    Account = _Account
    CallOpParam = _CallOpParam
    PJSIP_SC_SERVICE_UNAVAILABLE = 503
    PJSIP_SC_BUSY_HERE = 486


def _adapter() -> SipMediaAdapter:
    return SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:tester@127.0.0.1",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=4,
            output_capacity_frames=4,
            event_capacity=32,
            require_free_threaded=False,
        ),
        pjsua2_module=_Pjsua,
        enforce_runtime=False,
    )


def test_incoming_call_sends_explicit_180_then_public_answer_sends_200() -> None:
    _IncomingCall.instances.clear()
    adapter = _adapter()
    adapter._state = AdapterState.RUNNING
    adapter._install_callback_classes(_Pjsua)

    adapter._on_incoming_call(object(), SimpleNamespace(callId=7))
    call = _IncomingCall.instances[-1]
    events = adapter.drain_events()

    assert [param.statusCode for param in call.answers] == [180]
    assert events[0].kind is SipEventKind.PROTOCOL_REPLY
    assert events[0].status_code == 180
    assert events[0].local_reply is not None
    assert events[0].local_reply.action == "ring_before_readiness"
    assert events[1].kind is SipEventKind.CALL_STARTED
    assert events[1].details_dict()["answer_pending"] is True
    assert events[1].caller_id == "peer"

    assert adapter.answer() is True
    assert [param.statusCode for param in call.answers] == [180, 200]
    assert adapter.answer() is False
    assert all(param.statusCode != 0 for param in call.answers)


def test_incoming_call_can_be_rejected_with_explicit_503_after_readiness_failure() -> None:
    _IncomingCall.instances.clear()
    adapter = _adapter()
    adapter._state = AdapterState.RUNNING
    adapter._install_callback_classes(_Pjsua)
    adapter._on_incoming_call(object(), SimpleNamespace(callId=8))
    adapter.drain_events()

    assert adapter.reject(503, "ai_readiness_failed") is True
    call = _IncomingCall.instances[-1]
    events = adapter.drain_events()
    assert [param.statusCode for param in call.answers] == [180, 503]
    assert events[-1].kind is SipEventKind.PROTOCOL_REPLY
    assert events[-1].status_code == 503


class _FakeSip:
    def __init__(self) -> None:
        self.active_call_id = "call-1"
        self.answers: list[str] = []
        self.rejections: list[tuple[int, str]] = []

    def answer(self) -> bool:
        self.answers.append("200")
        return True

    def reject(self, status_code: int, reason: str) -> bool:
        self.rejections.append((status_code, reason))
        return True


class _ReadyReadiness:
    ready = True

    async def ensure_ready(self) -> object:
        raise AssertionError("ready runtime must not be warmed")


def _incoming_started(call_id: str = "call-1", caller_id: str | None = None) -> NormalizedSipEvent:
    return NormalizedSipEvent(
        call_id=call_id,
        kind=SipEventKind.CALL_STARTED,
        timestamp_ns=1,
        sequence=1,
        caller_id=caller_id,
        details=(("direction", "incoming"), ("answer_pending", True), ("provisional_status", 180)),
    )


def _terminal(call_id: str = "call-1") -> NormalizedSipEvent:
    return NormalizedSipEvent(
        call_id=call_id,
        kind=SipEventKind.REMOTE_CANCEL,
        timestamp_ns=2,
        sequence=2,
    )


def test_readiness_gate_skips_warmup_when_runtime_is_already_ready() -> None:
    async def scenario() -> None:
        sip = _FakeSip()
        gate = IncomingCallReadinessGate(sip, readiness=_ReadyReadiness())
        gate.observe(_incoming_started())
        await asyncio.sleep(0)
        assert sip.answers == ["200"]
        assert gate.pending_call_id is None

    asyncio.run(scenario())


def test_readiness_gate_warms_cold_runtime_off_loop_then_answers() -> None:
    async def scenario() -> None:
        sip = _FakeSip()
        ready = False
        warmup_started = Event()
        release = Event()

        def warmup() -> None:
            nonlocal ready
            warmup_started.set()
            release.wait(1.0)
            ready = True

        coordinator = RuntimeReadinessCoordinator(warmup)
        gate = IncomingCallReadinessGate(sip, readiness=coordinator)
        gate.observe(_incoming_started())
        await asyncio.to_thread(warmup_started.wait, 1.0)
        assert sip.answers == []
        release.set()
        await asyncio.sleep(0.05)
        assert sip.answers == ["200"]
        assert sip.rejections == []

    asyncio.run(scenario())


def test_readiness_gate_rejects_failed_warmup_and_does_not_fallback() -> None:
    async def scenario() -> None:
        sip = _FakeSip()
        coordinator = RuntimeReadinessCoordinator(
            lambda: (_ for _ in ()).throw(RuntimeError("cold start failed"))
        )
        gate = IncomingCallReadinessGate(sip, readiness=coordinator)
        gate.observe(_incoming_started())
        await asyncio.sleep(0.05)
        assert sip.answers == []
        assert sip.rejections == [(503, "ai_readiness_failed:RuntimeError")]

    asyncio.run(scenario())


def test_readiness_gate_drops_warmup_result_after_remote_cancel() -> None:
    async def scenario() -> None:
        sip = _FakeSip()
        release = Event()
        warmup_started = Event()
        ready = False

        def warmup() -> None:
            nonlocal ready
            warmup_started.set()
            release.wait(1.0)
            ready = True

        coordinator = RuntimeReadinessCoordinator(warmup)
        gate = IncomingCallReadinessGate(sip, readiness=coordinator)
        gate.observe(_incoming_started())
        await asyncio.to_thread(warmup_started.wait, 1.0)
        gate.observe(_terminal())
        release.set()
        await asyncio.sleep(0.05)
        assert sip.answers == []
        assert sip.rejections == []
        assert gate.pending_call_id is None

    asyncio.run(scenario())


def test_sip_uri_user_part_is_the_rag_routing_key() -> None:
    assert caller_id_from_sip_uri("<sips:demo-a1@pbx.example>;tag=1") == "demo-a1"
    assert caller_id_from_sip_uri("sip:demo-a1@pbx.example;transport=tls") == "demo-a1"
    assert caller_id_from_sip_uri("display name <sip:demo-a1@pbx.example>") == "demo-a1"
    assert caller_id_from_sip_uri("sip:pbx.example") is None


def test_readiness_gate_loads_caller_rag_before_200_and_cleans_on_terminal() -> None:
    async def scenario() -> None:
        sip = _FakeSip()
        prepared: list[tuple[str, str]] = []
        cleaned: list[tuple[str, str]] = []

        def prepare(call_id: str, caller_id: str) -> None:
            prepared.append((call_id, caller_id))

        def cleanup(call_id: str, caller_id: str) -> None:
            cleaned.append((call_id, caller_id))

        gate = IncomingCallReadinessGate(
            sip,
            readiness=_ReadyReadiness(),
            call_prepare=prepare,
            call_cleanup=cleanup,
        )
        gate.observe(_incoming_started(caller_id="demo-rag-1"))
        await asyncio.sleep(0.05)
        assert prepared == [("call-1", "demo-rag-1")]
        assert sip.answers == ["200"]

        gate.observe(_terminal())
        await asyncio.sleep(0.05)
        assert cleaned == [("call-1", "demo-rag-1")]

    asyncio.run(scenario())


def test_readiness_gate_waits_for_timed_out_worker_before_cleanup() -> None:
    async def scenario() -> None:
        sip = _FakeSip()
        started = Event()
        release = Event()
        cleaned: list[str] = []

        def prepare(_call_id: str, _caller_id: str) -> None:
            started.set()
            release.wait(1.0)

        def cleanup(_call_id: str, caller_id: str) -> None:
            cleaned.append(caller_id)

        gate = IncomingCallReadinessGate(
            sip,
            readiness=_ReadyReadiness(),
            call_prepare=prepare,
            call_cleanup=cleanup,
            preparation_timeout_s=0.01,
        )
        gate.observe(_incoming_started(caller_id="demo-slow"))
        await asyncio.to_thread(started.wait, 1.0)
        await asyncio.sleep(0.05)
        assert sip.answers == []
        assert sip.rejections == [(503, "ai_readiness_failed:TimeoutError")]
        assert cleaned == []
        release.set()
        await asyncio.sleep(0.05)
        assert cleaned == ["demo-slow"]

    asyncio.run(scenario())
