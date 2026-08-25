"""FastAPI REST surface (BUILD_PLAN.md section 14).

`/healthz`, `/api/nodes`, and the metric-series query endpoint prove the
end-to-end vertical slice (Milestone 0). `/api/jobs` orchestrates the
synthetic workload across the fleet (Milestone 3). The straggler report
and timeline endpoints are added in Milestones 4 and 6.

The FastAPI process also owns the asyncio TCP ingestion listener, started
and stopped via the lifespan context so both run on the same event loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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


class StartJobRequest(BaseModel):
    phase_count: int = 1
    sieve_limit: int | None = None


class StartJobResponse(BaseModel):
    job_id: str


@app.post("/api/jobs", status_code=202)
async def start_job(request: StartJobRequest) -> StartJobResponse:
    if not _config.workload_hosts:
        raise HTTPException(status_code=503, detail="no workload hosts configured (WORKLOAD_HOSTS)")
    if request.phase_count < 1:
        raise HTTPException(status_code=400, detail="phase_count must be at least 1")

    # create_job writes the row synchronously, so job_id is immediately
    # queryable via GET /api/jobs/{job_id}; execute_job then runs every
    # phase in the background so this call returns right away.
    job_id = create_job(_store, _config.workload_hosts, request.phase_count)
    asyncio.create_task(
        execute_job(_store, job_id, _config.workload_hosts, request.phase_count, request.sieve_limit)
    )
    return StartJobResponse(job_id=job_id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = _store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job_id: {job_id}")
    job["phase_events"] = _store.list_phase_events(job_id)
    return job
