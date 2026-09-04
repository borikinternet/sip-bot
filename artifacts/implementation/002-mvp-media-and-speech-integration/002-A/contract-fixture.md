# 002-A control contract fixture

Map-002-I revision consumed: `3`.

The runtime foundation materializes these control-only envelope fields:

| Field | Meaning |
|---|---|
| `kind` | `call_open`, `call_close`, `channel_open`, `channel_close`, or `terminal` |
| `call_id` | Non-empty call scope identity |
| `channel_id` | Optional channel scope; required for channel events |
| `channel_generation` | Positive generation; required for channel events |
| `sequence` | Monotonic runtime-local event sequence starting at 1 |
| `timestamp_ns` | Runtime clock observation; tests inject a deterministic clock |
| `payload` | Immutable typed lifecycle value object |

Payload classes are `CallOpen`, `CallClose`, `ChannelOpen`, `ChannelClose`,
and `Terminal`. Payload type must match `kind`, and envelope/payload scope IDs
must match. Arbitrary bytes, audio frames, ASR/TTS streams, large text, and RAG
fragments are rejected by the envelope boundary.

Channel close is idempotent and cancels its token. A new handle has a new
generation; the closed old handle rejects dispatch, so stale producer output
cannot reach the new channel. A terminal event is published before scoped
channel and call close events.

Handoff to `002-E`: use `ControlEvent`, `ControlEventKind`, `ControlEventSink`,
`ChannelHandle`, `ChannelLease`, and `CancelToken` as the runtime foundation.
The full process-local fan-out/event-bus implementation and Dialogue FSM remain
owned by `002-E`; this slice does not claim them.
