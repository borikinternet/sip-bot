# 001-S execution commands

Дата выполнения: `2026-08-27`  
Target distro: `Ubuntu-24.04`, user `sipbot`.

## Candidate and module provenance

```text
dpkg-query -W baresip
apt-cache policy baresip
baresip -h
sha256sum /usr/lib/baresip/modules/{g711.so,ausine.so,echo.so,menu.so}
```

Observed candidate: `baresip 1.0.0-4build14`, package candidate and installed version match. All four module hashes are
recorded in `candidate-manifest.json`.

## Reproducible scenarios

Each command starts its own Baresip process, writes the structured result to the named JSON file, and writes sibling
PJSUA2 and peer logs. Exit code was `0` for every command.

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py \
  --scenario lifecycle \
  --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/lifecycle.json \
  --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 \
  --peer-uri sip:peer@127.0.0.1:5080
```

Result: `pass`; event sequence includes `CALLING`, `EARLY`, `CONNECTING`, `CONFIRMED`, `probe_window_complete`,
`DISCONNECTED`.

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py \
  --scenario pcmu \
  --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/pcmu.json \
  --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 \
  --peer-uri sip:peer@127.0.0.1:5080
```

Result: `pass`; PCMU/8000/1 was negotiated, peer RTP counters were `201` transmit / `200` receive, and PJSUA2
captured `200` frames / `64000` bytes.

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py \
  --scenario bye \
  --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/bye.json \
  --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 \
  --peer-uri sip:peer@127.0.0.1:5080
```

Result: `pass`; the peer sent `b`/BYE after call establishment while a 10-second bounded background-work fixture was
active, PJSUA2 observed `DISCONNECTED` before local hangup, and the recorded loopback delivery interval was `0.453 ms`.

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py \
  --scenario transfer \
  --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/transfer.json \
  --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 \
  --peer-uri sip:peer@127.0.0.1:5080 \
  --operator-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/operator-5090 \
  --operator-uri sip:operator@127.0.0.1:5090
```

Result: `pass`; PJSUA2 issued a transfer request, the peer connected to `sip:operator@127.0.0.1:5090`, and the fake
operator log reports an established call.

## Scope notes

The `501 Not Implemented` response to self-registration is expected: the stand uses direct loopback URIs and does not
provide a registrar. No external PBX, SIP credential, user recording or production bot contract is involved.
