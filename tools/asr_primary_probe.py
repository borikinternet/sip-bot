"""Feasibility probe for the approved primary ASR candidate.

The probe deliberately separates a CPU-safe import/no-GIL stage from stages
that load the ASR model.  The latter require an explicit ``--allow-model-load``
flag so that preparation runs cannot accidentally download weights or start
GPU inference.

The current primary is faster-whisper.  Its streaming boundary is represented
by repeated bounded transcriptions of a growing audio prefix; this is a
feasibility scaffold, not the production Transcript Assembler.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import time
import traceback
import warnings


CANDIDATE_ID = "ASR-PRIMARY-001-faster-whisper"
CANDIDATE_PACKAGE = "faster-whisper"
CANDIDATE_VERSION = "1.2.1"
DEFAULT_MODEL_ID = "Systran/faster-whisper-large-v3"

# Keep this explicit.  It is an audit list, not a package-tree walk.
IMPORT_MANIFEST = (
    "numpy",
    "yaml",
    "ctranslate2",
    "onnxruntime",
    "av",
    "tokenizers",
    "faster_whisper",
    "faster_whisper.transcribe",
    "faster_whisper.vad",
)


def gil_enabled() -> bool | None:
    checker = getattr(sys, "_is_gil_enabled", None)
    return None if checker is None else bool(checker())


def metadata_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def base_result(stage: str, evidence_root: Path) -> dict[str, object]:
    return {
        "probe": "001-C2-asr-primary",
        "stage": stage,
        "candidate_id": CANDIDATE_ID,
        "candidate_package": CANDIDATE_PACKAGE,
        "candidate_version_expected": CANDIDATE_VERSION,
        "command": " ".join(sys.argv),
        "working_directory": os.getcwd(),
        "pid": os.getpid(),
        "started_at_epoch": time.time(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "machine": sysconfig.get_config_var("MULTIARCH"),
        "soabi": sysconfig.get_config_var("SOABI"),
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_before_import": gil_enabled(),
        "evidence_root": str(evidence_root),
        "warnings": [],
        "status": "fail",
    }


def import_stage(evidence_root: Path) -> tuple[dict[str, object], int]:
    result = base_result("import", evidence_root)
    result["imports"] = []
    result["import_errors"] = []
    result["package_versions"] = {}

    for module_name in IMPORT_MANIFEST:
        # A native module can permanently re-enable the GIL for its interpreter.
        # Probe every module in a fresh child so one red import cannot contaminate
        # the observations for later modules.
        child_code = r'''
import importlib, json, sys, traceback, warnings

def gil_enabled():
    checker = getattr(sys, "_is_gil_enabled", None)
    return None if checker is None else bool(checker())

module_name = sys.argv[1]
entry = {"module": module_name, "gil_before": gil_enabled(), "status": "fail", "warnings": []}
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    try:
        importlib.import_module(module_name)
        entry["status"] = "pass"
    except BaseException as error:
        entry["exception_type"] = type(error).__name__
        entry["exception"] = repr(error)
        entry["traceback"] = traceback.format_exc()
    entry["warnings"] = [
        {"category": item.category.__name__, "message": str(item.message)}
        for item in caught
    ]
entry["gil_after"] = gil_enabled()
print(json.dumps(entry, ensure_ascii=True, sort_keys=True))
'''
        entry: dict[str, object] = {
            "module": module_name,
            "status": "fail",
            "child_exit_code": None,
            "child_stdout": "",
            "child_stderr": "",
        }
        try:
            child = subprocess.run(
                [sys.executable, "-I", "-c", child_code, module_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            entry["child_exit_code"] = child.returncode
            entry["child_stdout"] = child.stdout
            entry["child_stderr"] = child.stderr
            lines = [line for line in child.stdout.splitlines() if line.strip()]
            if lines:
                entry.update(json.loads(lines[-1]))
            else:
                entry["exception_type"] = "NoChildOutput"
                entry["exception"] = "native import child produced no structured output"
        except BaseException as error:
            entry["exception_type"] = type(error).__name__
            entry["exception"] = repr(error)
            entry["traceback"] = traceback.format_exc()
        result["warnings"].extend(entry.get("warnings", []))
        if entry.get("status") != "pass":
            result["import_errors"].append(
                {
                    "module": module_name,
                    "type": entry.get("exception_type", "ImportError"),
                    "message": entry.get("exception", "import failed"),
                }
            )
        result["imports"].append(entry)

    for package in (
        "faster-whisper",
        "ctranslate2",
        "tokenizers",
        "av",
        "onnxruntime",
        "numpy",
        "PyYAML",
    ):
        result["package_versions"][package] = metadata_version(package)

    import_pass = (
        result["py_gil_disabled"] == 1
        and result["gil_before_import"] is False
        and not result["import_errors"]
        and all(item.get("gil_before") is False and item.get("gil_after") is False for item in result["imports"])
        and not result["warnings"]
    )
    result["gil_after_import"] = gil_enabled()
    result["status"] = "pass" if import_pass and result["gil_after_import"] is False else "fail"
    result["finished_at_epoch"] = time.time()
    return result, 0 if result["status"] == "pass" else 1


def decode_audio(path: Path):
    """Decode a fixture to mono float32 at 16 kHz using PyAV.

    The production media boundary remains PCMU 8 kHz -> PCM S16LE 8 kHz;
    this helper makes the additional Whisper-required 16 kHz resampling
    explicit in the future operation evidence.
    """

    import av
    import numpy as np

    with av.open(str(path)) as container:
        stream = next(stream for stream in container.streams if stream.type == "audio")
        resampler = av.audio.resampler.AudioResampler(format="flt", layout="mono", rate=16000)
        chunks = []
        for frame in container.decode(stream):
            for converted in resampler.resample(frame):
                chunks.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):
            chunks.append(converted.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("fixture contains no decodable audio frames")
    return np.concatenate(chunks).astype(np.float32, copy=False)


def transcribe_once(model, audio, language: str) -> str:
    segments, _ = model.transcribe(
        audio,
        language=language,
        task="transcribe",
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=False,
        without_timestamps=True,
    )
    return "".join(segment.text for segment in segments).strip()


def operation_stage(args: argparse.Namespace, evidence_root: Path) -> tuple[dict[str, object], int]:
    result = base_result("operation", evidence_root)
    result["model_id"] = args.model_id
    result["device"] = args.device
    result["compute_type"] = args.compute_type
    result["fixture"] = str(args.fixture)
    result["language"] = args.language
    result["conversion"] = {
        "media_boundary": "PCMU/G.711 mu-law, 8000 Hz, mono",
        "internal_pcm": "PCM S16LE, 8000 Hz, mono",
        "model_input": "float32, 16000 Hz, mono",
        "operation_probe_conversion": "PyAV fixture decode/resample to float32 16000 Hz mono",
    }
    if not args.allow_model_load:
        result["status"] = "blocked_model_load_not_authorized"
        result["blocker_id"] = "C2-B-004"
        result["finished_at_epoch"] = time.time()
        return result, 2

    try:
        from faster_whisper import WhisperModel

        audio = decode_audio(args.fixture)
        started = time.perf_counter()
        model = WhisperModel(
            args.model_id,
            device=args.device,
            compute_type=args.compute_type,
            download_root=str(args.model_cache) if args.model_cache else None,
        )
        result["model_load_seconds"] = time.perf_counter() - started
        result["gil_after_model_load"] = gil_enabled()
        if result["gil_after_model_load"] is not False:
            result["status"] = "fail_nogil_reenabled"
            result["blocker_id"] = "C2-B-004"
            result["failure_reason"] = "candidate import/model load enabled the GIL"
            result["finished_at_epoch"] = time.time()
            return result, 1
        result["audio_samples"] = int(audio.shape[0])
        result["audio_duration_seconds"] = float(audio.shape[0] / 16000.0)
        result["text"] = transcribe_once(model, audio, args.language)
        result["status"] = "pass" if result["text"] else "fail_empty_text"
    except BaseException as error:
        result["exception_type"] = type(error).__name__
        result["exception"] = repr(error)
        result["traceback"] = traceback.format_exc()
        result["status"] = "fail"
    result["gil_after_operation"] = gil_enabled()
    result["finished_at_epoch"] = time.time()
    return result, 0 if result["status"] == "pass" else 1


def streaming_stage(args: argparse.Namespace, evidence_root: Path) -> tuple[dict[str, object], int]:
    """Run the future bounded-prefix streaming feasibility operation.

    faster-whisper exposes a file/array transcription API rather than a
    session-level streaming API.  This stage intentionally makes that gap
    visible: each partial is produced by re-transcribing a growing prefix,
    while finality is a separate authoritative record.  No Transcript
    Assembler or endpoint detector is hidden here.
    """

    result = base_result("streaming", evidence_root)
    result["model_id"] = args.model_id
    result["device"] = args.device
    result["compute_type"] = args.compute_type
    result["fixture"] = str(args.fixture)
    result["language"] = args.language
    result["chunk_seconds"] = args.chunk_seconds
    result["partial_results"] = []
    result["conversion"] = {
        "media_boundary": "PCMU/G.711 mu-law, 8000 Hz, mono",
        "internal_pcm": "PCM S16LE, 8000 Hz, mono",
        "model_input": "float32, 16000 Hz, mono",
        "operation_probe_conversion": "PyAV fixture decode/resample to float32 16000 Hz mono",
    }
    if not args.allow_model_load:
        result["status"] = "blocked_model_load_not_authorized"
        result["blocker_id"] = "C2-B-004"
        result["finished_at_epoch"] = time.time()
        return result, 2

    try:
        from faster_whisper import WhisperModel

        audio = decode_audio(args.fixture)
        result["audio_samples"] = int(audio.shape[0])
        result["audio_duration_seconds"] = float(audio.shape[0] / 16000.0)
        started = time.perf_counter()
        model = WhisperModel(
            args.model_id,
            device=args.device,
            compute_type=args.compute_type,
            download_root=str(args.model_cache) if args.model_cache else None,
        )
        result["model_load_seconds"] = time.perf_counter() - started
        result["gil_after_model_load"] = gil_enabled()
        if result["gil_after_model_load"] is not False:
            result["status"] = "fail_nogil_reenabled"
            result["blocker_id"] = "C2-B-004"
            result["failure_reason"] = "candidate import/model load enabled the GIL"
            result["finished_at_epoch"] = time.time()
            return result, 1

        chunk_samples = max(1, int(args.chunk_seconds * 16000))
        prefix_end = min(chunk_samples, audio.shape[0])
        while prefix_end < audio.shape[0]:
            partial_started = time.time()
            partial_text = transcribe_once(model, audio[:prefix_end], args.language)
            result["partial_results"].append(
                {
                    "kind": "partial",
                    "prefix_end_seconds": prefix_end / 16000.0,
                    "text": partial_text,
                    "emitted_at_epoch": time.time(),
                    "elapsed_seconds": time.time() - partial_started,
                }
            )
            prefix_end = min(prefix_end + chunk_samples, audio.shape[0])

        final_started = time.time()
        final_text = transcribe_once(model, audio, args.language)
        result["final"] = {
            "kind": "final",
            "text": final_text,
            "emitted_at_epoch": time.time(),
            "elapsed_seconds": time.time() - final_started,
            "authoritative": True,
        }
        result["status"] = "pass" if final_text else "fail_empty_final"
    except BaseException as error:
        result["exception_type"] = type(error).__name__
        result["exception"] = repr(error)
        result["traceback"] = traceback.format_exc()
        result["status"] = "fail"
    result["gil_after_operation"] = gil_enabled()
    result["finished_at_epoch"] = time.time()
    return result, 0 if result["status"] == "pass" else 1


def cancellation_stage(args: argparse.Namespace, evidence_root: Path) -> tuple[dict[str, object], int]:
    """Exercise generator close after the first candidate-produced segment.

    faster-whisper exposes a lazy segment generator, but no independent
    cancellation token in this API.  Closing that generator is therefore the
    narrowest candidate-owned cancellation boundary available to this probe;
    the evidence records the limitation explicitly instead of claiming a
    stronger stop guarantee.
    """

    result = base_result("cancellation", evidence_root)
    result["model_id"] = args.model_id
    result["device"] = args.device
    result["compute_type"] = args.compute_type
    result["fixture"] = str(args.fixture)
    result["language"] = args.language
    result["cancellation"] = {
        "mechanism": "close faster-whisper lazy segment generator after first segment",
        "candidate_native_cancel_token": False,
        "cancel_requested": False,
        "cancel_requested_at_epoch": None,
        "stream_close_observed": False,
        "stale_result_accepted": False,
        "post_close_items_observed": None,
        "limitation": "faster-whisper 1.2.1 exposes generator close, not an independent cancellation token",
    }
    if not args.allow_model_load:
        result["status"] = "blocked_model_load_not_authorized"
        result["blocker_id"] = "C2-B-004"
        result["finished_at_epoch"] = time.time()
        return result, 2

    try:
        from faster_whisper import WhisperModel

        audio = decode_audio(args.fixture)
        started = time.perf_counter()
        model = WhisperModel(
            args.model_id,
            device=args.device,
            compute_type=args.compute_type,
            download_root=str(args.model_cache) if args.model_cache else None,
        )
        result["model_load_seconds"] = time.perf_counter() - started
        result["gil_after_model_load"] = gil_enabled()
        if result["gil_after_model_load"] is not False:
            result["status"] = "fail_nogil_reenabled"
            result["blocker_id"] = "C2-B-004"
            result["failure_reason"] = "candidate import/model load enabled the GIL"
            result["finished_at_epoch"] = time.time()
            return result, 1

        segments, _ = model.transcribe(
            audio,
            language=args.language,
            task="transcribe",
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=False,
            without_timestamps=True,
        )
        first = next(segments, None)
        if first is None:
            raise RuntimeError("candidate produced no segment before cancellation")
        result["first_segment"] = {
            "text": first.text,
            "observed_at_epoch": time.time(),
        }
        result["cancellation"]["cancel_requested"] = True
        result["cancellation"]["cancel_requested_at_epoch"] = time.time()
        segments.close()
        result["cancellation"]["stream_close_observed"] = True
        try:
            next(segments)
        except StopIteration:
            result["cancellation"]["post_close_items_observed"] = 0
        else:
            result["cancellation"]["post_close_items_observed"] = 1
            result["cancellation"]["stale_result_accepted"] = True
        result["status"] = "pass" if not result["cancellation"]["stale_result_accepted"] else "fail_stale_result"
    except BaseException as error:
        result["exception_type"] = type(error).__name__
        result["exception"] = repr(error)
        result["traceback"] = traceback.format_exc()
        result["status"] = "fail"
    result["gil_after_operation"] = gil_enabled()
    result["finished_at_epoch"] = time.time()
    return result, 0 if result["status"] == "pass" else 1


def write_result(result: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("import", "operation", "streaming", "cancellation"), required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="int8_float16")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--chunk-seconds", type=float, default=1.0)
    parser.add_argument("--allow-model-load", action="store_true")
    args = parser.parse_args()

    if args.stage in {"operation", "streaming", "cancellation"} and args.fixture is None:
        parser.error("--fixture is required for the selected model stage")

    result, exit_code = (
        import_stage(args.evidence_root)
        if args.stage == "import"
        else operation_stage(args, args.evidence_root)
        if args.stage == "operation"
        else streaming_stage(args, args.evidence_root)
        if args.stage == "streaming"
        else cancellation_stage(args, args.evidence_root)
    )
    default_output = {
        "import": "import-no-gil.json",
        "operation": "operation.json",
        "streaming": "partial-final.json",
        "cancellation": "cancellation.json",
    }[args.stage]
    output = args.output or args.evidence_root / default_output
    write_result(result, output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
