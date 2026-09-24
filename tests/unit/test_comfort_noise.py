from __future__ import annotations

import struct

import pytest

from sip_bot.sip_media.comfort_noise import ComfortNoiseSource
from sip_bot.sip_media.models import NegotiatedMediaProfile


def profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile("PCMU", 0, 20.0, 8000, 1, 160, rx_payload_type=0, tx_payload_type=0)


def test_comfort_noise_is_exact_size_nonzero_and_seed_reproducible() -> None:
    first = ComfortNoiseSource(profile(), 50, seed=1234)
    second = ComfortNoiseSource(profile(), 50, seed=1234)

    payload = first.next_frame(profile().frame_bytes)
    assert len(payload) == profile().frame_bytes
    assert payload != bytes(profile().frame_bytes)
    assert payload != first.next_frame(profile().frame_bytes)
    assert payload == second.next_frame(profile().frame_bytes)

    samples = struct.unpack("<160h", payload)
    rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
    assert 20.0 < rms < 500.0


def test_comfort_noise_rejects_invalid_pcm_size_and_level() -> None:
    source = ComfortNoiseSource(profile(), 50)
    with pytest.raises(ValueError, match="even"):
        source.next_frame(3)
    with pytest.raises(ValueError, match="0..127"):
        ComfortNoiseSource(profile(), 128)
