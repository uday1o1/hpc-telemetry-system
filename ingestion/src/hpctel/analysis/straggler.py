"""Straggler-ranking algorithm (BUILD_PLAN.md section 8): given one
completed job phase's per-node durations, ranks nodes by a robust,
median-absolute-deviation-based modified z-score and flags the top
candidate as the probable straggler, with a rule-based root-cause tag.

The naive maximum-duration baseline exists purely as a comparison point
for the evaluation harness (section 13), not as a shipped detection path.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

MAD_Z_THRESHOLD = 3.5  # Iglewicz and Hoya (1993) robust-outlier threshold
MAD_CONSTANT = 0.6745  # Iglewicz and Hoya's normalizing constant
MAD_FLOOR_NS = 1_000_000  # 1ms floor, avoids division by zero when all nodes tie
MIN_REPORTING_NODES = 3  # below this, MAD is not a meaningful robust statistic

_ROOT_CAUSE_RELATIVE_THRESHOLD = 0.25  # 25% relative increase over baseline


@dataclass(frozen=True)
class RankedNode:
    node_id: str
    duration_ns: int
    z_score: float
    flagged: bool


@dataclass(frozen=True)
class StragglerReport:
    job_id: str
    phase_index: int
    status: str  # "ranked" or "insufficient_evidence"
    ranked_nodes: list[RankedNode] = field(default_factory=list)
    top_candidate: str | None = None
    naive_baseline_candidate: str | None = None
    root_cause: str | None = None


def rank_stragglers(job_id: str, phase_index: int, durations_ns: dict[str, int]) -> StragglerReport:
    """`durations_ns` maps node_id to phase_end_mono_ns - phase_start_mono_ns
    (the monotonic-clock phase duration; see BUILD_PLAN.md section 7 on why
    duration math never uses the realtime ts_ns fields).
    """
    if len(durations_ns) < MIN_REPORTING_NODES:
        return StragglerReport(job_id=job_id, phase_index=phase_index, status="insufficient_evidence")

    node_ids = list(durations_ns.keys())
    values = [durations_ns[n] for n in node_ids]

    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    mad = max(mad, MAD_FLOOR_NS)

    z_scores = {n: MAD_CONSTANT * (durations_ns[n] - median) / mad for n in node_ids}

    # Deterministic ordering: z-score descending, ties broken by ascending
    # node_id, so the ranking is a total order reproducible from the same
    # input rows (BUILD_PLAN.md section 8, "deterministic tie-breaking").
    ordered = sorted(node_ids, key=lambda n: (-z_scores[n], n))

    ranked_nodes = [
        RankedNode(
            node_id=n,
            duration_ns=durations_ns[n],
            z_score=z_scores[n],
            flagged=z_scores[n] > MAD_Z_THRESHOLD,
        )
        for n in ordered
    ]

    flagged = [rn for rn in ranked_nodes if rn.flagged]
    top_candidate = flagged[0].node_id if flagged else None

    naive_baseline_candidate = max(node_ids, key=lambda n: (durations_ns[n], n))

    return StragglerReport(
        job_id=job_id,
        phase_index=phase_index,
        status="ranked",
        ranked_nodes=ranked_nodes,
        top_candidate=top_candidate,
        naive_baseline_candidate=naive_baseline_candidate,
    )


def tag_root_cause(
    cpu_pct_delta: float | None,
    iowait_pct_delta: float | None,
    net_bytes_s_delta: float | None,
) -> str:
    """Rule-based root-cause tag (BUILD_PLAN.md section 8): compares the
    flagged node's during-phase metric readings against its own pre-phase
    baseline. Each `*_delta` is a relative delta (e.g. 0.5 for a 50%
    increase over baseline); None means that metric could not be measured.
    Tags CPU_CONTENTION, IO_STALL, or NETWORK for whichever available
    metric shows the largest relative increase, or UNKNOWN if none exceeds
    the threshold (or none were measurable at all).
    """
    candidates = {
        "CPU_CONTENTION": cpu_pct_delta,
        "IO_STALL": iowait_pct_delta,
        "NETWORK": net_bytes_s_delta,
    }
    measurable = {tag: delta for tag, delta in candidates.items() if delta is not None}
    if not measurable:
        return "UNKNOWN"

    best_tag, best_delta = max(measurable.items(), key=lambda item: item[1])
    if best_delta > _ROOT_CAUSE_RELATIVE_THRESHOLD:
        return best_tag
    return "UNKNOWN"
