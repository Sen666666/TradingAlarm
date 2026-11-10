"""Synthetic technical contracts only. Never opens market data or an account."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

from s_amount import calculate, filter_stocks, _state_step
from s_amount_arithmetic import compare, log_ratio

ROOT = Path(__file__).resolve().parents[3]
ROUND = Path(__file__).resolve().parents[1]


def fixture(tail, amounts=100.0):
    warm = [100 * math.exp(0.01 * (i % 2)) for i in range(65)]
    prices = warm + list(tail)
    amount_tail = [amounts] * len(tail) if np.isscalar(amounts) else list(amounts)
    return pd.DataFrame({"close": prices, "amount": [100.] * 65 + amount_tail,
                         "segment_id": "synthetic-a"},
                        index=pd.date_range("2000-01-01", periods=len(prices)))


def legacy(frame):
    # Execute the unchanged old event source on synthetic constant-volume data.
    cols = ["confirmation", "leg_direction", "developing_extreme", "confirmed_pivot",
            "event", "pivot_age", "developing_extreme_price", "confirmed_pivot_price",
            "confirmed_pivot_date", "developing_extreme_date"]
    ns = dict(math=math, np=np, pd=pd, compare=compare, log_ratio=log_ratio,
              EVENT_COLUMNS=cols, EVENT_DATE_COLUMNS=cols[-2:])
    path = ROOT / "research_rounds/strict-entry-capacity-20261027/code/entry_kernel.py"
    exec(compile(path.read_text(), str(path), "exec"), ns)
    events, _ = ns["entry_events"](frame.assign(volume=100.))
    active, floor = False, math.nan
    rows = []
    for day, r in frame.iterrows():
        exited = False
        if active and compare(float(r.close), floor) <= 0:
            active, exited = False, True
        if events.loc[day, "event"] == 1:
            pivot = float(events.loc[day, "confirmed_pivot_price"])
            if active:
                floor = max(floor, pivot)
            elif not exited:
                active, floor = True, pivot
        rows.append((active, floor if active or exited else math.nan))
    return events, pd.DataFrame(rows, index=frame.index, columns=["target", "floor"])


class Contracts(unittest.TestCase):
    def test_normal_amount_confirms_at_independent_price_threshold(self):
        f = fixture([101, 102, 103, 104])
        z = calculate(f)
        self.assertEqual(z.index[z.event == 1].tolist(), [f.index[-1]])
        self.assertAlmostEqual(z.iloc[-1].threshold, 1.5 * math.sqrt(5) * .01)
        self.assertAlmostEqual(z.iloc[-1].credit, math.log(1.04))
        self.assertEqual(z.iloc[-1].pivot, 100.)

    def test_high_amount_cannot_make_insufficient_price_confirm(self):
        f = fixture([101, 102, 103, 103, 103, 103], [100, 100, 100, 1e6, 1e8, 1e10])
        z = calculate(f)
        self.assertFalse(z.event.any())
        self.assertTrue((z.iloc[-3:].delta_frontier == 0).all())
        self.assertTrue((z.iloc[-3:].credit == z.iloc[-4].credit).all())

    def test_flat_high_amount_cannot_retroactively_fund_low_amount_rise(self):
        f = fixture([101, 102, 103, 104, 104, 104, 106], [25, 25, 25, 25, 1e6, 1e6, 100])
        z = calculate(f)
        self.assertFalse(z.iloc[:-1].event.any())
        self.assertEqual(z.iloc[-1].event, 1)
        self.assertEqual(z.iloc[-2].credit, z.iloc[-4].credit)

    def test_quarter_amount_needs_more_actual_progress(self):
        f = fixture(list(range(101, 109)))
        normal = calculate(f)
        f.loc[f.index[65:], "amount"] = 25.
        low = calculate(f)
        self.assertGreater(low.index[low.event == 1][0], normal.index[normal.event == 1][0])
        self.assertEqual(low.index[low.event == 1][0], f.index[71])
        self.assertAlmostEqual(low.loc[f.index[71], "credit"], math.log(1.07) / 2)

    def test_normal_and_above_normal_amounts_are_capped_at_same_credit(self):
        f = fixture([101, 102, 103, 104, 108, 105, 101, 104, 110])
        a = calculate(f)
        f.loc[f.index[65:], "amount"] = 10000.
        b = calculate(f)
        for column in ["event", "credit", "frontier", "strict_target", "strict_floor"]:
            pd.testing.assert_series_equal(a[column], b[column])

    def test_returning_to_previous_frontier_does_not_mint_credit(self):
        f = fixture([102, 101, 102, 101.5, 102, 103], [100, 1e6, 1e6, 1e6, 1e6, 100])
        z = calculate(f)
        self.assertTrue((z.iloc[66:70].delta_frontier == 0).all())
        self.assertTrue((z.iloc[66:70].credit == z.iloc[65].credit).all())

    def test_decline_amount_does_not_assist_upward_credit(self):
        f = fixture([102, 101, 102, 103, 104])
        a = calculate(f)
        f.iloc[66, f.columns.get_loc("amount")] = 1e12
        b = calculate(f)
        pd.testing.assert_frame_equal(a, b)

    def test_anchor_baseline_excludes_anchor_day_and_remains_frozen(self):
        f = fixture([101] * 25 + [104])
        f.iloc[64, f.columns.get_loc("amount")] = 1e10
        z = calculate(f)
        used = z.iloc[64:]
        self.assertTrue((used.amount_baseline == 100).all())
        self.assertTrue((used.threshold == used.iloc[0].threshold).all())
        self.assertTrue((used.scale == used.iloc[0].scale).all())

    def test_new_low_reanchors_without_carrying_credit(self):
        z = calculate(fixture([102, 101, 99, 100]))
        row = z.iloc[-2]
        self.assertEqual(row.anchor_price, 99)
        self.assertEqual(row.frontier, 0)
        self.assertEqual(row.credit, 0)
        self.assertAlmostEqual(z.iloc[-1].credit, math.log(100 / 99))

    def test_downward_candidate_uses_its_own_frontier_and_resets_after_event(self):
        z = calculate(fixture([101, 102, 103, 104, 103, 102, 101, 100, 99]))
        up = z[z.event == 1].iloc[0]
        down = z[z.event == -1].iloc[0]
        self.assertEqual(up.next_credit, 0)
        self.assertEqual(up.next_frontier, 0)
        self.assertEqual(down.candidate_direction, -1)
        self.assertEqual(down.pivot, 104)
        self.assertAlmostEqual(down.credit, math.log(104 / fixture([101, 102, 103, 104, 103, 102, 101, 100, 99]).loc[down.name, "close"]))
        self.assertEqual(down.next_credit, 0)
        self.assertEqual(down.next_leg_direction, -1)

    def test_old_state_precedence_is_preserved(self):
        self.assertEqual(_state_step(True, 100., 99., 1, 98.), (False, 100., True))
        self.assertEqual(_state_step(True, 100., 105., 1, 99.), (True, 100., False))
        self.assertEqual(_state_step(True, 100., 105., 1, 102.), (True, 102., False))
        self.assertEqual(_state_step(True, 100., 103., -1, 110.), (True, 100., False))

    def test_persistent_state_does_not_add_current_buy_quality_gate(self):
        f = fixture([101, 102, 103, 104, 104, 104], [100, 100, 100, 100, 1e9, 1e9])
        z = calculate(f, pd.Series(True, index=f.index))
        self.assertTrue(z.iloc[-1].strict_buy)
        self.assertEqual(z.iloc[-1].event, 0)
        self.assertEqual(z.iloc[-1].strict_floor, 100)

    def test_original_buy_intersection_and_no_input_mutation(self):
        f = fixture([101, 102, 103, 104, 105])
        before = f.copy(deep=True)
        buy = pd.Series(False, index=f.index)
        buy.iloc[-1] = True
        z = calculate(f, buy)
        self.assertFalse((z.strict_buy & ~buy).any())
        self.assertTrue(z.iloc[-1].strict_buy)
        pd.testing.assert_frame_equal(f, before)

    def test_constant_amount_matches_legacy_s_events_and_state(self):
        f = fixture([101, 102, 104, 108, 105, 103, 104, 107, 110, 106, 101, 98, 101, 105])
        z = calculate(f)
        event, policy = legacy(f)
        np.testing.assert_array_equal(z.event.to_numpy(), event.event.to_numpy())
        np.testing.assert_array_equal(z.strict_target, policy.target)
        np.testing.assert_allclose(z.strict_floor, policy.floor, rtol=0, atol=0, equal_nan=True)

    def test_currency_unit_and_price_scale_invariance(self):
        f = fixture([101, 102, 103, 104, 105, 106, 107], 25)
        a = calculate(f)
        g = f.copy(); g.amount *= 10000; g.close *= 10
        b = calculate(g)
        np.testing.assert_array_equal(a.event, b.event)
        np.testing.assert_array_equal(a.strict_target, b.strict_target)
        for col in ["threshold", "credit", "frontier", "weight"]:
            np.testing.assert_allclose(a[col], b[col], rtol=1e-12, atol=1e-14, equal_nan=True)
        np.testing.assert_allclose(a.strict_floor * 10, b.strict_floor, equal_nan=True)

    def test_every_synthetic_prefix_is_exact(self):
        tail = [100 * math.exp(.015 * i + .035 * math.sin(i)) for i in range(80)]
        f = fixture(tail, [25., 100., 400., 80.] * 20)
        full = calculate(f)
        for n in range(1, len(f) + 1):
            pd.testing.assert_frame_equal(calculate(f.iloc[:n]), full.iloc[:n], check_exact=True)

    def test_missing_invalid_amount_or_price_is_rejected_without_modifying_input(self):
        for column in ["close", "amount"]:
            for bad in [np.nan, 0., -1., np.inf]:
                f = fixture([101, 104]); f.loc[f.index[-1], column] = bad
                before = f.copy(deep=True)
                with self.assertRaises(ValueError):
                    calculate(f)
                pd.testing.assert_frame_equal(f, before)

    def test_empty_input_and_new_source_segment_rewarm(self):
        f = fixture([101, 102, 104, 105])
        self.assertTrue(calculate(f.iloc[:0]).empty)
        f.loc[f.index[-2:], "segment_id"] = "synthetic-b"
        z = calculate(f)
        self.assertFalse(z.iloc[-2:].ready.any())
        self.assertFalse(z.iloc[-2:].strict_target.any())

    def test_invalid_order_segments_and_original_signal_are_rejected(self):
        f = fixture([101, 104])
        cases = [f.iloc[::-1], pd.concat([f.iloc[:1], f])]
        g = f.copy(); g.loc[g.index[1], "segment_id"] = "other"; cases.append(g)
        for frame in cases:
            with self.assertRaises(ValueError): calculate(frame)
        with self.assertRaises(ValueError): calculate(f, pd.Series(True, index=f.index[:-1]))
        with self.assertRaises(ValueError): calculate(f, pd.Series(1, index=f.index))

    def test_adapter_only_changes_buy_allowed_and_never_carries_a_stale_row(self):
        @dataclass(frozen=True)
        class Fact:
            value: bool
            available_at: object = None
            observed_at: object = None
            source_id: str = "original"
        @dataclass(frozen=True)
        class Stock:
            security_id: str
            buy_allowed: Fact
            trend_up: Fact
            floor: float = 93.
            rank: float = 67.
        f = fixture([101, 104])
        z = calculate(f)
        stock = Stock("A", Fact(True), Fact(True))
        clock = SimpleNamespace(decision_at=f.index[-1].to_pydatetime())
        self.assertIs(filter_stocks((stock,), {"A": z}, clock, Fact)[0], stock)
        clock.decision_at = (f.index[-1] + pd.Timedelta(days=1)).to_pydatetime()
        rejected = filter_stocks((stock,), {"A": z}, clock, Fact)[0]
        self.assertFalse(rejected.buy_allowed.value)
        self.assertIs(rejected.trend_up, stock.trend_up)
        self.assertEqual((rejected.floor, rejected.rank), (stock.floor, stock.rank))
        self.assertTrue(stock.buy_allowed.value)
        missing = filter_stocks((stock,), {}, clock, Fact)[0]
        self.assertFalse(missing.buy_allowed.value)
        clock.decision_at = f.index[-1].to_pydatetime()
        for bad in [np.nan, 1, "False"]:
            damaged = z.copy()
            damaged["strict_target"] = damaged.strict_target.astype(object)
            damaged.loc[damaged.index[-1], "strict_target"] = bad
            with self.assertRaises(ValueError):
                filter_stocks((stock,), {"A": damaged}, clock, Fact)
        with self.assertRaises(ValueError):
            filter_stocks((stock,), {"A": pd.concat([z, z.iloc[-1:]])}, clock, Fact)

    def test_old_frozen_sources_and_arithmetic_are_unchanged(self):
        reg = json.loads((ROOT / "research_rounds/sfw3-rs-baseline-20261028/registry.json").read_text())
        for name, expected in reg["source_sha256"].items():
            self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(), expected, name)
        original = ROOT / "research_rounds/pv-strength-b5-20261025/code/arithmetic.py"
        self.assertEqual(original.read_bytes(), (ROUND / "code/s_amount_arithmetic.py").read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise SystemExit("Refuse to overwrite an existing receipt")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    receipt = dict(passed=result.wasSuccessful(), tests=result.testsRun,
                   failures=[(str(t), detail) for t, detail in result.failures],
                   errors=[(str(t), detail) for t, detail in result.errors],
                   synthetic_prefixes=145, historical_signal_runs=0, backtests=0,
                   source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROUND / "code").glob("*.py"))})
    with args.receipt.open("x") as file:
        json.dump(receipt, file, ensure_ascii=False, indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
