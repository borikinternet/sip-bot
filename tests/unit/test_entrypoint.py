"""Bootstrap import and strict preflight tests."""

from sip_bot import __version__
from sip_bot.runtime import probe_runtime


def test_package_and_runtime_probe_are_importable() -> None:
    probe = probe_runtime()

    assert __version__ == "0.1.0"
    assert probe.implementation == "cpython"
    assert len(probe.version) == 3
    assert probe.gil_enabled in (True, False, None)
