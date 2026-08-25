#include "config.hpp"

#include <cstdlib>

namespace hpctel {

namespace {

std::string EnvOr(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return value != nullptr ? std::string(value) : fallback;
}

int EnvIntOr(const char* name, int fallback) {
    const char* value = std::getenv(name);
    if (value == nullptr) {
        return fallback;
    }
    try {
        return std::stoi(value);
    } catch (const std::exception&) {
        return fallback;
    }
}

}  // namespace

AgentConfig AgentConfig::FromEnvironment() {
    AgentConfig config;
    config.node_id = EnvOr("NODE_ID", "node-unknown");
    config.ingest_host = EnvOr("INGEST_HOST", "127.0.0.1");
    config.ingest_port = EnvIntOr("INGEST_PORT", 7070);
    config.sample_interval_ms = EnvIntOr("SAMPLE_INTERVAL_MS", 1000);
    config.proc_root = EnvOr("PROC_ROOT", "/proc");
    config.max_queue_size = static_cast<size_t>(EnvIntOr("MAX_QUEUE_SIZE", 512));
    return config;
}

}  // namespace hpctel
