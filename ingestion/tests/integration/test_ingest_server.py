"""Integration tests: a scripted fake agent client talks to the real
asyncio ingest_server over a real TCP socket. Implements the fault-oracle
table from BUILD_PLAN.md section 12 (transport, parsing, schema, temporal
fault classes) plus their negative controls.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from hpctel._generated.telemetry_pb2 import SampleBatch
from hpctel.ingest_server import run_tcp_server
from hpctel.storage.tsdb import TSDBStore

FRAME_TAG_SAMPLE_BATCH = 0x01


def _encode_sample_batch_frame(
    node_id: str, metric_id: int, ts_ns: int, value: float, schema_version: int = 1
) -> bytes:
    batch = SampleBatch()
    batch.schema_version = schema_version
    batch.producer_version = "fake-agent-test"
    sample = batch.samples.add()
    sample.node_id = node_id
    sample.metric_id = metric_id
    sample.ts_ns = ts_ns
    sample.mono_ns = 0
    sample.server_recv_ts_ns = 0
    sample.value = value
    payload = batch.SerializeToString()
    return bytes([FRAME_TAG_SAMPLE_BATCH]) + len(payload).to_bytes(4, "big") + payload


@pytest.fixture
async def running_server():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = TSDBStore(str(Path(tmp_dir) / "test.sqlite3"))
        server = await run_tcp_server("127.0.0.1", 0, store)
        port = server.sockets[0].getsockname()[1]
        yield "127.0.0.1", port, store
        server.close()
        await server.wait_closed()
        store.close()


async def _connect(host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    return await asyncio.open_connection(host, port)


@pytest.mark.asyncio
async def test_complete_batch_on_healthy_connection_is_accepted(running_server):
    host, port, store = running_server
    _, writer = await _connect(host, port)
    frame = _encode_sample_batch_frame("node-a", 1, time.time_ns(), 42.0)
    writer.write(frame)
    await writer.drain()
    await asyncio.sleep(0.2)  # let the server process
    writer.close()
    await asyncio.sleep(0.1)

    series = store.query_series("node-a", 1, limit=10)
    assert len(series) == 1
    assert series[0]["value"] == 42.0


@pytest.mark.asyncio
async def test_connection_dropped_mid_batch_discards_partial_frame_only(running_server, caplog):
    host, port, store = running_server
    _, writer = await _connect(host, port)
    full_frame = _encode_sample_batch_frame("node-b", 1, time.time_ns(), 1.0)
    # Send a complete header (5 bytes) claiming a payload, but only send
    # part of that payload before closing: "connection dropped mid-batch".
    writer.write(full_frame[:8])
    await writer.drain()
    writer.close()
    await asyncio.sleep(0.2)

    assert any(
        record.reason_code == "partial_frame"
        for record in caplog.records
        if hasattr(record, "reason_code")
    )
    # No sample from the partial batch should have been stored.
    assert store.query_series("node-b", 1, limit=10) == []


@pytest.mark.asyncio
async def test_truncated_header_logs_truncated_frame(running_server, caplog):
    host, port, _store = running_server
    _, writer = await _connect(host, port)
    # Fewer than the 5-byte header length, then disconnect.
    writer.write(b"\x01\x00")
    await writer.drain()
    writer.close()
    await asyncio.sleep(0.2)

    assert any(
        record.reason_code == "truncated_frame"
        for record in caplog.records
        if hasattr(record, "reason_code")
    )


@pytest.mark.asyncio
async def test_unknown_metric_id_dropped_rest_of_batch_processed(running_server):
    host, port, store = running_server
    batch = SampleBatch()
    batch.schema_version = 1
    batch.producer_version = "fake-agent-test"
    known = batch.samples.add()
    known.node_id = "node-c"
    known.metric_id = 1
    known.ts_ns = time.time_ns()
    known.value = 5.0
    unknown = batch.samples.add()
    unknown.node_id = "node-c"
    unknown.metric_id = 9999
    unknown.ts_ns = time.time_ns()
    unknown.value = 1.0
    payload = batch.SerializeToString()
    frame = bytes([FRAME_TAG_SAMPLE_BATCH]) + len(payload).to_bytes(4, "big") + payload

    _, writer = await _connect(host, port)
    writer.write(frame)
    await writer.drain()
    await asyncio.sleep(0.2)
    writer.close()

    series = store.query_series("node-c", 1, limit=10)
    assert len(series) == 1
    assert series[0]["value"] == 5.0


@pytest.mark.asyncio
async def test_schema_version_mismatch_rejects_entire_batch(running_server):
    host, port, store = running_server
    _, writer = await _connect(host, port)
    frame = _encode_sample_batch_frame(
        "node-d", 1, time.time_ns(), 7.0, schema_version=999
    )
    writer.write(frame)
    await writer.drain()
    await asyncio.sleep(0.2)
    writer.close()

    assert store.query_series("node-d", 1, limit=10) == []


@pytest.mark.asyncio
async def test_invalid_timestamp_far_future_dropped(running_server):
    host, port, store = running_server
    far_future_ns = time.time_ns() + 25 * 60 * 60 * 1_000_000_000
    _, writer = await _connect(host, port)
    frame = _encode_sample_batch_frame("node-e", 1, far_future_ns, 3.0)
    writer.write(frame)
    await writer.drain()
    await asyncio.sleep(0.2)
    writer.close()

    assert store.query_series("node-e", 1, limit=10) == []


@pytest.mark.asyncio
async def test_negative_control_recent_timestamp_is_accepted(running_server):
    host, port, store = running_server
    recent_ns = time.time_ns() - 1_000_000_000
    _, writer = await _connect(host, port)
    frame = _encode_sample_batch_frame("node-f", 1, recent_ns, 9.0)
    writer.write(frame)
    await writer.drain()
    await asyncio.sleep(0.2)
    writer.close()

    series = store.query_series("node-f", 1, limit=10)
    assert len(series) == 1
    assert series[0]["value"] == 9.0


@pytest.mark.asyncio
async def test_negative_control_batch_with_only_known_metrics_fully_accepted(running_server):
    host, port, store = running_server
    frame = _encode_sample_batch_frame("node-g", 4, time.time_ns(), 0.75)  # load1
    _, writer = await _connect(host, port)
    writer.write(frame)
    await writer.drain()
    await asyncio.sleep(0.2)
    writer.close()

    series = store.query_series("node-g", 4, limit=10)
    assert len(series) == 1
