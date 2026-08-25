"""Asyncio TCP listener accepting concurrent agent connections and decoding
the length-prefixed protobuf wire protocol (BUILD_PLAN.md section 7),
implementing the full fault-oracle contract from section 12.
"""

from __future__ import annotations

import asyncio
import logging
import time

from hpctel._generated.telemetry_pb2 import SampleBatch
from hpctel.constants import FRAME_TAG_SAMPLE_BATCH
from hpctel.framing import FRAME_HEADER_LENGTH, UnknownFrameTagError, decode_frame
from hpctel.storage.tsdb import TSDBStore
from hpctel.validation import validate_batch

logger = logging.getLogger("hpctel.ingest_server")

_READ_CHUNK_SIZE = 65536


async def handle_connection(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, store: TSDBStore
) -> None:
    peer = writer.get_extra_info("peername")
    logger.info("agent_connected", extra={"node_id": str(peer)})

    buffer = bytearray()
    try:
        while True:
            chunk = await reader.read(_READ_CHUNK_SIZE)
            if not chunk:
                # Clean EOF. If we were mid-frame, this is a genuine fault;
                # if the buffer is empty, it's just a normal disconnect.
                if len(buffer) >= FRAME_HEADER_LENGTH:
                    logger.warning(
                        "partial_frame", extra={"reason_code": "partial_frame", "node_id": str(peer)}
                    )
                elif len(buffer) > 0:
                    logger.warning(
                        "truncated_frame",
                        extra={"reason_code": "truncated_frame", "node_id": str(peer)},
                    )
                break

            buffer.extend(chunk)
            _drain_frames(buffer, store, peer)
    finally:
        writer.close()
        logger.info("agent_disconnected", extra={"node_id": str(peer)})


def _drain_frames(buffer: bytearray, store: TSDBStore, peer: object) -> None:
    while True:
        try:
            frame, consumed = decode_frame(bytes(buffer))
        except UnknownFrameTagError:
            logger.warning(
                "unknown_frame_tag", extra={"reason_code": "unknown_frame_tag", "node_id": str(peer)}
            )
            # A corrupted tag byte desynchronizes the stream; there is no
            # safe resync point, so the connection is dropped rather than
            # risk misinterpreting an arbitrary byte as a new header.
            buffer.clear()
            return
        if frame is None:
            return
        del buffer[:consumed]
        if frame.tag == FRAME_TAG_SAMPLE_BATCH:
            _handle_sample_batch(frame.payload, store)
        # PhaseEvent handling is added in Milestone 3.


def _handle_sample_batch(payload: bytes, store: TSDBStore) -> None:
    batch = SampleBatch()
    batch.ParseFromString(payload)

    samples = [
        (s.node_id, s.metric_id, s.ts_ns, s.mono_ns, s.value) for s in batch.samples
    ]
    result = validate_batch(batch.schema_version, batch.producer_version, samples)

    if result.batch_rejected_reason_code is not None:
        logger.warning(
            "batch_rejected",
            extra={"reason_code": result.batch_rejected_reason_code},
        )
        return

    for reason_code in result.dropped_reason_codes:
        logger.warning("sample_dropped", extra={"reason_code": reason_code})

    if not result.accepted:
        return

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
        for sample in result.accepted
    ]
    store.insert_samples(rows)
    logger.info("sample_batch_ingested", extra={"node_id": rows[0][0]})


async def run_tcp_server(host: str, port: int, store: TSDBStore) -> asyncio.AbstractServer:
    server = await asyncio.start_server(
        lambda r, w: handle_connection(r, w, store), host=host, port=port
    )
    logger.info("ingest_tcp_listening", extra={"node_id": f"{host}:{port}"})
    return server
