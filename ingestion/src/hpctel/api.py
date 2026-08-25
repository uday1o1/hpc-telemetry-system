"""FastAPI REST surface (BUILD_PLAN.md section 14).

`/healthz`, `/api/nodes`, and the metric-series query endpoint prove the
end-to-end vertical slice (Milestone 0). `/api/jobs` orchestrates the
synthetic workload across the fleet and optionally seeds a fault
(Milestones 3 and 4). `/api/jobs/{id}/straggler_report` computes the
straggler ranking for a completed phase (Milestone 4). The timeline
endpoint is added in Milestone 6.

The FastAPI process also owns the asyncio TCP ingestion listener, started
and stopped via the lifespan context so both run on the same event loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from hpctel.analysis.straggler import rank_stragglers, tag_root_cause
from hpctel.config import load_config
from hpctel.constants import METRIC_NAME_TO_ID
from hpctel.ingest_server import run_tcp_server
from hpctel.jobs import create_job, execute_job
from hpctel.logging_utils import configure_logging
from hpctel.storage.tsdb import TSDBStore

configure_logging()
logger = logging.getLogger("hpctel.api")

_config = load_config()
_store = TSDBStore(_config.db_path)

_ROLLUP_REFRESH_INTERVAL_S = 30.0


async def _refresh_rollups_periodically(store: TSDBStore) -> None:
    while True:
        await asyncio.sleep(_ROLLUP_REFRESH_INTERVAL_S)
        for node_id, metric_id in store.distinct_node_metric_pairs():
            store.recompute_rollups(node_id, metric_id)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    tcp_server = await run_tcp_server(_config.tcp_host, _config.tcp_port, _store)
    rollup_task = asyncio.create_task(_refresh_rollups_periodically(_store))
    try:
        yield
    finally:
        rollup_task.cancel()
        tcp_server.close()
        await tcp_server.wait_closed()
        _store.close()


app = FastAPI(title="HPC Telemetry System", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/nodes")
def list_nodes() -> list[dict[str, object]]:
    return _store.list_nodes()


@app.get("/api/metrics/{node_id}/{metric_name}")
def get_metric_series(
    node_id: str, metric_name: str, limit: int = 100, resolution: str = "raw"
) -> list[dict[str, object]]:
    metric_id = METRIC_NAME_TO_ID.get(metric_name)
    if metric_id is None:
        raise HTTPException(status_code=404, detail=f"unknown metric_name: {metric_name}")
    if resolution == "raw":
        return _store.query_series(node_id, metric_id, limit=limit)
    if resolution in ("1m", "1h"):
        return _store.query_rollup(node_id, metric_id, resolution, limit=limit)
    raise HTTPException(status_code=400, detail=f"unknown resolution: {resolution}")


class FaultManifestRequest(BaseModel):
    target_host: str
    phase_index: int
    fault_type: str
    intensity: int = 2


class StartJobRequest(BaseModel):
    phase_count: int = 1
    sieve_limit: int | None = None
    fault: FaultManifestRequest | None = None


class StartJobResponse(BaseModel):
    job_id: str


@app.post("/api/jobs", status_code=202)
async def start_job(request: StartJobRequest) -> StartJobResponse:
    if not _config.workload_hosts:
        raise HTTPException(status_code=503, detail="no workload hosts configured (WORKLOAD_HOSTS)")
    if request.phase_count < 1:
        raise HTTPException(status_code=400, detail="phase_count must be at least 1")
    if request.fault is not None and request.fault.target_host not in _config.workload_hosts:
        raise HTTPException(status_code=400, detail=f"unknown target_host: {request.fault.target_host}")

    fault_manifest = request.fault.model_dump() if request.fault is not None else None

    # create_job writes the row synchronously, so job_id is immediately
    # queryable via GET /api/jobs/{job_id}; execute_job then runs every
    # phase in the background so this call returns right away.
    job_id = create_job(_store, _config.workload_hosts, request.phase_count, fault_manifest)
    asyncio.create_task(
        execute_job(
            _store,
            job_id,
            _config.workload_hosts,
            request.phase_count,
            request.sieve_limit,
            fault_manifest,
        )
    )
    return StartJobResponse(job_id=job_id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = _store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job_id: {job_id}")
    job["phase_events"] = _store.list_phase_events(job_id)
    return job


_ROOT_CAUSE_BASELINE_WINDOW_NS = 30_000_000_000  # 30s pre-phase baseline window
_ROOT_CAUSE_SEARCH_RADIUS_NS = 3_000_000_000  # nearest-sample search radius during the phase


def _nearest_sample_value(node_id: str, metric_id: int, target_ts_ns: int) -> float | None:
    series = _store.query_series(node_id, metric_id, limit=50)
    candidates = [s for s in series if abs(s["ts_ns"] - target_ts_ns) <= _ROOT_CAUSE_SEARCH_RADIUS_NS]
    if not candidates:
        return None
    nearest = min(candidates, key=lambda s: abs(s["ts_ns"] - target_ts_ns))
    return float(nearest["value"])


def _baseline_mean_value(node_id: str, metric_id: int, phase_start_ts_ns: int) -> float | None:
    series = _store.query_series(node_id, metric_id, limit=200)
    window = [
        s["value"]
        for s in series
        if phase_start_ts_ns - _ROOT_CAUSE_BASELINE_WINDOW_NS <= s["ts_ns"] < phase_start_ts_ns
    ]
    if not window:
        return None
    return sum(window) / len(window)


def _relative_delta(baseline: float | None, during: float | None) -> float | None:
    if baseline is None or during is None:
        return None
    if baseline == 0:
        return None if during == 0 else float("inf")
    return (during - baseline) / abs(baseline)


@app.get("/api/jobs/{job_id}/straggler_report")
def get_straggler_report(job_id: str, phase_index: int = 0) -> dict[str, object]:
    job = _store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job_id: {job_id}")

    events = _store.list_phase_events(job_id, phase_index=phase_index)
    durations_ns = {
        e["node_id"]: e["phase_end_mono_ns"] - e["phase_start_mono_ns"] for e in events if e["status"] == "ok"
    }
    report = rank_stragglers(job_id, phase_index, durations_ns)

    root_cause = None
    if report.top_candidate is not None:
        top_event = next(e for e in events if e["node_id"] == report.top_candidate)
        phase_start_ts_ns = top_event["phase_start_ts_ns"]
        phase_mid_ts_ns = (top_event["phase_start_ts_ns"] + top_event["phase_end_ts_ns"]) // 2

        cpu_delta = _relative_delta(
            _baseline_mean_value(report.top_candidate, METRIC_NAME_TO_ID["cpu_pct"], phase_start_ts_ns),
            _nearest_sample_value(report.top_candidate, METRIC_NAME_TO_ID["cpu_pct"], phase_mid_ts_ns),
        )
        iowait_delta = _relative_delta(
            _baseline_mean_value(report.top_candidate, METRIC_NAME_TO_ID["iowait_pct"], phase_start_ts_ns),
            _nearest_sample_value(report.top_candidate, METRIC_NAME_TO_ID["iowait_pct"], phase_mid_ts_ns),
        )
        net_rx_delta = _relative_delta(
            _baseline_mean_value(report.top_candidate, METRIC_NAME_TO_ID["net_rx_bytes_s"], phase_start_ts_ns),
            _nearest_sample_value(report.top_candidate, METRIC_NAME_TO_ID["net_rx_bytes_s"], phase_mid_ts_ns),
        )
        root_cause = tag_root_cause(cpu_delta, iowait_delta, net_rx_delta)

    result = asdict(report)
    result["root_cause"] = root_cause
    return result
