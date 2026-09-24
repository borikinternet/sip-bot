# FreeSWITCH deployment evidence

Пошаговая реконструкция отдельного серверного развёртывания: [execution-journal.md](execution-journal.md). Это не журнал локального Debian WSL-стенда.

Target: `inrack@10.0.0.45`, Ubuntu 22.04.5 LTS.  Captured: `2026-09-22`.

## Accepted result

- Debian 12 Bookworm rootfs provenance and SHA-256 are recorded in `rootfs-provenance.txt`.
- FreeSWITCH `1.11.3`, `freeswitch-meta-vanilla`, `freeswitch-systemd`, and `freeswitch-mod-callcenter` are installed
  from the owner-provided signed Bookworm repository; see `package-status.txt` and `signing-key.txt`.
- Host unit `systemd-nspawn@freeswitch-bookworm.service` and guest unit `freeswitch.service` are enabled and active.
  A full container restart was included in the gate.
- The machine shares the Ubuntu host network. FreeSWITCH listens on `10.0.0.45:5060` and `10.0.0.45:5080`.
- `mod_sofia` and `mod_callcenter` are loaded. Queue `support@default`, agent `1001@default`, its tier, and extension
  `7000` are present.
- An external MicroSIP instance completed an authenticated REGISTER as extension `1000`; see
  `microsip-registration.txt`.
- Two server-local PJSUA2 endpoints completed direct and queue calls. `local-direct-active.txt` contains two
  `ACTIVE` PCMU/8 kHz legs. The queue evidence records `Trying -> Answered`, agent state `In a queue call`, and two
  `ACTIVE` PCMU/8 kHz legs in `local-queue-*.txt`.
- The probe cleaned up all calls and registrations. Subjective listening was not part of this headless deployment
  repeat; it remains a human workshop check.

## Platform decision

`apt-install-simulation.log` records why the Bookworm packages were not installed directly into Ubuntu 22.04: their
library requirements do not match Jammy. The Debian package baseline is isolated by `systemd-nspawn`; Docker and a
FreeSWITCH source build are not used. `freeswitch-bookworm.nspawn` captures the effective persistent machine settings.

The early `baresip-register.log` and `registration-state.txt` are retained corrective evidence from a rejected
host-local Baresip 1.0 probe (`400 Bad Contact Header`). They are not the accepted SIP result. The independent
MicroSIP registration and PJSUA2 call probes above passed.
