"""Embedded, write-ahead-logged time-series store backed by SQLite.

Owned schema and access layer (BUILD_PLAN.md section 6, "Storage engine").
A duplicate primary key on insert is an idempotent no-op, matching the
ordering and serialization contract in section 7: a retried batch cannot
corrupt the store.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hpctel.storage.schema import ALL_DDL, BUCKET_WIDTH_NS_1H, BUCKET_WIDTH_NS_1M


class TSDBStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        for statement in ALL_DDL:
            self._conn.execute(statement)
        self._conn.commit()

    def insert_samples(self, rows: list[tuple[str, int, int, int, int, float, str]]) -> int:
        """Insert (node_id, metric_id, ts_ns, mono_ns, server_recv_ts_ns,
        value, producer_version) rows. Returns the number of rows actually
        inserted (duplicates are silently skipped, not counted).
        """
        cursor = self._conn.executemany(
            """
            INSERT OR IGNORE INTO samples
                (node_id, metric_id, ts_ns, mono_ns, server_recv_ts_ns, value, producer_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return cursor.rowcount if cursor.rowcount is not None and cursor.rowcount > 0 else 0

    def list_nodes(self) -> list[dict[str, object]]:
        cursor = self._conn.execute(
            """
            SELECT node_id, MAX(ts_ns) AS last_seen_ts_ns, COUNT(*) AS sample_count
            FROM samples
            GROUP BY node_id
            ORDER BY node_id
            """
        )
        return [
            {"node_id": row[0], "last_seen_ts_ns": row[1], "sample_count": row[2]}
            for row in cursor.fetchall()
        ]

    def query_series(
        self, node_id: str, metric_id: int, limit: int = 100
    ) -> list[dict[str, object]]:
        cursor = self._conn.execute(
            """
            SELECT ts_ns, value
            FROM samples
            WHERE node_id = ? AND metric_id = ?
            ORDER BY ts_ns DESC
            LIMIT ?
            """,
            (node_id, metric_id, limit),
        )
        return [{"ts_ns": row[0], "value": row[1]} for row in cursor.fetchall()]

    def distinct_node_metric_pairs(self) -> list[tuple[str, int]]:
        cursor = self._conn.execute("SELECT DISTINCT node_id, metric_id FROM samples")
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def recompute_rollups(self, node_id: str, metric_id: int) -> None:
        """Recomputes both rollup_1m and rollup_1h for one (node_id,
        metric_id) pair entirely from the raw `samples` table, so a rollup
        can always be verified against (or rebuilt from) its raw source
        (BUILD_PLAN.md section 7).
        """
        for table_name, bucket_width_ns in (
            ("rollup_1m", BUCKET_WIDTH_NS_1M),
            ("rollup_1h", BUCKET_WIDTH_NS_1H),
        ):
            self._conn.execute(
                f"DELETE FROM {table_name} WHERE node_id = ? AND metric_id = ?",
                (node_id, metric_id),
            )
            self._conn.execute(
                f"""
                INSERT INTO {table_name}
                    (node_id, metric_id, bucket_ts_ns, avg_value, min_value, max_value, sample_count)
                SELECT
                    node_id,
                    metric_id,
                    (ts_ns / ?) * ? AS bucket_ts_ns,
                    AVG(value),
                    MIN(value),
                    MAX(value),
                    COUNT(*)
                FROM samples
                WHERE node_id = ? AND metric_id = ?
                GROUP BY bucket_ts_ns
                """,
                (bucket_width_ns, bucket_width_ns, node_id, metric_id),
            )
        self._conn.commit()

    def query_rollup(
        self, node_id: str, metric_id: int, resolution: str, limit: int = 100
    ) -> list[dict[str, object]]:
        table_name = {"1m": "rollup_1m", "1h": "rollup_1h"}[resolution]
        cursor = self._conn.execute(
            f"""
            SELECT bucket_ts_ns, avg_value, min_value, max_value, sample_count
            FROM {table_name}
            WHERE node_id = ? AND metric_id = ?
            ORDER BY bucket_ts_ns DESC
            LIMIT ?
            """,
            (node_id, metric_id, limit),
        )
        return [
            {
                "bucket_ts_ns": row[0],
                "avg_value": row[1],
                "min_value": row[2],
                "max_value": row[3],
                "sample_count": row[4],
            }
            for row in cursor.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
