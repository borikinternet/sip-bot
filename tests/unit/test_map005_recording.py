from __future__ import annotations

import wave

from tools.map005_stereo_recording import build_stereo


def _wave(path, payload: bytes, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(payload)


def test_stereo_builder_preserves_left_right_mapping_and_metadata(tmp_path) -> None:
    enc = tmp_path / "call-enc.wav"
    dec = tmp_path / "call-dec.wav"
    stereo = tmp_path / "conversation-stereo.wav"
    manifest = tmp_path / "recording-manifest.json"
    _wave(enc, b"\x01\x00\x02\x00")
    _wave(dec, b"\x0a\x00\x0b\x00")

    result = build_stereo(enc, dec, stereo, manifest)

    assert result["status"] == "pass"
    assert result["mapping"] == {"left": "user_to_bot", "right": "bot_to_user"}
    with wave.open(str(stereo), "rb") as stream:
        assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()) == (2, 2, 8000, 2)
        assert stream.readframes(2) == b"\x01\x00\x0a\x00\x02\x00\x0b\x00"


def test_stereo_builder_explicitly_pads_mismatched_recordings(tmp_path) -> None:
    enc = tmp_path / "enc.wav"
    dec = tmp_path / "dec.wav"
    _wave(enc, b"\x01\x00\x02\x00")
    _wave(dec, b"\x0a\x00")

    result = build_stereo(enc, dec, tmp_path / "out.wav", tmp_path / "manifest.json")

    assert result["status"] == "pass"
    assert result["alignment"]["policy"] == "strict_shared_timeline_trailing_cleanup_only"
    assert result["alignment"]["user_to_bot_padded_frames"] == 0
    assert result["alignment"]["bot_to_user_padded_frames"] == 1
    assert result["alignment"]["max_trailing_padding_ms"] == 500.0
    assert result["alignment"]["actual_padding_ms"] == 0.125


def test_stereo_builder_rejects_missing_timeline_larger_than_cleanup_tail(tmp_path) -> None:
    enc = tmp_path / "enc.wav"
    dec = tmp_path / "dec.wav"
    _wave(enc, b"\x01\x00" * 4002)
    _wave(dec, b"\x0a\x00")

    try:
        build_stereo(enc, dec, tmp_path / "out.wav", tmp_path / "manifest.json")
    except ValueError as exc:
        assert "exceeds the allowed cleanup tail" in str(exc)
    else:
        raise AssertionError("large raw-track gap must be rejected")
