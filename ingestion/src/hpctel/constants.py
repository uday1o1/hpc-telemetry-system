"""Canonical metric_id mapping, mirroring proto/telemetry.proto's comment
table and BUILD_PLAN.md section 7. This is the single Python-side source of
truth; the C++ agent's own constants must be kept in exact sync by hand,
since the wire format carries only the integer id, never the name.
"""

from __future__ import annotations

METRIC_ID_TO_NAME: dict[int, str] = {
    1: "cpu_pct",
    2: "mem_used_bytes",
    3: "mem_total_bytes",
    4: "load1",
    5: "iowait_pct",
    6: "disk_read_bytes_s",
    7: "disk_write_bytes_s",
    8: "net_rx_bytes_s",
    9: "net_tx_bytes_s",
    10: "proc_count",
}

METRIC_NAME_TO_ID: dict[str, int] = {name: metric_id for metric_id, name in METRIC_ID_TO_NAME.items()}

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

# Wire framing tags (BUILD_PLAN.md section 7): 1-byte type tag precedes the
# 4-byte big-endian length prefix on every frame.
FRAME_TAG_SAMPLE_BATCH = 0x01
FRAME_TAG_PHASE_EVENT = 0x02
