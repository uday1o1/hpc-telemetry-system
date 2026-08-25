cmake_minimum_required(VERSION 3.16)
project(hpctel_agent CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Prefer the modern CONFIG package (needed on newer Protobuf releases that
# depend on Abseil, e.g. local macOS dev via Homebrew) and fall back to the
# legacy FindProtobuf module (what Debian bookworm's apt-packaged Protobuf
# 3.21, used in the Linux container build, provides).
find_package(protobuf CONFIG QUIET)
if(NOT protobuf_FOUND)
  find_package(Protobuf MODULE REQUIRED)
endif()
find_package(Threads REQUIRED)

# The .proto schema lives at the repository root (proto/telemetry.proto) and
# is the single source of truth; the C++ binding is generated at build time,
# never hand-written or committed. See BUILD_PLAN.md section 10.
set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../proto)
set(PROTO_FILE ${PROTO_DIR}/telemetry.proto)
set(PROTO_GEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${PROTO_GEN_DIR})

add_custom_command(
  OUTPUT ${PROTO_GEN_DIR}/telemetry.pb.cc ${PROTO_GEN_DIR}/telemetry.pb.h
  COMMAND protobuf::protoc
  ARGS --cpp_out=${PROTO_GEN_DIR} -I ${PROTO_DIR} ${PROTO_FILE}
  DEPENDS ${PROTO_FILE}
  COMMENT "Generating C++ protobuf binding from telemetry.proto"
)

add_library(hpctel_agent_lib
  src/proc_reader.cpp
  src/framing.cpp
  src/config.cpp
  src/logging.cpp
  src/sender.cpp
  ${PROTO_GEN_DIR}/telemetry.pb.cc
)
target_include_directories(hpctel_agent_lib PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/src
  ${PROTO_GEN_DIR}
)
target_link_libraries(hpctel_agent_lib PUBLIC protobuf::libprotobuf Threads::Threads)

add_executable(hpctel_agent src/main.cpp)
target_link_libraries(hpctel_agent PRIVATE hpctel_agent_lib)

enable_testing()
option(HPCTEL_BUILD_TESTS "Build the agent's GoogleTest unit tests" ON)
if(HPCTEL_BUILD_TESTS)
  add_subdirectory(tests)
endif()
