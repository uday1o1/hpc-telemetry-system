#include "sender.hpp"

#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cstring>

#include "framing.hpp"
#include "logging.hpp"
#include "telemetry.pb.h"

namespace hpctel {

namespace {
constexpr uint32_t kSchemaVersion = 1;
constexpr const char* kProducerVersion = "hpctel-agent-0.1";
constexpr size_t kMaxBatchSize = 256;

bool SendAll(int sock_fd, const char* data, size_t length) {
    size_t sent = 0;
    while (sent < length) {
        const ssize_t n = send(sock_fd, data + sent, length - sent, 0);
        if (n <= 0) {
            return false;
        }
        sent += static_cast<size_t>(n);
    }
    return true;
}
}  // namespace

SampleSender::SampleSender(AgentConfig config) : config_(std::move(config)) {}

SampleSender::~SampleSender() { Stop(); }

void SampleSender::Start() {
    if (running_.exchange(true)) {
        return;
    }
    thread_ = std::thread(&SampleSender::RunLoop, this);
}

void SampleSender::Stop() {
    if (!running_.exchange(false)) {
        return;
    }
    queue_cv_.notify_all();
    if (thread_.joinable()) {
        thread_.join();
    }
    Disconnect();
}

void SampleSender::Enqueue(const SampleRecord& record) {
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        if (queue_.size() >= config_.max_queue_size) {
            queue_.pop_front();
            dropped_count_.fetch_add(1);
            LogEvent(LogLevel::kWarn, "queue_overflow", config_.node_id,
                     "dropped oldest queued sample");
        }
        queue_.push_back(record);
    }
    queue_cv_.notify_one();
}

size_t SampleSender::DroppedCount() const { return dropped_count_.load(); }

size_t SampleSender::QueueSizeForTest() const {
    std::lock_guard<std::mutex> lock(queue_mutex_);
    return queue_.size();
}

void SampleSender::RunLoop() {
    const auto interval = std::chrono::milliseconds(config_.sample_interval_ms);
    while (running_.load()) {
        std::vector<SampleRecord> batch;
        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            queue_cv_.wait_for(lock, interval, [this] { return !running_.load(); });
            const size_t take = std::min(queue_.size(), kMaxBatchSize);
            batch.assign(queue_.begin(), queue_.begin() + static_cast<long>(take));
        }
        if (batch.empty()) {
            continue;
        }
        if (!ConnectIfNeeded()) {
            LogEvent(LogLevel::kWarn, "ingest_connect_failed", config_.node_id);
            continue;
        }
        if (SendBatch(batch)) {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            const size_t erase_count = std::min(batch.size(), queue_.size());
            queue_.erase(queue_.begin(), queue_.begin() + static_cast<long>(erase_count));
        } else {
            LogEvent(LogLevel::kWarn, "ingest_send_failed", config_.node_id);
            Disconnect();
        }
    }
}

bool SampleSender::ConnectIfNeeded() {
    if (sock_fd_ >= 0) {
        return true;
    }

    const int sock_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (sock_fd < 0) {
        return false;
    }

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(config_.ingest_port));

    const hostent* resolved = gethostbyname(config_.ingest_host.c_str());
    if (resolved == nullptr || resolved->h_addr_list[0] == nullptr) {
        close(sock_fd);
        return false;
    }
    std::memcpy(&addr.sin_addr, resolved->h_addr_list[0], sizeof(addr.sin_addr));

    if (connect(sock_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        close(sock_fd);
        return false;
    }

    sock_fd_ = sock_fd;
    LogEvent(LogLevel::kInfo, "ingest_connected", config_.node_id);
    return true;
}

void SampleSender::Disconnect() {
    if (sock_fd_ >= 0) {
        close(sock_fd_);
        sock_fd_ = -1;
    }
}

bool SampleSender::SendBatch(const std::vector<SampleRecord>& batch) {
    hpctel::v1::SampleBatch proto_batch;
    proto_batch.set_schema_version(kSchemaVersion);
    proto_batch.set_producer_version(kProducerVersion);
    for (const auto& record : batch) {
        hpctel::v1::Sample* sample = proto_batch.add_samples();
        sample->set_node_id(config_.node_id);
        sample->set_metric_id(record.metric_id);
        sample->set_ts_ns(record.ts_ns);
        sample->set_mono_ns(record.mono_ns);
        sample->set_server_recv_ts_ns(0);
        sample->set_value(record.value);
    }

    std::string payload;
    if (!proto_batch.SerializeToString(&payload)) {
        return false;
    }
    const std::string frame = EncodeFrame(FrameTag::kSampleBatch, payload);
    return SendAll(sock_fd_, frame.data(), frame.size());
}

}  // namespace hpctel
