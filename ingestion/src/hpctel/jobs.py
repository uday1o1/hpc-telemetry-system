"""Synthetic job orchestration (BUILD_PLAN.md section 6, section 11):
dispatches each phase to every configured workload-runner host roughly
concurrently, then waits for all of them to report their PhaseEvent back
over the TCP wire protocol before advancing to the next phase.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

import httpx

from hpctel.storage.tsdb import TSDBStore

logger = logging.getLogger("hpctel.jobs")

_PHASE_DISPATCH_TIMEOUT_S = 10.0
_PHASE_REPORT_TIMEOUT_S = 30.0
_PHASE_REPORT_POLL_INTERVAL_S = 0.2


async def _dispatch_phase(host: str, job_id: str, phase_index: int, sieve_limit: int | None) -> None:
    url = f"http://{host}:9090/start_phase"
    body: dict[str, object] = {"job_id": job_id, "phase_index": phase_index}
    if sieve_limit is not None:
        body["sieve_limit"] = sieve_limit
    try:
        async with httpx.AsyncClient(timeout=_PHASE_DISPATCH_TIMEOUT_S) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("phase_dispatch_failed", extra={"node_id": host, "job_id": job_id})


async def _wait_for_phase_reports(store: TSDBStore, job_id: str, phase_index: int, expected_count: int) -> bool:
    deadline = time.monotonic() + _PHASE_REPORT_TIMEOUT_S
    while time.monotonic() < deadline:
        if store.count_phase_reports(job_id, phase_index) >= expected_count:
            return True
        await asyncio.sleep(_PHASE_REPORT_POLL_INTERVAL_S)
    return store.count_phase_reports(job_id, phase_index) >= expected_count


def create_job(store: TSDBStore, workload_hosts: list[str], phase_count: int) -> str:
    """Synchronously creates the job row and returns its job_id, so the API
    layer can respond to POST /api/jobs with a queryable job_id immediately,
    before the (potentially slow) phase execution begins.
    """
    job_id = str(uuid.uuid4())
    store.create_job(job_id, phase_count, workload_hosts, created_ts_ns=time.time_ns())
    return job_id


async def execute_job(
    store: TSDBStore,
    job_id: str,
    workload_hosts: list[str],
    phase_count: int,
    sieve_limit: int | None = None,
) -> None:
    """Runs every phase of an already-created job to completion or timeout.
    Intended to be scheduled as a background asyncio task by the API layer.
    """
    for phase_index in range(phase_count):
        await asyncio.gather(
            *(_dispatch_phase(host, job_id, phase_index, sieve_limit) for host in workload_hosts)
        )
        all_reported = await _wait_for_phase_reports(store, job_id, phase_index, len(workload_hosts))
        if not all_reported:
            store.set_job_status(job_id, "timed_out")
            logger.warning("job_timed_out", extra={"node_id": "orchestrator", "job_id": job_id})
            return

    store.set_job_status(job_id, "completed")
