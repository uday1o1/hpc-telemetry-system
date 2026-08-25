#include <csignal>

#include <atomic>
#include <chrono>
#include <thread>

#include "config.hpp"
#include "logging.hpp"
#include "proc_reader.hpp"
#include "sender.hpp"

namespace {
std::atomic<bool> g_shutdown_requested{false};

void HandleSignal(int) { g_shutdown_requested.store(true); }
}  // namespace

int main() {
    std::signal(SIGINT, HandleSignal);
    std::signal(SIGTERM, HandleSignal);

    const hpctel::AgentConfig config = hpctel::AgentConfig::FromEnvironment();
    hpctel::LogEvent(hpctel::LogLevel::kInfo, "agent_starting", config.node_id);

    hpctel::ProcReader proc_reader(config.proc_root);
    hpctel::SampleSender sender(config);
    sender.Start();

    const auto interval = std::chrono::milliseconds(config.sample_interval_ms);
    while (!g_shutdown_requested.load()) {
        const auto readings = proc_reader.Sample();
        const auto now_realtime_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                                          std::chrono::system_clock::now().time_since_epoch())
                                          .count();
        const auto now_mono_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                                      std::chrono::steady_clock::now().time_since_epoch())
                                      .count();
        for (const auto& reading : readings) {
            sender.Enqueue({reading.metric_id, now_realtime_ns, now_mono_ns, reading.value});
        }
        std::this_thread::sleep_for(interval);
    }

    hpctel::LogEvent(hpctel::LogLevel::kInfo, "agent_stopping", config.node_id,
                      "dropped=" + std::to_string(sender.DroppedCount()));
    sender.Stop();
    return 0;
}
