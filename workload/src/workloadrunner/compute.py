"""The synthetic job's bounded CPU-bound phase computation
(BUILD_PLAN.md section 11): a fixed-iteration-count prime sieve.

A fixed iteration count, rather than a fixed sleep duration, is essential:
a genuinely slower or contended node must take measurably longer to finish
the same amount of work, which is exactly the signal the straggler-ranking
algorithm (Milestone 4) is built to detect.
"""

from __future__ import annotations


def run_prime_sieve(limit: int) -> int:
    """Runs a Sieve of Eratosthenes up to `limit` and returns the count of
    primes found. The return value is deterministic for a given `limit`,
    which makes this function directly unit-testable independent of timing.
    """
    if limit < 2:
        return 0
    is_prime = bytearray([1]) * (limit + 1)
    is_prime[0] = 0
    is_prime[1] = 0
    for candidate in range(2, int(limit**0.5) + 1):
        if is_prime[candidate]:
            for multiple in range(candidate * candidate, limit + 1, candidate):
                is_prime[multiple] = 0
    return sum(is_prime)
