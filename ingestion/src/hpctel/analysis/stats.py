"""Wilson score confidence interval for a binomial proportion
(BUILD_PLAN.md section 13). Chosen over a normal-approximation interval
because it stays well-behaved near proportions of 0 or 1, and needs no
resampling procedure beyond the observed trial count.
"""

from __future__ import annotations

import math

Z_95 = 1.959963984540054  # two-sided 95% confidence z-score


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Returns (lower, upper) bounds of the Wilson score interval for
    `successes` out of `n` trials. If n == 0, returns the maximally
    uninformative (0.0, 1.0) interval rather than dividing by zero.
    """
    if n == 0:
        return (0.0, 1.0)
    if successes < 0 or successes > n:
        raise ValueError(f"successes ({successes}) must be within [0, n={n}]")

    phat = successes / n
    z_sq = z * z
    denom = 1.0 + z_sq / n
    center = (phat + z_sq / (2 * n)) / denom
    margin = (z * math.sqrt((phat * (1 - phat) + z_sq / (4 * n)) / n)) / denom

    return (max(0.0, center - margin), min(1.0, center + margin))
