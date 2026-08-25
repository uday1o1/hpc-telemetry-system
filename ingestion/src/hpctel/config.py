"""Environment-variable configuration for the ingestion service.

See BUILD_PLAN.md section 10 (toolchain and environment strategy).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    tcp_host: str
    tcp_port: int
    http_host: str
    http_port: int
    db_path: str


def load_config() -> Config:
    return Config(
        tcp_host=os.environ.get("INGEST_TCP_HOST", "0.0.0.0"),
        tcp_port=int(os.environ.get("INGEST_TCP_PORT", "7070")),
        http_host=os.environ.get("INGEST_HTTP_HOST", "0.0.0.0"),
        http_port=int(os.environ.get("INGEST_HTTP_PORT", "8080")),
        db_path=os.environ.get("HPCTEL_DB_PATH", "/data/hpctel.sqlite3"),
    )
