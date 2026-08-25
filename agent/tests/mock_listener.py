#!/usr/bin/env python3
"""Scripted mock TCP listener used for the Milestone 1 closest-real-user-path
verification (BUILD_PLAN.md section 16): accepts one agent connection,
counts complete frames received over a fixed duration, and reports whether
the connection stayed open the whole time with zero unexpected disconnects.

Usage: mock_listener.py <host> <port> <duration_seconds>
"""

from __future__ import annotations

import socket
import sys
import time

_HEADER_LENGTH = 5


def main() -> int:
    host, port, duration_s = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((host, port))
    listener.listen(1)
    listener.settimeout(duration_s + 10)

    print(f"mock_listener: waiting for a connection on {host}:{port}", flush=True)
    conn, addr = listener.accept()
    print(f"mock_listener: accepted connection from {addr}", flush=True)

    conn.settimeout(5.0)
    frame_count = 0
    unexpected_disconnect = False
    deadline = time.monotonic() + duration_s

    while time.monotonic() < deadline:
        try:
            header = _recv_exactly(conn, _HEADER_LENGTH)
        except TimeoutError:
            continue
        except ConnectionError:
            unexpected_disconnect = True
            break
        if header is None:
            unexpected_disconnect = True
            break
        length = int.from_bytes(header[1:5], byteorder="big")
        payload = _recv_exactly(conn, length)
        if payload is None:
            unexpected_disconnect = True
            break
        frame_count += 1

    conn.close()
    listener.close()

    print(f"mock_listener: received {frame_count} frames in {duration_s}s", flush=True)
    print(f"mock_listener: unexpected_disconnect={unexpected_disconnect}", flush=True)
    return 1 if unexpected_disconnect or frame_count == 0 else 0


def _recv_exactly(conn: socket.socket, count: int) -> bytes | None:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = conn.recv(count - len(chunks))
        if not chunk:
            return None
        chunks.extend(chunk)
    return bytes(chunks)


if __name__ == "__main__":
    raise SystemExit(main())
