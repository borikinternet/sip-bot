"""Typed SIP account-registration status used by the SIP adapter.

The PJSUA2 account owns the wire transaction.  These value objects carry only
an observation to the application control plane; credentials are deliberately
not represented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


REGISTRATION_EVENT_CALL_ID = "__registration__"


class RegistrationState(StrEnum):
    """Observable state of the optional account registration lifecycle."""

    DISABLED = "disabled"
    REGISTERING = "registering"
    REGISTERED = "registered"
    FAILED = "failed"
    UNREGISTERING = "unregistering"
    UNREGISTERED = "unregistered"


class RegistrationEventKind(StrEnum):
    """Meaning of one registration status observation."""

    DISABLED = "registration_disabled"
    STARTED = "registration_started"
    SUCCEEDED = "registration_succeeded"
    FAILED = "registration_failed"
    REFRESHED = "registration_refreshed"
    UNREGISTERING = "registration_unregistering"
    UNREGISTERED = "registration_unregistered"


_SIP_USERINFO_RE = re.compile(r"(?P<scheme>sips?):(?P<userinfo>[^@/?#]+)@(?P<rest>.+)", re.IGNORECASE)


def redact_sip_uri(uri: str) -> str:
    """Remove SIP userinfo, including a possible password, from a URI."""

    match = _SIP_USERINFO_RE.fullmatch(uri.strip())
    if match is None:
        return uri.strip()
    return f"{match.group('scheme')}:{match.group('rest')}"


@dataclass(frozen=True, slots=True)
class RegistrationStatus:
    """Password-free, immutable registration observation."""

    state: RegistrationState
    event: RegistrationEventKind
    enabled: bool
    registrar_uri: str
    status_code: int | None
    reason: str | None
    expires_seconds: int
    observed_at_ns: int
    expires_at_ns: int | None
    readiness: bool

    def __post_init__(self) -> None:
        if not isinstance(self.state, RegistrationState):
            raise TypeError("registration state must be RegistrationState")
        if not isinstance(self.event, RegistrationEventKind):
            raise TypeError("registration event must be RegistrationEventKind")
        if not isinstance(self.enabled, bool):
            raise TypeError("registration enabled must be bool")
        if self.observed_at_ns < 0:
            raise ValueError("registration observed_at_ns must be non-negative")
        if self.expires_seconds < 0:
            raise ValueError("registration expires_seconds must be non-negative")
        if self.expires_at_ns is not None and self.expires_at_ns < self.observed_at_ns:
            raise ValueError("registration expires_at_ns cannot precede observed_at_ns")
        if self.state is RegistrationState.REGISTERED and not self.readiness:
            raise ValueError("registered status must be ready")
        if self.state not in {RegistrationState.DISABLED, RegistrationState.REGISTERED} and self.readiness:
            raise ValueError("only disabled or registered status may be ready")
        if self.registrar_uri != redact_sip_uri(self.registrar_uri):
            raise ValueError("registration status must not contain SIP userinfo")

    def as_dict(self) -> dict[str, object]:
        """Return a diagnostics-safe representation with no credential field."""

        return {
            "state": self.state.value,
            "event": self.event.value,
            "enabled": self.enabled,
            "registrar_uri": self.registrar_uri,
            "status_code": self.status_code,
            "reason": self.reason,
            "expires_seconds": self.expires_seconds,
            "observed_at_ns": self.observed_at_ns,
            "expires_at_ns": self.expires_at_ns,
            "readiness": self.readiness,
        }
