"""Synthetic and existing-history checks for the independent ranking output.

No candidate trend model, numeric module, portfolio or account runner is read or
imported. Results go to a fresh JSON file and never overwrite prior evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import platform
import sys
import traceback
import unittest

import numpy as np
import pandas as pd

from data_utils import load_inputs, sha256
from ranking import EXCLUDED, POOL_MEMBERS, RANK_DECIMALS, rank_frames


BASE = Path(__file__).resolve().parents[1]


def make_frame(rate, n=330):
    index = pd.bdate_range("2020-01-01", periods=n, name="date")
    return pd.DataFrame({
        "close": 10.0 * np.exp(rate * np.arange(n)),
        "volume": np.linspace(100, 200, n),
        "target": np.arange(n) % 2,
    }, index=index)


def compare(left, right):
    pd.testing.assert_frame_equal(
        left, right, check_dtype=True, check_freq=False,
        check_exact=False, atol=1e-12, rtol=1e-12,
    )


class RankingTests(unittest.TestCase):
    def test_four_segment_formula_and_253_observations(self):
        frame = make_frame(.001)
        result = rank_frames({"600059.SH": frame})["600059.SH"]
        self.assertTrue(result.rs_score.iloc[:252].isna().all())
        self.assertAlmostEqual(result.rs_score.iloc[252], np.exp(.001 * 63) - 1)
        self.assertTrue(result.rank_score.isna().all())
        self.assertEqual(int(result.peer_count.iloc[251]), 0)
        self.assertEqual(int(result.peer_count.iloc[252]), 1)
        c = frame.close
        expected = (
            .4 * (c / c.shift(63) - 1)
            + .2 * (c.shift(63) / c.shift(126) - 1)
            + .2 * (c.shift(126) / c.shift(189) - 1)
            + .2 * (c.shift(189) / c.shift(252) - 1)
        )
        pd.testing.assert_series_equal(result.rs_score, expected, check_names=False)

    def test_fixed_pools_exclusion_and_single_peer(self):
        frames = {
            "600059.SH": make_frame(-.001), "600917.SH": make_frame(.001),
            "HK00002": make_frame(-.02), "HK00700": make_frame(-.01),
            "USHJ510300": make_frame(.02), "USHJ512480": make_frame(.03),
            "HK03033": make_frame(.10), "URFI881129": make_frame(.50),
        }
        result = rank_frames(frames)
        self.assertEqual(result["600059.SH"].rank_score.iloc[-1], 0.)
        self.assertEqual(result["600917.SH"].rank_score.iloc[-1], 1.)
        self.assertEqual(result["HK00002"].rank_score.iloc[-1], 0.)
        self.assertEqual(result["HK00700"].rank_score.iloc[-1], 1.)
        self.assertEqual(result["USHJ510300"].rank_score.iloc[-1], 0.)
        self.assertTrue(result["HK03033"].rank_score.isna().all())
        self.assertEqual(result["HK03033"].peer_count.iloc[-1], 1)
        self.assertTrue(result["URFI881129"].rank_score.isna().all())
        self.assertTrue(result["URFI881129"].peer_count.eq(0).all())
        self.assertTrue(result["URFI881129"].pool.eq("excluded").all())
        self.assertTrue(np.isfinite(result["URFI881129"].rs_score.iloc[-1]))

    def test_average_ties_and_predeclared_comparison_grid(self):
        a = make_frame(0.)
        b, c = a.copy(), a.copy()
        b.loc[b.index[-1], "close"] *= 1 + 1e-13
        c.loc[c.index[-1], "close"] *= 1.01
        result = rank_frames({"600059.SH": a, "600917.SH": b, "600919.SH": c})
        self.assertNotEqual(result["600059.SH"].rs_score.iloc[-1], result["600917.SH"].rs_score.iloc[-1])
        self.assertEqual(result["600059.SH"].rank_score.iloc[-1], .25)
        self.assertEqual(result["600917.SH"].rank_score.iloc[-1], .25)
        self.assertEqual(result["600919.SH"].rank_score.iloc[-1], 1.)
        for frame in result.values():
            self.assertEqual(frame.rank_score.iloc[252], .5)

    def test_missing_peer_date_is_not_forward_filled(self):
        a, b, c = make_frame(-.001), make_frame(.002), make_frame(.001)
        b = b.iloc[:-1]
        result = rank_frames({"600059.SH": a, "600917.SH": b, "600919.SH": c})
        last = a.index[-1]
        self.assertNotIn(last, result["600917.SH"].index)
        self.assertEqual(result["600059.SH"].peer_count.loc[last], 2)
        self.assertEqual(result["600919.SH"].rank_score.loc[last], 1.)
        self.assertEqual(result["600919.SH"].rank_score.iloc[-2], .5)

    def test_invalid_close_excluded_from_price_clock_without_fill(self):
        a = make_frame(.001, n=254)
        a.loc[a.index[0], "close"] = np.nan
        result = rank_frames({"600059.SH": a})["600059.SH"]
        self.assertTrue(result.rs_score.iloc[:253].isna().all())
        self.assertTrue(np.isfinite(result.rs_score.iloc[253]))
        a.loc[a.index[-1], "close"] = 0
        self.assertTrue(rank_frames({"600059.SH": a})["600059.SH"].rs_score.isna().all())

    def test_synthetic_prefixes(self):
        frames = {"600059.SH": make_frame(-.001), "600917.SH": make_frame(.001)}
        expected = rank_frames(frames)
        for cut in (100, 253, 329):
            actual = rank_frames({symbol: f.iloc[:cut].copy() for symbol, f in frames.items()})
            for symbol in frames:
                compare(actual[symbol], expected[symbol].iloc[:cut])

    def test_unit_scales_and_independence_from_other_columns(self):
        frames = {"600059.SH": make_frame(-.001), "600917.SH": make_frame(.001)}
        expected = rank_frames(frames)
        for factor in (7., 11.):
            changed = {}
            for i, (symbol, frame) in enumerate(frames.items()):
                x = frame[["close"]].copy()
                x["close"] *= factor * (i + 1)
                changed[symbol] = x
            actual = rank_frames(changed)
            for symbol in frames:
                compare(actual[symbol], expected[symbol])
        corrupt = {}
        for symbol, frame in frames.items():
            x = frame.copy()
            x["volume"] = "deliberately unavailable"
            x["target"] = None
            x["state"] = "opposite"
            corrupt[symbol] = x
        actual = rank_frames(corrupt)
        for symbol in frames:
            compare(actual[symbol], expected[symbol])

    def test_no_input_mutation(self):
        frame = make_frame(.001)
        original = frame.copy(deep=True)
        rank_frames({"600059.SH": frame})
        pd.testing.assert_frame_equal(frame, original)

    def test_invalid_universe_or_dates_rejected(self):
        with self.assertRaises(ValueError):
            rank_frames({"unknown": make_frame(.001)})
        with self.assertRaises(ValueError):
            rank_frames({"600059.SH": make_frame(.001).iloc[::-1]})
        frame = make_frame(.001)
        duplicate = pd.concat([frame, frame.iloc[-1:]])
        with self.assertRaises(ValueError):
            rank_frames({"600059.SH": duplicate})

    def test_empty_symbol_or_empty_mapping(self):
        self.assertEqual(rank_frames({}), {})
        result = rank_frames({"600059.SH": make_frame(.001).iloc[:0]})["600059.SH"]
        self.assertTrue(result.empty)
        self.assertEqual(list(result), ["rs_score", "rank_score", "peer_count", "pool"])
        self.assertEqual(str(result.peer_count.dtype), "int64")


def actual_checks():
    frames, _, _ = load_inputs(BASE)
    full = rank_frames(frames)
    rows = []

    def check(kind, symbol, action, **metadata):
        item = {"test": kind, "symbol": symbol, **metadata}
        try:
            action()
            item["passed"] = True
        except Exception as exc:
            item.update(passed=False, error=type(exc).__name__, message=str(exc)[:10000])
        rows.append(item)

    dates = pd.DatetimeIndex(sorted(set().union(*(set(frame.index) for frame in frames.values()))))
    # Common dates across all pools preserve the same-date peer opportunity set.
    cutoffs = [dates[len(dates) // 3 - 1], dates[2 * len(dates) // 3 - 1], dates[-2]]
    for cutoff in cutoffs:
        prefix = rank_frames({symbol: f.loc[:cutoff].copy() for symbol, f in frames.items()})
        for symbol in frames:
            check(
                "real_common_date_prefix", symbol,
                lambda s=symbol: compare(prefix[s], full[s].loc[:cutoff]),
                cutoff=str(cutoff.date()), dtype_checked=True,
            )
    changed = {}
    for i, (symbol, frame) in enumerate(frames.items()):
        value = frame[["close"]].copy()
        value["close"] *= 7.0
        # Adding arbitrary columns cannot affect a close-only module.
        value["volume"] = 11.0
        value["target"] = -1000
        changed[symbol] = value
    scaled = rank_frames(changed)
    for symbol in frames:
        check("real_price_times7_other_inputs_irrelevant", symbol,
              lambda s=symbol: compare(scaled[s], full[s]), dtype_checked=True)
    summary = [{
        "symbol": symbol, "observations": len(value),
        "score_available": int(value.rs_score.notna().sum()),
        "rank_available": int(value.rank_score.notna().sum()),
        "pool": str(value.pool.iloc[-1]),
        "maximum_peer_count": int(value.peer_count.max()),
    } for symbol, value in full.items()]
    return rows, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refuse overwrite: {args.output}")
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RankingTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    checks, summary = actual_checks()
    forbidden = ("numeric", "participation_response", "volume_response", "campaign_engine", "run_study")
    assert not any(name in sys.modules for name in forbidden)
    record = {
        "started_utc": started, "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "Independent price ranking only; no candidate trend or account execution",
        "ranking_sha256": sha256(BASE / "code/ranking.py"),
        "test_sha256": sha256(Path(__file__)),
        "data_utils_sha256": sha256(BASE / "code/data_utils.py"),
        "input_manifest_sha256": sha256(BASE / "inputs/manifest.json"),
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "formula": "0.4*(C/C63-1)+0.2*(C63/C126-1)+0.2*(C126/C189-1)+0.2*(C189/C252-1)",
        "comparison_policy": {
            "decimals": RANK_DECIMALS, "method": "round comparison key to 12 decimals; ascending average rank",
            "mapping": "(rank-1)/(n-1) if n>=2; otherwise NaN",
            "reported_rs_score": "unrounded",
            "limitations": "Finite specified scale checks, not proof of exact invariance for all floating-point scales.",
        },
        "pools": POOL_MEMBERS, "excluded": sorted(EXCLUDED),
        "synthetic_tests": result.testsRun,
        "synthetic_failures": [{"test": str(test), "traceback": trace} for test, trace in result.failures],
        "synthetic_errors": [{"test": str(test), "traceback": trace} for test, trace in result.errors],
        "real_checks": checks, "real_summary": summary,
        "passed": result.wasSuccessful() and all(row["passed"] for row in checks),
        "account_runs": 0, "candidate_runs": 0, "network_requests": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(args.output), "passed": record["passed"],
        "synthetic_tests": result.testsRun, "real_checks": len(checks),
        "real_failed": sum(not row["passed"] for row in checks),
    }))
    return int(not record["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
