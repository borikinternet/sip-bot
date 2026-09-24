from __future__ import annotations

from tools.vad_calibration_probe import Frame, _expected_speech, _frames, _runs


def test_frame_replay_is_exactly_20ms() -> None:
    frames = _frames(b"\x00\x00" * 320)
    assert [(frame.sequence, frame.start_ms, frame.end_ms) for frame in frames] == [(1, 0, 20), (2, 20, 40)]


def test_expected_speech_uses_manifest_intervals() -> None:
    segment = {"speech_started_s": 0.02, "speech_duration_s": 0.04}
    assert not _expected_speech(Frame(1, 0, 20, b""), [segment])
    assert _expected_speech(Frame(2, 20, 40, b""), [segment])
    assert _expected_speech(Frame(3, 40, 60, b""), [segment])


def test_runs_are_contiguous_regions() -> None:
    assert _runs([False, True, True, False, True]) == [(1, 3), (4, 5)]
