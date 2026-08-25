include(FetchContent)

FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG v1.18.0
)
# Keep gtest's own runtime library selection consistent with this project's
# default; avoids an MSVC-only warning on non-Windows builds but is a no-op
# there.
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

add_executable(hpctel_agent_tests
  test_proc_reader.cpp
  test_framing.cpp
)
target_link_libraries(hpctel_agent_tests PRIVATE hpctel_agent_lib gtest_main)
target_compile_definitions(hpctel_agent_tests PRIVATE
  HPCTEL_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
)

include(GoogleTest)
gtest_discover_tests(hpctel_agent_tests)
