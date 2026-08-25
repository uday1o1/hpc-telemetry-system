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

ALL_DDL: tuple[str, ...] = (
    CREATE_SAMPLES_TABLE,
    CREATE_SAMPLES_NODE_TS_INDEX,
)
