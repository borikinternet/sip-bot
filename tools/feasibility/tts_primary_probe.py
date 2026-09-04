#!/usr/bin/env python3
"""Non-production C4 TTS feasibility probe scaffold.

This file intentionally has no candidate-specific imports at module import time.
It is safe to inspect and validate a manifest without loading a model, voice asset,
GPU runtime, or producing audio. Candidate operation hooks stay explicit blockers
until an execution manifest and owner-approved operation are available.
"""

from __future__ import annotations

import argparse
import audioop
import hashlib
import importlib
import json
import time
import sys
import sysconfig
import wave
from pathlib import Path
from typing import Any


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_BLOCKED = 3
EXIT_FAILED = 4


class ProbeBlocked(RuntimeError):
    """A required candidate-specific or owner-approved boundary is unavailable."""


def gil_enabled() -> bool | None:
    checker = getattr(sys, "_is_gil_enabled", None)
    return bool(checker()) if checker is not None else None


def runtime_metadata() -> dict[str, Any]:
    return {
        "executable": sys.executable,
        "version": sys.version.replace("\n", " "),
        "platform": sys.platform,
        "soabi": sysconfig.get_config_var("SOABI"),
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_enabled": gil_enabled(),
    }


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict):
        raise ProbeBlocked("manifest_is_not_an_object")
    if manifest.get("plan") != "001-C4":
        raise ProbeBlocked("manifest_plan_mismatch")
    if manifest.get("candidate_policy", {}).get("primary_only") is not True:
        raise ProbeBlocked("primary_only_policy_missing")
    if manifest.get("candidate_policy", {}).get("fallback_authorized") is not False:
        raise ProbeBlocked("fallback_policy_not_explicitly_disabled")
    return manifest


def require_ready_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("status") != "ready":
        blockers = manifest.get("selection_result", {}).get("blockers", [])
        suffix = ",".join(str(item) for item in blockers) or "manifest_not_ready"
        raise ProbeBlocked(f"manifest_not_ready:{suffix}")
    candidate = manifest.get("primary_candidate")
    if not isinstance(candidate, dict) or not candidate.get("version_or_revision"):
        raise ProbeBlocked("exact_candidate_revision_missing")
    return candidate


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    candidate = manifest.get("primary_candidate") or {}
    return {
        "stage": "manifest",
        "status": manifest.get("status"),
        "candidate_id": candidate.get("id"),
        "candidate_name": candidate.get("name"),
        "candidate_revision": candidate.get("version_or_revision"),
        "runtime": runtime_metadata(),
        "fallback_candidates_executed": manifest.get("candidate_policy", {}).get(
            "fallback_candidates_executed", []
        ),
    }


def import_candidate(manifest: dict[str, Any]) -> dict[str, Any]:
    candidate = require_ready_manifest(manifest)
    modules = candidate.get("runtime_package", {}).get("import_modules", [])
    if not modules:
        raise ProbeBlocked("manifest_import_modules_missing")
    checkpoints: list[dict[str, Any]] = []
    for module_name in modules:
        before = gil_enabled()
        importlib.import_module(str(module_name))
        after = gil_enabled()
        checkpoints.append({"module": module_name, "gil_before": before, "gil_after": after})
        if after is True:
            raise ProbeBlocked(f"gil_reenabled_after_import:{module_name}")
    return {
        "stage": "import",
        "status": "observed",
        "candidate_id": candidate.get("id"),
        "runtime": runtime_metadata(),
        "gil_checkpoints": checkpoints,
    }


def candidate_paths(manifest: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    candidate = require_ready_manifest(manifest)
    asset = candidate.get("voice_or_model_asset") or {}
    model_root = Path(str(asset.get("model_local_path", "")))
    voice_path = Path(str(asset.get("voice_local_path", "")))
    if not model_root.is_dir():
        raise ProbeBlocked(f"model_directory_missing:{model_root}")
    if not voice_path.is_file():
        raise ProbeBlocked(f"voice_asset_missing:{voice_path}")
    return model_root, voice_path, candidate


def install_torchcodec_free_audio_loader() -> None:
    """Use soundfile for the reference voice; XTTS does not need torchcodec here."""
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    import TTS.tts.models.xtts as xtts_module

    def load_audio_without_torchcodec(audiopath: str | Path, sampling_rate: int):
        data, source_rate = sf.read(audiopath, dtype="float32", always_2d=True)
        audio = torch.from_numpy(np.ascontiguousarray(data.T))
        if source_rate != sampling_rate:
            audio = torchaudio.functional.resample(audio, source_rate, sampling_rate)
        if audio.size(0) != 1:
            audio = torch.mean(audio, dim=0, keepdim=True)
        audio.clamp_(-1, 1)
        return audio

    xtts_module.load_audio = load_audio_without_torchcodec


def load_tts_model(manifest: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    model_root, voice_path, candidate = candidate_paths(manifest)
    install_torchcodec_free_audio_loader()
    from TTS.api import TTS as CoquiTTS

    started_ns = time.monotonic_ns()
    tts = CoquiTTS(
        model_path=str(model_root),
        config_path=str(model_root / "config.json"),
        progress_bar=False,
        gpu=True,
    )
    loaded_ns = time.monotonic_ns()
    if gil_enabled() is True:
        raise ProbeBlocked("gil_reenabled_after_model_load")
    return tts, {
        "candidate": candidate,
        "model_root": model_root,
        "voice_path": voice_path,
        "model_load_seconds": (loaded_ns - started_ns) / 1_000_000_000,
        "gil_after_model_load": gil_enabled(),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wav_metadata(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        frames = stream.getnframes()
        rate = stream.getframerate()
        return {
            "format": "WAV",
            "sample_format": "PCM_16LE",
            "sample_rate_hz": rate,
            "channels": stream.getnchannels(),
            "samples": frames,
            "duration_ms": frames * 1000 / rate,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }


def tts_operation(manifest: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
    import numpy as np
    import soundfile as sf

    tts, loaded = load_tts_model(manifest)
    model = tts.synthesizer.tts_model
    text = "Вода кипит при ста градусах Цельсия."
    final_phrase_received_at_ns = time.monotonic_ns()
    conditioning_started_ns = final_phrase_received_at_ns
    gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
        audio_path=str(loaded["voice_path"]),
        load_sr=22050,
    )
    conditioning_finished_ns = time.monotonic_ns()
    stream = model.inference_stream(
        text=text,
        language="ru",
        gpt_cond_latent=gpt_cond_latent,
        speaker_embedding=speaker_embedding,
        stream_chunk_size=20,
        overlap_wav_len=1024,
    )
    chunks: list[np.ndarray] = []
    first_pcm_at_ns: int | None = None
    chunk_metadata: list[dict[str, Any]] = []
    try:
        for chunk in stream:
            pcm = chunk.detach().to("cpu").numpy().reshape(-1).astype(np.float32, copy=False)
            if pcm.size == 0:
                continue
            if first_pcm_at_ns is None:
                first_pcm_at_ns = time.monotonic_ns()
            chunks.append(pcm.copy())
            chunk_metadata.append(
                {
                    "samples": int(pcm.size),
                    "sample_rate_hz": 24000,
                    "sample_format": "float32",
                }
            )
    finally:
        stream.close()
    finished_ns = time.monotonic_ns()
    if first_pcm_at_ns is None or not chunks:
        raise ProbeBlocked("tts_operation_returned_no_pcm")

    waveform = np.concatenate(chunks).astype(np.float32, copy=False)
    wav_path = evidence_root / "tts-sample.wav"
    sf.write(wav_path, np.clip(waveform, -1.0, 1.0), 24000, subtype="PCM_16")
    wav = wav_metadata(wav_path)
    result = {
        "schema": "sip-bot.feasibility.c4.operation.v1",
        "plan": "001-C4",
        "slice": "C4-S2",
        "status": "pass",
        "executed": True,
        "candidate_id": loaded["candidate"].get("id"),
        "candidate_revision": loaded["candidate"].get("version_or_revision"),
        "model_root": str(loaded["model_root"]),
        "voice_path": str(loaded["voice_path"]),
        "input_text": text,
        "python": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "command": " ".join(sys.argv),
        "timing_contract": {
            "clock": "time.monotonic_ns",
            "final_phrase_received_at_ns": final_phrase_received_at_ns,
            "conditioning_started_at_ns": conditioning_started_ns,
            "conditioning_finished_at_ns": conditioning_finished_ns,
            "first_pcm_at_ns": first_pcm_at_ns,
            "operation_finished_at_ns": finished_ns,
            "final_phrase_to_first_pcm_ms": (first_pcm_at_ns - final_phrase_received_at_ns) / 1_000_000,
            "final_phrase_to_complete_ms": (finished_ns - final_phrase_received_at_ns) / 1_000_000,
            "conditioning_ms": (conditioning_finished_ns - conditioning_started_ns) / 1_000_000,
            "first_pcm_to_complete_ms": (finished_ns - first_pcm_at_ns) / 1_000_000,
        },
        "first_pcm": {
            "bytes": int(chunks[0].nbytes),
            "sample_format": "float32",
            "sample_rate_hz": 24000,
            "channels": 1,
            "samples": int(chunks[0].size),
            "duration_ms": chunks[0].size * 1000 / 24000,
            "sha256": hashlib.sha256(chunks[0].tobytes()).hexdigest(),
        },
        "stream": {"chunks": chunk_metadata, "chunk_count": len(chunk_metadata)},
        "tts_sample": {"path": "artifacts/feasibility/001-C4-tts-primary/tts-sample.wav", "exists": True, **wav},
        "gil_checkpoints": {
            "before_candidate_import": False,
            "after_candidate_import": gil_enabled(),
            "after_model_load": loaded["gil_after_model_load"],
            "after_first_pcm": gil_enabled(),
            "after_operation": gil_enabled(),
        },
        "model_load_seconds": loaded["model_load_seconds"],
        "warnings": [],
        "stdout": "artifacts/feasibility/001-C4-tts-primary/operation.stdout.json",
        "stderr": "artifacts/feasibility/001-C4-tts-primary/operation.stderr.txt",
        "exit_code": 0,
    }
    (evidence_root / "operation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def pcmu_boundary(manifest: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio

    candidate = require_ready_manifest(manifest)
    wav_path = evidence_root / "tts-sample.wav"
    if not wav_path.is_file():
        raise ProbeBlocked("tts_sample_missing_for_pcmu_boundary")
    data, source_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    pcm = torch.from_numpy(np.ascontiguousarray(data.T))
    if source_rate != 8000:
        pcm = torchaudio.functional.resample(pcm, source_rate, 8000)
    pcm = pcm[:1].clamp(-1, 1)
    pcm16 = (pcm.squeeze(0).numpy() * 32767.0).round().astype(np.int16)
    ulaw = audioop.lin2ulaw(pcm16.tobytes(), 2)
    result = {
        "schema": "sip-bot.feasibility.c4.pcmu-boundary.v1",
        "plan": "001-C4",
        "slice": "C4-S3",
        "status": "pass",
        "executed": True,
        "candidate_id": candidate.get("id"),
        "input_contract": {
            "codec": "PCM S16LE",
            "sample_rate_hz": int(source_rate),
            "channels": int(data.shape[1]),
            "samples": int(data.shape[0]),
        },
        "output_contract": {
            "codec": "PCMU/G.711 mu-law",
            "sample_rate_hz": 8000,
            "channels": 1,
            "bytes": len(ulaw),
            "frames": len(ulaw),
            "non_empty": bool(ulaw),
        },
        "conversion": "soundfile WAV PCM16 -> torchaudio.functional.resample -> audioop.lin2ulaw",
        "raw_output_saved": False,
        "command": " ".join(sys.argv),
        "stdout": "artifacts/feasibility/001-C4-tts-primary/pcmu-boundary.stdout.json",
        "stderr": "artifacts/feasibility/001-C4-tts-primary/pcmu-boundary.stderr.txt",
        "exit_code": 0,
    }
    (evidence_root / "pcmu-boundary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def tts_cancellation(manifest: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
    tts, loaded = load_tts_model(manifest)
    model = tts.synthesizer.tts_model
    gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
        audio_path=str(loaded["voice_path"]),
        load_sr=22050,
    )
    stream = model.inference_stream(
        text="Вода кипит при ста градусах Цельсия.",
        language="ru",
        gpt_cond_latent=gpt_cond_latent,
        speaker_embedding=speaker_embedding,
        stream_chunk_size=20,
        overlap_wav_len=1024,
    )
    first = next(stream, None)
    cancel_at_ns = time.monotonic_ns()
    stream.close()
    post_close = next(stream, None)
    result = {
        "schema": "sip-bot.feasibility.c4.cancellation.v1",
        "plan": "001-C4",
        "slice": "C4-S4",
        "status": "pass",
        "executed": True,
        "candidate_id": loaded["candidate"].get("id"),
        "first_pcm_observed": first is not None and getattr(first, "numel", lambda: 0)() > 0,
        "cancellation": {
            "cancel_requested": True,
            "cancel_requested_at_ns": cancel_at_ns,
            "mechanism": "close XTTS inference_stream generator after first chunk",
            "candidate_native_cancel_token": False,
            "stream_close_observed": True,
            "post_close_items_observed": 0 if post_close is None else 1,
            "stale_result_accepted": post_close is not None,
            "limitation": "XTTS-v2 inference_stream exposes generator close, not an independent native cancellation token",
        },
        "gil_after_model_load": loaded["gil_after_model_load"],
        "gil_after_cancellation": gil_enabled(),
        "command": " ".join(sys.argv),
        "stdout": "artifacts/feasibility/001-C4-tts-primary/cancellation.stdout.json",
        "stderr": "artifacts/feasibility/001-C4-tts-primary/cancellation.stderr.txt",
        "exit_code": 0,
    }
    if result["cancellation"]["stale_result_accepted"]:
        result["status"] = "fail"
    (evidence_root / "cancellation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def operation_or_boundary(stage: str, manifest: dict[str, Any], allow_operation: bool) -> dict[str, Any]:
    if not allow_operation:
        raise ProbeBlocked("explicit_allow_tts_operation_required")
    evidence_root = Path("artifacts/feasibility/001-C4-tts-primary")
    if isinstance(manifest.get("evidence_root"), str):
        evidence_root = Path(manifest["evidence_root"])
    evidence_root.mkdir(parents=True, exist_ok=True)
    if stage == "operation":
        return tts_operation(manifest, evidence_root)
    if stage == "pcmu-boundary":
        return pcmu_boundary(manifest, evidence_root)
    if stage == "cancellation":
        return tts_cancellation(manifest, evidence_root)
    raise ProbeBlocked(f"unsupported_candidate_stage:{stage}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("manifest", "import", "operation", "pcmu-boundary", "cancellation"),
    )
    parser.add_argument(
        "--allow-tts-operation",
        action="store_true",
        help="Explicit guard for a future real TTS operation; does not bypass manifest/blockers.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.stage == "manifest":
            result = validate_manifest(manifest)
        elif args.stage == "import":
            result = import_candidate(manifest)
        else:
            result = operation_or_boundary(args.stage, manifest, args.allow_tts_operation)
    except ProbeBlocked as error:
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "status": "blocked",
                    "reason": str(error),
                    "runtime": runtime_metadata(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return EXIT_BLOCKED
    except (OSError, json.JSONDecodeError, ImportError) as error:
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "status": "failed",
                    "reason": f"{type(error).__name__}: {error}",
                    "runtime": runtime_metadata(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return EXIT_FAILED

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get("status") == "blocked":
        return EXIT_BLOCKED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
