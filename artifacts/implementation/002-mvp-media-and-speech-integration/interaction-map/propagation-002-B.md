# Propagation checkpoint: `002-B`

Дата: `2026-09-03`

Источник: [`../002-B/pcmu-profile-handoff.json`](../002-B/pcmu-profile-handoff.json),
[`../002-B/remote-bye.json`](../002-B/remote-bye.json),
[`../002-B/lifecycle-options.json`](../002-B/lifecycle-options.json)

Target runtime: Ubuntu-24.04/WSL2, user `sipbot`,
`/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`.

## Materialized contract

`002-B` materialized the SIP/media application boundary on the accepted
PJSUA2/PJMEDIA `2.17` and Baresip `1.0.0-4build14` baseline.

### Per-call media profile

The adapter selects the active audio entry from `CallInfo.media` and carries
its actual non-negative `CallMediaInfo.index` in the call scope. That same
index is passed to both `getStreamInfo(media_index)` and
`getAudioMedia(media_index)`; the wildcard `-1` is not used for profile
extraction. The selected index is also present in `media_started` and
`media_reconfigured` event details.

The authoritative `NegotiatedMediaProfile` fields are:

- `codec`, `payload_type`, `rx_payload_type`, `tx_payload_type`;
- `ptime_ms` and `frame_time_usec`;
- `sample_rate_hz`, `channels`, `pcm_bits_per_sample`;
- `frame_size_samples` and `frame_bytes`;
- `source` identifying the PJMEDIA stream information.

The target evidence observed PCMU payload type `0`, 20 ms ptime, 8 kHz,
one channel, 160 samples and 320 bytes per 16-bit PCM frame.

### Direct media handoff

`PcmAudioBridge` owns two bounded direct channels:

- ingress: native `AudioMediaPort.onFrameReceived` → `PcmFrame` → consumer
  such as `002-C`;
- egress: producer such as `002-H` → `PcmFrame` → native
  `AudioMediaPort.onFrameRequested`.

`PcmFrame` carries `call_id`, `channel_id`, `generation`, monotonic
`sequence`, `timestamp_ns`, PCM S16LE bytes and the negotiated profile. Audio
payload does not pass through Dispatcher/event bus. Overflow, callback error,
stale generation and closed-channel behavior are represented by bounded
counter/failure semantics; no audio recording is produced.

### Control handoff and lifecycle

The adapter publishes compact normalized control/media events through the
runtime event boundary. Local SIP/protocol reactions remain inside the
adapter and do not wait for Dispatcher, ASR, LLM or TTS. Media index/profile
are included in media-start/reconfigure evidence; transport events carry the
corresponding media index.

On media-state change the adapter re-evaluates the per-call profile and
rebuilds the bridge with a new generation when the profile or media index
changes. On close, remote BYE, transport failure or media failure it stops
both media directions, closes bounded channels and releases the native media
port before endpoint destruction. A later channel cannot consume stale data
from a closed generation.

## Verified semantics

- `002-B` B1–B4 acceptance is complete; no C1 generated binding or patch was
  changed.
- Target B3 corrective rerun: `1 passed, 2 deselected`; PCMU profile was
  obtained from the actual active media index.
- Full target B integration: `3 passed`; no native PJMEDIA teardown abort.
- Target remote-BYE evidence observed 10 ingress and 10 egress application
  frames, 3200 bytes in each direction, zero callback errors and zero queue
  drops.
- Approved `001-S` evidence independently confirms bidirectional PCMU/RTP
  loopback and remains the stand-level RTP baseline.
- `002-C` may consume the propagated profile/frame contract and must perform
  its own conversion/re-framing and boundary tests; this checkpoint does not
  close `002-C`.

## Evidence

- [`../002-B/runtime-import.json`](../002-B/runtime-import.json) — target
  CPython 3.14.7t, patched PJSUA2 import/lifecycle and no-GIL state;
- [`../002-B/pcmu-profile-handoff.json`](../002-B/pcmu-profile-handoff.json)
  — B3 PCMU profile, actual media index and target pass;
- [`../002-B/remote-bye.json`](../002-B/remote-bye.json) — B2/B3 media
  lifecycle, bidirectional application frame counters and remote BYE;
- [`../002-B/lifecycle-options.json`](../002-B/lifecycle-options.json) —
  OPTIONS 200, call lifecycle and cleanup;
- [`../002-B/commands.md`](../002-B/commands.md) — commands, exit codes and
  interpretation;
- [`../../../../docs/plans/plan-002-I-boundary-interaction-map.md`](../../../../docs/plans/plan-002-I-boundary-interaction-map.md)
  — receiving Map-I revision 4.

This checkpoint propagates the observed SIP/media boundary to the next
consumer. It does not claim that the overall map or the downstream speech
and dialogue components are complete.
