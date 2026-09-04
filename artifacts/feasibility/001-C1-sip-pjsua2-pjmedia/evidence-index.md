# C1 evidence index

| Evidence | Meaning | Result |
|---|---|---|
| `candidate-manifest.json` | Candidate provenance, build, ABI and acceptance summary | Recorded |
| `commands.md` | Reproduction commands and exit codes | Recorded |
| `native-dependencies.txt` | Dynamic dependency inventory from `ldd` | Recorded |
| `unpatched-import-lifecycle.json` | Baseline upstream SWIG binding | GIL re-enabled; fail |
| `patched-import-lifecycle.json` | Binding with CPython free-threading declaration | Import and initialization pass |
| `patches/pjsua2-free-threading.patch` | Exact candidate-source compatibility patch | Applied to generated wrapper |
| `lifecycle.json` | C1 S2 via separate approved stand | SIP lifecycle pass |
| `pcmu.json` | C1 S3 via separate approved stand | PCMU/RTP pass |
| `bye.json` | C1 S4 via separate approved stand | BYE during active busy fixture pass |
| `closeout.md` | C1 final candidate decision and handoff | Recorded |

External stand evidence:

- `../001-S-voip-test-stand/lifecycle.json`
- `../001-S-voip-test-stand/pcmu.json`
- `../001-S-voip-test-stand/bye.json`
- `../001-S-voip-test-stand/transfer.json` (stand-only transfer coverage, outside C1 acceptance)

No audio, SIP credentials, external PBX data or user call recordings are present.
