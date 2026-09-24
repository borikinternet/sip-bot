# Ubuntu 22.04 deployment verification — 2026-09-22

Target: `inrack@10.0.0.45` (`a100-test`), Ubuntu 22.04, NVIDIA A100-SXM4-40GB.

## Result

The transferred project and model package is usable on Ubuntu 22.04. The application runtime was rebuilt locally for
this host instead of reusing the Ubuntu 24.04 binaries. CPython 3.14.7t remains free-threaded after all native imports.

- project regression: `245 passed, 3 skipped`;
- PJSUA2 2.17 lifecycle/no-GIL probe: PASS;
- WebRTC VAD, patched CTranslate2, tokenizers, torchaudio and monotonic-alignment imports: PASS with GIL disabled;
- faster-whisper ASR operation and streaming probes: PASS;
- XTTS operation, PCMU boundary and cancellation probes: PASS;
- Ollama `0.33.1`, `embeddinggemma` and `c3-qwen35-9b-q4km:latest`: PASS on CUDA;
- FreeSWITCH `1.11.3` with `mod_callcenter`: PASS in an autostarted Debian 12 `systemd-nspawn` machine using the
  Ubuntu host network; external MicroSIP REGISTER, direct `1000 -> 1001`, and queue `7000 -> support@default -> 1001`
  signaling/media probes: PASS;
- optional SIP REGISTER challenge, refresh and unregister lifecycle: PASS;
- current company-RAG full direct SIP/RTP rehearsal: PASS, including greeting, follow-up, barge-in, unknown-answer,
  transfer, report and stereo recording;
- RTP/media result: PCMU/8000/mono, `4049` ingress and egress frames, zero underruns, drops, overflows and callback
  errors.

The authoritative full-call result is
[`rag-direct-r1/map005-d-rehearsal.json`](rag-direct-r1/map005-d-rehearsal.json). The corresponding recording is
[`rag-direct-r1/recordings/conversation-stereo.wav`](rag-direct-r1/recordings/conversation-stereo.wav), and the call
report is [`rag-direct-r1/reports/j4-full-live-call/report.md`](rag-direct-r1/reports/j4-full-live-call/report.md).

`full-rehearsal-r1` is retained as corrective history. It ran the obsolete natural-science dialogue against the active
company corpus and therefore failed its transfer timing; it is not a runtime failure and is not the accepted result.

## Installed runtime

- CPython: `/home/inrack/.local/cpython-3.14.7t/bin/python3.14t`;
- combined venv: `/home/inrack/.cache/sip-bot-c4-xtts-v2-3.14.7t`;
- PJSIP/PJSUA2: `/home/inrack/.local/pjsip-2.17t`;
- ASR model: `/home/inrack/.local/models/faster-whisper-large-v3-edaa852e`;
- XTTS model: `/home/inrack/.cache/sip-bot-c4-xtts-v2-model`;
- Ollama bundle: `/home/inrack/src/c3-ollama/v0.33.1`;
- Ollama models: `/home/inrack/.ollama/models`.
- FreeSWITCH rootfs: `/var/lib/machines/freeswitch-bookworm`;
- FreeSWITCH container unit: `systemd-nspawn@freeswitch-bookworm.service`;
- FreeSWITCH workshop config source: `/home/inrack/sip-bot/config/workshops/freeswitch`.

The compatibility symlink `/home/sipbot -> /home/inrack` supplies the historical absolute paths still used by the live
tools. Ollama is enabled as `sip-bot-ollama.service`, listens only on `127.0.0.1:11434`, and was explicitly warmed after
service installation. A repeated short Qwen request completed in `133.477 ms` wall time.

Disk state after installation: root volume `98 GB`, `59 GB` used, `34 GB` available. The project occupies about
`684 MB`, the combined venv `8.7 GB`, Ollama data `5.9 GB`, and ASR models `2.9 GB`.

## FreeSWITCH deployment

The owner-provided package repository targets Debian Bookworm. A direct package-install simulation on Ubuntu 22.04 was
rejected because the repository requires newer Debian library versions (`libopencore-amrnb0`, `libspeexdsp1`,
`libjpeg62-turbo`, and `libtiff6`). The package baseline therefore runs in a Debian 12 `systemd-nspawn` machine with
the host network shared directly; Docker and a FreeSWITCH source build are not involved.

The host unit and the FreeSWITCH service are both enabled and survived a full container restart. FreeSWITCH listens on
`10.0.0.45:5060` and `10.0.0.45:5080`; `mod_sofia` and `mod_callcenter` are loaded. Queue `support@default`, callback
agent `1001@default`, its ready tier, and dialplan extension `7000` are installed from the project workshop assets.
MicroSIP extension `1000` completed a real authenticated REGISTER against the server.
Two server-local PJSUA2 endpoints then completed the full technical workshop sequence: the direct call had two
`ACTIVE` PCMU/8 kHz legs; the queue member changed from `Trying` to `Answered`, agent `1001@default` changed to
`In a queue call`, and the resulting bridge again had two `ACTIVE` PCMU/8 kHz legs. The probes ended with no calls or
registrations left behind. Subjective audibility was not re-evaluated on this headless server.

The detailed evidence is in [`freeswitch-server/`](freeswitch-server/), notably
[`freeswitch-validation.txt`](freeswitch-server/freeswitch-validation.txt),
[`network-validation.txt`](freeswitch-server/network-validation.txt), and
[`freeswitch-server/README.md`](freeswitch-server/README.md).

## Remaining deployment boundary

The application constants still contain the committed local workshop profile in `config/constants.py`, with optional
registration disabled by default. Registration of the bot itself as a real FreeSWITCH queue agent and a complete
FreeSWITCH-routed bot call have not yet been performed.

The repository also does not yet contain a persistent bot daemon/CLI that waits for arbitrary incoming PBX calls.
Current live runners are deterministic test/workshop orchestrators and must not be presented as that daemon. Creating
the launcher, its systemd unit and the final real-FreeSWITCH registration/call check is the next implementation scope.

## Notable corrective action

The canonical PJSUA2 free-threading patch was corrected so `PyUnstable_Module_SetGIL(..., Py_MOD_GIL_NOT_USED)` is
inserted after the complete Python-2/Python-3 module-creation conditional. The previous hunk could fuzz into the Python-2
branch when regenerated on Ubuntu 22.04. The rebuilt wheel and lifecycle probe confirm the corrected placement.
