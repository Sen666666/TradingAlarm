"""Frozen E0 scalar arithmetic, copied without changing operation order.

Source: pv-participation-response-20261020/code/numeric.py.  These pure
functions contain no event, position, participation, or account state.
"""
from __future__ import annotations

import math

import numpy as np


UNIT_ROUNDOFF = np.finfo(np.float64).eps / 2
ROUNDING_STEPS = 4
GAMMA4 = ROUNDING_STEPS * UNIT_ROUNDOFF / (1 - ROUNDING_STEPS * UNIT_ROUNDOFF)


def compare(a: float, b: float) -> int:
    """Order finite nonnegative magnitudes with the original gamma4 tie band."""
    a, b = float(a), float(b)
    if not (math.isfinite(a) and math.isfinite(b) and a >= 0 and b >= 0):
        raise ValueError("finite nonnegative magnitudes required")
    if abs(a - b) <= GAMMA4 * max(a, b):
        return 0
    return 1 if a > b else -1


def log_ratio(a: float, b: float) -> float:
    """The original local log change, including its exact branch choices."""
    a, b = float(a), float(b)
    if not (math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0):
        raise ValueError("finite positive prices required")
    if compare(a, b) == 0:
        return 0.0
    if 0.5 <= a / b <= 2:
        return math.log1p((a - b) / b)
    return math.log(a) - math.log(b)


def higher(old: float, new: float) -> float:
    """Retain the old value on a numerical tie, as in the frozen E0 policy."""
    return float(new) if compare(new, old) > 0 else float(old)
