"""FastAPI micro-service exposing /start_phase, the command endpoint the
ingestion service's job orchestrator calls to run one synthetic job phase
on this node (BUILD_PLAN.md section 6, "Workload runner").
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI
from pydantic import BaseModel

from workloadrunner.compute import run_prime_sieve
from workloadrunner.config import load_config
from workloadrunner.reporter import report_phase_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workloadrunner")

_config = load_config()
app = FastAPI(title="HPC Telemetry System Workload Runner")


class StartPhaseRequest(BaseModel):
    job_id: str
    phase_index: int
    sieve_limit: int | None = None


class StartPhaseResponse(BaseModel):
    node_id: str
    job_id: str
    phase_index: int
    status: str
    phase_start_ts_ns: int
    phase_end_ts_ns: int
    duration_ms: float


def _now_realtime_ns() -> int:
    return time.time_ns()


def _now_monotonic_ns() -> int:
    return time.monotonic_ns()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/start_phase", response_model=StartPhaseResponse)
async def start_phase(request: StartPhaseRequest) -> StartPhaseResponse:
    sieve_limit = request.sieve_limit or _config.default_sieve_limit

    phase_start_ts_ns = _now_realtime_ns()
    phase_start_mono_ns = _now_monotonic_ns()

    status = "ok"
    try:
        # Run the CPU-bound work off the event loop thread so the process
        # stays responsive (e.g. to /healthz) while the phase is running.
        await asyncio.to_thread(run_prime_sieve, sieve_limit)
    except Exception:
        logger.exception("phase_failed", extra={"node_id": _config.node_id, "job_id": request.job_id})
        status = "error"

    phase_end_ts_ns = _now_realtime_ns()
    phase_end_mono_ns = _now_monotonic_ns()

    await report_phase_event(
        host=_config.ingest_host,
        port=_config.ingest_tcp_port,
        job_id=request.job_id,
        node_id=_config.node_id,
        phase_index=request.phase_index,
        phase_start_ts_ns=phase_start_ts_ns,
        phase_start_mono_ns=phase_start_mono_ns,
        phase_end_ts_ns=phase_end_ts_ns,
        phase_end_mono_ns=phase_end_mono_ns,
        status=status,
    )

    return StartPhaseResponse(
        node_id=_config.node_id,
        job_id=request.job_id,
        phase_index=request.phase_index,
        status=status,
        phase_start_ts_ns=phase_start_ts_ns,
        phase_end_ts_ns=phase_end_ts_ns,
        duration_ms=(phase_end_mono_ns - phase_start_mono_ns) / 1e6,
    )
