"""Independent synthetic audit. No real candidate paths or accounts are loaded.

Default: print JSON. --output writes a new JSON path and refuses overwrite.
Synthetic upstream events isolate the new state machine; a separate test uses
the frozen original detector on synthetic prices to verify no-conflict identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from baseline_event_structure import event_frame
from volume_response import attach_exact_pivots, response_frame


def fixture(n=35):
    idx = pd.date_range("2000-01-01", periods=n)
    b = pd.DataFrame({"open": 99., "high": 100., "low": 98.,
                      "close": 99., "volume": 100.}, index=idx)
    b.attrs["source_first_close"] = 99.
    e = pd.DataFrame({"event": 0., "confirmed_pivot": np.nan,
                      "confirmed_pivot_relative": np.nan}, index=idx)
    e.attrs["source_first_close"] = 99.
    return b, e


def bar(b, i, close=99., high=102., low=98., volume=200.):
    b.iloc[i] = [close, high, low, close, volume]


def event(e, i, direction, pivot):
    e.iloc[i] = [direction, np.log(pivot),
                 np.log(pivot / e.attrs["source_first_close"])]


def conflict_fixture():
    b, e = fixture()
    event(e, 20, -1, 100.)
    bar(b, 21)
    return b, e


def check_quantity_selection():
    b, e = conflict_fixture()
    b.iloc[21, b.columns.get_loc("volume")] = 199.99
    bar(b, 22, volume=200.)
    r, _ = response_frame(b, e)
    assert r.iloc[21].created == 0
    assert r.iloc[22].created == 1
    assert r.iloc[22].volume_ratio == 2.


def check_complete_prior_volume():
    b, e = conflict_fixture()
    b.iloc[5, b.columns.get_loc("volume")] = np.nan
    event(e, 21, 1, 97.)
    r, _ = response_frame(b, e)
    assert np.isnan(r.iloc[21].volume_ratio)
    assert r.iloc[21].created == 0 and r.iloc[21].target == 1
    # Having only 20 prior observations is also insufficient.
    b, e = fixture()
    event(e, 19, -1, 100.)
    bar(b, 20, volume=200.)
    r, _ = response_frame(b, e)
    assert np.isnan(r.iloc[20].volume_ratio) and r.iloc[20].created == 0


def check_reference_available_next_observation():
    b, e = fixture()
    event(e, 21, -1, 100.)
    bar(b, 21, volume=200.)
    bar(b, 22, volume=200.)
    r, ledger = response_frame(b, e)
    assert r.iloc[21].created == 0
    assert r.iloc[22].created == 1
    assert ledger.iloc[0].peak_confirmation_date == "2000-01-22"


def check_pending_is_frozen_and_blocks_original_entry():
    b, e = conflict_fixture()
    event(e, 21, 1, 97.)
    # Larger intraday range and much larger volume cannot move the memory.
    bar(b, 22, close=99., high=110., low=96., volume=5000.)
    event(e, 22, 1, 98.5)
    r, ledger = response_frame(b, e)
    assert r.iloc[21].blocked_price_event == r.iloc[22].blocked_price_event == 1
    assert r.iloc[21].target == r.iloc[22].target == 0
    assert r.iloc[22].pending_high == 102. and r.iloc[22].pending_low == 98.
    assert len(ledger) == 1 and ledger.iloc[0].created_date == "2000-01-22"


def check_upper_resolution_with_missing_current_volume():
    b, e = conflict_fixture()
    bar(b, 22, close=103., high=104., low=102.5, volume=np.nan)
    r, ledger = response_frame(b, e)
    assert r.iloc[22].resolved == 1 and r.iloc[22].entered == 1
    assert r.iloc[22].created == 0 and r.iloc[22].pending == 0
    assert r.iloc[22].entry_kind == "volume_resolution"
    assert np.isclose(r.iloc[22].floor, 98.)
    assert ledger.iloc[0].outcome == 1


def check_lower_resolution_overrides_same_day_up_event():
    b, e = conflict_fixture()
    bar(b, 22, close=97., high=101., low=96., volume=1000.)
    event(e, 22, 1, 95.)
    r, ledger = response_frame(b, e)
    assert r.iloc[22].resolved == -1
    assert r.iloc[22].entered == r.iloc[22].target == 0
    assert r.iloc[22].created == r.iloc[22].pending == 0
    assert ledger.iloc[0].outcome == -1


def check_boundary_equalities_do_not_resolve():
    b, e = conflict_fixture()
    bar(b, 22, close=102., high=103., low=101., volume=100.)
    bar(b, 23, close=98., high=99., low=97., volume=100.)
    r, _ = response_frame(b, e)
    assert (r.iloc[22:24].resolved == 0).all()
    assert (r.iloc[22:24].pending == 1).all()


def check_resolution_then_original_floor_ratchet():
    b, e = conflict_fixture()
    bar(b, 22, close=103., high=104., low=102., volume=100.)
    event(e, 22, 1, 99.)
    r, _ = response_frame(b, e)
    assert r.iloc[22].resolved == 1 and r.iloc[22].entered == 1
    assert np.isclose(r.iloc[22].floor, 99.)
    event(e, 22, 1, 96.)
    r, _ = response_frame(b, e)
    assert np.isclose(r.iloc[22].floor, 98.)


def check_active_structure_ignores_volume_conflict():
    b, e = fixture()
    event(e, 19, -1, 100.)
    event(e, 20, 1, 97.)
    bar(b, 21, volume=1000.)
    event(e, 22, -1, 101.)
    bar(b, 22, close=98.5, high=101., low=98., volume=1000.)
    event(e, 23, 1, 98.)
    r, ledger = response_frame(b, e)
    assert (r.iloc[20:24].target == 1).all()
    assert r.iloc[21:24].created.sum() == r.iloc[21:24].exited.sum() == 0
    assert np.isclose(r.iloc[23].floor, 98.) and ledger.empty


def check_floor_failure_has_priority_and_missing_volume_does_not_hide_it():
    b, e = fixture()
    event(e, 19, -1, 100.)
    event(e, 20, 1, 97.)
    bar(b, 21, close=96., high=101., low=95., volume=np.nan)
    event(e, 21, 1, 95.)
    r, _ = response_frame(b, e)
    assert r.iloc[21].exited == 1 and r.iloc[21].target == 0
    assert r.iloc[21].entered == r.iloc[21].created == 0
    b.iloc[21, b.columns.get_loc("volume")] = 1000.
    r, _ = response_frame(b, e)
    assert r.iloc[21].exited == 1 and r.iloc[21].created == 0


def check_direct_breakout_needs_no_retest():
    b, e = fixture()
    event(e, 20, -1, 100.)
    bar(b, 21, close=103., high=104., low=101., volume=1000.)
    event(e, 21, 1, 98.)
    r, _ = response_frame(b, e)
    assert r.iloc[21].created == 0 and r.iloc[21].entered == 1
    assert r.iloc[21].entry_kind == "original_event"


def check_downside_attempt_and_dual_attempt():
    b, e = fixture()
    event(e, 18, -1, 100.)
    event(e, 19, 1, 97.)
    bar(b, 20, close=96., high=99., low=95., volume=100.)
    bar(b, 21, close=98., high=99., low=96., volume=200.)
    r, ledger = response_frame(b, e)
    assert r.iloc[21].created == 1
    assert ledger.iloc[0].attempt == "down_not_retained"
    # A bar can test both sides; preserve ambiguity instead of picking a side.
    bar(b, 21, close=98., high=101., low=96., volume=200.)
    r, ledger = response_frame(b, e)
    assert ledger.iloc[0].attempt == "both"


def check_same_price_different_volume_and_all_conflicts_control():
    b, e = conflict_fixture()
    event(e, 21, 1, 97.)
    low = b.copy()
    low.iloc[21, low.columns.get_loc("volume")] = 100.
    high_result, _ = response_frame(b, e)
    low_result, _ = response_frame(low, e)
    all_result, _ = response_frame(low, e, mode="all")
    none_result, _ = response_frame(b, e, mode="none")
    assert high_result.iloc[21].target == 0 and low_result.iloc[21].target == 1
    assert all_result.iloc[21].target == 0 and none_result.iloc[21].target == 1


def check_zero_range_and_pending_no_timeout():
    b, e = conflict_fixture()
    bar(b, 22, close=99., high=99., low=99., volume=1000.)
    r, ledger = response_frame(b, e)
    assert r.iloc[22].created == r.iloc[22].resolved == 0
    assert r.iloc[-1].pending == 1 and ledger.iloc[0].outcome == 0


def check_prefix_and_future_forks():
    b, e = conflict_fixture()
    event(e, 21, 1, 97.)
    bar(b, 25, close=103., high=104., low=102., volume=100.)
    full, ledger = response_frame(b, e)
    for n in range(1, len(b) + 1):
        cut, cut_ledger = response_frame(b.iloc[:n], e.iloc[:n])
        assert_frame_equal(cut, full.iloc[:n], check_dtype=False)
        if len(cut_ledger):
            known = ledger[ledger.created_date <= str(b.index[n-1].date())].copy()
            future = known.resolved_date.notna() & (known.resolved_date > str(b.index[n-1].date()))
            known.loc[future, "resolved_date"] = None
            known.loc[future, "outcome"] = 0
            assert_frame_equal(cut_ledger, known.reset_index(drop=True), check_dtype=False)
    fork = b.copy()
    bar(fork, 25, close=97., high=98., low=96., volume=1000.)
    opposite, _ = response_frame(fork, e)
    assert_frame_equal(full.iloc[:25], opposite.iloc[:25], check_dtype=False)
    assert full.iloc[25].resolved == 1 and opposite.iloc[25].resolved == -1


def check_price_and_volume_units():
    b, e = conflict_fixture()
    event(e, 21, 1, 97.)
    bar(b, 24, close=103., high=104., low=102., volume=100.)
    a, _ = response_frame(b, e)
    scaled = b.copy()
    scaled[["open", "high", "low", "close"]] *= 7.3
    scaled.volume *= 10000.
    scaled.attrs["source_first_close"] *= 7.3
    scaled_events = e.copy()
    scaled_events.confirmed_pivot += np.log(7.3)
    scaled_events.attrs["source_first_close"] *= 7.3
    other, _ = response_frame(scaled, scaled_events)
    for col in ["target", "entered", "exited", "created", "resolved", "blocked_price_event"]:
        assert np.array_equal(a[col], other[col]), col
    for col in ["floor", "pending_high", "pending_low", "reference_peak", "reference_trough"]:
        assert np.allclose(a[col] * 7.3, other[col], equal_nan=True), col
    assert np.allclose(a.volume_ratio, other.volume_ratio, equal_nan=True)


def check_none_identity_against_original_synthetic_detector():
    t = np.arange(280)
    c = 100. * np.exp(.02 * np.sin(t / 3.) + .005 * np.sin(t / 13.)
                      + .001 * np.minimum(t, 140) - .0015 * np.maximum(t - 140, 0))
    # Deliberately revisit exact prior prices to exercise equality invalidation.
    c[180:190] = [95., 96., 97., 96., 95., 94., 95., 96., 95., 94.]
    v = 100. * (1 + .3 * np.sin(t / 7.))
    idx = pd.date_range("2001-01-01", periods=len(c))
    close, volume = pd.Series(c, index=idx), pd.Series(v, index=idx)
    original = event_frame(close, volume)
    b = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * .99,
                      "close": c, "volume": v}, index=idx)
    b.attrs["source_first_close"] = float(c[0])
    exact = attach_exact_pivots(b, original)
    replay, _ = response_frame(b, exact, mode="none")
    for col in ["target", "entered", "exited"]:
        assert np.array_equal(replay[col], original[col]), col
    assert np.allclose(replay.floor, np.exp(original.structure_floor), equal_nan=True)
    for n in (65, 103, 181, 230):
        prefix_events = event_frame(close.iloc[:n], volume.iloc[:n])
        prefix_exact = attach_exact_pivots(b.iloc[:n], prefix_events)
        prefix, _ = response_frame(b.iloc[:n], prefix_exact, mode="none")
        assert_frame_equal(prefix, replay.iloc[:n], check_dtype=False)


def check_absolute_pivot_input_is_rejected():
    b, e = conflict_fixture()
    try:
        response_frame(b, e.drop(columns="confirmed_pivot_relative"))
    except ValueError as error:
        assert "attach_exact_pivots" in str(error)
    else:
        raise AssertionError("absolute-only pivot input must be rejected")


def check_missing_and_inconsistent_origins_are_rejected():
    b, e = conflict_fixture()
    missing = b.copy()
    missing.attrs.clear()
    for invalid in (missing, b.copy()):
        if invalid.attrs:
            invalid.attrs["source_first_close"] = 100.
        try:
            response_frame(invalid, e)
        except ValueError:
            pass
        else:
            raise AssertionError("missing or inconsistent coordinate origins must be rejected")


def check_exact_floor_touch_with_adapter_and_price_units():
    values = np.r_[100. + .1 * np.sin(np.arange(80)), [98., 99., 100., 98.]]
    idx = pd.date_range("2002-01-01", periods=len(values))
    for scale in (1., 7.3, 1000.):
        c = values * scale
        b = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * .99,
                          "close": c, "volume": 100.}, index=idx)
        b.attrs["source_first_close"] = float(c[0])
        original = event_frame(b.close, b.volume)
        exact = attach_exact_pivots(b, original)
        result, _ = response_frame(b, exact, mode="none")
        assert original.iloc[-1].exited == 1, "fixture must touch an active floor"
        assert result.iloc[-1].exited == 1, scale
        for col in ("target", "entered", "exited"):
            assert np.array_equal(result[col], original[col]), (scale, col)
        for t in np.flatnonzero(original.event.to_numpy()):
            pivot_index = t - int(original.iloc[t].pivot_age)
            expected = np.log(b.close.iloc[pivot_index] / b.close.iloc[0])
            assert exact.iloc[t].confirmed_pivot_relative == expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise SystemExit(f"Refuse overwrite: {args.output}")
    results = []
    for name, function in sorted(globals().copy().items()):
        if name.startswith("check_") and callable(function):
            try:
                function()
                results.append({"test": name, "passed": True})
            except Exception as exc:
                results.append({"test": name, "passed": False,
                                "error": repr(exc), "traceback": traceback.format_exc()})
    base = Path(__file__).resolve().parent
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Independent synthetic-only state/causality audit; no real candidate or account execution",
        "passed": all(r["passed"] for r in results),
        "test_count": len(results), "results": results,
        "sha256": {name: hashlib.sha256((base / name).read_bytes()).hexdigest()
                   for name in ("volume_response.py", "baseline_event_structure.py",
                                "test_response_independent.py")},
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(exist_ok=True, parents=True)
        with args.output.open("x") as f:
            f.write(text)
    print(text)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
