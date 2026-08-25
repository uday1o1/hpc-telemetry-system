#include "proc_reader.hpp"

#include <dirent.h>

#include <chrono>
#include <cctype>
#include <fstream>
#include <sstream>

namespace hpctel {

namespace {

// Canonical metric_id values (proto/telemetry.proto).
constexpr uint32_t kMetricCpuPct = 1;
constexpr uint32_t kMetricMemUsedBytes = 2;
constexpr uint32_t kMetricMemTotalBytes = 3;
constexpr uint32_t kMetricLoad1 = 4;
constexpr uint32_t kMetricIowaitPct = 5;
constexpr uint32_t kMetricDiskReadBytesS = 6;
constexpr uint32_t kMetricDiskWriteBytesS = 7;
constexpr uint32_t kMetricNetRxBytesS = 8;
constexpr uint32_t kMetricNetTxBytesS = 9;
constexpr uint32_t kMetricProcCount = 10;

constexpr double kSectorBytes = 512.0;

int64_t NowMonotonicNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

bool IsAllDigits(const std::string& s) {
    if (s.empty()) {
        return false;
    }
    for (char c : s) {
        if (!std::isdigit(static_cast<unsigned char>(c))) {
            return false;
        }
    }
    return true;
}

}  // namespace

ProcReader::ProcReader(std::string proc_root) : proc_root_(std::move(proc_root)) {}

std::optional<ProcReader::CpuTicks> ProcReader::ReadCpuTicks() const {
    std::ifstream file(proc_root_ + "/stat");
    if (!file.is_open()) {
        return std::nullopt;
    }
    std::string first_line;
    if (!std::getline(file, first_line)) {
        return std::nullopt;
    }
    std::istringstream stream(first_line);
    std::string label;
    stream >> label;
    if (label != "cpu") {
        return std::nullopt;
    }
    CpuTicks ticks;
    // Field order per `man proc`: user nice system idle iowait irq softirq
    // steal guest guest_nice. We only need the first 8; a short line (older
    // kernels) still yields valid zero-initialized trailing fields.
    stream >> ticks.user >> ticks.nice >> ticks.system >> ticks.idle >>
        ticks.iowait >> ticks.irq >> ticks.softirq >> ticks.steal;
    if (stream.fail() && !stream.eof()) {
        return std::nullopt;
    }
    return ticks;
}

std::optional<double> ProcReader::ReadLoad1() const {
    std::ifstream file(proc_root_ + "/loadavg");
    if (!file.is_open()) {
        return std::nullopt;
    }
    double load1 = 0.0;
    file >> load1;
    if (file.fail()) {
        return std::nullopt;
    }
    return load1;
}

std::optional<std::pair<double, double>> ProcReader::ReadMemUsedAndTotalBytes() const {
    std::ifstream file(proc_root_ + "/meminfo");
    if (!file.is_open()) {
        return std::nullopt;
    }
    std::optional<double> mem_total_kb;
    std::optional<double> mem_available_kb;
    std::string line;
    while (std::getline(file, line)) {
        std::istringstream stream(line);
        std::string key;
        double value = 0.0;
        stream >> key >> value;
        if (key == "MemTotal:") {
            mem_total_kb = value;
        } else if (key == "MemAvailable:") {
            mem_available_kb = value;
        }
        if (mem_total_kb.has_value() && mem_available_kb.has_value()) {
            break;
        }
    }
    if (!mem_total_kb.has_value() || !mem_available_kb.has_value()) {
        return std::nullopt;
    }
    const double total_bytes = *mem_total_kb * 1024.0;
    const double used_bytes = (*mem_total_kb - *mem_available_kb) * 1024.0;
    return std::make_pair(used_bytes, total_bytes);
}

std::optional<ProcReader::DiskCounters> ProcReader::ReadDiskCounters() const {
    std::ifstream file(proc_root_ + "/diskstats");
    if (!file.is_open()) {
        return std::nullopt;
    }
    DiskCounters totals;
    std::string line;
    bool saw_any_device = false;
    while (std::getline(file, line)) {
        std::istringstream stream(line);
        std::string major, minor, name;
        unsigned long long reads_completed = 0, reads_merged = 0, sectors_read = 0,
                            time_reading_ms = 0, writes_completed = 0, writes_merged = 0,
                            sectors_written = 0;
        stream >> major >> minor >> name >> reads_completed >> reads_merged >>
            sectors_read >> time_reading_ms >> writes_completed >> writes_merged >>
            sectors_written;
        if (stream.fail()) {
            continue;
        }
        // Skip loopback and ram-backed pseudo devices: they are not real
        // hardware I/O and would otherwise dominate the aggregate under
        // container filesystem churn.
        if (name.rfind("loop", 0) == 0 || name.rfind("ram", 0) == 0) {
            continue;
        }
        totals.sectors_read += sectors_read;
        totals.sectors_written += sectors_written;
        saw_any_device = true;
    }
    if (!saw_any_device) {
        return std::nullopt;
    }
    return totals;
}

std::optional<ProcReader::NetCounters> ProcReader::ReadNetCounters() const {
    std::ifstream file(proc_root_ + "/net/dev");
    if (!file.is_open()) {
        return std::nullopt;
    }
    std::string line;
    // Skip the 2-line header.
    std::getline(file, line);
    std::getline(file, line);

    NetCounters totals;
    bool saw_any_interface = false;
    while (std::getline(file, line)) {
        const auto colon_pos = line.find(':');
        if (colon_pos == std::string::npos) {
            continue;
        }
        std::string iface = line.substr(0, colon_pos);
        iface.erase(0, iface.find_first_not_of(" \t"));
        if (iface == "lo") {
            continue;
        }
        std::istringstream stream(line.substr(colon_pos + 1));
        unsigned long long rx_bytes = 0, rx_packets = 0, rx_errs = 0, rx_drop = 0,
                            rx_fifo = 0, rx_frame = 0, rx_compressed = 0, rx_multicast = 0,
                            tx_bytes = 0;
        stream >> rx_bytes >> rx_packets >> rx_errs >> rx_drop >> rx_fifo >> rx_frame >>
            rx_compressed >> rx_multicast >> tx_bytes;
        if (stream.fail()) {
            continue;
        }
        totals.rx_bytes += rx_bytes;
        totals.tx_bytes += tx_bytes;
        saw_any_interface = true;
    }
    if (!saw_any_interface) {
        return std::nullopt;
    }
    return totals;
}

std::optional<int> ProcReader::ReadProcCount() const {
    DIR* dir = opendir(proc_root_.c_str());
    if (dir == nullptr) {
        return std::nullopt;
    }
    int count = 0;
    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        std::string name(entry->d_name);
        if (IsAllDigits(name)) {
            ++count;
        }
    }
    closedir(dir);
    return count;
}

std::vector<MetricReading> ProcReader::Sample() {
    std::vector<MetricReading> readings;
    const int64_t now_mono_ns = NowMonotonicNs();

    const auto cpu_ticks = ReadCpuTicks();
    const auto disk = ReadDiskCounters();
    const auto net = ReadNetCounters();

    if (has_prior_sample_) {
        const double elapsed_s =
            static_cast<double>(now_mono_ns - prior_mono_ns_) / 1e9;
        if (elapsed_s > 0.0) {
            if (cpu_ticks.has_value()) {
                const unsigned long long prior_total = prior_cpu_ticks_.Total();
                const unsigned long long total = cpu_ticks->Total();
                if (total > prior_total) {
                    const unsigned long long delta_total = total - prior_total;
                    const unsigned long long prior_active =
                        prior_total - prior_cpu_ticks_.idle - prior_cpu_ticks_.iowait;
                    const unsigned long long active = total - cpu_ticks->idle - cpu_ticks->iowait;
                    const double delta_active =
                        static_cast<double>(active) - static_cast<double>(prior_active);
                    const double delta_iowait = static_cast<double>(cpu_ticks->iowait) -
                                                 static_cast<double>(prior_cpu_ticks_.iowait);
                    readings.push_back(
                        {kMetricCpuPct, 100.0 * delta_active / static_cast<double>(delta_total)});
                    readings.push_back(
                        {kMetricIowaitPct,
                         100.0 * delta_iowait / static_cast<double>(delta_total)});
                }
            }
            if (disk.has_value() && disk->sectors_read >= prior_disk_.sectors_read &&
                disk->sectors_written >= prior_disk_.sectors_written) {
                const double read_bytes_s =
                    static_cast<double>(disk->sectors_read - prior_disk_.sectors_read) *
                    kSectorBytes / elapsed_s;
                const double write_bytes_s =
                    static_cast<double>(disk->sectors_written - prior_disk_.sectors_written) *
                    kSectorBytes / elapsed_s;
                readings.push_back({kMetricDiskReadBytesS, read_bytes_s});
                readings.push_back({kMetricDiskWriteBytesS, write_bytes_s});
            }
            if (net.has_value() && net->rx_bytes >= prior_net_.rx_bytes &&
                net->tx_bytes >= prior_net_.tx_bytes) {
                const double rx_bytes_s =
                    static_cast<double>(net->rx_bytes - prior_net_.rx_bytes) / elapsed_s;
                const double tx_bytes_s =
                    static_cast<double>(net->tx_bytes - prior_net_.tx_bytes) / elapsed_s;
                readings.push_back({kMetricNetRxBytesS, rx_bytes_s});
                readings.push_back({kMetricNetTxBytesS, tx_bytes_s});
            }
        }
    }

    if (cpu_ticks.has_value()) {
        prior_cpu_ticks_ = *cpu_ticks;
    }
    if (disk.has_value()) {
        prior_disk_ = *disk;
    }
    if (net.has_value()) {
        prior_net_ = *net;
    }
    prior_mono_ns_ = now_mono_ns;
    has_prior_sample_ = true;

    if (const auto load1 = ReadLoad1(); load1.has_value()) {
        readings.push_back({kMetricLoad1, *load1});
    }
    if (const auto mem = ReadMemUsedAndTotalBytes(); mem.has_value()) {
        readings.push_back({kMetricMemUsedBytes, mem->first});
        readings.push_back({kMetricMemTotalBytes, mem->second});
    }
    if (const auto proc_count = ReadProcCount(); proc_count.has_value()) {
        readings.push_back({kMetricProcCount, static_cast<double>(*proc_count)});
    }

    return readings;
}

}  // namespace hpctel
