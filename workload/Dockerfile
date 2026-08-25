# syntax=docker/dockerfile:1
#
# Build context is the repository root (see docker-compose.yml) so this
# Dockerfile can reach both workload/ and the shared proto/ schema.
FROM python:3.12-slim-bookworm@sha256:0f5b26b9518d002b6173fd61daad821fa340635ebfec5bba471013f9ca114579 AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY proto ./proto
COPY workload/pyproject.toml ./workload/pyproject.toml
COPY workload/src ./workload/src

RUN mkdir -p workload/src/workloadrunner/_generated \
    && protoc --python_out=workload/src/workloadrunner/_generated -I proto proto/telemetry.proto \
    && touch workload/src/workloadrunner/_generated/__init__.py

RUN pip install --no-cache-dir ./workload

RUN groupadd --system hpctel && useradd --system --gid hpctel --no-create-home hpctel

USER hpctel
EXPOSE 9090

CMD ["uvicorn", "workloadrunner.runner:app", "--host", "0.0.0.0", "--port", "9090"]
