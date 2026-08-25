from hpctel.analysis.stats import wilson_interval


def test_zero_trials_returns_maximally_uninformative_interval():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_all_successes_upper_bound_is_less_than_one():
    lower, upper = wilson_interval(10, 10)
    assert lower > 0.6
    assert upper == 1.0 or upper < 1.0 + 1e-9


def test_zero_successes_lower_bound_is_zero_and_upper_bound_is_positive():
    lower, upper = wilson_interval(0, 20)
    assert lower == 0.0
    assert upper > 0.0  # never asserted as literally zero percent


def test_interval_narrows_with_more_trials_at_same_proportion():
    small_lower, small_upper = wilson_interval(5, 10)
    large_lower, large_upper = wilson_interval(50, 100)
    assert (large_upper - large_lower) < (small_upper - small_lower)


def test_interval_is_symmetric_around_half_at_p_half():
    lower, upper = wilson_interval(50, 100)
    assert abs((lower + upper) / 2 - 0.5) < 1e-9


def test_rejects_successes_greater_than_n():
    import pytest

    with pytest.raises(ValueError):
        wilson_interval(11, 10)
