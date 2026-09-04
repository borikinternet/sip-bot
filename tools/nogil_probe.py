"""Stdlib-only diagnostic for a free-threaded CPython executable.

This probe intentionally imports no project code and no third-party package.
It records the GIL state before and after an explicit stdlib import manifest,
then runs a small deterministic threaded workload.
"""

import sys


IMPORT_MANIFEST = (
    "sysconfig",
    "platform",
    "json",
    "pathlib",
    "threading",
    "queue",
    "concurrent.futures",
    "time",
    "statistics",
)
WORKERS = 4
ITERATIONS = 25_000
BARRIER_TIMEOUT_SECONDS = 5.0
FUTURE_TIMEOUT_SECONDS = 15.0


def gil_enabled():
    checker = getattr(sys, "_is_gil_enabled", None)
    if checker is None:
        return None
    return bool(checker())


def run_concurrency_smoke():
    import concurrent.futures
    import threading
    import time

    barrier = threading.Barrier(WORKERS)
    lock = threading.Lock()
    shared_total = [0]

    def worker(worker_id):
        barrier.wait(timeout=BARRIER_TIMEOUT_SECONDS)
        value = 0
        for iteration in range(ITERATIONS):
            value = (value + (worker_id + 1) * (iteration + 17)) % 1_000_003
        with lock:
            shared_total[0] += value
        return value

    gil_before = gil_enabled()
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(worker, worker_id) for worker_id in range(WORKERS)]
        values = [future.result(timeout=FUTURE_TIMEOUT_SECONDS) for future in futures]

    return {
        "workers": WORKERS,
        "iterations": ITERATIONS,
        "barrier_timeout_seconds": BARRIER_TIMEOUT_SECONDS,
        "future_timeout_seconds": FUTURE_TIMEOUT_SECONDS,
        "values": values,
        "expected_shared_total": sum(values),
        "shared_total": shared_total[0],
        "elapsed_seconds": time.monotonic() - started,
        "gil_before": gil_before,
        "gil_after": gil_enabled(),
    }


def main():
    result = {
        "probe": "001-B-free-threaded-cpython-stdlib",
        "executable": sys.executable,
        "implementation": {
            "name": sys.implementation.name,
            "version": list(sys.version_info[:5]),
            "version_string": sys.version,
        },
        "platform_machine": None,
        "soabi": None,
        "py_gil_disabled": None,
        "gil_supported": hasattr(sys, "_is_gil_enabled"),
        "gil_before_stdlib_imports": gil_enabled(),
        "import_manifest": list(IMPORT_MANIFEST),
        "imports": [],
        "import_errors": [],
        "concurrency": None,
    }

    for module_name in IMPORT_MANIFEST:
        try:
            __import__(module_name)
            result["imports"].append(
                {"module": module_name, "status": "pass", "gil_enabled": gil_enabled()}
            )
        except BaseException as error:  # The result must preserve diagnostic failures.
            result["import_errors"].append(
                {
                    "module": module_name,
                    "type": type(error).__name__,
                    "message": str(error),
                    "gil_enabled": gil_enabled(),
                }
            )

    sysconfig_module = sys.modules.get("sysconfig")
    platform_module = sys.modules.get("platform")
    if sysconfig_module is not None:
        result["py_gil_disabled"] = sysconfig_module.get_config_var("Py_GIL_DISABLED")
        result["soabi"] = sysconfig_module.get_config_var("SOABI")
    if platform_module is not None:
        result["platform_machine"] = platform_module.machine()

    result["gil_after_stdlib_imports"] = gil_enabled()
    import_gil_states = [item["gil_enabled"] for item in result["imports"]]
    imports_pass = not result["import_errors"] and all(state is False for state in import_gil_states)

    if imports_pass and result["py_gil_disabled"] == 1 and result["gil_before_stdlib_imports"] is False:
        try:
            result["concurrency"] = run_concurrency_smoke()
        except BaseException as error:  # The caller gets a non-zero result with structured details.
            result["concurrency"] = {
                "status": "fail",
                "type": type(error).__name__,
                "message": str(error),
                "gil_at_failure": gil_enabled(),
            }

    concurrency_pass = (
        isinstance(result["concurrency"], dict)
        and result["concurrency"].get("shared_total") == result["concurrency"].get("expected_shared_total")
        and result["concurrency"].get("gil_before") is False
        and result["concurrency"].get("gil_after") is False
    )
    result["status"] = "pass" if imports_pass and concurrency_pass else "fail"

    import json

    sys.stdout.write(json.dumps(result, ensure_ascii=True, sort_keys=True) + "\n")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
