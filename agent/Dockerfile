# syntax=docker/dockerfile:1
#
# Build context is the repository root (see docker-compose.yml) so this
# Dockerfile can reach both agent/ and the shared proto/ schema.
FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171 AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    libprotobuf-dev \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY proto ./proto
COPY agent/CMakeLists.txt ./agent/CMakeLists.txt
COPY agent/src ./agent/src

WORKDIR /src/agent
RUN cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build

FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171

RUN apt-get update && apt-get install -y --no-install-recommends libprotobuf32 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system hpctel && useradd --system --gid hpctel --no-create-home hpctel

COPY --from=build /src/agent/build/hpctel_agent /usr/local/bin/hpctel_agent

USER hpctel
ENTRYPOINT ["/usr/local/bin/hpctel_agent"]
