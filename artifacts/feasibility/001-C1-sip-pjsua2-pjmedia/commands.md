# C1 execution commands

Target distro: `Ubuntu-24.04`, user `sipbot`.

## Dependency and source preparation

```text
apt-get update
apt-get install -y swig
curl -L --fail --retry 3 --output /home/sipbot/src/pjsip-build/pjproject-2.17.tar.gz https://github.com/pjsip/pjproject/archive/refs/tags/2.17.tar.gz
sha256sum /home/sipbot/src/pjsip-build/pjproject-2.17.tar.gz
```

Observed: SWIG install exit `0`; source SHA-256 is recorded in `candidate-manifest.json`.

## PJSIP/PJMEDIA build

```text
./configure --prefix=/home/sipbot/.local/pjsip-2.17t CFLAGS=-fPIC CXXFLAGS=-fPIC
make dep
make -j4
make install
```

Observed exit codes: configure `0`, combined `make dep && make -j4` `0`, install `0`.

## Python binding

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -m pip install --no-cache-dir setuptools
make PYTHON_EXE=/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t
python3.14t -I -m pip install --no-build-isolation --no-deps --no-cache-dir --force-reinstall .
```

The first upstream `make install --user` failed because the old setup script attempted to treat the custom Python
executable as an installable user script. It was not used as the acceptance path; the same binding was installed with
pip and the exact gap is retained in the plan/evidence.

## Probe

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I -X faulthandler \
  /mnt/c/devel/sip-bot/tools/feasibility/pjsua2_pjmedia_probe.py \
  --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-C1-sip-pjsua2-pjmedia/patched-import-lifecycle.json \
  --initialize
```

Unpatched run exit code: `1` (expected negative evidence). Patched run exit code: `0`.

## Peer-dependent C1 lanes

The separate `001-S` stand was used without changing the C1 production contract:

```text
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py --scenario lifecycle --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/lifecycle.json --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 --peer-uri sip:peer@127.0.0.1:5080
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py --scenario pcmu --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/pcmu.json --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 --peer-uri sip:peer@127.0.0.1:5080
/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t -I /mnt/c/devel/sip-bot/tools/feasibility/voip_test_stand_probe.py --scenario bye --output /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/bye.json --peer-config /mnt/c/devel/sip-bot/artifacts/feasibility/001-S-voip-test-stand/config/peer-5080 --peer-uri sip:peer@127.0.0.1:5080
```

All three commands exited `0`; detailed command lines, peer logs and structured results are owned by `001-S`.
