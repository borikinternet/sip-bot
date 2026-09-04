# Plan-002-B evidence index

- [`runtime-import.json`](runtime-import.json) — target runtime, import, PJSUA2 lifecycle, no-GIL evidence.
- [`patch-identity.json`](patch-identity.json) — accepted C1/PJSUA2/PJMEDIA identity and unchanged patch hashes.
- [`lifecycle-options.json`](lifecycle-options.json) — Baresip call, automatic OPTIONS response, local hangup.
- [`remote-bye.json`](remote-bye.json) — remote BYE observed and call scope closed without Dispatcher/AI wait.
- [`pcmu-profile-handoff.json`](pcmu-profile-handoff.json) — target B3 rerun; PCMU profile and selected per-call media index.
- [`gap-B-002-B-GAP-001.md`](gap-B-002-B-GAP-001.md) — resolved APG gap record; local adapter defect and corrective evidence.
- [`../interaction-map/propagation-002-B.md`](../interaction-map/propagation-002-B.md) — B4 contract propagation checkpoint for Map-I revision 4.
- [`commands.md`](commands.md) — commands, exit codes, and acceptance interpretation.
- [`target-b2.stdout.log`](target-b2.stdout.log) / [`target-b2.stderr.log`](target-b2.stderr.log) — target B2 process stdout/stderr.
- [`target-b3.stdout.log`](target-b3.stdout.log) / [`target-b3.stderr.log`](target-b3.stderr.log) — target B3 corrective rerun stdout/stderr.
- [`target-b-full.stdout.log`](target-b-full.stdout.log) / [`target-b-full.stderr.log`](target-b-full.stderr.log) — full target B integration rerun stdout/stderr.

`pcmu-profile-handoff.json` proves the application profile/handoff path; the
same target adapter’s `remote-bye.json` records bidirectional application media
frames, and the approved `001-S` evidence proves PCMU/RTP loopback. Together
these close B3 without recording audio.
