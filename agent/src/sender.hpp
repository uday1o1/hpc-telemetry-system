#pragma once

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "config.hpp"

namespace hpctel {

struct SampleRecord {
    uint32_t metric_id;
    int64_t ts_ns;
    int64_t mono_ns;
    double value;
};

// Owns a background thread that batches queued samples, frames them as a
// protobuf SampleBatch (BUILD_PLAN.md section 7), and streams them to the
// ingestion service over TCP, reconnecting on failure.
//
// Backpressure policy (BUILD_PLAN.md section 6): Enqueue() never blocks the
// caller (the sampling loop). If the internal queue is full, the oldest
// queued record is dropped to make room and a queue_overflow event is
// logged; the sampling loop's cadence is never slowed down by a stalled or
// disconnected ingestion service.
class SampleSender {
public:
    explicit SampleSender(AgentConfig config);
    ~SampleSender();

    SampleSender(const SampleSender&) = delete;
    SampleSender& operator=(const SampleSender&) = delete;

    void Start();
    void Stop();

    void Enqueue(const SampleRecord& record);

    size_t DroppedCount() const;
    size_t QueueSizeForTest() const;

private:
    void RunLoop();
    bool ConnectIfNeeded();
    void Disconnect();
    bool SendBatch(const std::vector<SampleRecord>& batch);

    AgentConfig config_;
    std::thread thread_;
    std::atomic<bool> running_{false};

    mutable std::mutex queue_mutex_;
    std::condition_variable queue_cv_;
    std::deque<SampleRecord> queue_;
    std::atomic<size_t> dropped_count_{0};

    int sock_fd_ = -1;
};

}  // namespace hpctel
