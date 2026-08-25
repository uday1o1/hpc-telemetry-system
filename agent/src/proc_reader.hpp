#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace hpctel {

// One derived metric reading, ready to become a wire Sample.
// metric_id follows the canonical mapping in proto/telemetry.proto.
struct MetricReading {
    uint32_t metric_id;
    double value;
};

// Reads OS and hardware counters from a Linux /proc hierarchy and derives
// the 10 canonical metrics (BUILD_PLAN.md section 7). Rate-based metrics
// (cpu_pct, iowait_pct, disk_*_bytes_s, net_*_bytes_s) need a delta between
// two samples, so this class keeps internal previous-sample state; the
// first call to Sample() returns only the non-rate metrics (load1,
// mem_used_bytes, mem_total_bytes, proc_count), since no prior sample
// exists yet to derive a rate from.
//
// `proc_root` defaults to "/proc" but can be pointed at a fixture directory
// for deterministic, hardware-independent unit tests (see
// agent/tests/test_proc_reader.cpp).
class ProcReader {
public:
    explicit ProcReader(std::string proc_root = "/proc");

    std::vector<MetricReading> Sample();

    // Individual parsers, exposed for direct unit testing against fixtures.
    // Each returns std::nullopt if the expected file or field is missing or
    // malformed, so a transient read failure can be handled by omitting
    // that metric from the batch rather than crashing the agent.
    struct CpuTicks {
        unsigned long long user = 0;
        unsigned long long nice = 0;
        unsigned long long system = 0;
        unsigned long long idle = 0;
        unsigned long long iowait = 0;
        unsigned long long irq = 0;
        unsigned long long softirq = 0;
        unsigned long long steal = 0;
        unsigned long long Total() const {
            return user + nice + system + idle + iowait + irq + softirq + steal;
        }
    };
    std::optional<CpuTicks> ReadCpuTicks() const;
    std::optional<double> ReadLoad1() const;
    std::optional<std::pair<double, double>> ReadMemUsedAndTotalBytes() const;
    struct DiskCounters {
        unsigned long long sectors_read = 0;
        unsigned long long sectors_written = 0;
    };
    std::optional<DiskCounters> ReadDiskCounters() const;
    struct NetCounters {
        unsigned long long rx_bytes = 0;
        unsigned long long tx_bytes = 0;
    };
    std::optional<NetCounters> ReadNetCounters() const;
    std::optional<int> ReadProcCount() const;

private:
    std::string proc_root_;

    bool has_prior_sample_ = false;
    CpuTicks prior_cpu_ticks_{};
    DiskCounters prior_disk_{};
    NetCounters prior_net_{};
    int64_t prior_mono_ns_ = 0;
};

}  // namespace hpctel
