# syntax=docker/dockerfile:1
#
# Build context is the repository root (see docker-compose.yml) so this
# Dockerfile can reach both ingestion/ and the shared proto/ schema.
FROM python:3.12-slim-bookworm@sha256:0f5b26b9518d002b6173fd61daad821fa340635ebfec5bba471013f9ca114579 AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY proto ./proto
COPY ingestion/pyproject.toml ./ingestion/pyproject.toml
COPY ingestion/src ./ingestion/src

RUN mkdir -p ingestion/src/hpctel/_generated \
    && protoc --python_out=ingestion/src/hpctel/_generated -I proto proto/telemetry.proto \
    && touch ingestion/src/hpctel/_generated/__init__.py

RUN pip install --no-cache-dir ./ingestion

RUN groupadd --system hpctel && useradd --system --gid hpctel --no-create-home hpctel \
    && mkdir -p /data && chown hpctel:hpctel /data

USER hpctel
ENV HPCTEL_DB_PATH=/data/hpctel.sqlite3
EXPOSE 7070 8080

CMD ["uvicorn", "hpctel.api:app", "--host", "0.0.0.0", "--port", "8080"]
