#pragma once

#include <cstdint>
#include <string>

namespace hpctel {

struct AgentConfig {
    std::string node_id;
    std::string ingest_host;
    int ingest_port;
    int sample_interval_ms;
    std::string proc_root;
    size_t max_queue_size;

    static AgentConfig FromEnvironment();
};

}  // namespace hpctel
