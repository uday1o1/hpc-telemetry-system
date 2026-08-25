#include "logging.hpp"

#include <chrono>
#include <iostream>
#include <sstream>

namespace hpctel {

namespace {

std::string LevelName(LogLevel level) {
    switch (level) {
        case LogLevel::kDebug:
            return "DEBUG";
        case LogLevel::kInfo:
            return "INFO";
        case LogLevel::kWarn:
            return "WARN";
        case LogLevel::kError:
            return "ERROR";
    }
    return "UNKNOWN";
}

std::string JsonEscape(const std::string& raw) {
    std::string escaped;
    escaped.reserve(raw.size());
    for (char c : raw) {
        switch (c) {
            case '"':
                escaped += "\\\"";
                break;
            case '\\':
                escaped += "\\\\";
                break;
            case '\n':
                escaped += "\\n";
                break;
            default:
                escaped += c;
        }
    }
    return escaped;
}

double NowEpochSeconds() {
    return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch())
        .count();
}

}  // namespace

void LogEvent(LogLevel level, const std::string& event, const std::string& node_id,
              const std::string& detail) {
    std::ostringstream line;
    line << "{\"ts\":" << NowEpochSeconds() << ",\"level\":\"" << LevelName(level)
         << "\",\"logger\":\"hpctel.agent\",\"message\":\"" << JsonEscape(event)
         << "\",\"node_id\":\"" << JsonEscape(node_id) << "\"";
    if (!detail.empty()) {
        line << ",\"detail\":\"" << JsonEscape(detail) << "\"";
    }
    line << "}";
    std::cout << line.str() << std::endl;
}

}  // namespace hpctel
