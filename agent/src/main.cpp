#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "telemetry.pb.h"

// Milestone 0 feasibility spike (see BUILD_PLAN.md section 16, Milestone 0).
// Proves the C++ toolchain builds inside the Linux container image, reads
// one real value from /proc/stat, serializes it as a protobuf SampleBatch,
// frames it with the 1-byte type tag + 4-byte big-endian length prefix
// described in BUILD_PLAN.md section 7, and delivers it over TCP to the
// ingestion service. This is a one-shot spike, not the agent's final
// design: the full multi-metric parser, batching, background sender
// thread, bounded queue, and structured logging are built out in
// Milestone 1, with this file replaced by the modular
// proc_reader/framing/sender/config/logging components.

namespace {

constexpr uint8_t kSampleBatchTag = 0x01;
constexpr uint32_t kSchemaVersion = 1;
constexpr uint32_t kMetricIdCpuPct = 1;  // see proto/telemetry.proto mapping table

std::string EnvOr(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return value != nullptr ? std::string(value) : fallback;
}

int64_t NowRealtimeNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

int64_t NowMonotonicNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

// Reads the raw cpu user-mode tick count from /proc/stat's first line.
// This is a stand-in raw reading for the M0 wiring proof, not the final
// cpu_pct derivation (a percentage requires a delta between two samples
// over elapsed time, implemented properly in Milestone 1).
bool ReadProcStatUserTicks(double* out_value) {
    std::ifstream stat_file("/proc/stat");
    if (!stat_file.is_open()) {
        return false;
    }
    std::string first_line;
    if (!std::getline(stat_file, first_line)) {
        return false;
    }
    std::istringstream line_stream(first_line);
    std::string label;
    unsigned long long user_ticks = 0;
    line_stream >> label >> user_ticks;
    if (label != "cpu") {
        return false;
    }
    *out_value = static_cast<double>(user_ticks);
    return true;
}

bool SendAll(int sock_fd, const char* data, size_t length) {
    size_t sent = 0;
    while (sent < length) {
        ssize_t n = send(sock_fd, data + sent, length - sent, 0);
        if (n <= 0) {
            return false;
        }
        sent += static_cast<size_t>(n);
    }
    return true;
}

}  // namespace

int main() {
    const std::string node_id = EnvOr("NODE_ID", "node-unknown");
    const std::string ingest_host = EnvOr("INGEST_HOST", "127.0.0.1");
    const int ingest_port = std::stoi(EnvOr("INGEST_PORT", "7070"));

    double raw_value = 0.0;
    if (!ReadProcStatUserTicks(&raw_value)) {
        std::cerr << "hpctel_agent: failed to read /proc/stat" << std::endl;
        return 1;
    }

    hpctel::v1::SampleBatch batch;
    batch.set_schema_version(kSchemaVersion);
    batch.set_producer_version("milestone-0-spike");

    hpctel::v1::Sample* sample = batch.add_samples();
    sample->set_node_id(node_id);
    sample->set_metric_id(kMetricIdCpuPct);
    sample->set_ts_ns(NowRealtimeNs());
    sample->set_mono_ns(NowMonotonicNs());
    sample->set_server_recv_ts_ns(0);
    sample->set_value(raw_value);

    std::string payload;
    if (!batch.SerializeToString(&payload)) {
        std::cerr << "hpctel_agent: failed to serialize batch" << std::endl;
        return 1;
    }

    const int sock_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (sock_fd < 0) {
        std::cerr << "hpctel_agent: failed to create socket" << std::endl;
        return 1;
    }

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(ingest_port));

    const hostent* resolved = gethostbyname(ingest_host.c_str());
    if (resolved == nullptr || resolved->h_addr_list[0] == nullptr) {
        std::cerr << "hpctel_agent: failed to resolve " << ingest_host << std::endl;
        close(sock_fd);
        return 1;
    }
    std::memcpy(&addr.sin_addr, resolved->h_addr_list[0], sizeof(addr.sin_addr));

    if (connect(sock_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::cerr << "hpctel_agent: failed to connect to " << ingest_host << ":" << ingest_port << std::endl;
        close(sock_fd);
        return 1;
    }

    const uint32_t length_be = htonl(static_cast<uint32_t>(payload.size()));
    std::string frame;
    frame.push_back(static_cast<char>(kSampleBatchTag));
    frame.append(reinterpret_cast<const char*>(&length_be), sizeof(length_be));
    frame.append(payload);

    if (!SendAll(sock_fd, frame.data(), frame.size())) {
        std::cerr << "hpctel_agent: failed to send frame" << std::endl;
        close(sock_fd);
        return 1;
    }

    std::cout << "hpctel_agent: sent 1 sample (node_id=" << node_id
              << ", metric_id=" << kMetricIdCpuPct << ", value=" << raw_value
              << ") to " << ingest_host << ":" << ingest_port << std::endl;

    close(sock_fd);
    return 0;
}
