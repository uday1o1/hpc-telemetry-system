import pytest

from hpctel.constants import FRAME_TAG_PHASE_EVENT, FRAME_TAG_SAMPLE_BATCH
from hpctel.framing import FRAME_HEADER_LENGTH, UnknownFrameTagError, decode_frame


def _encode(tag: int, payload: bytes) -> bytes:
    return bytes([tag]) + len(payload).to_bytes(4, "big") + payload


def test_round_trip_sample_batch():
    frame = _encode(FRAME_TAG_SAMPLE_BATCH, b"hello-payload")
    decoded, consumed = decode_frame(frame)
    assert decoded is not None
    assert decoded.tag == FRAME_TAG_SAMPLE_BATCH
    assert decoded.payload == b"hello-payload"
    assert consumed == len(frame)


def test_round_trip_phase_event():
    frame = _encode(FRAME_TAG_PHASE_EVENT, b"phase-bytes")
    decoded, _consumed = decode_frame(frame)
    assert decoded is not None
    assert decoded.tag == FRAME_TAG_PHASE_EVENT


def test_empty_payload_round_trips():
    frame = _encode(FRAME_TAG_SAMPLE_BATCH, b"")
    decoded, consumed = decode_frame(frame)
    assert decoded is not None
    assert decoded.payload == b""
    assert consumed == FRAME_HEADER_LENGTH


def test_incomplete_header_returns_none():
    frame = _encode(FRAME_TAG_SAMPLE_BATCH, b"payload")
    decoded, consumed = decode_frame(frame[:3])
    assert decoded is None
    assert consumed == 0


def test_incomplete_payload_returns_none():
    frame = _encode(FRAME_TAG_SAMPLE_BATCH, b"0123456789")
    decoded, consumed = decode_frame(frame[:-3])
    assert decoded is None
    assert consumed == 0


def test_unknown_tag_raises():
    frame = bytes([0x7F]) + (1).to_bytes(4, "big") + b"x"
    with pytest.raises(UnknownFrameTagError):
        decode_frame(frame)


def test_two_frames_decode_sequentially():
    frame_a = _encode(FRAME_TAG_SAMPLE_BATCH, b"AAA")
    frame_b = _encode(FRAME_TAG_PHASE_EVENT, b"BB")
    combined = frame_a + frame_b

    decoded_a, consumed_a = decode_frame(combined)
    assert decoded_a is not None
    assert decoded_a.payload == b"AAA"

    decoded_b, _consumed_b = decode_frame(combined[consumed_a:])
    assert decoded_b is not None
    assert decoded_b.tag == FRAME_TAG_PHASE_EVENT
    assert decoded_b.payload == b"BB"
