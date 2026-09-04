"""Pure Python G.711 PCMU conversion used at the application boundary."""

from __future__ import annotations

from array import array
import sys


_BIAS = 0x84
_CLIP = 32635


def _decode_sample(value: int) -> int:
    value = (~value) & 0xFF
    sign = value & 0x80
    exponent = (value >> 4) & 0x07
    mantissa = value & 0x0F
    sample = ((mantissa << 3) + _BIAS) << exponent
    sample -= _BIAS
    return -sample if sign else sample


def _encode_sample(sample: int) -> int:
    sample = max(-_CLIP, min(_CLIP, int(sample)))
    sign = 0x80 if sample < 0 else 0
    if sign:
        sample = -sample
    sample += _BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def decode_pcmu(payload: bytes | bytearray | memoryview) -> bytes:
    """Decode RTP PCMU octets to little-endian signed 16-bit PCM."""

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("PCMU payload must be bytes-like")
    samples = array("h", (_decode_sample(value) for value in bytes(payload)))
    if samples.itemsize != 2:
        raise RuntimeError("the platform does not expose 16-bit short samples")
    # array('h') is native-endian; the application contract is explicitly LE.
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def encode_pcmu(pcm_s16le: bytes | bytearray | memoryview) -> bytes:
    """Encode little-endian signed 16-bit PCM to RTP PCMU octets."""

    if not isinstance(pcm_s16le, (bytes, bytearray, memoryview)):
        raise TypeError("PCM payload must be bytes-like")
    payload = bytes(pcm_s16le)
    if len(payload) % 2:
        raise ValueError("PCM S16LE payload must contain whole samples")
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    return bytes(_encode_sample(sample) for sample in samples)


class PcmuCodec:
    """Namespaced codec facade for callers that prefer an object API."""

    decode = staticmethod(decode_pcmu)
    encode = staticmethod(encode_pcmu)
