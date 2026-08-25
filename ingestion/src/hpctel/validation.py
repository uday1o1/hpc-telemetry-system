"""Schema and temporal validation for decoded SampleBatch payloads
(BUILD_PLAN.md section 12, fault and oracle contract).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from hpctel.constants import METRIC_ID_TO_NAME, SUPPORTED_SCHEMA_VERSIONS

_ONE_DAY_NS = 24 * 60 * 60 * 1_000_000_000


@dataclass(frozen=True)
class ValidSample:
    node_id: str
    metric_id: int
    ts_ns: int
    mono_ns: int
    value: float


@dataclass(frozen=True)
class ValidationResult:
    accepted: list[ValidSample]
    dropped_reason_codes: list[str]
    batch_rejected_reason_code: str | None


def validate_batch(
    schema_version: int,
    producer_version: str,
    samples: list[tuple[str, int, int, int, float]],
    now_ns: int | None = None,
) -> ValidationResult:
    """Validates a decoded SampleBatch's fields.

    `samples` is a list of (node_id, metric_id, ts_ns, mono_ns, value)
    tuples, as extracted from the protobuf message.
    """
    del producer_version  # not currently validated, recorded as-is

    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return ValidationResult(
            accepted=[], dropped_reason_codes=[], batch_rejected_reason_code="schema_mismatch"
        )

    if now_ns is None:
        now_ns = time.time_ns()

    accepted: list[ValidSample] = []
    dropped_reason_codes: list[str] = []

    for node_id, metric_id, ts_ns, mono_ns, value in samples:
        if metric_id not in METRIC_ID_TO_NAME:
            dropped_reason_codes.append("unknown_metric_id")
            continue
        if ts_ns < 0 or ts_ns > now_ns + _ONE_DAY_NS:
            dropped_reason_codes.append("invalid_timestamp")
            continue
        accepted.append(
            ValidSample(node_id=node_id, metric_id=metric_id, ts_ns=ts_ns, mono_ns=mono_ns, value=value)
        )

    return ValidationResult(
        accepted=accepted, dropped_reason_codes=dropped_reason_codes, batch_rejected_reason_code=None
    )
