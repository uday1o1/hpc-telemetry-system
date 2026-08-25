#!/usr/bin/env python3
"""Runs the frozen confirmatory fault-injection trial batch against a
live, already-running 8-node rack (`docker compose up -d` from the
repository root) and computes the statistical decision contract from
BUILD_PLAN.md section 13.

Each trial's full result is written to eval/results/<trial_id>.json as
soon as it completes, so a killed or interrupted run can be resumed by
rerunning this script: trials with an existing result file are skipped.

Usage:
    python3 eval/run_trials.py                 # run any trials not yet completed
    python3 eval/run_trials.py --replay         # recompute the summary from
                                                 # existing eval/results/*.json
                                                 # without running anything new
                                                 # (the clean-checkout determinism
                                                 # check in BUILD_PLAN.md section 19)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion" / "src"))
from hpctel.analysis.stats import wilson_interval  # noqa: E402

BASE_URL = "http://127.0.0.1:8080"
RESULTS_DIR = Path(__file__).parent / "results"
MANIFEST_PATH = Path(__file__).parent / "trial_seeds.json"
JOB_POLL_INTERVAL_S = 0.3
JOB_POLL_TIMEOUT_S = 30.0

DETECTION_LOWER_BOUND_THRESHOLD = 0.75
FP_UPPER_BOUND_THRESHOLD = 0.15
NO_FAULT_FP_UPPER_BOUND_THRESHOLD = 0.10

_EXPECTED_TAG = {"cpu_contention": "CPU_CONTENTION", "io_stall": "IO_STALL"}


def _http_post(path: str, body: dict[str, object]) -> dict[str, object]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE_URL + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _http_get(path: str) -> dict[str, object]:
    with urllib.request.urlopen(BASE_URL + path, timeout=15) as resp:
        return json.loads(resp.read())


def _check_rack_reachable() -> None:
    try:
        health = _http_get("/healthz")
    except (urllib.error.URLError, OSError) as exc:
        print(
            f"ERROR: cannot reach {BASE_URL}/healthz ({exc}). "
            "Run `docker compose up -d` from the repository root first.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    if health.get("status") != "ok":
        print(f"ERROR: ingestion service unhealthy: {health}", file=sys.stderr)
        raise SystemExit(2)


def _wait_for_job(job_id: str) -> dict[str, object] | None:
    deadline = time.monotonic() + JOB_POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        job = _http_get(f"/api/jobs/{job_id}")
        if job["status"] in ("completed", "timed_out"):
            return job
        time.sleep(JOB_POLL_INTERVAL_S)
    return None


def _run_trial(trial: dict[str, object]) -> dict[str, object]:
    body: dict[str, object] = {"phase_count": 1, "sieve_limit": trial["sieve_limit"]}
    expected_target_node_id = None
    if trial["fault_type"] is not None:
        expected_target_node_id = trial["target_host"].replace("workload-", "node-")
        body["fault"] = {
            "target_host": trial["target_host"],
            "phase_index": trial["phase_index"],
            "fault_type": trial["fault_type"],
            "intensity": trial["intensity"],
        }

    try:
        start_resp = _http_post("/api/jobs", body)
    except (urllib.error.URLError, OSError) as exc:
        return {"trial_id": trial["trial_id"], "outcome": "ABORTED", "reason": f"dispatch_error: {exc}"}

    job_id = start_resp["job_id"]
    job = _wait_for_job(job_id)
    if job is None:
        return {"trial_id": trial["trial_id"], "outcome": "ABORTED", "reason": "job_poll_timeout"}
    if job["status"] != "completed":
        return {"trial_id": trial["trial_id"], "outcome": "ABORTED", "reason": f"job_status={job['status']}"}

    report = _http_get(f"/api/jobs/{job_id}/straggler_report?phase_index={trial['phase_index']}")

    return {
        "trial_id": trial["trial_id"],
        "outcome": "COMPLETED",
        "job_id": job_id,
        "fault_type": trial["fault_type"],
        "target_host": trial["target_host"],
        "expected_target_node_id": expected_target_node_id,
        "straggler_status": report["status"],
        "top_candidate": report["top_candidate"],
        "naive_baseline_candidate": report["naive_baseline_candidate"],
        "root_cause": report["root_cause"],
        "ranked_nodes": report["ranked_nodes"],
    }


def _run_missing_trials(manifest: dict[str, object]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_trials = manifest["fault_trials"] + manifest["no_fault_trials"]
    for i, trial in enumerate(all_trials):
        result_path = RESULTS_DIR / f"{trial['trial_id']}.json"
        if result_path.exists():
            continue
        print(f"[{i + 1}/{len(all_trials)}] running trial {trial['trial_id']}...", flush=True)
        result = _run_trial(trial)
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"  -> {result['outcome']}", flush=True)


def _load_results(trial_ids: list[str]) -> list[dict[str, object]]:
    results = []
    for trial_id in trial_ids:
        result_path = RESULTS_DIR / f"{trial_id}.json"
        if result_path.exists():
            results.append(json.loads(result_path.read_text()))
    return results


def _decide(successes: int, n: int, predeclared_n: int, upper_bound_rule: bool, threshold: float) -> dict:
    if n < predeclared_n:
        return {"decision": "INSUFFICIENT_EVIDENCE", "n": n, "predeclared_n": predeclared_n}
    lower, upper = wilson_interval(successes, n)
    if upper_bound_rule:
        decision = "PASS" if upper <= threshold else "FAIL"
        bound_used = upper
    else:
        decision = "PASS" if lower >= threshold else "FAIL"
        bound_used = lower
    return {
        "decision": decision,
        "successes": successes,
        "n": n,
        "predeclared_n": predeclared_n,
        "point_estimate": successes / n,
        "wilson_lower": lower,
        "wilson_upper": upper,
        "bound_used": bound_used,
        "threshold": threshold,
    }


def _summarize(manifest: dict[str, object]) -> dict[str, object]:
    fault_trial_ids = [t["trial_id"] for t in manifest["fault_trials"]]
    no_fault_trial_ids = [t["trial_id"] for t in manifest["no_fault_trials"]]

    fault_results = _load_results(fault_trial_ids)
    no_fault_results = _load_results(no_fault_trial_ids)

    completed_fault = [r for r in fault_results if r["outcome"] == "COMPLETED"]
    completed_no_fault = [r for r in no_fault_results if r["outcome"] == "COMPLETED"]

    # Estimand 1: top-1 detection rate.
    detections = sum(
        1
        for r in completed_fault
        if r["straggler_status"] == "ranked" and r["top_candidate"] == r["expected_target_node_id"]
    )
    estimand_1 = _decide(
        detections, len(completed_fault), len(fault_trial_ids), upper_bound_rule=False,
        threshold=DETECTION_LOWER_BOUND_THRESHOLD,
    )

    # Estimand 2: trial-level false-positive rate on fault trials (any
    # healthy node other than the true target flagged).
    fault_false_positive_trials = sum(
        1
        for r in completed_fault
        if r["straggler_status"] == "ranked"
        and any(n["flagged"] and n["node_id"] != r["expected_target_node_id"] for n in r["ranked_nodes"])
    )
    estimand_2 = _decide(
        fault_false_positive_trials, len(completed_fault), len(fault_trial_ids), upper_bound_rule=True,
        threshold=FP_UPPER_BOUND_THRESHOLD,
    )

    # Estimand 3: no-fault baseline false-flag rate.
    no_fault_false_flags = sum(
        1
        for r in completed_no_fault
        if r["straggler_status"] == "ranked" and any(n["flagged"] for n in r["ranked_nodes"])
    )
    estimand_3 = _decide(
        no_fault_false_flags, len(completed_no_fault), len(no_fault_trial_ids), upper_bound_rule=True,
        threshold=NO_FAULT_FP_UPPER_BOUND_THRESHOLD,
    )

    # Estimand 4 (tertiary, non-gating): root-cause tag accuracy,
    # conditional on estimand-1 detection succeeding.
    true_positives = [
        r
        for r in completed_fault
        if r["straggler_status"] == "ranked" and r["top_candidate"] == r["expected_target_node_id"]
    ]
    tag_matches = sum(1 for r in true_positives if r["root_cause"] == _EXPECTED_TAG.get(r["fault_type"]))
    estimand_4 = _decide(
        tag_matches, len(true_positives), len(true_positives), upper_bound_rule=False, threshold=0.0
    )
    estimand_4["note"] = "tertiary, non-gating; predeclared_n intentionally equals n (conditional estimand)"

    # Naive maximum-duration baseline, evaluated on the identical fault
    # trials (paired comparison), reported alongside estimand 1.
    naive_detections = sum(
        1 for r in completed_fault if r["naive_baseline_candidate"] == r["expected_target_node_id"]
    )
    naive_baseline = _decide(
        naive_detections, len(completed_fault), len(fault_trial_ids), upper_bound_rule=False,
        threshold=DETECTION_LOWER_BOUND_THRESHOLD,
    )

    primary_claim_supported = estimand_1["decision"] == "PASS" and estimand_2["decision"] == "PASS"

    # Per-fault-type breakdown, useful for root-causing a shortfall.
    by_fault_type = {}
    for fault_type in ("cpu_contention", "io_stall"):
        subset = [r for r in completed_fault if r["fault_type"] == fault_type]
        subset_detections = sum(1 for r in subset if r["top_candidate"] == r["expected_target_node_id"])
        by_fault_type[fault_type] = _decide(
            subset_detections, len(subset), 40, upper_bound_rule=False,
            threshold=DETECTION_LOWER_BOUND_THRESHOLD,
        )

    return {
        "estimand_1_top1_detection_rate": estimand_1,
        "estimand_2_trial_level_false_positive_rate": estimand_2,
        "estimand_3_no_fault_false_flag_rate": estimand_3,
        "estimand_4_root_cause_tag_accuracy": estimand_4,
        "naive_baseline_top1_detection_rate": naive_baseline,
        "detection_rate_by_fault_type": by_fault_type,
        "primary_claim_supported": primary_claim_supported,
        "fault_trial_outcomes": {
            "completed": len(completed_fault),
            "aborted": len(fault_results) - len(completed_fault),
            "not_yet_run": len(fault_trial_ids) - len(fault_results),
        },
        "no_fault_trial_outcomes": {
            "completed": len(completed_no_fault),
            "aborted": len(no_fault_results) - len(completed_no_fault),
            "not_yet_run": len(no_fault_trial_ids) - len(no_fault_results),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay", action="store_true",
        help="Recompute the summary from existing results only; do not run new trials.",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text())

    if not args.replay:
        _check_rack_reachable()
        _run_missing_trials(manifest)

    summary = _summarize(manifest)
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
