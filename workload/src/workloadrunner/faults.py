"""Seeded, userspace-only fault injectors (BUILD_PLAN.md section 11).

Both fault types run entirely inside this container's own process: no
`tc netem`, no `NET_ADMIN` or other elevated container capability is
required, which keeps the security contract in section 12 simple (V1
never needs privileged containers) and portable across Docker Desktop and
Colima alike.
"""

from __future__ import annotations

import multiprocessing
import os
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class FaultManifest:
    fault_type: str  # "cpu_contention" or "io_stall"
    intensity: int = 2


def _cpu_busy_loop(stop_flag) -> None:
    # A tight, allocation-free arithmetic loop: real CPU contention against
    # sibling processes on the same host/core, not a sleep.
    x = 0
    while not stop_flag.value:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF


@contextmanager
def _cpu_contention(intensity: int):
    manager = multiprocessing.Manager()
    stop_flag = manager.Value("b", False)
    workers = [
        multiprocessing.Process(target=_cpu_busy_loop, args=(stop_flag,), daemon=True)
        for _ in range(max(1, intensity))
    ]
    for worker in workers:
        worker.start()
    try:
        yield
    finally:
        stop_flag.value = True
        for worker in workers:
            worker.join(timeout=5.0)
            if worker.is_alive():
                worker.terminate()
        manager.shutdown()


def _io_stall_loop(stop_event: threading.Event, chunk_bytes: bytes) -> None:
    fd, path = tempfile.mkstemp(prefix="hpctel-io-stall-")
    try:
        while not stop_event.is_set():
            os.write(fd, chunk_bytes)
            os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
    finally:
        os.close(fd)
        os.remove(path)


@contextmanager
def _io_stall(intensity: int):
    stop_event = threading.Event()
    chunk_bytes = os.urandom(1_000_000)  # 1 MB per write, bounded and local to this container
    threads = [
        threading.Thread(target=_io_stall_loop, args=(stop_event, chunk_bytes), daemon=True)
        for _ in range(max(1, intensity))
    ]
    for thread in threads:
        thread.start()
    try:
        yield
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5.0)


@contextmanager
def apply_fault(manifest: FaultManifest | None):
    """A no-op context manager if `manifest` is None, otherwise activates
    the named fault for the duration of the `with` block.
    """
    if manifest is None:
        yield
        return

    if manifest.fault_type == "cpu_contention":
        with _cpu_contention(manifest.intensity):
            yield
    elif manifest.fault_type == "io_stall":
        with _io_stall(manifest.intensity):
            yield
    else:
        raise ValueError(f"unknown fault_type: {manifest.fault_type}")
