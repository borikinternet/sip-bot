#!/usr/bin/env python3
"""Measure warmed XTTS first-audio latency and producer cadence.

The model and speaker conditioning are loaded once.  Every candidate is then
run against the same Russian phrase/repeat matrix with a repeatable torch seed.
The probe writes complete 8 kHz PCM WAV files so timing improvements never
replace an inspectable audio result.
"""

from __future__ import annotations

import argparse
from array import array
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import sysconfig
import time
import wave


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_SITE = "/home/sipbot/.local/cpython-3.14.7t/lib/python3.14t/site-packages"
XTTS_SITE = "/home/sipbot/.cache/sip-bot-c4-xtts-v2-3.14.7t/lib/python3.14t/site-packages"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, XTTS_SITE)
sys.path.insert(0, TARGET_SITE)

from config import constants  # noqa: E402
from real_composition_probe import _RealXttsEngine, _profile  # noqa: E402
from sip_bot.tts import TtsLatencyStage, XttsV2Adapter  # noqa: E402


PHRASES = (
    ("greeting", "Алло."),
    ("transfer", "Подключить оператора?"),
    ("short-answer", "Небо кажется голубым из-за рассеяния света в атмосфере."),
    (
        "medium-answer",
        "На закате синий свет рассеивается сильнее, поэтому прямой свет выглядит красным.",
    ),
    (
        "unknown-answer",
        "Я не могу надёжно ответить на этот вопрос по доступной базе знаний. Подключить оператора?",
    ),
)


@dataclass(frozen=True, slots=True)
class RunMetrics:
    chunk_size: int
    repeat: int
    phrase_id: str
    text: str
    seed: int
    adapter_started_ns: int
    engine_first_chunk_ns: int
    pcm_first_chunk_ns: int
    completed_ns: int
    engine_ttfa_ms: float
    normalized_pcm_ttfa_ms: float
    normalization_ms: float
    full_generation_ms: float
    audio_duration_ms: float
    first_chunk_duration_ms: float
    realtime_factor: float
    chunk_count: int
    chunk_arrival_gaps_ms: tuple[float, ...]
    minimum_buffer_before_refill_ms: float
    producer_underrun_count: int
    pcm_bytes: int
    pcm_sha256: str
    peak_abs: int
    rms_dbfs: float
    clipped_sample_ratio: float
    wav: str


def _gil_enabled() -> bool | None:
    probe = getattr(sys, "_is_gil_enabled", None)
    return None if probe is None else bool(probe())


def _write_wav(path: Path, pcm: bytes, sample_rate_hz: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate_hz)
        stream.writeframes(pcm)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def _signal_metrics(pcm: bytes) -> tuple[int, float, float]:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0, float("-inf"), 0.0
    peak = max(abs(value) for value in samples)
    mean_square = sum(float(value) * float(value) for value in samples) / len(samples)
    rms = math.sqrt(mean_square)
    rms_dbfs = float("-inf") if rms <= 0 else 20.0 * math.log10(rms / 32768.0)
    clipped = sum(1 for value in samples if abs(value) >= 32767) / len(samples)
    return peak, rms_dbfs, clipped


def _cadence(chunk_bytes: list[int], arrivals_ns: list[int], sample_rate_hz: int) -> tuple[float, int]:
    durations_ms = [size / (sample_rate_hz * 2) * 1000.0 for size in chunk_bytes]
    buffered_ms = durations_ms[0]
    minimum_before_refill_ms = buffered_ms
    underruns = 0
    for index in range(1, len(durations_ms)):
        elapsed_ms = (arrivals_ns[index] - arrivals_ns[index - 1]) / 1_000_000
        buffered_ms -= elapsed_ms
        minimum_before_refill_ms = min(minimum_before_refill_ms, buffered_ms)
        if buffered_ms < 0:
            underruns += 1
            buffered_ms = 0.0
        buffered_ms += durations_ms[index]
    return minimum_before_refill_ms, underruns


def _run_one(
    *,
    engine: _RealXttsEngine,
    torch: object,
    output_root: Path,
    chunk_size: int,
    repeat: int,
    phrase_index: int,
    phrase_id: str,
    text: str,
) -> RunMetrics:
    seed = 10_000 + repeat * 100 + phrase_index
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.cuda.synchronize()
    engine.configure_streaming(stream_chunk_size=chunk_size)
    events = []
    adapter = XttsV2Adapter(
        engine,
        operation_id_factory=lambda: f"tts-sweep-{chunk_size}-{repeat}-{phrase_id}",
        latency_sink=events.append,
    )
    profile = _profile()
    chunks: list[bytes] = []
    arrivals_ns: list[int] = []
    for chunk in adapter.stream(
        text,
        call_id="tts-sweep",
        channel_id="tts-sweep:playback",
        turn_id=f"tts-sweep:{phrase_id}",
        generation=1,
        profile=profile,
    ):
        arrivals_ns.append(time.monotonic_ns())
        chunks.append(chunk.pcm_s16le)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    completed_ns = time.monotonic_ns()
    if not chunks:
        raise RuntimeError(f"XTTS produced no PCM for chunk_size={chunk_size} phrase={phrase_id}")

    stages = {event.stage: event for event in events}
    required = (
        TtsLatencyStage.ADAPTER_STARTED,
        TtsLatencyStage.ENGINE_FIRST_CHUNK,
        TtsLatencyStage.PCM_FIRST_CHUNK,
    )
    missing = [stage.value for stage in required if stage not in stages]
    if missing:
        raise RuntimeError(f"missing TTS latency stages: {missing}")
    adapter_started_ns = stages[TtsLatencyStage.ADAPTER_STARTED].timestamp_ns
    engine_first_ns = stages[TtsLatencyStage.ENGINE_FIRST_CHUNK].timestamp_ns
    pcm_first_ns = stages[TtsLatencyStage.PCM_FIRST_CHUNK].timestamp_ns
    pcm = b"".join(chunks)
    audio_duration_ms = len(pcm) / (profile.sample_rate_hz * profile.channels * 2) * 1000.0
    full_generation_ms = (completed_ns - adapter_started_ns) / 1_000_000
    chunk_sizes = [len(item) for item in chunks]
    minimum_buffer_ms, underruns = _cadence(chunk_sizes, arrivals_ns, profile.sample_rate_hz)
    peak, rms_dbfs, clipped = _signal_metrics(pcm)
    wav_path = output_root / f"chunk-{chunk_size}" / f"r{repeat}-{phrase_id}.wav"
    _write_wav(wav_path, pcm, profile.sample_rate_hz)
    return RunMetrics(
        chunk_size=chunk_size,
        repeat=repeat,
        phrase_id=phrase_id,
        text=text,
        seed=seed,
        adapter_started_ns=adapter_started_ns,
        engine_first_chunk_ns=engine_first_ns,
        pcm_first_chunk_ns=pcm_first_ns,
        completed_ns=completed_ns,
        engine_ttfa_ms=(engine_first_ns - adapter_started_ns) / 1_000_000,
        normalized_pcm_ttfa_ms=(pcm_first_ns - adapter_started_ns) / 1_000_000,
        normalization_ms=(pcm_first_ns - engine_first_ns) / 1_000_000,
        full_generation_ms=full_generation_ms,
        audio_duration_ms=audio_duration_ms,
        first_chunk_duration_ms=chunk_sizes[0] / (profile.sample_rate_hz * 2) * 1000.0,
        realtime_factor=full_generation_ms / audio_duration_ms,
        chunk_count=len(chunks),
        chunk_arrival_gaps_ms=tuple(
            (arrivals_ns[index] - arrivals_ns[index - 1]) / 1_000_000
            for index in range(1, len(arrivals_ns))
        ),
        minimum_buffer_before_refill_ms=minimum_buffer_ms,
        producer_underrun_count=underruns,
        pcm_bytes=len(pcm),
        pcm_sha256=hashlib.sha256(pcm).hexdigest(),
        peak_abs=peak,
        rms_dbfs=rms_dbfs,
        clipped_sample_ratio=clipped,
        wav=str(wav_path),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, default=Path("/home/sipbot/.cache/sip-bot-c4-xtts-v2-model"))
    parser.add_argument("--voice", type=Path, default=None)
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=(20, 10, 5))
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1 or any(value < 1 for value in args.chunk_sizes):
        parser.error("repeats and chunk sizes must be positive")
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    voice = args.voice or args.model_root / "samples" / "en_sample.wav"
    runtime_before = {
        "python": sys.executable,
        "version": sys.version.replace("\n", " "),
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_enabled": _gil_enabled(),
    }

    engine = _RealXttsEngine(
        args.model_root,
        voice,
        stream_chunk_size=constants.TTS_STREAM_CHUNK_SIZE,
        overlap_wav_len=constants.TTS_STREAM_OVERLAP_WAV_LEN,
    )
    import torch

    # One discarded operation removes lazy CUDA graph/kernel effects from the
    # candidate matrix.  Every measured candidate then sees the same owner.
    warmup = XttsV2Adapter(engine, operation_id_factory=lambda: "tts-sweep-warmup")
    warmup_stream = warmup.stream(
        "Проверка готовности.",
        call_id="tts-sweep-warmup",
        channel_id="tts-sweep-warmup:playback",
        turn_id="tts-sweep-warmup:turn-1",
        generation=1,
        profile=_profile(),
    )
    try:
        next(warmup_stream)
    finally:
        warmup_stream.close()

    runs: list[RunMetrics] = []
    for repeat in range(1, args.repeats + 1):
        order = list(args.chunk_sizes) if repeat % 2 else list(reversed(args.chunk_sizes))
        for phrase_index, (phrase_id, text) in enumerate(PHRASES, start=1):
            for chunk_size in order:
                metrics = _run_one(
                    engine=engine,
                    torch=torch,
                    output_root=output_root,
                    chunk_size=chunk_size,
                    repeat=repeat,
                    phrase_index=phrase_index,
                    phrase_id=phrase_id,
                    text=text,
                )
                runs.append(metrics)
                print(
                    f"chunk={chunk_size} repeat={repeat} phrase={phrase_id} "
                    f"ttfa={metrics.normalized_pcm_ttfa_ms:.1f}ms "
                    f"rtf={metrics.realtime_factor:.3f} underruns={metrics.producer_underrun_count}",
                    flush=True,
                )

    summaries: list[dict[str, object]] = []
    for chunk_size in args.chunk_sizes:
        selected = [item for item in runs if item.chunk_size == chunk_size]
        ttfa = [item.normalized_pcm_ttfa_ms for item in selected]
        rtfs = [item.realtime_factor for item in selected]
        summary = {
            "chunk_size": chunk_size,
            "run_count": len(selected),
            "ttfa_median_ms": statistics.median(ttfa),
            "ttfa_p95_ms": _percentile(ttfa, 0.95),
            "ttfa_max_ms": max(ttfa),
            "full_rtf_median": statistics.median(rtfs),
            "full_rtf_max": max(rtfs),
            "minimum_buffer_before_refill_ms": min(item.minimum_buffer_before_refill_ms for item in selected),
            "producer_underrun_count": sum(item.producer_underrun_count for item in selected),
            "max_clipped_sample_ratio": max(item.clipped_sample_ratio for item in selected),
        }
        summary["viable"] = (
            summary["producer_underrun_count"] == 0
            and summary["full_rtf_max"] < 1.0
            and summary["max_clipped_sample_ratio"] < 0.01
        )
        summaries.append(summary)

    viable = [item for item in summaries if item["viable"]]
    recommended = min(viable, key=lambda item: (item["ttfa_median_ms"], item["chunk_size"])) if viable else None
    result = {
        "schema": "sip-bot.plan-018.tts-stream-latency.v1",
        "status": "pass" if recommended is not None else "fail",
        "runtime_before_model": runtime_before,
        "runtime_after_operation": {
            "gil_enabled": _gil_enabled(),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "model_root": str(args.model_root),
        "voice": str(voice),
        "overlap_wav_len": constants.TTS_STREAM_OVERLAP_WAV_LEN,
        "phrases": [{"id": key, "text": text} for key, text in PHRASES],
        "runs": [asdict(item) for item in runs],
        "summaries": summaries,
        "recommended_chunk_size": recommended["chunk_size"] if recommended is not None else None,
        "selection_rule": "lowest median normalized PCM TTFA among zero-underrun, full-RTF<1, non-clipping candidates",
    }
    result_path = output_root / "probe.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "recommended": result["recommended_chunk_size"], "summaries": summaries}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
