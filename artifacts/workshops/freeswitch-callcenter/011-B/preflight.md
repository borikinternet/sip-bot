# Map-011 / 011-B MicroSIP preflight

Дата: 2026-09-20  
Результат: `partial pass` — package install and dual-process startup verified; account/call/audio acceptance pending.

## Package provenance

- Official download page: https://www.microsip.org/downloads
- Official portable archive: https://www.microsip.org/download/MicroSIP-3.22.16.zip
- Version: `3.22.16` (release date shown by vendor page: 2026-09-14)
- Archive SHA-256: `B269465205DF18DE018C2D78CA9D1107B396460E1E8D257C443E75FE99BE42F4`
- Executable SHA-256: `FE5AD81043E4F755DD8730A520917490787BB66F5AB7EF9E1172D637DB8B99DC`
- Executable signature: signer `CN=MSIP Code Signing 2025`, thumbprint `FDD0593557BAC6FAD1883DDD5403694DDAC76DF1`; Windows chain status `UntrustedRoot`. No certificate was added to a trust store and no Windows security check was bypassed.

## Installed copies

```text
%LOCALAPPDATA%\Programs\MicroSIP-Workshop\Caller-1000\MicroSIP.exe
%LOCALAPPDATA%\Programs\MicroSIP-Workshop\Agent-1001\MicroSIP.exe
```

Both copies were launched at the same time with `/minimized`; Windows showed two different process IDs and each directory generated its own `MicroSIP.ini`. The documented `/exit` command was sent to each copy; each invocation returned exit code `0`, and a subsequent process check found zero running MicroSIP processes.

## Not tested

- Account setup or SIP `REGISTER`.
- Direct call, SDP, RTP or codec negotiation with FreeSWITCH.
- Microphone/speaker routing or audible bidirectional media.

The Codex session has no native GUI surface for MicroSIP. These checks require an operator to configure both profiles in the application and confirm the audible result. This preflight does not claim a successful SIP call.
