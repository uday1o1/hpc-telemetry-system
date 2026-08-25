"""Unit test for fault targeting in jobs.execute_job: the fault manifest
must be attached only to the dispatch call for its target_host and
phase_index, never to any other host or phase (BUILD_PLAN.md section 11).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from hpctel.jobs import create_job, execute_job
from hpctel.storage.tsdb import TSDBStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        s = TSDBStore(str(Path(tmp_dir) / "test.sqlite3"))
        yield s
        s.close()


@pytest.mark.asyncio
async def test_fault_only_dispatched_to_target_host_and_phase(store, monkeypatch):
    import hpctel.jobs as jobs_module

    calls = []

    async def fake_dispatch(host, job_id, phase_index, sieve_limit, fault=None):
        calls.append((host, phase_index, fault))

    monkeypatch.setattr(jobs_module, "_dispatch_phase", fake_dispatch)
    monkeypatch.setattr(
        jobs_module, "_wait_for_phase_reports", AsyncMock(return_value=True)
    )

    hosts = ["node-a", "node-b", "node-c"]
    fault_manifest = {
        "target_host": "node-b",
        "phase_index": 1,
        "fault_type": "cpu_contention",
        "intensity": 3,
    }

    job_id = create_job(store, hosts, phase_count=2, fault_manifest=fault_manifest)
    await execute_job(store, job_id, hosts, phase_count=2, fault_manifest=fault_manifest)

    faulted_calls = [c for c in calls if c[2] is not None]
    assert len(faulted_calls) == 1
    host, phase_index, fault = faulted_calls[0]
    assert host == "node-b"
    assert phase_index == 1
    assert fault == {"fault_type": "cpu_contention", "intensity": 3}

    # Every other (host, phase) combination got no fault.
    unfaulted_calls = [c for c in calls if c[2] is None]
    assert len(unfaulted_calls) == len(hosts) * 2 - 1


@pytest.mark.asyncio
async def test_no_fault_manifest_means_no_host_ever_faulted(store, monkeypatch):
    import hpctel.jobs as jobs_module

    calls = []

    async def fake_dispatch(host, job_id, phase_index, sieve_limit, fault=None):
        calls.append(fault)

    monkeypatch.setattr(jobs_module, "_dispatch_phase", fake_dispatch)
    monkeypatch.setattr(
        jobs_module, "_wait_for_phase_reports", AsyncMock(return_value=True)
    )

    hosts = ["node-a", "node-b"]
    job_id = create_job(store, hosts, phase_count=1)
    await execute_job(store, job_id, hosts, phase_count=1)

    assert all(fault is None for fault in calls)
