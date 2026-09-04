"""Local SIP reactions and normalized application events.

PJSUA2 owns the wire transaction.  This module records the local reaction and
normalizes an observation for the upper control plane; it never calls a
Dispatcher or an AI component from a PJSUA2 callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol

from .models import NegotiatedMediaProfile


class SipMethod(StrEnum):
    BYE = "BYE"
    CANCEL = "CANCEL"
    OPTIONS = "OPTIONS"
    INVITE = "INVITE"
    UPDATE = "UPDATE"
    RTP = "RTP"
    TRANSPORT = "TRANSPORT"


class SipEventKind(StrEnum):
    CALL_STARTED = "call_started"
    CALL_ANSWERED = "call_answered"
    CALL_ENDED = "call_ended"
    REMOTE_HANGUP = "remote_hangup"
    REMOTE_CANCEL = "remote_cancel"
    REMOTE_HOLD_STARTED = "remote_hold_started"
    REMOTE_RESUMED = "remote_resumed"
    MEDIA_STARTED = "media_started"
    MEDIA_STOPPED = "media_stopped"
    MEDIA_RECONFIGURED = "media_reconfigured"
    RTP_TIMEOUT = "rtp_timeout"
    MEDIA_FAILED = "media_failed"
    SIP_TRANSACTION = "sip_transaction"
    PROTOCOL_REPLY = "protocol_reply"


@dataclass(frozen=True, slots=True)
class LocalProtocolReply:
    """The immediate local result required at a SIP protocol edge."""

    method: SipMethod
    status_code: int | None
    reason: str
    action: str
    automatic: bool = True


_LOCAL_REPLIES: Mapping[SipMethod, LocalProtocolReply] = {
    SipMethod.BYE: LocalProtocolReply(SipMethod.BYE, 200, "OK", "terminate_call"),
    SipMethod.CANCEL: LocalProtocolReply(SipMethod.CANCEL, 200, "OK", "cancel_pending_invite"),
    SipMethod.OPTIONS: LocalProtocolReply(SipMethod.OPTIONS, 200, "OK", "automatic_endpoint_reply"),
    SipMethod.INVITE: LocalProtocolReply(SipMethod.INVITE, 200, "OK", "accept_media_offer"),
    SipMethod.UPDATE: LocalProtocolReply(SipMethod.UPDATE, 200, "OK", "accept_media_update"),
    SipMethod.RTP: LocalProtocolReply(SipMethod.RTP, None, "media_timeout", "close_media"),
    SipMethod.TRANSPORT: LocalProtocolReply(SipMethod.TRANSPORT, None, "transport_failure", "close_call"),
}


def protocol_reply_for(method: str | SipMethod) -> LocalProtocolReply:
    """Return the table-driven local reaction for a supported edge."""

    try:
        normalized = SipMethod(str(method).upper())
    except ValueError as exc:
        raise ValueError(f"unsupported SIP protocol edge: {method!r}") from exc
    return _LOCAL_REPLIES[normalized]


Details = tuple[tuple[str, str | int | float | bool | None], ...]


@dataclass(frozen=True, slots=True)
class NormalizedSipEvent:
    """Immutable, small control-plane event; audio bytes never appear here."""

    call_id: str
    kind: SipEventKind
    timestamp_ns: int
    sequence: int
    method: SipMethod | None = None
    status_code: int | None = None
    reason: str | None = None
    details: Details = ()
    media_profile: NegotiatedMediaProfile | None = None
    local_reply: LocalProtocolReply | None = None

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ValueError("call_id must be non-empty")
        if self.timestamp_ns < 0 or self.sequence < 1:
            raise ValueError("event timestamp/sequence is invalid")
        if self.kind is SipEventKind.PROTOCOL_REPLY and self.local_reply is None:
            raise ValueError("protocol_reply event must include local_reply")
        if self.kind is not SipEventKind.PROTOCOL_REPLY and self.local_reply is not None:
            raise ValueError("local_reply is only valid for protocol_reply events")

    def details_dict(self) -> dict[str, str | int | float | bool | None]:
        return dict(self.details)

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "call_id": self.call_id,
            "kind": self.kind.value,
            "timestamp_ns": self.timestamp_ns,
            "sequence": self.sequence,
            "method": self.method.value if self.method else None,
            "status_code": self.status_code,
            "reason": self.reason,
            "details": self.details_dict(),
        }
        if self.media_profile is not None:
            result["media_profile"] = self.media_profile.as_dict()
        if self.local_reply is not None:
            result["local_reply"] = {
                "method": self.local_reply.method.value,
                "status_code": self.local_reply.status_code,
                "reason": self.local_reply.reason,
                "action": self.local_reply.action,
                "automatic": self.local_reply.automatic,
            }
        return result


class SipEventSink(Protocol):
    """Typed handoff consumed by a future Dispatcher/FSM integration."""

    def publish(self, event: NormalizedSipEvent) -> None:
        """Consume one normalized control-plane event."""
