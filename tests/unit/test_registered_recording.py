from __future__ import annotations

import json
import wave

from tools.freeswitch_workshop.registered_full_rehearsal import (
    _collect_recording,
    _insert_silence,
    _prepare_continuous_fixture,
    _registered_peer_config,
)
from tools.map005_stereo_recording import infer_recording_start_ns


def _wave(path, payload: bytes) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(payload)


def test_registered_peer_config_enables_baresip_recording(tmp_path) -> None:
    peer = _registered_peer_config(
        tmp_path / "stand",
        tmp_path / "fixture.wav",
        tmp_path / "recording",
        registrar_address="10.0.0.45:5060",
        peer_user="1000",
        peer_password="Workshop-2026!",
    )

    config = (peer / "config").read_text(encoding="utf-8")
    account = (peer / "accounts").read_text(encoding="utf-8")

    assert "module            sndfile.so" in config
    assert f"snd_path          {tmp_path / 'recording'}" in config
    assert "<sip:1000@10.0.0.45:5060>" in account
    assert "auth_user=1000" in account
    assert "auth_pass=Workshop-2026!" in account


def test_registered_input_fixture_can_keep_source_transmitting_after_last_turn(tmp_path) -> None:
    source = tmp_path / "source.wav"
    target = tmp_path / "target.wav"
    _wave(source, b"\x01\x00" * 2)

    _prepare_continuous_fixture(source, target, 0.5)

    with wave.open(str(target), "rb") as stream:
        assert stream.getnframes() == 2 + 4_000


def test_registered_fixture_can_shift_barge_in_window(tmp_path) -> None:
    source = tmp_path / "source.wav"
    target = tmp_path / "target.wav"
    _wave(source, b"\x01\x00" * 8_000)

    _insert_silence(source, target, at_s=0.5, duration_s=0.25)

    with wave.open(str(target), "rb") as stream:
        assert stream.getnframes() == 8_000 + 2_000


def test_collect_recording_keeps_raw_tracks_and_builds_stereo(tmp_path) -> None:
    recording_dir = tmp_path / "raw-source"
    recording_dir.mkdir()
    _wave(recording_dir / "dump-call-enc.wav", b"\x01\x00\x02\x00")
    _wave(recording_dir / "dump-call-dec.wav", b"\x0a\x00\x0b\x00")

    result = _collect_recording(recording_dir, tmp_path / "run", expected_ptime_ms=20.0)

    assert result["status"] == "pass"
    assert (tmp_path / "run" / "recordings" / "raw" / "dump-call-enc.wav").exists()
    assert (tmp_path / "run" / "recordings" / "raw" / "dump-call-dec.wav").exists()
    assert (tmp_path / "run" / "recordings" / "conversation-stereo.wav").exists()
    manifest = json.loads(
        (tmp_path / "run" / "recordings" / "recording-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["mapping"] == {"left": "user_to_bot", "right": "bot_to_user"}
    assert manifest["alignment"]["policy"] == "strict_shared_timeline_trailing_cleanup_only"
    assert manifest["alignment"]["expected_ptime_ms"] == 20.0


def test_collect_recording_uses_answered_call_window_not_raw_track_duration(tmp_path) -> None:
    recording_dir = tmp_path / "raw-source"
    recording_dir.mkdir()
    _wave(recording_dir / "dump-call-enc.wav", b"\x01\x00" * 8_000)
    _wave(recording_dir / "dump-call-dec.wav", b"\x0a\x00" * 8_000)

    result = _collect_recording(
        recording_dir,
        tmp_path / "run",
        expected_ptime_ms=20.0,
        call_window_ms=1_000.0,
    )

    assert result["status"] == "pass"
    manifest = json.loads(
        (tmp_path / "run" / "recordings" / "recording-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["alignment"]["policy"] == "answered_call_event_window"
    assert manifest["alignment"]["call_window_ms"] == 1_000.0
    assert manifest["alignment"]["call_window_is_authoritative"] is True
    assert manifest["alignment"]["max_trailing_padding_applies"] is False
    with wave.open(str(tmp_path / "run" / "recordings" / "conversation-stereo.wav"), "rb") as stream:
        assert stream.getnframes() == 8_000


def test_collect_recording_pads_short_raw_track_to_answered_call_window(tmp_path) -> None:
    recording_dir = tmp_path / "raw-source"
    recording_dir.mkdir()
    _wave(recording_dir / "dump-call-enc.wav", b"\x01\x00" * 8_000)
    _wave(recording_dir / "dump-call-dec.wav", b"\x0a\x00" * 2_000)

    result = _collect_recording(
        recording_dir,
        tmp_path / "run",
        call_window_ms=1_000.0,
    )

    assert result["status"] == "pass"
    with wave.open(str(tmp_path / "run" / "recordings" / "conversation-stereo.wav"), "rb") as stream:
        assert stream.getnframes() == 8_000
    assert result["alignment"]["bot_to_user_padded_frames"] == 6_000


def test_collect_recording_aligns_directional_start_offsets(tmp_path) -> None:
    recording_dir = tmp_path / "raw-source"
    recording_dir.mkdir()
    enc = recording_dir / "dump-2026-09-14-10-00-00-enc.wav"
    dec = recording_dir / "dump-2026-09-14-10-00-01-dec.wav"
    _wave(enc, b"\x01\x00" * 8_000)
    _wave(dec, b"\x0a\x00" * 8_000)
    answer_start_ns = infer_recording_start_ns(enc)
    assert answer_start_ns is not None

    result = _collect_recording(
        recording_dir,
        tmp_path / "run",
        call_window_ms=2_000.0,
        call_window_start_ns=answer_start_ns,
    )

    assert result["status"] == "pass"
    alignment = result["alignment"]
    assert alignment["policy"] == "answered_call_event_window"
    assert alignment["user_to_bot_start_offset_frames"] == 0
    assert alignment["bot_to_user_start_offset_frames"] == 8_000
    assert alignment["bot_to_user_leading_padding_frames"] == 8_000
    with wave.open(str(tmp_path / "run" / "recordings" / "conversation-stereo.wav"), "rb") as stream:
        assert stream.getnframes() == 16_000
        first = stream.readframes(1)
        stream.setpos(8_000)
        second_track_start = stream.readframes(1)
    assert first == b"\x01\x00\x00\x00"
    assert second_track_start == b"\x00\x00\x0a\x00"
