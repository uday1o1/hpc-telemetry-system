"""Asyncio TCP listener accepting concurrent agent connections and decoding
the length-prefixed protobuf wire protocol (BUILD_PLAN.md section 7).

Milestone 0 scope: decode a SampleBatch frame and write it to the TSDB
store. The full fault-oracle behavior (schema_mismatch, unknown_metric_id,
invalid_timestamp, truncated_frame reason codes and their tests) is built
out in Milestone 2 per BUILD_PLAN.md section 12.
"""

from __future__ import annotations

import asyncio
import logging
import time

from hpctel._generated.telemetry_pb2 import SampleBatch
from hpctel.constants import FRAME_TAG_SAMPLE_BATCH
from hpctel.storage.tsdb import TSDBStore

logger = logging.getLogger("hpctel.ingest_server")

_FRAME_HEADER_LENGTH = 5  # 1-byte tag + 4-byte big-endian length prefix


async def _read_exactly(reader: asyncio.StreamReader, count: int) -> bytes | None:
    try:
        return await reader.readexactly(count)
    except asyncio.IncompleteReadError:
        return None


async def handle_connection(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, store: TSDBStore
) -> None:
    peer = writer.get_extra_info("peername")
    logger.info("agent connected", extra={"node_id": str(peer)})
    try:
        while True:
            header = await _read_exactly(reader, _FRAME_HEADER_LENGTH)
            if header is None:
                break

            tag = header[0]
            length = int.from_bytes(header[1:5], byteorder="big", signed=False)
            payload = await _read_exactly(reader, length)
            if payload is None:
                logger.warning("truncated_frame", extra={"reason_code": "truncated_frame"})
                break

            if tag == FRAME_TAG_SAMPLE_BATCH:
                _handle_sample_batch(payload, store)
            else:
                logger.warning("unknown_frame_tag", extra={"reason_code": "unknown_frame_tag"})
    finally:
        writer.close()
        logger.info("agent disconnected", extra={"node_id": str(peer)})


def _handle_sample_batch(payload: bytes, store: TSDBStore) -> None:
    batch = SampleBatch()
    batch.ParseFromString(payload)
    server_recv_ts_ns = time.time_ns()
    rows = [
        (
            sample.node_id,
            sample.metric_id,
            sample.ts_ns,
            sample.mono_ns,
            server_recv_ts_ns,
            sample.value,
            batch.producer_version,
        )
        for sample in batch.samples
    ]
    inserted = store.insert_samples(rows)
    logger.info(
        "sample_batch_ingested",
        extra={"node_id": rows[0][0] if rows else "unknown"},
    )
    logger.debug("inserted=%d of %d samples", inserted, len(rows))


async def run_tcp_server(host: str, port: int, store: TSDBStore) -> asyncio.AbstractServer:
    server = await asyncio.start_server(
        lambda r, w: handle_connection(r, w, store), host=host, port=port
    )
    logger.info("ingest_tcp_listening", extra={"node_id": f"{host}:{port}"})
    return server
