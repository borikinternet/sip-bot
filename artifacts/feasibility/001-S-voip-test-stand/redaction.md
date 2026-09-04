# 001-S redaction record

Проверено: `2026-08-27`.

- SIP endpoints are loopback addresses with synthetic user names only.
- No passwords, registrar credentials, external SIP addresses or PBX data are present.
- `ausine` generates a deterministic 440 Hz fixture; no input microphone or user conversation is recorded.
- Logs contain only local process diagnostics, signaling, event timing and RTP counters.
- The generated `uuid` files are local Baresip identifiers and contain no credentials.

The evidence is suitable for the repository's feasibility record; any future machine-specific or secret material must
remain outside the repository and be covered by `.gitignore`.
