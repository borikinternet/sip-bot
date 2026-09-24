# 021-E local WSL infrastructure evidence — 2026-09-23

Статус: `pass` для FreeSWITCH mirrored/LAN SIP-RTP configuration; host-side registered browser proof относится к
предыдущему NAT/forwarder режиму и не заменяет внешний phone-LAN check. Это не registered browser → queue → bot gate.

## FreeSWITCH

Distribution: `Debian-Bookworm-FS`; service state from `fs_cli`: `active`/ready, FreeSWITCH `1.11.3`.

Fresh local inspection after switching WSL to mirrored mode showed:

- WSL LAN interface `eth2` on `192.168.1.74/24`;
- `internal` SIP profile on `192.168.1.74:5060`;
- WS binding `192.168.1.74:5066`;
- WSS binding `sips:mod_sofia@192.168.1.74:7443;transport=wss`;
- `mod_callcenter` is loaded;
- queues `science-bot@default` and `support@default` exist.

Inside the FreeSWITCH WSL environment, this read-only WebSocket upgrade probe:

```text
curl -sk --http1.1 https://192.168.1.74:7443/ \
  -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
  -H 'Sec-WebSocket-Key: SGVsbG9XU1M=' \
  -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Protocol: sip'
```

returned:

```text
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Protocol: sip
```

This confirms the current local WSS transport and SIP subprotocol response.

## Previous host-side browser proof

Before mirrored mode, Windows had an active route to the NAT WSL subnet and a conference-only user-level TCP
forwarder exposed `192.168.1.74:7443`. The fresh browser probe in that mode passed:

- two WSS connections and SIP REGISTER (`1000`/`1001`);
- incoming offer with ICE and DTLS fingerprint;
- confirmed call;
- `connectionState=connected`, `iceConnectionState=connected`, `dtlsState=connected` on both sides;
- bidirectional media counters (`229/213` packets caller, `209/209` packets callee in the sampled window);
- BYE completion.

The self-signed certificate remains intentionally accepted only by the isolated diagnostic browser.

## RTP/NAT decision

Current FreeSWITCH values after the mirrored-LAN patch are:

```text
Auto-NAT:    false
RTP-IP:      192.168.1.74
Ext-RTP-IP:  192.168.1.74
SIP-IP:      192.168.1.74
Ext-SIP-IP:  192.168.1.74
candidate ACL: rfc1918.auto
```

The values are now pinned through `local_ip_v4`, `external_rtp_ip`, `external_sip_ip`, and the internal profile bind.
This is the direct mirrored-LAN path, so the same reachable address is used for signaling and SDP/RTP publication;
no TCP-only bridge is involved and no STUN/`autonat` change is introduced. Windows denied automatic creation of the
Hyper-V inbound rule from the non-elevated Codex session; an elevated host policy may still be required for the phone
to reach WSS and the FreeSWITCH RTP range (`16384-32768/udp`).

No claim is made here for browser → `mod_callcenter` → bot sequencing, caller-ID correlation, or custom-RAG isolation.
