#!/usr/bin/env python3
"""Safe preparation/preflight probe for the C3 LLM feasibility slice.

The default ``preflight`` stage is intentionally non-invasive: it inspects the
free-threaded interpreter and discovers installed backend modules without
importing them.  The optional ``import`` stage imports only explicitly named
modules and never loads model weights, creates a model, allocates GPU memory,
or performs generation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import platform
import sys
import sysconfig
import time
import traceback
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from types import ModuleType


PRIMARY_MODEL = "Qwen/Qwen3.5-9B"
PRIMARY_QUANTIZATION = "4-bit"
PRIMARY_MODE = "non-thinking/instruct"
PRIMARY_ARTIFACT = "/home/sipbot/models/c3-qwen35-9b-gguf/Qwen3.5-9B-Q4_K_M.gguf"
PRIMARY_ARTIFACT_SHA256 = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"
PRIMARY_BACKEND = "Ollama"
PRIMARY_BACKEND_VERSION = "0.33.1"
DEFAULT_DISCOVERY_MODULES = (
    "torch",
    "transformers",
    "accelerate",
    "safetensors",
    "bitsandbytes",
    "llama_cpp",
    "vllm",
)


def gil_enabled() -> bool | None:
    checker = getattr(sys, "_is_gil_enabled", None)
    return bool(checker()) if checker is not None else None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def runtime_record() -> dict[str, object]:
    return {
        "executable": sys.executable,
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "soabi": sysconfig.get_config_var("SOABI"),
        "py_gil_disabled": sysconfig.get_config_var("Py_GIL_DISABLED"),
        "gil_enabled": gil_enabled(),
    }


def discover_modules(names: list[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name in names:
        try:
            spec = importlib.util.find_spec(name)
            result.append(
                {
                    "module": name,
                    "available": spec is not None,
                    "origin": spec.origin if spec is not None else None,
                    "loader": type(spec.loader).__name__ if spec is not None and spec.loader else None,
                }
            )
        except (ImportError, ModuleNotFoundError, ValueError) as exc:
            result.append(
                {
                    "module": name,
                    "available": False,
                    "discovery_error": f"{type(exc).__name__}: {exc}",
                }
            )
    return result


def import_modules(names: list[str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for name in names:
        before = gil_enabled()
        captured: list[dict[str, str]] = []
        status = "pass"
        error: str | None = None
        module: ModuleType | None = None
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            try:
                module = __import__(name, fromlist=["*"])
            except Exception as exc:  # noqa: BLE001 - evidence must retain import failures
                status = "fail"
                error = f"{type(exc).__name__}: {exc}"
                traceback.print_exc(file=sys.stderr)
            for item in emitted:
                captured.append(
                    {
                        "category": item.category.__name__,
                        "message": str(item.message),
                    }
                )
        after = gil_enabled()
        if before is True or after is True:
            status = "fail"
            error = error or "GIL became enabled during explicit import"
        results.append(
            {
                "module": name,
                "status": status,
                "gil_before": before,
                "gil_after": after,
                "warnings": captured,
                "module_file": getattr(module, "__file__", None),
                "error": error,
            }
        )
    return results


def timing_ms(end_ns: int | None, start_ns: int | None) -> float | str:
    if end_ns is None or start_ns is None:
        return "not_available"
    return round((end_ns - start_ns) / 1_000_000, 3)


def response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "text"],
        "properties": {
            "action": {"type": "string", "enum": ["answer"]},
            "text": {"type": "string", "minLength": 1},
        },
    }


def valid_structured_response(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {"action", "text"}:
        return False
    return value.get("action") == "answer" and isinstance(value.get("text"), str) and bool(value["text"].strip())


def gpu_record_base(args: argparse.Namespace, prompt: dict[str, object]) -> dict[str, object]:
    return {
        "evidence_id": "E-C3-TOKEN-001",
        "stage": "gpu",
        "status": "not_run",
        "candidate": {
            "model_id": PRIMARY_MODEL,
            "quantization": PRIMARY_QUANTIZATION,
            "mode": PRIMARY_MODE,
            "fallback_run": False,
        },
        "backend": {
            "name": PRIMARY_BACKEND,
            "version": PRIMARY_BACKEND_VERSION,
            "model_name": args.ollama_model,
            "url": args.ollama_url,
            "artifact_path": PRIMARY_ARTIFACT,
            "artifact_sha256": PRIMARY_ARTIFACT_SHA256,
            "controller": "stdlib urllib.request",
        },
        "fixture": {
            "fixture_id": prompt.get("fixture_id"),
            "authority": prompt.get("authority"),
            "final_user_phrase": prompt.get("final_user_phrase"),
        },
        "safety": {
            "model_weights_loaded": "backend-dependent; this stage is the authorized GPU execution stage",
            "model_generation_started": False,
            "gpu_inference_started": False,
            "vram_benchmark_started": False,
            "latency_benchmark_started": False,
            "cancellation_benchmark_started": False,
        },
        "fallback_run": False,
        "response_contract": response_schema(),
        "final_phrase_handoff": {
            "authority": "synthetic_authoritative_final_user_turn",
            "final_phrase_received_at": None,
            "final_phrase_received_monotonic_ns": None,
            "request_started_at": None,
            "request_started_monotonic_ns": None,
        },
        "first_useful_output_at": None,
        "first_useful_output_monotonic_ns": None,
        "first_valid_response_at": None,
        "first_valid_response_monotonic_ns": None,
        "timings": {
            "final_phrase_to_first_useful_output_ms": "not_available",
            "final_phrase_to_first_valid_response_ms": "not_available",
            "request_to_first_useful_output_ms": "not_available",
            "request_to_first_valid_response_ms": "not_available",
        },
        "stream_mode": "stream",
        "raw_output": "",
        "response": None,
        "errors": [],
    }


def run_gpu_ollama(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    if not args.allow_gpu:
        raise RuntimeError("GPU stage requires explicit --allow-gpu")
    if args.prompt_file is None:
        raise RuntimeError("GPU stage requires --prompt-file")

    prompt = json.loads(args.prompt_file.read_text(encoding="utf-8"))
    final_phrase = prompt.get("final_user_phrase")
    if not isinstance(final_phrase, str) or not final_phrase.strip():
        raise ValueError("prompt fixture has no non-empty final_user_phrase")
    record = gpu_record_base(args, prompt)
    final_phrase_received_wall = utc_now()
    final_phrase_received_ns = time.monotonic_ns()
    request_payload = {
        "model": args.ollama_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Отвечай только валидным JSON без Markdown и рассуждений. "
                    "Формат: объект с полями action=answer и непустым text."
                ),
            },
            {"role": "user", "content": final_phrase},
        ],
        "stream": True,
        "think": False,
        "format": response_schema(),
        "options": {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 20,
            "num_ctx": 8192,
            "num_predict": 128,
        },
    }
    record["final_phrase_handoff"] = {
        "authority": "synthetic_authoritative_final_user_turn",
        "final_phrase_received_at": final_phrase_received_wall,
        "final_phrase_received_monotonic_ns": final_phrase_received_ns,
        "request_started_at": None,
        "request_started_monotonic_ns": None,
    }
    request_started_wall = utc_now()
    request_started_ns = time.monotonic_ns()
    record["final_phrase_handoff"]["request_started_at"] = request_started_wall
    record["final_phrase_handoff"]["request_started_monotonic_ns"] = request_started_ns
    request = urllib.request.Request(
        args.ollama_url.rstrip("/") + "/api/chat",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    chunks: list[str] = []
    first_useful_ns: int | None = None
    first_valid_ns: int | None = None
    first_valid_response: dict[str, object] | None = None
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            while True:
                line = response.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                event = json.loads(line)
                message = event.get("message")
                piece = message.get("content", "") if isinstance(message, dict) else event.get("response", "")
                if isinstance(piece, str) and piece:
                    chunks.append(piece)
                    if first_useful_ns is None and piece.strip():
                        first_useful_ns = time.monotonic_ns()
                    if first_valid_ns is None:
                        try:
                            candidate = json.loads("".join(chunks).strip())
                        except json.JSONDecodeError:
                            candidate = None
                        if valid_structured_response(candidate):
                            first_valid_ns = time.monotonic_ns()
                            first_valid_response = candidate
        record["raw_output"] = "".join(chunks)
        record["first_useful_output_monotonic_ns"] = first_useful_ns
        record["first_valid_response_monotonic_ns"] = first_valid_ns
        record["first_useful_output_at"] = utc_now() if first_useful_ns is not None else None
        record["first_valid_response_at"] = utc_now() if first_valid_ns is not None else None
        record["response"] = first_valid_response
        record["timings"] = {
            "final_phrase_to_first_useful_output_ms": timing_ms(first_useful_ns, final_phrase_received_ns),
            "final_phrase_to_first_valid_response_ms": timing_ms(first_valid_ns, final_phrase_received_ns),
            "request_to_first_useful_output_ms": timing_ms(first_useful_ns, request_started_ns),
            "request_to_first_valid_response_ms": timing_ms(first_valid_ns, request_started_ns),
        }
        if first_valid_response is None:
            record["status"] = "fail_invalid_structured_response"
            record["errors"].append("stream ended without a valid structured response")
            return record, 1
        record["status"] = "gpu_inference_completed"
        record["safety"]["gpu_inference_started"] = True
        record["safety"]["model_generation_started"] = True
        record["safety"]["model_weights_loaded"] = True
        return record, 0
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        record["raw_output"] = "".join(chunks)
        record["first_useful_output_monotonic_ns"] = first_useful_ns
        record["first_valid_response_monotonic_ns"] = first_valid_ns
        record["timings"] = {
            "final_phrase_to_first_useful_output_ms": timing_ms(first_useful_ns, final_phrase_received_ns),
            "final_phrase_to_first_valid_response_ms": timing_ms(first_valid_ns, final_phrase_received_ns),
            "request_to_first_useful_output_ms": timing_ms(first_useful_ns, request_started_ns),
            "request_to_first_valid_response_ms": timing_ms(first_valid_ns, request_started_ns),
        }
        record["status"] = "fail"
        record["errors"].append(f"{type(exc).__name__}: {exc}")
        return record, 1


def run_cancel_ollama(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    if not args.allow_gpu:
        raise RuntimeError("Cancellation stage requires explicit --allow-gpu")
    if args.prompt_file is None:
        raise RuntimeError("Cancellation stage requires --prompt-file")

    prompt = json.loads(args.prompt_file.read_text(encoding="utf-8"))
    final_phrase = prompt.get("final_user_phrase")
    if not isinstance(final_phrase, str) or not final_phrase.strip():
        raise ValueError("prompt fixture has no non-empty final_user_phrase")

    record = gpu_record_base(args, prompt)
    record["evidence_id"] = "E-C3-CANCEL-001"
    record["stage"] = "cancel"
    record["stream_mode"] = "stream_cancel_by_client_close"
    record["cancellation"] = {
        "mechanism": "close HTTP response after first useful output",
        "cancel_requested": False,
        "cancel_requested_at": None,
        "cancel_requested_monotonic_ns": None,
        "stream_closed_at": None,
        "stream_closed_monotonic_ns": None,
        "backend_cancel_ack": "not_available; Ollama HTTP API has no separate acknowledgement",
        "tokens_after_cancel_observed": None,
        "published_result": False,
        "stale_result_accepted": False,
        "cleanup_wait_seconds": 1.0,
    }
    request_payload = {
        "model": args.ollama_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Отвечай только валидным JSON без Markdown и рассуждений. "
                    "Формат: объект с полями action=answer и непустым text. "
                    "Сформируй развёрнутый ответ, чтобы поток оставался активным."
                ),
            },
            {"role": "user", "content": final_phrase},
        ],
        "stream": True,
        "think": False,
        "format": response_schema(),
        "keep_alive": 0,
        "options": {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 20,
            "num_ctx": 8192,
            "num_predict": 512,
        },
    }
    final_phrase_received_ns = time.monotonic_ns()
    final_phrase_received_wall = utc_now()
    request_started_ns = time.monotonic_ns()
    request_started_wall = utc_now()
    record["final_phrase_handoff"] = {
        "authority": "synthetic_authoritative_final_user_turn",
        "final_phrase_received_at": final_phrase_received_wall,
        "final_phrase_received_monotonic_ns": final_phrase_received_ns,
        "request_started_at": request_started_wall,
        "request_started_monotonic_ns": request_started_ns,
    }
    request = urllib.request.Request(
        args.ollama_url.rstrip("/") + "/api/chat",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    first_useful_ns: int | None = None
    chunks: list[str] = []
    try:
        response = urllib.request.urlopen(request, timeout=args.timeout)
        try:
            while True:
                line = response.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                event = json.loads(line)
                message = event.get("message")
                piece = message.get("content", "") if isinstance(message, dict) else event.get("response", "")
                if not isinstance(piece, str) or not piece:
                    continue
                chunks.append(piece)
                if first_useful_ns is None and piece.strip():
                    first_useful_ns = time.monotonic_ns()
                    record["first_useful_output_monotonic_ns"] = first_useful_ns
                    record["first_useful_output_at"] = utc_now()
                    cancel_ns = time.monotonic_ns()
                    record["cancellation"].update(
                        {
                            "cancel_requested": True,
                            "cancel_requested_at": utc_now(),
                            "cancel_requested_monotonic_ns": cancel_ns,
                        }
                    )
                    response.close()
                    closed_ns = time.monotonic_ns()
                    record["cancellation"].update(
                        {
                            "stream_closed_at": utc_now(),
                            "stream_closed_monotonic_ns": closed_ns,
                            "tokens_after_cancel_observed": 0,
                        }
                    )
                    break
            if first_useful_ns is None:
                raise RuntimeError("stream ended before a useful output chunk; cancellation was not exercised")
        finally:
            response.close()
        time.sleep(1.0)
        record["raw_output"] = "".join(chunks)
        record["timings"] = {
            "final_phrase_to_first_useful_output_ms": timing_ms(first_useful_ns, final_phrase_received_ns),
            "final_phrase_to_first_valid_response_ms": "not_available; request cancelled before final response",
            "request_to_first_useful_output_ms": timing_ms(first_useful_ns, request_started_ns),
            "request_to_first_valid_response_ms": "not_available; request cancelled before final response",
        }
        record["safety"].update(
            {
                "model_weights_loaded": True,
                "model_generation_started": True,
                "gpu_inference_started": True,
                "cancellation_benchmark_started": True,
            }
        )
        record["status"] = "cancelled_stream_closed"
        return record, 0
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, RuntimeError) as exc:
        record["raw_output"] = "".join(chunks)
        record["timings"] = {
            "final_phrase_to_first_useful_output_ms": timing_ms(first_useful_ns, final_phrase_received_ns),
            "final_phrase_to_first_valid_response_ms": "not_available",
            "request_to_first_useful_output_ms": timing_ms(first_useful_ns, request_started_ns),
            "request_to_first_valid_response_ms": "not_available",
        }
        record["status"] = "fail"
        record["errors"].append(f"{type(exc).__name__}: {exc}")
        return record, 1


def build_record(args: argparse.Namespace) -> dict[str, object]:
    before = gil_enabled()
    record: dict[str, object] = {
        "probe": "001-C3-llm-primary",
        "stage": args.stage,
        "status": "prepared_only",
        "started_at_utc": utc_now(),
        "candidate": {
            "model_id": PRIMARY_MODEL,
            "quantization": PRIMARY_QUANTIZATION,
            "mode": PRIMARY_MODE,
            "fallback_run": False,
        },
        "runtime": runtime_record(),
        "safety": {
            "model_weights_loaded": False,
            "model_generation_started": False,
            "gpu_inference_started": False,
            "vram_benchmark_started": False,
            "latency_benchmark_started": False,
            "cancellation_benchmark_started": False,
        },
        "gil_before_probe": before,
        "module_discovery": discover_modules(args.modules),
        "import_results": [],
        "notes": [
            "Preflight does not import backend modules and does not load model weights.",
            "Import stage is opt-in and limited to explicitly named modules; it still does not create a model or generate output.",
            "Final-phrase timing is measured only in the later GPU execution stage from synthetic authoritative handoff.",
        ],
    }
    if args.stage == "import":
        record["import_results"] = import_modules(args.modules)
        record["status"] = "import_only"
    record["gil_after_probe"] = gil_enabled()
    record["finished_at_utc"] = utc_now()
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("preflight", "import", "gpu", "cancel"), default="preflight")
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-gpu", action="store_true")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-model", default="c3-qwen35-9b-q4km")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--modules",
        nargs="+",
        help="Modules to discover; for --stage import this must be supplied explicitly.",
    )
    args = parser.parse_args()
    if args.stage in {"gpu", "cancel"} and not args.allow_gpu:
        parser.error(f"--stage {args.stage} requires explicit --allow-gpu")
    if args.stage in {"gpu", "cancel"} and args.prompt_file is None:
        parser.error(f"--stage {args.stage} requires --prompt-file")
    if args.modules is None:
        if args.stage == "import":
            parser.error("--stage import requires explicit --modules")
        args.modules = list(DEFAULT_DISCOVERY_MODULES)
    return args


def main() -> int:
    args = parse_args()
    if args.stage in {"gpu", "cancel"}:
        runner = run_gpu_ollama if args.stage == "gpu" else run_cancel_ollama
        record, exit_code = runner(args)
        output = args.output or args.evidence_root / ("inference.json" if args.stage == "gpu" else "cancellation.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return exit_code
    record = build_record(args)
    output = args.output or args.evidence_root / "import-probe.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
