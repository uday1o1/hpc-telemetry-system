import time

import pytest

from workloadrunner.compute import run_prime_sieve
from workloadrunner.faults import FaultManifest, apply_fault


def test_no_fault_is_a_true_no_op():
    with apply_fault(None):
        pass  # must not raise, must not spawn anything


def test_cpu_contention_runs_and_cleans_up():
    with apply_fault(FaultManifest(fault_type="cpu_contention", intensity=1)):
        run_prime_sieve(50_000)
    # If worker processes were not cleaned up, a second activation should
    # still work cleanly (no leaked state), so run it again.
    with apply_fault(FaultManifest(fault_type="cpu_contention", intensity=1)):
        run_prime_sieve(50_000)


def test_io_stall_runs_and_cleans_up():
    with apply_fault(FaultManifest(fault_type="io_stall", intensity=1)):
        run_prime_sieve(50_000)


def test_unknown_fault_type_raises():
    with pytest.raises(ValueError), apply_fault(FaultManifest(fault_type="not_a_real_fault")):
        pass


def test_cpu_contention_measurably_slows_a_fixed_computation():
    # Directional, generously-toleranced timing check: contention against
    # a fixed amount of CPU work should make it take longer, not shorter
    # or equal, on average. A tight quantitative bound belongs to the
    # Milestone 4 confirmatory evaluation batch (eval/run_trials.py), not
    # this fast unit test.
    sieve_limit = 300_000
    baseline_durations = []
    contended_durations = []
    for _ in range(2):
        start = time.perf_counter()
        run_prime_sieve(sieve_limit)
        baseline_durations.append(time.perf_counter() - start)

    for _ in range(2):
        with apply_fault(FaultManifest(fault_type="cpu_contention", intensity=2)):
            start = time.perf_counter()
            run_prime_sieve(sieve_limit)
            contended_durations.append(time.perf_counter() - start)

    assert min(contended_durations) > min(baseline_durations)
