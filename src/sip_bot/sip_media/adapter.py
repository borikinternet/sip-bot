"""Application SIP/media adapter over the accepted PJSUA2/PJMEDIA baseline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import queue
from threading import RLock
import time
from typing import Any, Callable, Iterable
from uuid import uuid4

from ..config import RuntimeConfig
from ..runtime import RuntimeCompatibilityError, probe_runtime
from .media_port import EgressSourceMode, PcmAudioBridge
from .models import MediaNegotiationError, NegotiatedMediaProfile, PcmFrame
from .protocol_events import (
    Details,
    LocalProtocolReply,
    NormalizedSipEvent,
    SipEventKind,
    SipEventSink,
    SipMethod,
    protocol_reply_for,
)


class AdapterState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class SipMediaConfig:
    """Explicit application-facing settings for one PJSUA2 adapter."""

    bind_host: str
    bind_port: int
    local_uri: str
    codec: str
    sample_rate_hz: int
    channels: int
    input_capacity_frames: int
    output_capacity_frames: int
    event_capacity: int
    require_free_threaded: bool = True

    @classmethod
    def from_runtime_config(
        cls,
        config: RuntimeConfig,
        *,
        local_uri: str = "sip:tester@127.0.0.1",
        bind_port: int | None = None,
    ) -> "SipMediaConfig":
        return cls(
            bind_host=config.sip_bind_host,
            bind_port=config.sip_bind_port if bind_port is None else bind_port,
            local_uri=local_uri,
            codec=config.sip_codec,
            sample_rate_hz=config.sip_sample_rate_hz,
            channels=config.sip_channels,
            input_capacity_frames=config.audio_input_buffer_capacity_frames,
            output_capacity_frames=config.audio_output_buffer_capacity_frames,
            event_capacity=config.control_event_buffer_capacity,
            require_free_threaded=config.require_free_threaded,
        )

    def __post_init__(self) -> None:
        if self.codec.upper() != "PCMU":
            raise ValueError("the accepted MVP SIP codec is PCMU")
        if self.bind_port < 1 or self.bind_port > 65535:
            raise ValueError("bind_port is outside the UDP port range")
        if self.sample_rate_hz != 8000 or self.channels != 1:
            raise ValueError("the accepted MVP media profile is 8 kHz mono")
        if min(self.input_capacity_frames, self.output_capacity_frames, self.event_capacity) < 1:
            raise ValueError("bounded queue capacities must be positive")


@dataclass(slots=True)
class _CallContext:
    call_id: str
    call: Any
    peer_uri: str
    direction: str
    channel_id: str
    generation: int = 1
    answered: bool = False
    media_started: bool = False
    close_requested: bool = False
    closed: bool = False
    profile: NegotiatedMediaProfile | None = None
    bridge: PcmAudioBridge | None = None
    media_index: int | None = None
    last_media_direction: int | None = None
    last_protocol_method: SipMethod | None = None


class SipMediaAdapter:
    """Own one endpoint, one account, one call and one media bridge.

    PJSUA2 callbacks only update the scoped context and enqueue compact typed
    events.  ``dispatch_events`` is the explicit handoff to an upper control
    consumer and is never called by a native callback.
    """

    def __init__(
        self,
        config: SipMediaConfig | RuntimeConfig | None = None,
        *,
        local_uri: str = "sip:tester@127.0.0.1",
        bind_port: int | None = None,
        event_sink: SipEventSink | Callable[[NormalizedSipEvent], None] | None = None,
        pjsua2_module: Any | None = None,
        enforce_runtime: bool = True,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if config is None:
            config = RuntimeConfig.from_constants()
        if isinstance(config, RuntimeConfig):
            config = SipMediaConfig.from_runtime_config(config, local_uri=local_uri, bind_port=bind_port)
        self.config = config
        self.event_sink = event_sink
        self._pjsua2 = pjsua2_module
        self._enforce_runtime = enforce_runtime
        self._clock_ns = clock_ns
        self._event_queue: queue.Queue[NormalizedSipEvent] = queue.Queue(maxsize=config.event_capacity)
        self._event_lock = RLock()
        self._event_sequence = 0
        self._state = AdapterState.STOPPED
        self._endpoint: Any | None = None
        self._account: Any | None = None
        self._call_class: type[Any] | None = None
        self._account_class: type[Any] | None = None
        self._call: _CallContext | None = None
        self._last_runtime_probe: Any | None = None
        self._dropped_events = 0
        self._last_media_stats: dict[str, int] = {}

    @property
    def state(self) -> AdapterState:
        return self._state

    @property
    def active_call_id(self) -> str | None:
        return self._call.call_id if self._call is not None and not self._call.closed else None

    @property
    def dropped_event_count(self) -> int:
        return self._dropped_events

    @property
    def runtime_probe(self) -> Any | None:
        return self._last_runtime_probe

    def start(self) -> Any:
        if self._state is AdapterState.RUNNING:
            return self._last_runtime_probe
        if self._state is AdapterState.CLOSED:
            raise RuntimeError("adapter cannot be restarted after close")
        pjsua2 = self._load_pjsua2()
        if self._enforce_runtime:
            probe = probe_runtime()
            self._last_runtime_probe = probe
            if not probe.meets(RuntimeConfig.from_constants()):
                raise RuntimeCompatibilityError(
                    "SIP/media adapter requires the target free-threaded CPython runtime; "
                    f"observed executable={probe.executable} version={probe.version} "
                    f"Py_GIL_DISABLED={probe.py_gil_disabled} gil_enabled={probe.gil_enabled}"
                )
        endpoint = pjsua2.Endpoint()
        try:
            endpoint.libCreate()
            ep_config = pjsua2.EpConfig()
            ep_config.logConfig.level = 0
            endpoint.libInit(ep_config)
            transport_config = pjsua2.TransportConfig()
            transport_config.port = self.config.bind_port
            transport_type = getattr(pjsua2, "PJSIP_TRANSPORT_UDP")
            endpoint.transportCreate(transport_type, transport_config)
            endpoint.libStart()
            endpoint.audDevManager().setNullDev()
            self._endpoint = endpoint
            self._install_callback_classes(pjsua2)
            account_config = pjsua2.AccountConfig()
            account_config.idUri = self.config.local_uri
            account = self._account_class()  # type: ignore[misc]
            account.create(account_config, True)
            self._account = account
            self._state = AdapterState.RUNNING
            return self._last_runtime_probe
        except BaseException:
            self._account = None
            self._endpoint = None
            try:
                endpoint.libDestroy()
            except BaseException:
                pass
            raise

    def poll(self, timeout_ms: int = 10) -> int:
        """Let PJSUA2 process signaling/media callbacks for a bounded interval."""

        if self._state is not AdapterState.RUNNING or self._endpoint is None:
            raise RuntimeError("adapter is not running")
        return int(self._endpoint.libHandleEvents(max(0, int(timeout_ms))))

    def make_call(self, peer_uri: str, *, call_id: str | None = None) -> str:
        self._require_running()
        if self._call is not None and not self._call.closed:
            raise RuntimeError("one active call is already owned by the adapter")
        if self._account is None or self._call_class is None:
            raise RuntimeError("PJSUA2 account is not initialized")
        application_call_id = call_id or f"call-{uuid4().hex}"
        call = self._call_class(self._account, getattr(self._pjsua2, "PJSUA_INVALID_ID"), self)  # type: ignore[misc]
        context = _CallContext(
            call_id=application_call_id,
            call=call,
            peer_uri=peer_uri,
            direction="outgoing",
            channel_id=f"{application_call_id}:media",
        )
        self._call = context
        try:
            call.makeCall(peer_uri, self._pjsua2.CallOpParam(True))
        except BaseException:
            self._call = None
            call = None
            raise
        self._emit(
            SipEventKind.CALL_STARTED,
            application_call_id,
            details=(
                ("direction", "outgoing"),
                ("peer_uri", peer_uri),
            ),
        )
        return application_call_id

    def answer(self) -> bool:
        """Answer the current incoming call without an upper-layer round trip."""

        context = self._require_call()
        if context.closed:
            return False
        context.call.answer(self._pjsua2.CallOpParam(True))
        return True

    def hangup(self, reason: str = "local_hangup") -> bool:
        context = self._require_call()
        if context.closed or context.close_requested:
            return False
        context.close_requested = True
        try:
            context.call.hangup(self._pjsua2.CallOpParam(True))
        except BaseException as exc:
            self._emit(
                SipEventKind.MEDIA_FAILED,
                context.call_id,
                reason=f"local hangup failed: {exc}",
                details=(("operation", "hangup"),),
            )
            self._close_context(context, reason)
        return True

    def hold(self) -> bool:
        context = self._require_call()
        if context.closed:
            return False
        context.call.setHold(self._pjsua2.CallOpParam(True))
        return True

    def resume(self) -> bool:
        context = self._require_call()
        if context.closed:
            return False
        prm = self._pjsua2.CallOpParam(True)
        prm.opt.flag = getattr(self._pjsua2, "PJSUA_CALL_UNHOLD", 0)
        context.call.reinvite(prm)
        return True

    def update(self) -> bool:
        context = self._require_call()
        if context.closed:
            return False
        context.call.update(self._pjsua2.CallOpParam(True))
        return True

    def transfer(self, target: str) -> bool:
        context = self._require_call()
        if context.closed:
            return False
        context.call.xfer(target, self._pjsua2.CallOpParam(True))
        return True

    def next_ingress_frame(self) -> PcmFrame | None:
        context = self._require_call()
        return context.bridge.next_ingress() if context.bridge is not None else None

    def enqueue_egress_frame(self, frame: PcmFrame) -> bool:
        context = self._require_call()
        if context.bridge is None:
            raise RuntimeError("media is not active")
        return context.bridge.enqueue(frame)

    def set_egress_source_mode(self, mode: EgressSourceMode | str) -> bool:
        """Select the current call's source for the PJMEDIA egress clock."""

        context = self._require_call()
        if context.bridge is None:
            raise RuntimeError("media is not active")
        return context.bridge.set_egress_source_mode(mode)

    def media_profile(self) -> NegotiatedMediaProfile | None:
        return self._call.profile if self._call is not None else None

    def media_stats(self) -> dict[str, int]:
        if self._call and self._call.bridge:
            return self._call.bridge.stats.as_dict()
        return dict(self._last_media_stats)

    def drain_events(self, limit: int | None = None) -> tuple[NormalizedSipEvent, ...]:
        events: list[NormalizedSipEvent] = []
        while limit is None or len(events) < limit:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return tuple(events)

    def dispatch_events(self, limit: int | None = None) -> int:
        """Deliver queued events outside PJSUA2 callbacks."""

        if self.event_sink is None:
            return len(self.drain_events(limit))
        delivered = 0
        for event in self.drain_events(limit):
            if hasattr(self.event_sink, "publish"):
                self.event_sink.publish(event)  # type: ignore[union-attr]
            else:
                self.event_sink(event)  # type: ignore[operator]
            delivered += 1
        return delivered

    def close(self, reason: str = "adapter_shutdown") -> bool:
        if self._state is AdapterState.CLOSED:
            return False
        if self._call is not None:
            context = self._call
            if not context.closed:
                context.close_requested = True
                try:
                    if context.call.isActive():
                        context.call.hangup(self._pjsua2.CallOpParam(True))
                except BaseException:
                    pass
                self._close_context(context, reason)
            # Release callback-owned native objects while the endpoint and
            # account are still alive.  PJSUA2 destructors may call into the
            # native library during this release.
            context.call = None
            self._call = None
        if self._account is not None:
            account = self._account
            self._account = None
            try:
                account.shutdown()
            except BaseException:
                pass
        if self._endpoint is not None:
            endpoint = self._endpoint
            self._endpoint = None
            try:
                endpoint.libDestroy()
            except BaseException:
                pass
        self._state = AdapterState.CLOSED
        return True

    def __enter__(self) -> "SipMediaAdapter":
        self.start()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.close()

    def _load_pjsua2(self) -> Any:
        if self._pjsua2 is None:
            import pjsua2  # type: ignore[import-not-found]

            self._pjsua2 = pjsua2
        return self._pjsua2

    def _install_callback_classes(self, pjsua2: Any) -> None:
        adapter = self

        class AdapterCall(pjsua2.Call):  # type: ignore[misc]
            def __init__(self, account: Any, call_id: int, owner: "SipMediaAdapter") -> None:
                super().__init__(account, call_id)
                self._owner = owner

            def onCallState(self, prm: Any) -> None:
                self._owner._on_call_state(self, prm)

            def onCallMediaState(self, prm: Any) -> None:
                self._owner._on_call_media_state(self, prm)

            def onCallTsxState(self, prm: Any) -> None:
                self._owner._on_call_tsx_state(self, prm)

            def onCallRxReinvite(self, prm: Any) -> None:
                self._owner._on_call_rx_reinvite(self, prm)

            def onCallRxOffer(self, prm: Any) -> None:
                self._owner._on_call_rx_offer(self, prm)

            def onCallMediaTransportState(self, prm: Any) -> None:
                self._owner._on_media_transport_state(self, prm)

            def onCallTransferStatus(self, prm: Any) -> None:
                self._owner._on_transfer_status(self, prm)

        class AdapterAccount(pjsua2.Account):  # type: ignore[misc]
            def onIncomingCall(self, prm: Any) -> None:
                adapter._on_incoming_call(self, prm)

        self._call_class = AdapterCall
        self._account_class = AdapterAccount

    def _on_incoming_call(self, account: Any, prm: Any) -> None:
        call_id = f"call-in-{getattr(prm, 'callId', 'unknown')}"
        if self._call is not None and not self._call.closed:
            try:
                reject = self._pjsua2.Call(account, getattr(prm, "callId"))
                reject_prm = self._pjsua2.CallOpParam()
                reject_prm.statusCode = getattr(self._pjsua2, "PJSIP_SC_BUSY_HERE", 486)
                reject.answer(reject_prm)
            except BaseException:
                pass
            return
        if self._call_class is None:
            return
        call = self._call_class(account, getattr(prm, "callId"), self)
        peer_uri = ""
        try:
            peer_uri = str(call.getInfo().remoteUri)
        except BaseException:
            pass
        context = _CallContext(
            call_id=call_id,
            call=call,
            peer_uri=peer_uri,
            direction="incoming",
            channel_id=f"{call_id}:media",
        )
        self._call = context
        self._emit(
            SipEventKind.CALL_STARTED,
            call_id,
            details=(("direction", "incoming"), ("peer_uri", peer_uri)),
        )
        try:
            call.answer(self._pjsua2.CallOpParam(True))
        except BaseException as exc:
            self._emit(SipEventKind.MEDIA_FAILED, call_id, reason=f"incoming answer failed: {exc}")
            self._close_context(context, "incoming_answer_failed")

    def _on_call_state(self, call: Any, _prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        try:
            info = call.getInfo()
            state = str(getattr(info, "stateText", "")).upper()
            status_code = int(getattr(info, "lastStatusCode", 0) or 0)
            reason = str(getattr(info, "lastReason", "") or "")
        except BaseException as exc:
            self._emit(SipEventKind.MEDIA_FAILED, context.call_id, reason=f"call state read failed: {exc}")
            return
        details: Details = (("state", state), ("pjsua_call_id", getattr(info, "id", None)))
        if state == "CONFIRMED" and not context.answered:
            context.answered = True
            self._emit(
                SipEventKind.CALL_ANSWERED,
                context.call_id,
                status_code=status_code,
                reason=reason or None,
                details=details,
            )
        elif state == "DISCONNECTED":
            event_kind = (
                SipEventKind.REMOTE_CANCEL
                if not context.answered and status_code == 487 and not context.close_requested
                else SipEventKind.REMOTE_HANGUP
                if not context.close_requested
                else SipEventKind.CALL_ENDED
            )
            self._emit(
                event_kind,
                context.call_id,
                method=SipMethod.CANCEL if event_kind is SipEventKind.REMOTE_CANCEL else SipMethod.BYE
                if event_kind is SipEventKind.REMOTE_HANGUP
                else None,
                status_code=status_code,
                reason=reason or None,
                details=details,
            )
            self._close_context(context, reason or "call_disconnected")

    def _on_call_media_state(self, call: Any, _prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        try:
            info = call.getInfo()
            media = list(getattr(info, "media", ()))
            active_audio = self._select_active_audio_media(media)
            if active_audio is None:
                if context.media_started:
                    self._stop_bridge(context)
                    self._emit(SipEventKind.MEDIA_STOPPED, context.call_id)
                    context.media_started = False
                return
            media_index, media_info = active_audio
            profile = NegotiatedMediaProfile.from_call(call, media_index)
            old_profile = context.profile
            old_direction = context.last_media_direction
            direction = int(getattr(media_info, "dir", 0) or 0)
            if context.bridge is None:
                context.profile = profile
                context.media_index = media_index
                context.bridge = PcmAudioBridge(
                    pjsua2_module=self._pjsua2,
                    call_id=context.call_id,
                    channel_id=context.channel_id,
                    generation=context.generation,
                    profile=profile,
                    capacity_frames=self.config.input_capacity_frames,
                    output_capacity_frames=self.config.output_capacity_frames,
                    clock_ns=self._clock_ns,
                    failure_callback=lambda failure: self._on_bridge_failure(context.call_id, failure),
                )
                call_media = call.getAudioMedia(media_index)
                call_media.startTransmit(context.bridge.port)
                context.bridge.port.startTransmit(call_media)
                context.media_started = True
                self._emit(
                    SipEventKind.MEDIA_STARTED,
                    context.call_id,
                    media_profile=profile,
                    details=(("direction", direction), ("media_index", media_index)),
                )
            elif old_profile != profile or context.media_index != media_index:
                self._stop_bridge(context)
                context.profile = profile
                context.media_index = media_index
                context.bridge = PcmAudioBridge(
                    pjsua2_module=self._pjsua2,
                    call_id=context.call_id,
                    channel_id=context.channel_id,
                    generation=context.generation + 1,
                    profile=profile,
                    capacity_frames=self.config.input_capacity_frames,
                    output_capacity_frames=self.config.output_capacity_frames,
                    clock_ns=self._clock_ns,
                    failure_callback=lambda failure: self._on_bridge_failure(context.call_id, failure),
                )
                call_media = call.getAudioMedia(media_index)
                call_media.startTransmit(context.bridge.port)
                context.bridge.port.startTransmit(call_media)
                context.generation += 1
                self._emit(
                    SipEventKind.MEDIA_RECONFIGURED,
                    context.call_id,
                    media_profile=profile,
                    details=(("direction", direction), ("media_index", media_index)),
                )
            if old_direction is not None and old_direction != direction:
                if direction == getattr(self._pjsua2, "PJMEDIA_DIR_ENCODING", 1):
                    self._emit(SipEventKind.REMOTE_HOLD_STARTED, context.call_id, details=(("direction", direction),))
                elif direction == getattr(self._pjsua2, "PJMEDIA_DIR_ENCODING_DECODING", 3):
                    self._emit(SipEventKind.REMOTE_RESUMED, context.call_id, details=(("direction", direction),))
            context.last_media_direction = direction
        except MediaNegotiationError as exc:
            self._on_bridge_failure(context.call_id, f"media_negotiation:{exc}")
        except BaseException as exc:
            self._on_bridge_failure(context.call_id, f"media_state:{type(exc).__name__}:{exc}")

    def _select_active_audio_media(self, media: list[Any]) -> tuple[int, Any] | None:
        active_statuses = {
            getattr(self._pjsua2, "PJSUA_CALL_MEDIA_ACTIVE", 1),
            getattr(self._pjsua2, "PJSUA_CALL_MEDIA_LOCAL_HOLD", 2),
            getattr(self._pjsua2, "PJSUA_CALL_MEDIA_REMOTE_HOLD", 3),
        }
        audio_type = getattr(self._pjsua2, "PJMEDIA_TYPE_AUDIO")
        for item in media:
            if getattr(item, "type", None) != audio_type or getattr(item, "status", None) not in active_statuses:
                continue
            raw_index = getattr(item, "index", None)
            try:
                media_index = int(raw_index)
            except (TypeError, ValueError) as exc:
                raise MediaNegotiationError("active audio media does not expose a valid media index") from exc
            if media_index < 0:
                raise MediaNegotiationError("active audio media index must be non-negative")
            return media_index, item
        return None

    def _on_call_tsx_state(self, call: Any, prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        tsx_event = getattr(getattr(prm, "e", None), "tsx", None)
        method = self._method_from_text(getattr(tsx_event, "method", None))
        if method is None:
            return
        context.last_protocol_method = method
        status_code = int(getattr(tsx_event, "statusCode", 0) or 0)
        self._emit(
            SipEventKind.SIP_TRANSACTION,
            context.call_id,
            method=method,
            status_code=status_code or None,
            details=(("role", getattr(tsx_event, "role", None)), ("state", getattr(tsx_event, "state", None))),
        )

    def _on_call_rx_reinvite(self, call: Any, prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        method = SipMethod.INVITE
        context.last_protocol_method = method
        try:
            prm.statusCode = 200
            prm.isAsync = False
        finally:
            self._emit_protocol_reply(context, method)

    def _on_call_rx_offer(self, call: Any, prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        method = context.last_protocol_method if context.last_protocol_method in {SipMethod.INVITE, SipMethod.UPDATE} else SipMethod.UPDATE
        try:
            prm.statusCode = 200
        finally:
            self._emit_protocol_reply(context, method)

    def _on_media_transport_state(self, call: Any, prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        status = int(getattr(prm, "status", 0) or 0)
        if status:
            self._emit_protocol_reply(context, SipMethod.TRANSPORT)
            self._emit(
                SipEventKind.MEDIA_FAILED,
                context.call_id,
                method=SipMethod.TRANSPORT,
                status_code=int(getattr(prm, "sipErrorCode", 0) or 0) or None,
                reason=f"PJMEDIA transport status {status}",
                details=(("media_index", getattr(prm, "medIdx", None)), ("transport_state", getattr(prm, "state", None))),
            )
            return
        self._emit(
            SipEventKind.SIP_TRANSACTION,
            context.call_id,
            method=SipMethod.RTP,
            details=(("media_index", getattr(prm, "medIdx", None)), ("transport_state", getattr(prm, "state", None))),
        )

    def _on_transfer_status(self, call: Any, prm: Any) -> None:
        context = self._call
        if context is None or context.call is not call or context.closed:
            return
        status = int(getattr(prm, "statusCode", 0) or 0)
        self._emit(
            SipEventKind.SIP_TRANSACTION,
            context.call_id,
            method=SipMethod.INVITE,
            status_code=status or None,
            reason=str(getattr(prm, "reason", "") or "") or None,
            details=(("operation", "transfer"), ("final_notify", bool(getattr(prm, "finalNotify", False)))),
        )

    def _emit_protocol_reply(self, context: _CallContext, method: SipMethod) -> LocalProtocolReply:
        reply = protocol_reply_for(method)
        self._emit(
            SipEventKind.PROTOCOL_REPLY,
            context.call_id,
            method=method,
            status_code=reply.status_code,
            reason=reply.reason,
            local_reply=reply,
        )
        return reply

    def _on_bridge_failure(self, call_id: str, reason: str) -> None:
        kind = SipEventKind.RTP_TIMEOUT if "timeout" in reason.lower() else SipEventKind.MEDIA_FAILED
        context = self._call
        method = SipMethod.TRANSPORT if "transport" in reason.lower() else SipMethod.RTP
        if context is not None and context.call_id == call_id and not context.closed:
            # This is an internal immediate reaction.  It is queued for
            # observation, never delivered to a sink from a native callback.
            self._emit_protocol_reply(context, method)
            if context.bridge is not None:
                self._stop_bridge(context)
                context.media_started = False
                self._emit(SipEventKind.MEDIA_STOPPED, call_id, reason=reason)
        self._emit(kind, call_id, method=method, reason=reason)

    def _stop_bridge(self, context: _CallContext) -> None:
        bridge = context.bridge
        if bridge is None:
            return
        self._last_media_stats = bridge.stats.as_dict()
        try:
            if context.media_index is None:
                raise RuntimeError("media index is missing for active bridge")
            call_media = context.call.getAudioMedia(context.media_index)
            call_media.stopTransmit(bridge.port)
            bridge.port.stopTransmit(call_media)
        except BaseException:
            pass
        bridge.close()
        released_port = bridge.release_port()
        del released_port
        context.bridge = None

    def _close_context(self, context: _CallContext, reason: str) -> None:
        if context.closed:
            return
        had_media = context.media_started or context.bridge is not None
        self._stop_bridge(context)
        context.media_started = False
        context.closed = True
        if had_media:
            self._emit(
                SipEventKind.MEDIA_STOPPED,
                context.call_id,
                reason=reason,
                details=(("idempotent", False),),
            )

    def _emit(
        self,
        kind: SipEventKind,
        call_id: str,
        *,
        method: SipMethod | None = None,
        status_code: int | None = None,
        reason: str | None = None,
        details: Iterable[tuple[str, str | int | float | bool | None]] = (),
        media_profile: NegotiatedMediaProfile | None = None,
        local_reply: LocalProtocolReply | None = None,
    ) -> None:
        with self._event_lock:
            self._event_sequence += 1
            event = NormalizedSipEvent(
                call_id=call_id,
                kind=kind,
                timestamp_ns=self._clock_ns(),
                sequence=self._event_sequence,
                method=method,
                status_code=status_code,
                reason=reason,
                details=tuple(details),
                media_profile=media_profile,
                local_reply=local_reply,
            )
            try:
                self._event_queue.put_nowait(event)
            except queue.Full:
                self._dropped_events += 1

    @staticmethod
    def _method_from_text(value: Any) -> SipMethod | None:
        if value is None:
            return None
        try:
            return SipMethod(str(value).upper())
        except ValueError:
            return None

    def _require_running(self) -> None:
        if self._state is not AdapterState.RUNNING:
            raise RuntimeError("adapter is not running")

    def _require_call(self) -> _CallContext:
        self._require_running()
        if self._call is None:
            raise RuntimeError("no active call")
        return self._call
