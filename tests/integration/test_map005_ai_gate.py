from __future__ import annotations

from sip_bot.sip_media.media_port import EgressSourceMode


def test_ai_gate_acceptance_contract_keeps_source_lifecycle_explicit() -> None:
    # The real LLM/XTTS run is main-executor-only; this test protects the
    # integration vocabulary that the target gate must report.
    assert EgressSourceMode.PLAYING.value == "playing"
    assert EgressSourceMode.PREROLL.value == "preroll"
    assert EgressSourceMode.CANCELLED.value == "cancelled"
