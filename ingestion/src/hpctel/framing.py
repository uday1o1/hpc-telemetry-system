"""Pure, socket-free frame parsing (BUILD_PLAN.md section 7 and section 12).

Kept separate from the asyncio connection loop in ingest_server.py so the
parsing logic itself is directly unit-testable without a real socket, and
so the fault-oracle reason codes in section 12 map onto distinct, testable
code paths.
"""

from __future__ import annotations

from dataclasses import dataclass

from hpctel.constants import FRAME_TAG_PHASE_EVENT, FRAME_TAG_SAMPLE_BATCH

FRAME_HEADER_LENGTH = 5  # 1-byte tag + 4-byte big-endian length prefix
_KNOWN_TAGS = frozenset({FRAME_TAG_SAMPLE_BATCH, FRAME_TAG_PHASE_EVENT})


class UnknownFrameTagError(Exception):
    """Raised when a frame's tag byte is not a recognized FrameTag."""

    reason_code = "unknown_frame_tag"


@dataclass(frozen=True)
class DecodedFrame:
    tag: int
    payload: bytes


def decode_frame(buffer: bytes) -> tuple[DecodedFrame | None, int]:
    """Attempts to decode exactly one frame from the front of `buffer`.

    Returns (None, 0) if `buffer` does not yet contain a complete frame; the
    caller should read more bytes and retry. Returns (frame, bytes_consumed)
    on success. Raises UnknownFrameTagError if the tag byte is decodable
    (buffer is at least 1 byte) but not a recognized FrameTag.
    """
    if len(buffer) < 1:
        return None, 0
    tag = buffer[0]
    if tag not in _KNOWN_TAGS:
        raise UnknownFrameTagError()
    if len(buffer) < FRAME_HEADER_LENGTH:
        return None, 0
    length = int.from_bytes(buffer[1:FRAME_HEADER_LENGTH], byteorder="big", signed=False)
    total = FRAME_HEADER_LENGTH + length
    if len(buffer) < total:
        return None, 0
    payload = bytes(buffer[FRAME_HEADER_LENGTH:total])
    return DecodedFrame(tag=tag, payload=payload), total
