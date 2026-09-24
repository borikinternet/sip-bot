from __future__ import annotations

from sip_bot.playback import PlaybackChannel, PlaybackEventKind
from sip_bot.sip_media.media_port import EgressSourceMode, PcmAudioBridge
from sip_bot.sip_media.models import NegotiatedMediaProfile, PcmFrame
from sip_bot.tts import MediaPacer, TtsOutputBuffer, TtsPcmChunk


class _Vector:
    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload

    def size(self) -> int:
        return len(self.payload)

    def copy_to_bytearray(self, target: bytearray) -> None:
        target[:] = self.payload

    def assign_from_bytes(self, payload: bytes) -> None:
        self.payload = bytes(payload)


class _Frame:
    def __init__(self, capacity: int) -> None:
        self.buf = _Vector()
        self.size = capacity
        self.type = 0


class _Port:
    def createPort(self, _name: str, _fmt: object) -> None:
        return None


class _Pjsua:
    class AudioMediaPort(_Port):
        pass

    MediaFormatAudio = type("MediaFormatAudio", (), {})
    PJMEDIA_TYPE_AUDIO = 1
    PJMEDIA_FRAME_TYPE_NONE = 0
    PJMEDIA_FRAME_TYPE_AUDIO = 1


def profile() -> NegotiatedMediaProfile:
    return NegotiatedMediaProfile("PCMU", 0, 20.0, 8000, 1, 160, rx_payload_type=0, tx_payload_type=0)


def pcm_frame(p: NegotiatedMediaProfile, sequence: int = 1, value: int = 7) -> PcmFrame:
    return PcmFrame("call-c", "call-c:media", 1, sequence, sequence * 20_000_000, bytes([value]) * p.frame_bytes, p)


def tts_chunk(p: NegotiatedMediaProfile, sequence: int = 1) -> TtsPcmChunk:
    return TtsPcmChunk("op-c", "call-c", "call-c:tts", 1, sequence, b"\x07\x00" * p.frame_size_samples, p)


def test_media_source_modes_separate_startup_intentional_silence_and_underrun() -> None:
    p = profile()
    bridge = PcmAudioBridge(
        pjsua2_module=_Pjsua,
        call_id="call-c",
        channel_id="call-c:media",
        generation=1,
        profile=p,
        capacity_frames=4,
    )

    assert bridge.egress_source_mode is EgressSourceMode.IDLE
    idle = _Frame(p.frame_bytes)
    bridge.port.onFrameRequested(idle)
    assert len(idle.buf.payload) == p.frame_bytes
    assert idle.buf.payload != bytes(p.frame_bytes)
    assert bridge.stats.egress_underruns == 0
    assert bridge.stats.intentional_silence_frames == 1

    bridge.set_egress_source_mode(EgressSourceMode.PREROLL)
    preroll = _Frame(p.frame_bytes)
    bridge.port.onFrameRequested(preroll)
    assert len(preroll.buf.payload) == p.frame_bytes
    assert preroll.buf.payload != bytes(p.frame_bytes)
    assert bridge.stats.tts_startup_wait == 1
    assert bridge.stats.egress_underruns == 0

    assert bridge.enqueue(pcm_frame(p))
    playing = _Frame(p.frame_bytes)
    bridge.set_egress_source_mode(EgressSourceMode.PLAYING)
    bridge.port.onFrameRequested(playing)
    assert playing.buf.payload == bytes([7]) * p.frame_bytes
    assert bridge.stats.egress_underruns == 0

    underrun = _Frame(p.frame_bytes)
    bridge.port.onFrameRequested(underrun)
    assert len(underrun.buf.payload) == p.frame_bytes
    assert underrun.buf.payload != bytes(p.frame_bytes)
    assert bridge.stats.egress_underruns == 1

    bridge.set_egress_source_mode(EgressSourceMode.CANCELLED)
    cancelled = _Frame(p.frame_bytes)
    bridge.port.onFrameRequested(cancelled)
    assert bridge.stats.intentional_silence_frames == 2


def test_tts_output_boundary_frames_arbitrary_chunks_and_playback_generation() -> None:
    p = profile()
    output = TtsOutputBuffer(
        profile=p,
        call_id="call-c",
        channel_id="call-c:tts",
        generation=1,
        max_buffer_bytes=p.frame_bytes * 4,
        max_pending_frames=4,
        start_timestamp_ns=100,
    )
    first = tts_chunk(p)
    assert output.push(first)
    assert output.pending_frames == 1
    pacer = MediaPacer(output, clock_ns=lambda: 100)
    sent: list[PcmFrame] = []
    events = []
    channel = PlaybackChannel(
        call_id="call-c",
        channel_id="call-c:tts",
        generation=1,
        pacer=pacer,
        send_frame=sent.append,
        on_event=events.append,
        clock_ns=lambda: 100,
    )

    channel.open()
    assert channel.pump(100) == sent[0]
    assert events[1].kind is PlaybackEventKind.STARTED
    assert events[-1].kind is PlaybackEventKind.FRAME_SENT
    assert len(sent) == 1
    assert sent[0].pcm_s16le == first.pcm_s16le

    assert channel.cancel("barge_in")
    assert channel.closed
    assert output.cancelled
    assert events[-1].kind is PlaybackEventKind.CANCELLED


def test_media_draining_keeps_tail_frame_and_reclassifies_empty_tail_as_idle() -> None:
    p = profile()
    bridge = PcmAudioBridge(
        pjsua2_module=_Pjsua,
        call_id="call-drain",
        channel_id="call-drain:media",
        generation=1,
        profile=p,
        capacity_frames=4,
    )
    assert bridge.enqueue(
        PcmFrame("call-drain", "call-drain:media", 1, 1, 0, bytes([9]) * p.frame_bytes, p)
    )
    bridge.set_egress_source_mode(EgressSourceMode.DRAINING)

    tail = _Frame(p.frame_bytes)
    bridge.port.onFrameRequested(tail)
    assert tail.buf.payload == bytes([9]) * p.frame_bytes
    assert bridge.egress_source_mode is EgressSourceMode.DRAINING
    assert bridge.stats.egress_underruns == 0

    silence = _Frame(p.frame_bytes)
    bridge.port.onFrameRequested(silence)
    assert len(silence.buf.payload) == p.frame_bytes
    assert silence.buf.payload != bytes(p.frame_bytes)
    assert bridge.egress_source_mode is EgressSourceMode.IDLE
    assert bridge.stats.egress_underruns == 0
    assert bridge.stats.intentional_silence_frames == 1


def test_stale_tts_generation_is_dropped_before_playback() -> None:
    p = profile()
    output = TtsOutputBuffer(
        profile=p,
        call_id="call-c",
        channel_id="call-c:tts",
        generation=2,
        max_buffer_bytes=p.frame_bytes * 2,
        max_pending_frames=2,
    )
    stale = TtsPcmChunk("op-old", "call-c", "call-c:tts", 1, 1, b"\x01\x00" * p.frame_size_samples, p)
    assert not output.push(stale)
    assert output.stats.dropped_stale_chunks == 1
