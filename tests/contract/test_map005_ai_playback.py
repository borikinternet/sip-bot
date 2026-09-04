from __future__ import annotations

import pytest

from sip_bot.sip_media.media_port import EgressSourceMode, MediaPortStats


def test_source_mode_contract_is_typed_and_observable() -> None:
    assert [mode.value for mode in EgressSourceMode] == [
        "idle", "preroll", "playing", "draining", "cancelled", "closed"
    ]
    stats = MediaPortStats()
    stats.intentional_silence_frames = 2
    stats.tts_startup_wait = 3
    stats.egress_underruns = 4
    result = stats.as_dict()
    assert result["intentional_silence_frames"] == 2
    assert result["tts_startup_wait"] == 3
    assert result["egress_underruns"] == 4


def test_unknown_source_mode_cannot_be_silently_accepted() -> None:
    with pytest.raises(ValueError):
        EgressSourceMode("not-a-source")
