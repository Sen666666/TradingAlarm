"""Pure synthetic contracts for numeric.py; no real data or accounts."""
from __future__ import annotations
import json
import math

import numpy as np
import pandas as pd

from numeric import GAMMA4, compare, event_frame_numeric, higher, log_ratio


def run():
    tests = []

    def check(name, fn):
        fn()
        tests.append(name)

    def boundary_semantics():
        p = 100.0
        near = np.nextafter(p, math.inf)
        assert compare(near, p) == 0
        assert not compare(near, p) > 0       # no invented strict breakout
        assert compare(near, p) <= 0         # existing <= floor remains inclusive
        assert higher(p, near) == p           # no phantom floor ratchet
        assert log_ratio(near, p) == 0
        assert compare(p * (1 + 1e-12), p) == 1   # real tiny movement is not erased
        assert compare(p * (1 - 1e-12), p) == -1
    check("tie_strict_breakout_inclusive_floor_and_old_ratchet", boundary_semantics)

    def units():
        for factor in [0.001, 7.0, 1000.0]:
            assert compare(101 * factor, 100 * factor) == 1
            assert compare(100 * factor, 100 * factor) == 0
            assert abs(log_ratio(101 * factor, 100 * factor) - math.log(1.01)) < 1e-15
    check("ordinary_unit_changes_and_local_log_ratio", units)

    def no_universal_claim():
        a, b = 1.0, 1.0 + 2 * math.ulp(1.0)
        assert compare(a, b) == 0
        assert compare(a * 7, b * 7) == -1
    check("documented_roundoff_budget_edge_counterexample", no_universal_claim)

    def invalid():
        for value in [math.nan, math.inf, -1.0]:
            try:
                compare(value, 1)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid input accepted")
        try:
            log_ratio(0, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("zero price accepted")
    check("invalid_inputs_rejected", invalid)

    def path():
        prices = 100 * np.exp(0.01 * np.sin(np.arange(90) / 4))
        prices = np.r_[prices, [100, 101, 104, 104, 104, 100, 96, 97, 100, 103]]
        index = pd.date_range("2000-01-01", periods=len(prices))
        close = pd.Series(prices, index=index)
        volume = pd.Series(100 + np.arange(len(prices)) % 7, index=index)
        full = event_frame_numeric(close, volume)
        for cut in [1, 64, 65, 90, 97, len(prices) - 1]:
            pd.testing.assert_frame_equal(
                event_frame_numeric(close.iloc[:cut], volume.iloc[:cut]), full.iloc[:cut])
        scaled = event_frame_numeric(close * 7, volume * 11)
        for col in ["event", "target", "entered", "exited", "pivot_age",
                    "confirmed_pivot_date", "developing_extreme_date"]:
            pd.testing.assert_series_equal(full[col], scaled[col])
    check("synthetic_event_prefix_and_unit_discrete_states", path)
    return {"passed": len(tests), "tests": tests, "gamma4": GAMMA4,
            "scope": "synthetic numerical contract only; finite scale tests, not universal proof"}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
