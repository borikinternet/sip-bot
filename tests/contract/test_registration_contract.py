"""Contract tests for the optional PJSUA2 registration lifecycle."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sip_bot.config import RegistrationProfile
from sip_bot.sip_media.adapter import AdapterState, SipMediaAdapter, SipMediaConfig
from sip_bot.sip_media.protocol_events import SipEventKind
from sip_bot.sip_media.registration import (
    REGISTRATION_EVENT_CALL_ID,
    RegistrationEventKind,
    RegistrationState,
    RegistrationStatus,
    redact_sip_uri,
)


class _FakeAuthCredInfo:
    def __init__(self, scheme: str, realm: str, username: str, data_type: int, data: str) -> None:
        self.scheme = scheme
        self.realm = realm
        self.username = username
        self.dataType = data_type
        self.data = data


class _FakeCredVector(list[object]):
    def push_back(self, value: object) -> None:
        self.append(value)


class _FakeAccountConfig:
    def __init__(self) -> None:
        self.idUri = ""
        self.regConfig = SimpleNamespace(
            registrarUri="",
            registerOnAdd=True,
            timeoutSec=0,
        )
        self.sipConfig = SimpleNamespace(authCreds=_FakeCredVector())


class _FakeEndpoint:
    instances: list["_FakeEndpoint"] = []

    def __init__(self) -> None:
        self.destroyed = False
        self.codec_priorities: dict[str, int] = {}
        self.__class__.instances.append(self)

    def libCreate(self) -> None:
        return None

    def libInit(self, config: object) -> None:
        self.ep_config = config
        return None

    def transportCreate(self, _transport: object, _config: object) -> None:
        return None

    def libStart(self) -> None:
        return None

    def codecEnum2(self) -> list[object]:
        return [
            SimpleNamespace(codecId="PCMU/8000/1"),
            SimpleNamespace(codecId="G722/16000/1"),
        ]

    def codecSetPriority(self, codec_id: str, priority: int) -> None:
        self.codec_priorities[codec_id] = priority

    def audDevManager(self) -> "_FakeEndpoint":
        return self

    def setNullDev(self) -> None:
        return None

    def libDestroy(self) -> None:
        self.destroyed = True


class _FakeEpConfig:
    def __init__(self) -> None:
        self.logConfig = SimpleNamespace(level=0)
        self.medConfig = SimpleNamespace(noVad=False)


class _FakeTransportConfig:
    def __init__(self) -> None:
        self.port = 0


class _FakeCall:
    def __init__(self, _account: object, _call_id: int) -> None:
        return None


class _FakeCallOpParam:
    def __init__(self, _use_default: bool = False) -> None:
        self.statusCode = 0


class _FakeAccount:
    instances: list["_FakeAccount"] = []

    def __init__(self) -> None:
        self.created_config: _FakeAccountConfig | None = None
        self.registration_calls: list[bool] = []
        self.shutdown_called = False
        self.info = SimpleNamespace(
            regIsActive=False,
            regStatus=0,
            regStatusText="",
            regExpiresSec=0,
        )
        self.__class__.instances.append(self)

    def create(self, config: _FakeAccountConfig, _is_default: bool) -> None:
        self.created_config = config

    def getInfo(self) -> object:
        return self.info

    def setRegistration(self, renew: bool) -> None:
        self.registration_calls.append(renew)

    def shutdown(self) -> None:
        self.shutdown_called = True


class _FakePjsua:
    Endpoint = _FakeEndpoint
    EpConfig = _FakeEpConfig
    TransportConfig = _FakeTransportConfig
    AccountConfig = _FakeAccountConfig
    Account = _FakeAccount
    Call = _FakeCall
    CallOpParam = _FakeCallOpParam
    AuthCredInfo = _FakeAuthCredInfo
    PJSIP_TRANSPORT_UDP = 1
    PJSIP_CRED_DATA_PLAIN_PASSWD = 0


def _profile() -> RegistrationProfile:
    return RegistrationProfile(
        enabled=True,
        registrar_uri="sip:127.0.0.1:5099",
        identity_uri="sip:tester@127.0.0.1",
        username="tester",
        password="PUBLIC-DEMO-SIP-PASSWORD",
        expires_seconds=120,
    )


def _adapter() -> SipMediaAdapter:
    return SipMediaAdapter(
        SipMediaConfig(
            bind_host="127.0.0.1",
            bind_port=5070,
            local_uri="sip:direct@example.invalid",
            codec="PCMU",
            sample_rate_hz=8000,
            channels=1,
            input_capacity_frames=2,
            output_capacity_frames=2,
            event_capacity=32,
            require_free_threaded=False,
            registration_profile=_profile(),
        ),
        pjsua2_module=_FakePjsua,
        enforce_runtime=False,
        clock_ns=lambda: 1_000_000_000,
    )


@pytest.fixture(autouse=True)
def _reset_fake_state() -> None:
    _FakeEndpoint.instances.clear()
    _FakeAccount.instances.clear()


def test_registrar_uri_redaction_removes_userinfo_and_password() -> None:
    assert redact_sip_uri("sip:tester:secret@127.0.0.1:5060;transport=udp") == (
        "sip:127.0.0.1:5060;transport=udp"
    )


def test_enabled_profile_materializes_pjsua2_registrar_digest_and_expiry() -> None:
    adapter = _adapter()

    adapter.start()

    endpoint = _FakeEndpoint.instances[0]
    assert endpoint.ep_config.medConfig.noVad is True
    assert endpoint.codec_priorities == {"PCMU/8000/1": 255, "G722/16000/1": 0}
    account = _FakeAccount.instances[0]
    assert account.created_config is not None
    assert account.created_config.idUri == "sip:tester@127.0.0.1"
    assert account.created_config.regConfig.registrarUri == "sip:127.0.0.1:5099"
    assert account.created_config.regConfig.registerOnAdd is True
    assert account.created_config.regConfig.timeoutSec == 120
    credential = account.created_config.sipConfig.authCreds[0]
    assert isinstance(credential, _FakeAuthCredInfo)
    assert (credential.scheme, credential.realm, credential.username, credential.data) == (
        "digest",
        "*",
        "tester",
        "PUBLIC-DEMO-SIP-PASSWORD",
    )
    assert adapter.registration_ready is False
    assert adapter.drain_events()[0].registration_status is not None
    adapter.close()


def test_registration_callbacks_map_success_refresh_failure_and_unregister_without_password() -> None:
    adapter = _adapter()
    adapter.start()
    account = _FakeAccount.instances[0]
    callback = account

    callback.onRegStarted(SimpleNamespace(renew=True))
    account.info = SimpleNamespace(regIsActive=True, regStatus=200, regStatusText="OK", regExpiresSec=120)
    callback.onRegState(SimpleNamespace(code=200, reason="OK", expiration=120))
    assert adapter.registration_status.state is RegistrationState.REGISTERED
    assert adapter.registration_status.event is RegistrationEventKind.SUCCEEDED
    assert adapter.registration_ready is True

    callback.onRegState(SimpleNamespace(code=200, reason="OK", expiration=119))
    assert adapter.registration_status.event is RegistrationEventKind.REFRESHED
    assert adapter.registration_status.expires_seconds == 119

    account.info = SimpleNamespace(regIsActive=False, regStatus=403, regStatusText="Forbidden", regExpiresSec=0)
    callback.onRegState(SimpleNamespace(code=403, reason="Forbidden", expiration=0))
    assert adapter.registration_status.state is RegistrationState.FAILED
    assert adapter.registration_ready is False

    adapter._registration_close_requested = True
    callback.onRegStarted(SimpleNamespace(renew=False))
    assert adapter.registration_status.state is RegistrationState.UNREGISTERING
    account.info = SimpleNamespace(regIsActive=False, regStatus=200, regStatusText="OK", regExpiresSec=0)
    callback.onRegState(SimpleNamespace(code=200, reason="OK", expiration=0))
    assert adapter.registration_status.state is RegistrationState.UNREGISTERED

    events = adapter.drain_events()
    assert all(event.call_id == REGISTRATION_EVENT_CALL_ID for event in events)
    assert all(event.kind is SipEventKind.REGISTRATION_STATE for event in events)
    for event in events:
        assert event.registration_status is not None
        assert "PUBLIC-DEMO-SIP-PASSWORD" not in repr(event)
        assert "password" not in event.registration_status.as_dict()
    adapter.close()


def test_enabled_registration_failure_does_not_fallback_to_direct_uri() -> None:
    adapter = _adapter()
    adapter.start()

    with pytest.raises(RuntimeError, match="direct-URI admission is disabled"):
        adapter.make_call("sip:peer@127.0.0.1:5080")

    adapter.close()


def test_close_requests_unregister_before_account_shutdown_and_is_idempotent() -> None:
    adapter = _adapter()
    adapter.start()
    account = _FakeAccount.instances[0]

    assert adapter.close() is True
    assert account.registration_calls == [False]
    assert account.shutdown_called is True
    assert adapter.registration_status.state is RegistrationState.UNREGISTERED
    assert adapter.state is AdapterState.CLOSED
    assert adapter.close() is False
