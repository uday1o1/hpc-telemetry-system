"""Environment-variable configuration for the workload runner."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    node_id: str
    ingest_host: str
    ingest_tcp_port: int
    http_port: int
    default_sieve_limit: int


def load_config() -> Config:
    return Config(
        node_id=os.environ.get("NODE_ID", "node-unknown"),
        ingest_host=os.environ.get("INGEST_HOST", "127.0.0.1"),
        ingest_tcp_port=int(os.environ.get("INGEST_PORT", "7070")),
        http_port=int(os.environ.get("WORKLOAD_HTTP_PORT", "9090")),
        default_sieve_limit=int(os.environ.get("DEFAULT_SIEVE_LIMIT", "500000")),
    )
