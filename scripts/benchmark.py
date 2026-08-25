#!/usr/bin/env python3
"""Milestone 5 performance benchmark protocol (BUILD_PLAN.md section 13).

Measures end-to-end ingestion latency (p50/p95/p99), throughput, and
per-agent CPU/RSS overhead for two workload configurations (a 1-second
baseline sample interval and a 200-millisecond stress interval), 5
independent trials each in randomized (interleaved) order, discarding a
trial if a host-side thermal-throttle proxy check fires.

Duration adaptation, documented here and in docs/PERFORMANCE.md: the plan
calls for 5-minute trials; this script uses 60-second trials instead. At
the baseline rate (~80 samples/sec aggregate) a 60s trial already yields
several thousand latency observations, comfortably enough for stable
percentile estimates, and 60s keeps the full 10-trial (2 configs x 5
trials) protocol's wall-clock cost reasonable. This is the same kind of
documented, evidence-based adaptation used elsewhere in this project
(see BUILD_PLAN.md's Milestone 0 kill/fallback note), not an unexplained
shortcut.

Prerequisite: `docker compose up -d` must already have been run once (the
images must exist); this script restarts only the agent-* services when
switching SAMPLE_INTERVAL_MS between trials.
"""

from __future__ import annotations

import json
import random
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8080"
REPO_ROOT = Path(__file__).parent.parent
RESULTS_PATH = REPO_ROOT / "docs" / "performance_raw.json"

TRIAL_DURATION_S = 60.0
WARMUP_S = 30.0
TRIALS_PER_CONFIG = 5
THERMAL_THROTTLE_RATIO = 1.20  # discard a trial if calibration slows >20%
RANDOM_SEED = 7  # fixed, for a reproducible interleaving order

CONFIGS = {
    "baseline_1000ms": "1000",
    "stress_200ms": "200",
}


def _http_get(path: str) -> dict[str, object]:
    with urllib.request.urlopen(BASE_URL + path, timeout=15) as resp:
        return json.loads(resp.read())


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kwargs)


def _calibration_duration_s() -> float:
    # A fixed, allocation-light arithmetic loop, used only as a relative
    # before/after timing signal on the host, not as a benchmark result.
    start = time.perf_counter()
    x = 0
    for _ in range(20_000_000):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
    return time.perf_counter() - start


def _record_environment() -> dict[str, object]:
    env: dict[str, object] = {}
    try:
        env["docker_version"] = _run(["docker", "--version"]).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        env["docker_version"] = "unknown"
    try:
        env["colima_status"] = _run(["colima", "status"]).stderr.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        env["colima_status"] = "unknown"
    try:
        uname = _run(["docker", "compose", "exec", "-T", "ingestion", "uname", "-r"], cwd=REPO_ROOT)
        env["container_kernel"] = uname.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        env["container_kernel"] = "unknown"
    env["host"] = "Apple M2 MacBook Pro, 8 GB unified memory"
    return env


def _set_sample_interval(interval_ms: str) -> None:
    subprocess.run(
        ["docker", "compose", "up", "-d", "--no-deps"]
        + [f"agent-{i}" for i in range(1, 9)],
        cwd=REPO_ROOT,
        env={"SAMPLE_INTERVAL_MS": interval_ms, "PATH": _path_env()},
        check=True,
        capture_output=True,
        text=True,
    )


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")


def _agent_stats() -> dict[str, float]:
    result = _run(
        [
            "docker", "stats", "--no-stream", "--format",
            "{{.Name}},{{.CPUPerc}},{{.MemUsage}}",
        ]
    )
    cpu_pcts = []
    mem_mibs = []
    for line in result.stdout.strip().splitlines():
        name, cpu_pct_str, mem_str = line.split(",", 2)
        if "-agent-" not in name:
            continue
        cpu_pcts.append(float(cpu_pct_str.strip().rstrip("%")))
        mem_part = mem_str.split("/")[0].strip()
        if mem_part.endswith("MiB"):
            mem_mibs.append(float(mem_part[:-3]))
        elif mem_part.endswith("KiB"):
            mem_mibs.append(float(mem_part[:-3]) / 1024)
        elif mem_part.endswith("GiB"):
            mem_mibs.append(float(mem_part[:-3]) * 1024)
    return {
        "cpu_pct_median": statistics.median(cpu_pcts) if cpu_pcts else float("nan"),
        "mem_mib_median": statistics.median(mem_mibs) if mem_mibs else float("nan"),
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    f, c = int(k), min(int(k) + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _run_one_trial(config_label: str) -> dict[str, object]:
    before = _calibration_duration_s()
    trial_start = time.monotonic()
    time.sleep(TRIAL_DURATION_S)
    after = _calibration_duration_s()

    throttled = after > before * THERMAL_THROTTLE_RATIO
    latency_payload = _http_get(f"/api/diagnostics/ingestion_latency_ms?since_seconds={TRIAL_DURATION_S}")
    latencies = latency_payload["latencies_ms"]
    agent_stats = _agent_stats()

    return {
        "config": config_label,
        "throttled": throttled,
        "calibration_before_s": before,
        "calibration_after_s": after,
        "trial_wall_seconds": time.monotonic() - trial_start,
        "sample_count": latency_payload["sample_count"],
        "throughput_samples_per_s": latency_payload["sample_count"] / TRIAL_DURATION_S,
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
        "p99_ms": _percentile(latencies, 99),
        "agent_cpu_pct_median": agent_stats["cpu_pct_median"],
        "agent_mem_mib_median": agent_stats["mem_mib_median"],
    }


def main() -> None:
    environment = _record_environment()

    order = [config for config in CONFIGS for _ in range(TRIALS_PER_CONFIG)]
    random.Random(RANDOM_SEED).shuffle(order)

    trials = []
    current_config = None
    for i, config_label in enumerate(order):
        if config_label != current_config:
            print(f"switching to config {config_label} ({CONFIGS[config_label]}ms)...", flush=True)
            _set_sample_interval(CONFIGS[config_label])
            time.sleep(WARMUP_S)
            current_config = config_label
        print(f"[{i + 1}/{len(order)}] running trial for {config_label}...", flush=True)
        trial = _run_one_trial(config_label)
        trials.append(trial)
        print(f"  -> p50={trial['p50_ms']:.1f}ms p95={trial['p95_ms']:.1f}ms "
              f"throughput={trial['throughput_samples_per_s']:.1f}/s throttled={trial['throttled']}", flush=True)

    output = {"environment": environment, "trials": trials}
    RESULTS_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
