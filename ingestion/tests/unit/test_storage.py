import tempfile
from pathlib import Path

import pytest

from hpctel.storage.tsdb import TSDBStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "test.sqlite3")
        s = TSDBStore(db_path)
        yield s
        s.close()


def test_insert_and_query_series(store: TSDBStore):
    rows = [
        ("node-1", 1, 100, 100, 105, 10.0, "v1"),
        ("node-1", 1, 200, 200, 205, 20.0, "v1"),
    ]
    inserted = store.insert_samples(rows)
    assert inserted == 2

    series = store.query_series("node-1", 1, limit=10)
    assert [row["value"] for row in series] == [20.0, 10.0]  # DESC order


def test_duplicate_primary_key_insert_is_idempotent_noop(store: TSDBStore):
    row = ("node-1", 1, 100, 100, 105, 10.0, "v1")
    first = store.insert_samples([row])
    second = store.insert_samples([row])  # exact duplicate (node_id, metric_id, ts_ns)
    assert first == 1
    assert second == 0
    series = store.query_series("node-1", 1, limit=10)
    assert len(series) == 1


def test_list_nodes_reports_last_seen_and_count(store: TSDBStore):
    store.insert_samples(
        [
            ("node-1", 1, 100, 100, 105, 10.0, "v1"),
            ("node-1", 1, 200, 200, 205, 20.0, "v1"),
            ("node-2", 1, 150, 150, 155, 5.0, "v1"),
        ]
    )
    nodes = {n["node_id"]: n for n in store.list_nodes()}
    assert nodes["node-1"]["sample_count"] == 2
    assert nodes["node-1"]["last_seen_ts_ns"] == 200
    assert nodes["node-2"]["sample_count"] == 1


def test_rollup_1m_matches_hand_computed_aggregate(store: TSDBStore):
    bucket_width_ns = 60_000_000_000
    base_ts = 10 * bucket_width_ns  # aligned bucket start
    rows = [
        ("node-1", 1, base_ts + 0, base_ts, base_ts, 10.0, "v1"),
        ("node-1", 1, base_ts + 1_000_000_000, base_ts, base_ts, 20.0, "v1"),
        ("node-1", 1, base_ts + 2_000_000_000, base_ts, base_ts, 30.0, "v1"),
    ]
    store.insert_samples(rows)
    store.recompute_rollups("node-1", 1)

    rollup = store.query_rollup("node-1", 1, "1m", limit=10)
    assert len(rollup) == 1
    bucket = rollup[0]
    assert bucket["bucket_ts_ns"] == base_ts
    assert bucket["sample_count"] == 3
    assert abs(bucket["avg_value"] - 20.0) < 1e-6
    assert abs(bucket["min_value"] - 10.0) < 1e-6
    assert abs(bucket["max_value"] - 30.0) < 1e-6


def test_rollup_is_recomputable_and_idempotent(store: TSDBStore):
    bucket_width_ns = 60_000_000_000
    base_ts = 5 * bucket_width_ns
    store.insert_samples([("node-1", 2, base_ts, base_ts, base_ts, 100.0, "v1")])
    store.recompute_rollups("node-1", 2)
    first = store.query_rollup("node-1", 2, "1m", limit=10)
    store.recompute_rollups("node-1", 2)  # recompute again, should be identical
    second = store.query_rollup("node-1", 2, "1m", limit=10)
    assert first == second


def test_rollup_separates_buckets_across_the_1m_boundary(store: TSDBStore):
    bucket_width_ns = 60_000_000_000
    bucket_a = 5 * bucket_width_ns
    bucket_b = 6 * bucket_width_ns
    store.insert_samples(
        [
            ("node-1", 1, bucket_a, bucket_a, bucket_a, 10.0, "v1"),
            ("node-1", 1, bucket_b, bucket_b, bucket_b, 50.0, "v1"),
        ]
    )
    store.recompute_rollups("node-1", 1)
    rollup = store.query_rollup("node-1", 1, "1m", limit=10)
    assert len(rollup) == 2
    buckets = {b["bucket_ts_ns"]: b for b in rollup}
    assert buckets[bucket_a]["avg_value"] == 10.0
    assert buckets[bucket_b]["avg_value"] == 50.0
