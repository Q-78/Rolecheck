"""Dependency-free exploratory statistics for paired binary outcomes."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def exact_binomial_two_sided(successes: int, trials: int) -> float:
    """Return the exact two-sided p-value under p=0.5."""
    if trials < 0 or not 0 <= successes <= trials:
        raise ValueError("invalid binomial counts")
    if trials == 0:
        return 1.0
    observed = math.comb(trials, successes) / (2**trials)
    return float(
        min(
            1.0,
            sum(
                math.comb(trials, k) / (2**trials)
                for k in range(trials + 1)
                if math.comb(trials, k) / (2**trials) <= observed + 1e-15
            ),
        )
    )


def exact_mcnemar(correct_to_wrong: int, wrong_to_correct: int) -> float:
    """Return the exact two-sided McNemar/binomial p-value."""
    if correct_to_wrong < 0 or wrong_to_correct < 0:
        raise ValueError("discordant counts cannot be negative")
    return exact_binomial_two_sided(
        min(correct_to_wrong, wrong_to_correct),
        correct_to_wrong + wrong_to_correct,
    )


def bootstrap_mean_ci(
    values: Sequence[float], *, seed: int, samples: int = 10_000, alpha: float = 0.05
) -> dict[str, float | int | None]:
    """Deterministically bootstrap a percentile interval for the mean."""
    if samples <= 0 or not 0.0 < alpha < 1.0:
        raise ValueError("invalid bootstrap configuration")
    if not values:
        return {"seed": seed, "samples": samples, "mean": None, "low": None, "high": None}
    rng = random.Random(seed)
    size = len(values)
    estimates = sorted(
        sum(values[rng.randrange(size)] for _ in range(size)) / size for _ in range(samples)
    )
    low_index = max(0, math.floor((alpha / 2) * samples))
    high_index = min(samples - 1, math.ceil((1 - alpha / 2) * samples) - 1)
    return {
        "seed": seed,
        "samples": samples,
        "mean": sum(values) / size,
        "low": estimates[low_index],
        "high": estimates[high_index],
    }
