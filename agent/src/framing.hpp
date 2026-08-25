#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace hpctel {

// Wire framing (BUILD_PLAN.md section 7): a 1-byte type tag, a 4-byte
// big-endian length prefix, then exactly `length` bytes of protobuf
// payload. FrameTagSampleBatch and FrameTagPhaseEvent must stay in sync
// with ingestion/src/hpctel/constants.py on the Python side.
enum class FrameTag : uint8_t {
    kSampleBatch = 0x01,
    kPhaseEvent = 0x02,
};

// Serializes one frame (tag + length prefix + payload) ready to write to a
// socket.
std::string EncodeFrame(FrameTag tag, const std::string& payload);

struct DecodedFrame {
    FrameTag tag;
    std::string payload;
};

// Parses exactly one frame from the front of `buffer`. Returns std::nullopt
// if `buffer` does not yet contain a complete frame (caller should read
// more bytes and retry) or if the tag byte is not a recognized FrameTag.
// On success, `consumed` is set to the number of bytes the frame occupied
// in `buffer`, so the caller can erase them and process any following
// frame in the same buffer.
std::optional<DecodedFrame> DecodeFrame(const std::string& buffer, size_t* consumed);

}  // namespace hpctel
