"""Independent synthetic checks of the participation mechanism; no accounts.

Only numeric.py and participation.py are imported. No saved market history or
candidate results are read. Output is exclusive-create so prior failures remain.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import traceback
import unittest

import numpy as np
import pandas as pd

from numeric import compare, event_frame_numeric
from participation import participation_frame


BASE = Path(__file__).resolve().parents[1]
WARM = 26


def bar(close, volume=100.0, low=None, high=None, opening=None):
    return dict(open=close if opening is None else opening,
                high=close + 1 if high is None else high,
                low=close - 1 if low is None else low,
                close=close, volume=volume)


def fixture(tail, confirmations=None, warm=WARM, ready=True):
    bars = pd.DataFrame([bar(100.0) for _ in range(warm)] + tail,
                        index=pd.bdate_range("2020-01-01", periods=warm + len(tail),
                                             name="date")).astype(float)
    events = pd.DataFrame({
        "event": 0.0,
        "leg_direction": -1.0 if ready else np.nan,
        "confirmed_pivot_price": np.nan,
    }, index=bars.index)
    for offset, pivot in (confirmations or {}).items():
        events.loc[bars.index[warm + offset], ["event", "confirmed_pivot_price"]] = [1, pivot]
    return bars, events


def run(tail, confirmations=None, mode="volume", **kwargs):
    bars, events = fixture(tail, confirmations, **kwargs)
    state, ledger = participation_frame(bars, events, mode)
    return state.iloc[kwargs.get("warm", WARM):], ledger


def assert_frames(left, right):
    pd.testing.assert_frame_equal(left, right, check_dtype=True, check_freq=False,
                                  check_exact=False, atol=1e-10, rtol=1e-10)


def ledger_asof(full, n, last_date):
    """Project full ledger to facts knowable at a prefix, preserving its schema."""
    result = full.loc[full.created_observation.lt(n)].copy().reset_index(drop=True)
    future = result.resolved_date.isna() | result.resolved_date.gt(str(last_date.date()))
    result.loc[future, "resolved_date"] = pd.NA
    result.loc[future, "outcome"] = "open"
    for col in ("response", "independent_entry", "original_entry_same_day"):
        result.loc[future, col] = 0
    result.loc[future, "resolution_volume_ratio"] = None
    result.loc[future, "waiting_observations"] = (
        n - 1 - result.loc[future, "created_observation"]
    )
    return result


class ParticipationTests(unittest.TestCase):
    def test_same_price_different_volume_reclaim_below_event_high(self):
        tail = [bar(96, 300, low=94, high=101), bar(100.5, low=96, high=100.8)]
        high, ledger = run(tail)
        low_tail = [dict(tail[0], volume=100), tail[1]]
        low, low_ledger = run(low_tail)
        self.assertEqual(high.created.tolist(), [1, 0])
        self.assertEqual(high.independent_entry.tolist(), [0, 1])
        self.assertEqual(high.floor.iloc[1], 94)
        self.assertLess(tail[1]["close"], tail[0]["high"])
        self.assertEqual(low.target.tolist(), [0, 0])
        self.assertTrue(low_ledger.empty)
        self.assertEqual(ledger.outcome.iloc[0], "reclaimed")
        self.assertEqual(ledger.waiting_observations.iloc[0], 1)

    def test_q_inclusive_and_previous_21_positive_observations(self):
        state, _ = run([bar(96, 200)])
        self.assertEqual(state.created.iloc[0], 1)
        below, _ = run([bar(96, 199.9)])
        self.assertEqual(below.created.iloc[0], 0)
        twenty, _ = run([bar(96, 300)], warm=20)
        twenty_one, _ = run([bar(96, 300)], warm=21)
        self.assertEqual(twenty.created.iloc[0], 0)
        self.assertEqual(twenty_one.created.iloc[0], 1)
        bars, events = fixture([bar(96, 300)])
        bars.loc[bars.index[-2], "volume"] = np.nan
        state, _ = participation_frame(bars, events)
        self.assertEqual(state.created.iloc[-1], 0)
        self.assertTrue(pd.isna(state.volume_ratio.iloc[-1]))

    def test_creation_requires_numeric_upstream_readiness(self):
        bars, events = fixture([bar(96, 300), bar(95, 300)], ready=False)
        events.loc[bars.index[-1], "leg_direction"] = -1
        state, ledger = participation_frame(bars, events)
        self.assertEqual(state.created.iloc[-2:].tolist(), [0, 1])
        self.assertEqual(ledger.reclaim.iloc[0], 96)

    def test_only_declines_create_not_high_volume_flat_or_up(self):
        for close in (100.0, 101.0):
            state, ledger = run([bar(close, 300)])
            self.assertEqual(state.created.iloc[0], 0)
            self.assertTrue(ledger.empty)

    def test_h_equals_l_gap_down_is_valid_price_fact(self):
        state, ledger = run([bar(96, 300, low=96, high=96), bar(101)])
        self.assertEqual(state.created.iloc[0], 1)
        self.assertEqual(state.independent_entry.iloc[1], 1)
        self.assertEqual(ledger.lower.iloc[0], 96)

    def test_ordinary_volume_rejection_destroys_memory(self):
        state, ledger = run([bar(96, 300, low=94), bar(93), bar(101)])
        self.assertEqual(state.response.tolist(), [0, -1, 0])
        self.assertEqual(state.created.tolist(), [1, 0, 0])
        self.assertEqual(state.target.tolist(), [0, 0, 0])
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger.outcome.iloc[0], "rejected")

    def test_reject_then_high_volume_creates_new_independent_id(self):
        state, ledger = run([bar(96, 300, low=94),
                             bar(93, 300, low=92), bar(97)])
        self.assertEqual(state.created.tolist(), [1, 1, 0])
        self.assertEqual(state.pending_id.iloc[:2].tolist(), [1, 2])
        self.assertEqual(state.ended_id.iloc[1], 1)
        self.assertEqual(state.target.tolist(), [0, 0, 1])
        self.assertEqual(ledger.id.tolist(), [1, 2])
        self.assertEqual(ledger.outcome.tolist(), ["rejected", "reclaimed"])
        self.assertEqual(ledger.reclaim.tolist(), [100, 96])
        self.assertEqual(ledger.lower.tolist(), [94, 92])
        self.assertEqual(state.floor.iloc[2], 92)
        self.assertLess(97, ledger.reclaim.iloc[0])

    def test_unresolved_high_volume_does_not_replace_or_accumulate(self):
        state, ledger = run([bar(96, 300, low=94),
                             bar(95, 400, low=94.5), bar(99), bar(101)])
        self.assertEqual(state.created.tolist(), [1, 0, 0, 0])
        self.assertEqual(state.pending_reclaim.iloc[:3].tolist(), [100, 100, 100])
        self.assertEqual(state.pending_lower.iloc[:3].tolist(), [94, 94, 94])
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger.event_volume.iloc[0], 300)

    def test_original_confirmation_consumes_pending_without_waiting(self):
        state, ledger = run([bar(96, 300, low=94), bar(99)], {1: 95})
        self.assertEqual(state.target.tolist(), [0, 1])
        self.assertEqual(state.floor.iloc[1], 95)
        self.assertEqual(state.consumed_by_base.iloc[1], 1)
        self.assertEqual(state.independent_entry.iloc[1], 0)
        self.assertEqual(ledger.outcome.iloc[0], "base_confirmed")
        self.assertEqual(ledger.response.iloc[0], 0)

    def test_original_has_priority_when_reclaim_also_true(self):
        state, ledger = run([bar(96, 300, low=94), bar(101)], {1: 97})
        self.assertEqual(state.response.iloc[1], 1)
        self.assertEqual(state.floor.iloc[1], 97)
        self.assertEqual(state.independent_entry.iloc[1], 0)
        self.assertEqual(state.entry_kind.iloc[1], "original_event")
        self.assertEqual(ledger.outcome.iloc[0], "base_confirmed")
        self.assertEqual(ledger.original_entry_same_day.iloc[0], 1)

    def test_original_still_opens_on_old_event_rejection(self):
        state, ledger = run([bar(96, 300, low=94), bar(93, 300, low=92)], {1: 90})
        self.assertEqual(state.target.iloc[1], 1)
        self.assertEqual(state.floor.iloc[1], 90)
        self.assertEqual(state.created.iloc[1], 0)
        self.assertEqual(ledger.outcome.iloc[0], "rejected")
        self.assertEqual(ledger.original_entry_same_day.iloc[0], 1)

    def test_exit_day_records_but_cannot_reenter_even_with_original_event(self):
        state, ledger = run([bar(100), bar(90, 300, low=89), bar(101)],
                            {0: 90, 1: 85})
        self.assertEqual(state.target.tolist(), [1, 0, 1])
        self.assertEqual(state.entered.tolist(), [1, 0, 1])
        self.assertEqual(state.exited.tolist(), [0, 1, 0])
        self.assertEqual(state.created.tolist(), [0, 1, 0])
        self.assertEqual(ledger.created_on_exit.iloc[0], 1)
        self.assertEqual(ledger.reclaim.iloc[0], 100)
        self.assertEqual(state.floor.iloc[2], 89)

    def test_existing_structure_ignores_new_volume_and_down_events(self):
        bars, events = fixture([bar(100), bar(96, 400, low=94), bar(95), bar(99)],
                                {0: 90})
        events.loc[bars.index[-2], "event"] = -1
        state, ledger = participation_frame(bars, events)
        self.assertEqual(state.target.iloc[-4:].tolist(), [1, 1, 1, 1])
        self.assertEqual(state.floor.iloc[-4:].tolist(), [90] * 4)
        self.assertEqual(state.created.sum(), 0)
        self.assertTrue(ledger.empty)

    def test_original_floor_ratchets_and_price_failure_ignores_missing_volume(self):
        state, _ = run([bar(100), bar(101), bar(94, np.nan)],
                        {0: 90, 1: 95})
        self.assertEqual(state.floor.tolist(), [90, 95, 95])
        self.assertEqual(state.exited.tolist(), [0, 0, 1])
        self.assertEqual(state.target.tolist(), [1, 1, 0])

    def test_missing_zero_infinite_volume_do_not_create(self):
        for volume in (np.nan, 0.0, np.inf):
            state, ledger = run([bar(96, volume, low=94)])
            self.assertEqual(state.created.iloc[0], 0)
            self.assertTrue(ledger.empty)

    def test_missing_volume_can_reclaim_or_reject(self):
        for close, response, target in ((101, 1, 1), (93, -1, 0)):
            state, ledger = run([bar(96, 300, low=94), bar(close, np.nan)])
            self.assertEqual(state.response.iloc[1], response)
            self.assertEqual(state.target.iloc[1], target)
            self.assertTrue(pd.isna(ledger.resolution_volume_ratio.iloc[0]))

    def test_equal_boundaries_and_intraday_crossings_do_not_respond(self):
        state, ledger = run([bar(96, 300, low=94),
                             bar(100, high=102, low=93),
                             bar(94, high=102, low=93),
                             bar(101)])
        self.assertEqual(state.response.tolist(), [0, 0, 0, 1])
        self.assertEqual(state.pending.tolist(), [1, 1, 1, 0])
        self.assertEqual(ledger.waiting_observations.iloc[0], 3)

    def test_declared_compare_policy_controls_ties(self):
        self.assertEqual(compare(np.nextafter(100.0, np.inf), 100.0), 0)
        self.assertEqual(compare(np.nextafter(94.0, 0), 94.0), 0)
        state, _ = run([bar(96, 300, low=94),
                        bar(np.nextafter(100.0, np.inf)),
                        bar(np.nextafter(94.0, 0)),
                        bar(100.1)])
        self.assertEqual(state.response.tolist(), [0, 0, 0, 1])
        for close in (100.0, np.nextafter(100.0, 0)):
            state, _ = run([bar(close, 300)])
            self.assertEqual(state.created.iloc[0], 0)

    def test_no_expiry_and_no_blocking_after_long_wait(self):
        tail = [bar(96, 300, low=94)] + [bar(98) for _ in range(180)] + [bar(99)]
        state, ledger = run(tail, {181: 95})
        self.assertEqual(state.pending.iloc[:181].sum(), 181)
        self.assertEqual(state.target.iloc[-1], 1)
        self.assertEqual(ledger.waiting_observations.iloc[0], 181)
        self.assertEqual(ledger.outcome.iloc[0], "base_confirmed")

    def test_no_same_day_creation_response_or_future_high_use(self):
        state, ledger = run([bar(96, 300, low=94, high=110)])
        self.assertEqual(state.target.iloc[0], 0)
        self.assertEqual(state.response.iloc[0], 0)
        self.assertEqual(state.pending.iloc[0], 1)
        self.assertEqual(ledger.outcome.iloc[0], "open")

    def test_all_mode_removes_only_new_volume_gate(self):
        tail = [bar(96, 100, low=94), bar(101)]
        candidate, _ = run(tail)
        all_declines, ledger = run(tail, mode="all")
        disabled, _ = run(tail, mode="none")
        self.assertEqual(candidate.target.tolist(), [0, 0])
        self.assertEqual(disabled.target.tolist(), [0, 0])
        self.assertEqual(all_declines.target.tolist(), [0, 1])
        self.assertEqual(ledger.volume_ratio.iloc[0], 1)

    def test_none_and_constant_new_volume_restore_numeric_base(self):
        n = 240
        index = pd.bdate_range("2020-01-01", periods=n, name="date")
        close = 100 * np.exp(.07 * np.sin(np.arange(n) / 7) + .0004 * np.arange(n))
        volume = np.where(np.arange(n) % 17 == 0, 400., 100.)
        bars = pd.DataFrame(dict(open=close, high=close * 1.01, low=close * .99,
                                 close=close, volume=volume), index=index)
        events = event_frame_numeric(bars.close, bars.volume)
        self.assertGreater(events.entered.sum(), 2)
        disabled, ledger = participation_frame(bars, events, "none")
        constant, constant_ledger = participation_frame(bars.assign(volume=100.), events)
        for state in (disabled, constant):
            for column in ("target", "entered", "exited"):
                np.testing.assert_array_equal(state[column], events[column])
            np.testing.assert_allclose(state.floor, events.structure_floor_price,
                                       equal_nan=True, atol=1e-10, rtol=1e-10)
        self.assertTrue(ledger.empty)
        self.assertTrue(constant_ledger.empty)

    def test_input_contract_rejections(self):
        bars, events = fixture([bar(96, 300)])
        for bad_bars, bad_events, mode in (
            (bars, events, "bad"),
            (bars.iloc[::-1], events, "volume"),
            (pd.concat([bars, bars.iloc[[-1]]]), events, "volume"),
            (bars, events.drop(columns="confirmed_pivot_price"), "volume"),
        ):
            with self.assertRaises(ValueError):
                participation_frame(bad_bars, bad_events, mode)

    def prefix_fixture(self):
        tail = [
            bar(96, 300, low=94), bar(98), bar(101), bar(93, 300, low=92),
            bar(91, 300, low=90), bar(94), bar(89), bar(88, 300, low=86),
            bar(89), bar(85), bar(84, 300, low=82), bar(83),
        ]
        return fixture(tail, {8: 87})

    def test_all_state_columns_prefix_values_and_types(self):
        bars, events = self.prefix_fixture()
        for mode in ("volume", "all", "none"):
            full, _ = participation_frame(bars, events, mode)
            for n in range(1, len(bars) + 1):
                prefix, _ = participation_frame(bars.iloc[:n], events.iloc[:n], mode)
                assert_frames(prefix, full.iloc[:n])

    def test_all_ledger_columns_prefix_values_and_types(self):
        bars, events = self.prefix_fixture()
        issues = []
        for mode in ("volume", "all"):
            _, full = participation_frame(bars, events, mode)
            for n in range(1, len(bars) + 1):
                _, prefix = participation_frame(bars.iloc[:n], events.iloc[:n], mode)
                try:
                    assert_frames(prefix.reset_index(drop=True),
                                  ledger_asof(full, n, bars.index[n - 1]))
                except AssertionError as error:
                    issues.append(dict(mode=mode, prefix=n, error=str(error)))
        self.assertFalse(issues, json.dumps(issues[:12], ensure_ascii=False, indent=2)
                         + f"\nTotal failing prefixes: {len(issues)}")

    def test_nonempty_open_ledger_types_do_not_depend_on_future_resolution(self):
        bars, events = fixture([bar(96, 300, low=94), bar(98), bar(101)])
        _, full = participation_frame(bars, events)
        n = WARM + 1
        _, prefix = participation_frame(bars.iloc[:n], events.iloc[:n])
        assert_frames(prefix, ledger_asof(full, n, bars.index[n - 1]))

    def test_common_prefix_with_opposite_futures(self):
        first = [bar(96, 300, low=94), bar(98)]
        up_bars, up_events = fixture(first + [bar(101)])
        down_bars, down_events = fixture(first + [bar(93)])
        n = WARM + len(first)
        up_state, up_ledger = participation_frame(up_bars, up_events)
        down_state, down_ledger = participation_frame(down_bars, down_events)
        assert_frames(up_state.iloc[:n], down_state.iloc[:n])
        assert_frames(ledger_asof(up_ledger, n, up_bars.index[n - 1]),
                      ledger_asof(down_ledger, n, down_bars.index[n - 1]))

    def test_price_and_volume_units_on_frozen_mechanism(self):
        bars, events = self.prefix_fixture()
        full_state, full_ledger = participation_frame(bars, events)
        for price_scale, volume_scale in ((7., 11.), (.1, .01)):
            scaled_bars, scaled_events = bars.copy(), events.copy()
            scaled_bars[["open", "high", "low", "close"]] *= price_scale
            scaled_bars.volume *= volume_scale
            scaled_events.confirmed_pivot_price *= price_scale
            state, ledger = participation_frame(scaled_bars, scaled_events)
            for col in ("floor", "pending_reclaim", "pending_lower"):
                state[col] /= price_scale
            for col in ("reclaim", "lower", "event_open", "event_high", "event_close"):
                ledger[col] /= price_scale
            for col in ("event_volume", "volume_baseline"):
                ledger[col] /= volume_scale
            assert_frames(state, full_state)
            assert_frames(ledger, full_ledger)


class Results(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append(dict(test=test.id().split(".")[-1], passed=True))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append(dict(test=test.id().split(".")[-1], passed=False,
                                 error="".join(traceback.format_exception(*err))))

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append(dict(test=test.id().split(".")[-1], passed=False,
                                 error="".join(traceback.format_exception(*err))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite prior evidence: {args.output}")
    result = Results()
    unittest.defaultTestLoader.loadTestsFromTestCase(ParticipationTests).run(result)
    files = ["participation.py", "numeric.py", "tests_participation.py"]
    payload = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "synthetic mechanism and prefix checks; no historical candidate or accounts",
        "python": platform.python_version(), "pandas": pd.__version__,
        "tests_run": result.testsRun,
        "passed": sum(record["passed"] for record in result.records),
        "failed": sum(not record["passed"] for record in result.records),
        "account_calls": 0,
        "code_sha256": {name: hashlib.sha256((BASE / "code" / name).read_bytes()).hexdigest()
                        for name in files},
        "state_prefix_checks": 3 * (WARM + 12),
        "ledger_prefix_checks": 2 * (WARM + 12),
        "results": result.records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({key: payload[key] for key in
                      ("tests_run", "passed", "failed", "account_calls")}))
    for record in result.records:
        if not record["passed"]:
            print(record["test"])
            print(record["error"][-3500:])
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
