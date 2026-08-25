"""Golden, property, metamorphic, and boundary tests for the straggler
ranking algorithm (BUILD_PLAN.md section 8).
"""

from __future__ import annotations

from hpctel.analysis.straggler import (
    MAD_Z_THRESHOLD,
    rank_stragglers,
    tag_root_cause,
)


def test_golden_five_node_example_matches_hand_computed_z_scores():
    # Durations in ns; node-e is a clear straggler (500ms vs ~100ms peers).
    durations = {
        "node-a": 100_000_000,
        "node-b": 105_000_000,
        "node-c": 98_000_000,
        "node-d": 102_000_000,
        "node-e": 500_000_000,
    }
    # Hand-computed: median=102e6, MAD=median(|dev|)=3e6.
    # z_e = 0.6745 * (500e6-102e6) / 3e6 = 0.6745 * 398/3 = 89.483666...
    # z_b = 0.6745 * (105e6-102e6) / 3e6 = 0.6745
    report = rank_stragglers("job-1", 0, durations)

    assert report.status == "ranked"
    assert report.top_candidate == "node-e"
    assert report.naive_baseline_candidate == "node-e"

    by_node = {rn.node_id: rn for rn in report.ranked_nodes}
    assert abs(by_node["node-e"].z_score - 89.48366666666666) < 1e-6
    assert abs(by_node["node-b"].z_score - 0.6745) < 1e-6
    assert by_node["node-e"].flagged is True
    assert by_node["node-b"].flagged is False

    # Ranking is ordered by z-score descending.
    ordered_ids = [rn.node_id for rn in report.ranked_nodes]
    assert ordered_ids[0] == "node-e"


def test_deterministic_tie_break_by_ascending_node_id():
    # Two nodes with identical duration should tie in z-score and be
    # ordered by ascending node_id.
    durations = {"node-z": 100_000_000, "node-a": 100_000_000, "node-m": 100_000_000}
    report = rank_stragglers("job-2", 0, durations)
    ordered_ids = [rn.node_id for rn in report.ranked_nodes]
    assert ordered_ids == ["node-a", "node-m", "node-z"]


def test_property_duplicating_the_median_node_does_not_change_top_candidate():
    base = {
        "node-a": 100_000_000,
        "node-b": 103_000_000,
        "node-c": 99_000_000,
        "node-d": 101_000_000,
        "node-straggler": 800_000_000,
    }
    report_before = rank_stragglers("job-3", 0, base)

    # Duplicate the median-duration node (node-d, 101ms) under a new id.
    with_duplicate = dict(base)
    with_duplicate["node-d-duplicate"] = base["node-d"]
    report_after = rank_stragglers("job-3", 0, with_duplicate)

    assert report_before.top_candidate == report_after.top_candidate == "node-straggler"


def test_metamorphic_scaling_all_durations_preserves_ranking():
    base = {
        "node-a": 100_000_000,
        "node-b": 103_000_000,
        "node-c": 99_000_000,
        "node-d": 101_000_000,
        "node-straggler": 400_000_000,
    }
    scaled = {node: int(duration * 2.5) for node, duration in base.items()}

    report_base = rank_stragglers("job-4", 0, base)
    report_scaled = rank_stragglers("job-4", 0, scaled)

    base_order = [rn.node_id for rn in report_base.ranked_nodes]
    scaled_order = [rn.node_id for rn in report_scaled.ranked_nodes]
    assert base_order == scaled_order
    assert report_base.top_candidate == report_scaled.top_candidate


def test_boundary_insufficient_evidence_at_two_nodes_not_at_three():
    two_nodes = {"node-a": 100_000_000, "node-b": 500_000_000}
    three_nodes = {"node-a": 100_000_000, "node-b": 105_000_000, "node-c": 500_000_000}

    report_two = rank_stragglers("job-5", 0, two_nodes)
    report_three = rank_stragglers("job-5", 0, three_nodes)

    assert report_two.status == "insufficient_evidence"
    assert report_two.ranked_nodes == []
    assert report_three.status == "ranked"


def test_all_nodes_identical_duration_uses_mad_floor_and_flags_nothing():
    durations = {"node-a": 100_000_000, "node-b": 100_000_000, "node-c": 100_000_000}
    report = rank_stragglers("job-6", 0, durations)
    assert report.status == "ranked"
    assert all(rn.z_score == 0.0 for rn in report.ranked_nodes)
    assert report.top_candidate is None  # nothing exceeds MAD_Z_THRESHOLD


def test_z_threshold_constant_is_the_documented_value():
    assert MAD_Z_THRESHOLD == 3.5


def test_tag_root_cause_picks_largest_relative_delta_above_threshold():
    assert tag_root_cause(cpu_pct_delta=0.6, iowait_pct_delta=0.1, net_bytes_s_delta=0.05) == "CPU_CONTENTION"
    assert tag_root_cause(cpu_pct_delta=0.1, iowait_pct_delta=0.9, net_bytes_s_delta=0.05) == "IO_STALL"
    assert tag_root_cause(cpu_pct_delta=0.1, iowait_pct_delta=0.1, net_bytes_s_delta=0.9) == "NETWORK"


def test_tag_root_cause_unknown_when_nothing_exceeds_threshold():
    assert tag_root_cause(cpu_pct_delta=0.1, iowait_pct_delta=0.05, net_bytes_s_delta=0.0) == "UNKNOWN"


def test_tag_root_cause_unknown_when_nothing_measurable():
    assert tag_root_cause(cpu_pct_delta=None, iowait_pct_delta=None, net_bytes_s_delta=None) == "UNKNOWN"


def test_tag_root_cause_handles_partial_measurability():
    # Only iowait was measurable, and it clears the threshold.
    assert tag_root_cause(cpu_pct_delta=None, iowait_pct_delta=0.5, net_bytes_s_delta=None) == "IO_STALL"
