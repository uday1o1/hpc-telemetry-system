"""Owned time-series schema (BUILD_PLAN.md section 7 and section 9).

The `samples` table is the raw source of truth and is never overwritten in
place; downsampled rollups (added in Milestone 2) live in separate tables
computed from these raw rows, so a rollup can always be recomputed and
verified against its raw source.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

CREATE_SAMPLES_TABLE = """
CREATE TABLE IF NOT EXISTS samples (
    node_id TEXT NOT NULL,
    metric_id INTEGER NOT NULL,
    ts_ns INTEGER NOT NULL,
    mono_ns INTEGER NOT NULL,
    server_recv_ts_ns INTEGER NOT NULL,
    value REAL NOT NULL,
    producer_version TEXT NOT NULL,
    PRIMARY KEY (node_id, metric_id, ts_ns)
);
"""

CREATE_SAMPLES_NODE_TS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_samples_node_ts ON samples (node_id, ts_ns);
"""

# Downsampled rollups (Milestone 2). Computed from, and always recomputable
# from, the raw `samples` table above; never written to directly by the
# ingestion path. bucket_ts_ns is the bucket's start, floor-aligned to the
# bucket width in nanoseconds (60e9 for 1m, 3600e9 for 1h).
_ROLLUP_TABLE_TEMPLATE = """
CREATE TABLE IF NOT EXISTS {table_name} (
    node_id TEXT NOT NULL,
    metric_id INTEGER NOT NULL,
    bucket_ts_ns INTEGER NOT NULL,
    avg_value REAL NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    PRIMARY KEY (node_id, metric_id, bucket_ts_ns)
);
"""

CREATE_ROLLUP_1M_TABLE = _ROLLUP_TABLE_TEMPLATE.format(table_name="rollup_1m")
CREATE_ROLLUP_1H_TABLE = _ROLLUP_TABLE_TEMPLATE.format(table_name="rollup_1h")

BUCKET_WIDTH_NS_1M = 60_000_000_000
BUCKET_WIDTH_NS_1H = 3_600_000_000_000

ALL_DDL: tuple[str, ...] = (
    CREATE_SAMPLES_TABLE,
    CREATE_SAMPLES_NODE_TS_INDEX,
    CREATE_ROLLUP_1M_TABLE,
    CREATE_ROLLUP_1H_TABLE,
)
