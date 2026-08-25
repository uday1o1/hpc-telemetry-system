from workloadrunner.compute import run_prime_sieve


def test_sieve_of_100_matches_known_prime_count():
    # There are 25 primes below 100 (2, 3, 5, ..., 97), a well-known value.
    assert run_prime_sieve(100) == 25


def test_sieve_is_deterministic():
    assert run_prime_sieve(10_000) == run_prime_sieve(10_000)


def test_sieve_of_small_limits():
    assert run_prime_sieve(0) == 0
    assert run_prime_sieve(1) == 0
    assert run_prime_sieve(2) == 1  # just "2"


def test_sieve_monotonic_in_limit():
    assert run_prime_sieve(1000) <= run_prime_sieve(2000)
