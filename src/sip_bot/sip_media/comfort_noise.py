"""Small deterministic comfort-noise source for the application PCMU path.

The source produces PCM16 samples for the already negotiated media clock.  It
is deliberately an in-process helper of ``PcmAudioBridge``: it has no SIP/RTP
knowledge, publishes no events, and performs no blocking I/O.

``level_dbov_magnitude`` is an engineering configuration value for the MVP,
not a claim of conformance to an absolute comfort-noise level.  A future
calibration pass can replace it with a measured level derived from the
negotiated call's background noise.
"""

from __future__ import annotations

from math import sqrt
import struct

from .models import NegotiatedMediaProfile


class ComfortNoiseSource:
    """Generate bounded, deterministic, exact-size PCM16 noise frames."""

    _UINT32_MASK = 0xFFFFFFFF
    _UINT32_SCALE = 1.0 / 4294967296.0

    def __init__(
        self,
        profile: NegotiatedMediaProfile,
        level_dbov_magnitude: int = 50,
        *,
        seed: int = 0x51F15EED,
    ) -> None:
        if profile.channels != 1 or profile.pcm_bits_per_sample != 16:
            raise ValueError("comfort noise requires mono PCM16")
        if not isinstance(level_dbov_magnitude, int) or isinstance(level_dbov_magnitude, bool):
            raise TypeError("level_dbov_magnitude must be an int")
        if not 0 <= level_dbov_magnitude <= 127:
            raise ValueError("level_dbov_magnitude must be in the dBov magnitude range 0..127")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("seed must be an int")
        self.profile = profile
        self.level_dbov_magnitude = level_dbov_magnitude
        self._state = seed & self._UINT32_MASK
        if self._state == 0:
            self._state = 1

        target_rms = 32767.0 * 10.0 ** (-level_dbov_magnitude / 20.0)
        # Uniform noise has RMS = peak / sqrt(3).  Do not clip at normal
        # levels; level 0 is still kept in the accepted configuration range.
        self._peak = max(1, min(32767, int(round(target_rms * sqrt(3.0)))))

    def _next_unit(self) -> float:
        """Return a reproducible value in [0, 1) using a tiny xorshift PRNG."""

        state = self._state
        state ^= (state << 13) & self._UINT32_MASK
        state ^= state >> 17
        state ^= (state << 5) & self._UINT32_MASK
        self._state = state & self._UINT32_MASK
        return self._state * self._UINT32_SCALE

    def next_frame(self, byte_count: int) -> bytes:
        """Return exactly ``byte_count`` bytes of little-endian PCM16."""

        if not isinstance(byte_count, int) or isinstance(byte_count, bool):
            raise TypeError("byte_count must be an int")
        if byte_count < 0 or byte_count % 2:
            raise ValueError("PCM16 byte_count must be a non-negative even integer")
        payload = bytearray(byte_count)
        has_nonzero_sample = False
        for offset in range(0, byte_count, 2):
            sample = int(round((self._next_unit() * 2.0 - 1.0) * self._peak))
            sample = max(-32768, min(32767, sample))
            if sample:
                has_nonzero_sample = True
            struct.pack_into("<h", payload, offset, sample)
        # A very low configured level can round a short frame to digital zero.
        # Preserve the source contract (audible/transport-visible non-zero
        # frame) without introducing a periodic waveform for normal levels.
        if byte_count and not has_nonzero_sample:
            struct.pack_into("<h", payload, 0, 1)
        return bytes(payload)
