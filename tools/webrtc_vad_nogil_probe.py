"""Target-runtime WebRTC VAD import, operation and no-GIL probe."""

from __future__ import annotations

import argparse
import array
import hashlib
import importlib.metadata
import json
import sys
import sysconfig
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _pcm(sample_rate_hz: int, duration_ms: int, amplitude: int = 0) -> bytes:
    count = sample_rate_hz * duration_ms // 1000
    values = array.array("h", [amplitude if index % 4 < 2 else -amplitude for index in range(count)])
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


def _sha256(path: str | None) -> str | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _gil_enabled() -> bool:
    return bool(sys._is_gil_enabled())


def _run(output_root: Path | None) -> dict[str, object]:
    gil_before_import = _gil_enabled()
    import webrtcvad

    gil_after_import = _gil_enabled()
    candidate = webrtcvad.Vad(2)
    gil_after_construct = _gil_enabled()

    operations: list[dict[str, object]] = []
    for sample_rate_hz in (8000, 16000, 32000, 48000):
        for duration_ms in (10, 20, 30):
            pcm = _pcm(sample_rate_hz, duration_ms, amplitude=1000)
            operations.append(
                {
                    "sample_rate_hz": sample_rate_hz,
                    "duration_ms": duration_ms,
                    "bytes": len(pcm),
                    "is_speech": bool(candidate.is_speech(pcm, sample_rate_hz)),
                }
            )
    gil_after_operation = _gil_enabled()

    def worker(mode: int) -> int:
        local = webrtcvad.Vad(mode % 4)
        pcm = _pcm(8000, 20, amplitude=1000)
        return sum(bool(local.is_speech(pcm, 8000)) for _ in range(200))

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="webrtc-vad") as executor:
        concurrency_results = list(executor.map(worker, range(8)))
    gil_after_concurrency = _gil_enabled()

    invalid_results: list[dict[str, object]] = []
    for sample_rate_hz, duration_ms in ((8000, 9), (8000, 40), (11025, 20)):
        try:
            candidate.is_speech(_pcm(sample_rate_hz, duration_ms), sample_rate_hz)
        except Exception as exc:  # binding-specific Error is part of this gate
            invalid_results.append(
                {
                    "sample_rate_hz": sample_rate_hz,
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        else:
            raise AssertionError(f"invalid VAD input was accepted: {sample_rate_hz}/{duration_ms}")

    native_path = getattr(webrtcvad, "__file__", None)
    native_module = Path(native_path).with_name("_webrtcvad.cpython-314t-x86_64-linux-gnu.so") if native_path else None
    manifest: dict[str, object] = {
        "status": "pass",
        "python_executable": sys.executable,
        "python_version": sys.version,
        "implementation": sys.implementation.name,
        "soabi": sysconfig.get_config_var("SOABI"),
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_before_import": gil_before_import,
        "gil_after_import": gil_after_import,
        "gil_after_construct": gil_after_construct,
        "gil_after_operation": gil_after_operation,
        "gil_after_concurrency": gil_after_concurrency,
        "distribution": "webrtcvad-wheels",
        "distribution_version": importlib.metadata.version("webrtcvad-wheels"),
        "distribution_license": importlib.metadata.metadata("webrtcvad-wheels").get("License"),
        "python_module": native_path,
        "native_module": str(native_module) if native_module else None,
        "native_module_sha256": _sha256(str(native_module) if native_module else None),
        "valid_operations": operations,
        "concurrency_results": concurrency_results,
        "invalid_operations": invalid_results,
        "claims": {
            "target_frame_contract": "8/16/32/48 kHz mono PCM16, 10/20/30 ms",
            "application_baseline": "8 kHz mono PCM16, 20 ms",
            "gpu_required": False,
            "live_sip_evidence": False,
        },
    }
    if gil_before_import or gil_after_import or gil_after_construct or gil_after_operation or gil_after_concurrency:
        raise AssertionError("WebRTC binding enabled the interpreter GIL")
    if len(operations) != 12 or len(invalid_results) != 3 or len(concurrency_results) != 8:
        raise AssertionError("WebRTC VAD operation matrix is incomplete")
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "webrtc-vad-runtime.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    try:
        _run(args.output_root)
    except Exception as exc:
        print(json.dumps({"status": "fail", "error_type": type(exc).__name__, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
