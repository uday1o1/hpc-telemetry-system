"""Integration test for job orchestration (BUILD_PLAN.md section 16,
Milestone 3): starts a job across N fake workload-runner hosts and asserts
all N report a phase-end event within a bounded time window.

Uses three fake workload hosts, each bound to 127.0.0.1 on its own port
(mirroring how the real 8-node docker-compose rack gives each
workload-runner container its own hostname on port 9090, just keyed by
port instead of address since macOS does not auto-bind loopback aliases
beyond 127.0.0.1 the way Linux does). This proves the orchestration and
wait-for-reports logic at unit-test speed; the real 8-node rack is
verified separately via `docker compose up` as the closest real
user-path check for this milestone.
"""

from __future__ import annotations

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hpctel._generated.telemetry_pb2 import PhaseEvent
from hpctel.ingest_server import run_tcp_server
from hpctel.jobs import create_job, execute_job
from hpctel.storage.tsdb import TSDBStore

# Logical "hosts" for the orchestrator, each mapped to its own port on
# 127.0.0.1 (see module docstring for why we key by port, not address).
_FAKE_HOSTS = ["fake-0", "fake-1", "fake-2"]
_FAKE_HOST_PORTS = {"fake-0": 19090, "fake-1": 19091, "fake-2": 19092}


def _send_phase_event_sync(ingest_port: int, node_id: str, job_id: str, phase_index: int) -> None:
    import socket
    import time as time_module

    event = PhaseEvent()
    event.job_id = job_id
    event.node_id = node_id
    event.phase_index = phase_index
    event.phase_start_ts_ns = time_module.time_ns()
    event.phase_start_mono_ns = time_module.monotonic_ns()
    event.phase_end_ts_ns = time_module.time_ns()
    event.phase_end_mono_ns = time_module.monotonic_ns()
    event.status = "ok"

    payload = event.SerializeToString()
    frame = bytes([0x02]) + len(payload).to_bytes(4, "big") + payload

    with socket.create_connection(("127.0.0.1", ingest_port), timeout=5.0) as sock:
        sock.sendall(frame)


def _make_fake_workload_handler(node_id: str, ingest_port: int) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length)) if length else {}
            _send_phase_event_sync(ingest_port, node_id, body["job_id"], body["phase_index"])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        def log_message(self, format: str, *args: object) -> None:
            pass  # silence request logging during tests

    return Handler


@pytest.fixture
async def rack():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = TSDBStore(str(Path(tmp_dir) / "test.sqlite3"))
        tcp_server = await run_tcp_server("127.0.0.1", 0, store)
        ingest_port = tcp_server.sockets[0].getsockname()[1]

        http_servers = []
        threads = []
        for host in _FAKE_HOSTS:
            handler_cls = _make_fake_workload_handler(f"fake-node-{host}", ingest_port)
            server = ThreadingHTTPServer(("127.0.0.1", _FAKE_HOST_PORTS[host]), handler_cls)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            http_servers.append(server)
            threads.append(thread)

        yield store, ingest_port

        for server in http_servers:
            server.shutdown()
        tcp_server.close()
        await tcp_server.wait_closed()
        store.close()


@pytest.mark.asyncio
async def test_job_across_all_fake_nodes_reports_within_bounded_window(rack, monkeypatch):
    store, _ingest_port = rack

    # jobs.py hardcodes port 9090 for real workload runners; point it at
    # this test's fake-host port instead.
    import hpctel.jobs as jobs_module

    monkeypatch.setattr(jobs_module, "_dispatch_phase", _dispatch_phase_override)

    job_id = create_job(store, _FAKE_HOSTS, phase_count=1)
    await execute_job(store, job_id, _FAKE_HOSTS, phase_count=1)

    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"

    events = store.list_phase_events(job_id, phase_index=0)
    assert len(events) == len(_FAKE_HOSTS)
    assert {e["status"] for e in events} == {"ok"}


async def _dispatch_phase_override(host: str, job_id: str, phase_index: int, sieve_limit: object, fault: object = None) -> None:
    import httpx

    url = f"http://127.0.0.1:{_FAKE_HOST_PORTS[host]}/start_phase"
    body = {"job_id": job_id, "phase_index": phase_index}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()


@pytest.mark.asyncio
async def test_job_times_out_when_a_node_never_reports(rack, monkeypatch):
    store, _ingest_port = rack
    import hpctel.jobs as jobs_module

    monkeypatch.setattr(jobs_module, "_PHASE_REPORT_TIMEOUT_S", 0.5)
    monkeypatch.setattr(jobs_module, "_PHASE_REPORT_POLL_INTERVAL_S", 0.05)

    async def _dispatch_phase_noop(host: str, job_id: str, phase_index: int, sieve_limit, fault=None) -> None:
        return None  # simulates a node that never calls back

    monkeypatch.setattr(jobs_module, "_dispatch_phase", _dispatch_phase_noop)

    job_id = create_job(store, _FAKE_HOSTS, phase_count=1)
    await execute_job(store, job_id, _FAKE_HOSTS, phase_count=1)

    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "timed_out"
