# 001-S preflight

Дата: `2026-08-27`  
Статус: `pass`

## Environment

- Ubuntu `24.04.4 LTS`, WSL2, `x86_64`, user `sipbot`.
- Target DUT runtime: `/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t`, CPython `3.14.7t`.
- No external SIP/PBX endpoint and no audio recording are used.
- The stand uses loopback SIP addresses only: peer `127.0.0.1:5080`, fake operator `127.0.0.1:5090`.

## Candidate freeze

The selected stand candidate is Ubuntu Noble's stable `baresip` package `1.0.0-4build14` from `universe`.
The installed modules used by the scenarios are `g711.so`, `ausine.so`, `echo.so` and `menu.so`; their hashes and
configuration paths are recorded in `candidate-manifest.json`.

The canonical peer configurations are:

- `config/peer-5080/config` and `config/peer-5080/accounts`;
- `config/operator-5090/config` and `config/operator-5090/accounts`.

The older descriptive files `config/baresip-peer.config` and `config/baresip-peer.accounts` are not used by the
execution commands.

## Preflight result

- Baresip starts as an independent local process.
- PJSUA2/PJMEDIA establishes a direct loopback call and remains on the free-threaded CPython runtime.
- PCMU negotiation and bidirectional RTP are observable.
- A remote `BYE` can be sent while the DUT probe is in its bounded operation window.
- A Baresip peer can transfer the call to the local fake operator, which answers it.

Baresip's attempted self-registration receives `501 Not Implemented`; this is expected for the direct-IP loopback
stand without a registrar and is not a blocker for the tested call paths.
