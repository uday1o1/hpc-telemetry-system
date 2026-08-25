#include "framing.hpp"

#include <gtest/gtest.h>

TEST(Framing, RoundTripSampleBatchTag) {
    const std::string payload = "hello-protobuf-payload";
    const std::string frame = hpctel::EncodeFrame(hpctel::FrameTag::kSampleBatch, payload);

    size_t consumed = 0;
    const auto decoded = hpctel::DecodeFrame(frame, &consumed);
    ASSERT_TRUE(decoded.has_value());
    EXPECT_EQ(decoded->tag, hpctel::FrameTag::kSampleBatch);
    EXPECT_EQ(decoded->payload, payload);
    EXPECT_EQ(consumed, frame.size());
}

TEST(Framing, RoundTripPhaseEventTag) {
    const std::string payload = "phase-event-bytes";
    const std::string frame = hpctel::EncodeFrame(hpctel::FrameTag::kPhaseEvent, payload);

    size_t consumed = 0;
    const auto decoded = hpctel::DecodeFrame(frame, &consumed);
    ASSERT_TRUE(decoded.has_value());
    EXPECT_EQ(decoded->tag, hpctel::FrameTag::kPhaseEvent);
    EXPECT_EQ(decoded->payload, payload);
}

TEST(Framing, EmptyPayloadRoundTrips) {
    const std::string frame = hpctel::EncodeFrame(hpctel::FrameTag::kSampleBatch, "");
    size_t consumed = 0;
    const auto decoded = hpctel::DecodeFrame(frame, &consumed);
    ASSERT_TRUE(decoded.has_value());
    EXPECT_TRUE(decoded->payload.empty());
    EXPECT_EQ(consumed, 5u);  // header only
}

TEST(Framing, TruncatedHeaderReturnsNulloptAndConsumesNothing) {
    const std::string frame = hpctel::EncodeFrame(hpctel::FrameTag::kSampleBatch, "payload");
    const std::string truncated = frame.substr(0, 3);  // less than the 5-byte header
    size_t consumed = 0;
    const auto decoded = hpctel::DecodeFrame(truncated, &consumed);
    EXPECT_FALSE(decoded.has_value());
    EXPECT_EQ(consumed, 0u);
}

TEST(Framing, TruncatedPayloadReturnsNullopt) {
    const std::string frame = hpctel::EncodeFrame(hpctel::FrameTag::kSampleBatch, "0123456789");
    const std::string truncated = frame.substr(0, frame.size() - 3);  // header claims 10 bytes, only 7 present
    size_t consumed = 0;
    const auto decoded = hpctel::DecodeFrame(truncated, &consumed);
    EXPECT_FALSE(decoded.has_value());
    EXPECT_EQ(consumed, 0u);
}

TEST(Framing, UnknownTagByteIsRejected) {
    std::string frame = hpctel::EncodeFrame(hpctel::FrameTag::kSampleBatch, "x");
    frame[0] = static_cast<char>(0x7F);  // not a recognized FrameTag
    size_t consumed = 0;
    const auto decoded = hpctel::DecodeFrame(frame, &consumed);
    EXPECT_FALSE(decoded.has_value());
    EXPECT_EQ(consumed, 0u);
}

TEST(Framing, TwoFramesBackToBackDecodeSequentially) {
    const std::string frame_a = hpctel::EncodeFrame(hpctel::FrameTag::kSampleBatch, "AAA");
    const std::string frame_b = hpctel::EncodeFrame(hpctel::FrameTag::kPhaseEvent, "BB");
    const std::string combined = frame_a + frame_b;

    size_t consumed_a = 0;
    const auto decoded_a = hpctel::DecodeFrame(combined, &consumed_a);
    ASSERT_TRUE(decoded_a.has_value());
    EXPECT_EQ(decoded_a->payload, "AAA");

    const std::string remainder = combined.substr(consumed_a);
    size_t consumed_b = 0;
    const auto decoded_b = hpctel::DecodeFrame(remainder, &consumed_b);
    ASSERT_TRUE(decoded_b.has_value());
    EXPECT_EQ(decoded_b->tag, hpctel::FrameTag::kPhaseEvent);
    EXPECT_EQ(decoded_b->payload, "BB");
}
