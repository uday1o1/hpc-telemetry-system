cmake_minimum_required(VERSION 3.16)
project(hpctel_agent CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Protobuf REQUIRED)

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

add_executable(hpctel_agent
  src/main.cpp
  ${PROTO_GEN_DIR}/telemetry.pb.cc
)

target_include_directories(hpctel_agent PRIVATE ${PROTO_GEN_DIR} ${Protobuf_INCLUDE_DIRS})
target_link_libraries(hpctel_agent PRIVATE protobuf::libprotobuf)

enable_testing()
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/CMakeLists.txt)
  add_subdirectory(tests)
endif()
