#pragma once

#include <string>

namespace hpctel {

enum class LogLevel { kDebug, kInfo, kWarn, kError };

// Minimal structured JSON logger to stdout (BUILD_PLAN.md section 6 and
// section 12): one JSON object per line, correlated by node_id where
// applicable, so agent logs can be grepped or shipped alongside the
// ingestion service's own JSON logs.
void LogEvent(LogLevel level, const std::string& event, const std::string& node_id,
              const std::string& detail = "");

}  // namespace hpctel
