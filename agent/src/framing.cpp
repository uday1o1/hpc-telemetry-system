#include "framing.hpp"

#include <arpa/inet.h>

#include <cstring>

namespace hpctel {

namespace {
constexpr size_t kHeaderLength = 5;  // 1-byte tag + 4-byte length prefix
}

std::string EncodeFrame(FrameTag tag, const std::string& payload) {
    std::string frame;
    frame.reserve(kHeaderLength + payload.size());
    frame.push_back(static_cast<char>(tag));
    const uint32_t length_be = htonl(static_cast<uint32_t>(payload.size()));
    frame.append(reinterpret_cast<const char*>(&length_be), sizeof(length_be));
    frame.append(payload);
    return frame;
}

std::optional<DecodedFrame> DecodeFrame(const std::string& buffer, size_t* consumed) {
    *consumed = 0;
    if (buffer.size() < kHeaderLength) {
        return std::nullopt;
    }

    const auto raw_tag = static_cast<uint8_t>(buffer[0]);
    if (raw_tag != static_cast<uint8_t>(FrameTag::kSampleBatch) &&
        raw_tag != static_cast<uint8_t>(FrameTag::kPhaseEvent)) {
        return std::nullopt;
    }

    uint32_t length_be = 0;
    std::memcpy(&length_be, buffer.data() + 1, sizeof(length_be));
    const uint32_t length = ntohl(length_be);

    if (buffer.size() < kHeaderLength + length) {
        return std::nullopt;
    }

    DecodedFrame result;
    result.tag = static_cast<FrameTag>(raw_tag);
    result.payload = buffer.substr(kHeaderLength, length);
    *consumed = kHeaderLength + length;
    return result;
}

}  // namespace hpctel
