"""Reports a completed phase to the ingestion service over the same
length-prefixed protobuf wire protocol used by the C++ agent
(BUILD_PLAN.md section 7).
"""

from __future__ import annotations

import asyncio

from workloadrunner._generated.telemetry_pb2 import PhaseEvent

_FRAME_TAG_PHASE_EVENT = 0x02


async def report_phase_event(
    host: str,
    port: int,
    job_id: str,
    node_id: str,
    phase_index: int,
    phase_start_ts_ns: int,
    phase_start_mono_ns: int,
    phase_end_ts_ns: int,
    phase_end_mono_ns: int,
    status: str,
) -> None:
    event = PhaseEvent()
    event.job_id = job_id
    event.node_id = node_id
    event.phase_index = phase_index
    event.phase_start_ts_ns = phase_start_ts_ns
    event.phase_start_mono_ns = phase_start_mono_ns
    event.phase_end_ts_ns = phase_end_ts_ns
    event.phase_end_mono_ns = phase_end_mono_ns
    event.status = status

    payload = event.SerializeToString()
    frame = bytes([_FRAME_TAG_PHASE_EVENT]) + len(payload).to_bytes(4, "big") + payload

    _reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(frame)
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
