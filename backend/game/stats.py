"""Small statistics helpers for the pilot analysis (no third-party dependencies).

The unit the platform randomises and watches is the *learner*, while most counts
are over (learner, step) pairs or (learner, day) snapshots. Rows of one learner
are not independent: if a learner leaves, all their open pairs "leave" at once.
So every interval here is computed with an *effective* sample size: rows of one
learner are treated as fully correlated (worst case), which gives a wider, honest
interval instead of one that looks tighter than the data allow.
"""

import math
from collections import Counter

Z95 = 1.96


def wilson_interval(successes, n, z=Z95):
    """Wilson score interval for a share; ``None`` for an empty sample.

    ``successes`` and ``n`` may be fractional (see :func:`effective_n`).
    """
    if n <= 0:
        return None
    p = min(1.0, max(0.0, successes / n))
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def effective_n(sizes):
    """Effective number of independent observations from per-learner row counts.

    ``N^2 / sum(n_i^2)`` (Kish). One row per learner gives ``N``; if one learner
    owns every row it is 1. Accepts an iterable of counts or a mapping.
    """
    counts = list(sizes.values()) if hasattr(sizes, "values") else list(sizes)
    total = sum(counts)
    squares = sum(c * c for c in counts)
    return total * total / squares if squares else 0.0


def cluster_counts(pairs):
    """{learner: rows} for an iterable of ``(learner, ...)`` keys."""
    return Counter(key[0] if isinstance(key, tuple) else key for key in pairs)


def clustered_share(successes, sizes, z=Z95):
    """Share, its interval and the effective n, for rows grouped by learner.

    ``successes`` is the number of rows with the outcome, ``sizes`` the rows per
    learner. Returns ``None`` for an empty sample, else
    ``{"share", "ci_low", "ci_high", "n", "n_eff", "learners"}`` (shares in 0-1).
    """
    n = sum(sizes.values()) if hasattr(sizes, "values") else sum(sizes)
    if not n:
        return None
    share = successes / n
    n_eff = effective_n(sizes)
    low, high = wilson_interval(share * n_eff, n_eff, z)
    return {
        "share": share,
        "ci_low": low,
        "ci_high": high,
        "n": n,
        "n_eff": round(n_eff, 1),
        "learners": len(sizes),
    }
