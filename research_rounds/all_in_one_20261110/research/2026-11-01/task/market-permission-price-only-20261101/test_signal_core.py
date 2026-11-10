"""Synthetic-only tests. No historical adapter or project import."""
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from signal_core import (A, K, S_FLOOR, VERSION, Observation, Source, State,
                         SemanticDecisionRequired, dumps, loads, run, scale_from_prior, step)

HERE = Path(__file__).resolve().parent
SRC = Source("synthetic-fixed-roster", "synthetic-price", "signed-m-fixture", "v1")


def observations(prices, breadths=None, source=SRC, offset=0):
    breadths = [.8] * len(prices) if breadths is None else breadths
    return tuple(Observation(f"{i + offset:06d}", source, price, breadth)
                 for i, (price, breadth) in enumerate(zip(prices, breadths)))


def warm():
    return observations([100 * math.exp(.01 * (i % 2)) for i in range(64)], [.5] * 64)


def series(tail, breadths=None):
    return warm() + observations(tail, breadths, offset=64)


def trace(seq, scope="global:synthetic"):
    state = State(scope=scope)
    states, decisions = [], []
    for observation in seq:
        state, decision = step(state, observation)
        states.append(state)
        decisions.append(decision)
    return states, decisions


class PermissionTests(unittest.TestCase):
    def test_fast_break_start_without_five_day_wait(self):
        states, ds = trace(series([110]))
        self.assertEqual(states[-2].mode, "WAIT")
        self.assertEqual(states[-1].mode, "ACTIVE")
        self.assertTrue(ds[-1].permit_next_open)
        self.assertEqual(ds[-1].events, ("break_started",))
        self.assertEqual(states[-1].credit, 0)
        self.assertIsNone(ds[-1].line_used)
        self.assertAlmostEqual(ds[-1].next_line, 110 * math.exp(-K * 1.4826 * .01))

    def test_single_jump_then_flat_does_not_reuse_credit(self):
        states, ds = trace(series([110, 120] + [120] * 12))
        self.assertEqual(sum("price_advance" in d.events for d in ds), 1)
        self.assertEqual(states[-1].credit, 0)
        self.assertEqual(len({s.line for s in states[-13:]}), 1)

    def test_persistent_gradual_rise_accumulates_new_frontier(self):
        states, ds = trace(series([110 * math.exp(.01 * i) for i in range(13)]))
        self.assertGreaterEqual(sum("price_advance" in d.events for d in ds), 3)
        active_lines = [s.line for s in states if s.mode == "ACTIVE"]
        self.assertEqual(active_lines, sorted(active_lines))
        self.assertIn("price_advance", ds[68].events)

    def test_repair_below_old_high_and_new_line_next_observation(self):
        states, ds = trace(series([110, 125, 114, 112, 116]))
        self.assertEqual([s.mode for s in states[-5:]], ["ACTIVE", "ACTIVE", "REPAIR", "REPAIR", "ACTIVE"])
        self.assertEqual(states[-2].anchor, 112)
        self.assertEqual(states[-2].credit, 0)
        self.assertEqual(states[-2].scale, states[-3].scale)
        self.assertFalse(ds[-1].original_break)
        self.assertTrue(ds[-1].permit_next_open)
        self.assertLess(116, max(s.frontier or 0 for s in states[:-1]))
        self.assertLess(ds[-1].next_line, ds[-1].line_used)
        self.assertEqual(states[-1].repairs, 1)

    def test_adverse_lagging_positive_breadth_bear_bounce_can_false_repair(self):
        states, ds = trace(series([110, 125, 114, 118, 100, 90], [.8, .8, .8, .8, .8, .4]))
        self.assertIn("repair_restored", ds[-3].events)
        self.assertTrue(ds[-3].permit_next_open)
        self.assertEqual(states[-2].mode, "REPAIR")
        self.assertEqual(states[-1].mode, "ENDED")
        self.assertEqual(states[-1].failures, 2)

    def test_double_failure_then_bounce_requires_new_break(self):
        states, ds = trace(series([110, 125, 114, 118, 100, 90, 95, 100, 110],
                                 [.8, .8, .8, .8, .8, .4, .9, .9, .9]))
        self.assertEqual(states[-1].failures, 2)
        self.assertTrue(all(s.mode == "ENDED" for s in states[-4:]))
        self.assertFalse(any(d.permit_next_open for d in ds[-4:]))
        restarted, d = step(states[-1], Observation("000100", SRC, 130, .9))
        self.assertEqual(restarted.mode, "ACTIVE")
        self.assertEqual(d.events, ("break_started",))

    def test_breadth_strict_threshold_and_temporary_weakness(self):
        state, _ = run(series([110]), "global:synthetic")
        for b in (.6, math.nextafter(.6, 0), None):
            n, d = step(state, Observation("000065", SRC, 111, b))
            self.assertEqual(n.mode, "ACTIVE")
            self.assertFalse(d.permit_next_open)
            self.assertEqual(n.anchor, state.anchor)
        n, d = step(state, Observation("000065", SRC, 111, math.nextafter(.6, 1)))
        self.assertTrue(d.permit_next_open)
        for b, expected in [(.6, "ENDED"), (math.nextafter(.6, 1), "REPAIR")]:
            n, d = step(state, Observation("000065", SRC, 90, b))
            self.assertEqual(n.mode, expected)
            self.assertFalse(d.permit_next_open)

    def test_no_same_close_reopen_even_if_original_break_is_true(self):
        # A formerly high effective line plus an aged-out 63-high can coincide
        # with a fresh rolling BREAK. Failure must still win on ACTIVE input.
        state, _ = run(series([110]), "global:synthetic")
        state = replace(state, line=120, previous_close=100, prior_closes=(100,) * 63)
        n, d = step(state, Observation("000065", SRC, 110, .9))
        self.assertTrue(d.original_break)
        self.assertEqual(n.mode, "REPAIR")
        self.assertEqual(n.credit, 0)
        self.assertFalse(d.permit_next_open)
        self.assertNotIn("repair_restored", d.events)

    def test_global_weak_industry_strong_are_independent(self):
        _, global_ds = run(series([110, 111], [.3, .3]), "global:synthetic")
        _, sector_ds = run(series([110, 111], [.97, .96]), "industry:semiconductor:synthetic")
        self.assertFalse(global_ds[-1].permit_next_open)
        self.assertTrue(sector_ds[-1].permit_next_open)
        self.assertEqual(global_ds[-1].mode, "WAIT")

    def test_account_histories_are_not_signal_inputs(self):
        seq = series([110, 125, 114, 118, 100, 90], [.8, .8, .8, .8, .8, .4])
        histories = [dict(cash=1_000_000, position=0, nav_drawdown=0),
                     dict(cash=0, position=80, nav_drawdown=.9)]
        signals = [run(seq, "global:synthetic") for _unused in histories]
        self.assertEqual(signals[0], signals[1])

    def test_unknown_price_denies_preserves_and_does_not_bridge_return(self):
        state, _ = run(series([110]), "global:synthetic")
        n, d = step(state, Observation("000065", SRC, None, .9))
        self.assertEqual((n.mode, n.line, n.anchor, n.frontier), (state.mode, state.line, state.anchor, state.frontier))
        self.assertFalse(d.permit_next_open)
        self.assertEqual(n.prior_abs_returns, state.prior_abs_returns)
        n2, d2 = step(n, Observation("000066", SRC, 90, .9))
        self.assertEqual(n2.mode, "REPAIR")
        self.assertEqual(n2.failures, 1)
        self.assertEqual(n2.prior_abs_returns, n.prior_abs_returns)

    def test_unknown_breadth_preserves_observed_price_progress(self):
        state, _ = run(series([110]), "global:synthetic")
        n, d = step(state, Observation("000065", SRC, 125, None))
        self.assertIn("price_advance", d.events)
        self.assertFalse(d.permit_next_open)
        self.assertGreater(n.line, state.line)

    def test_unknown_breach_is_explicit_blocker_without_mutation(self):
        state, _ = run(series([110]), "global:synthetic")
        checkpoint = dumps(state)
        with self.assertRaises(SemanticDecisionRequired) as error:
            step(state, Observation("000065", SRC, 90, None))
        self.assertEqual(checkpoint, dumps(state))
        receipt = json.loads(json.dumps(error.exception.evidence, allow_nan=False))
        self.assertTrue(receipt['observed_failure'])
        self.assertFalse(receipt['permit_next_open'])
        self.assertEqual(receipt['observed_close'], 90)
        self.assertEqual(receipt['failed_old_line'], state.line)
        self.assertEqual(receipt['failures_including_blocked_receipt'], state.failures + 1)

    def test_invalid_numbers_never_become_positive_evidence(self):
        state, _ = run(series([110]), "global:synthetic")
        for x in (0, -1, math.nan, math.inf, True):
            _, d = step(state, Observation("000065", SRC, x, .9))
            self.assertFalse(d.permit_next_open)
            self.assertIn("price", d.unknown)
        for x in (-.1, 1.1, math.nan, math.inf, True):
            _, d = step(state, Observation("000065", SRC, 111, x))
            self.assertFalse(d.permit_next_open)
            self.assertIn("breadth", d.unknown)

    def test_source_change_ends_context_and_rewarms_without_cross_credit(self):
        state, _ = run(series([110, 125, 114]), "global:synthetic")
        other = replace(SRC, universe="synthetic-other-universe")
        n, d = step(state, Observation("000067", other, 1000, .99))
        self.assertEqual(n.mode, "ENDED")
        self.assertEqual(n.failures, state.failures)
        self.assertEqual(n.last_failure_at, state.last_failure_at)
        self.assertEqual(n.prior_closes, (1000,))
        self.assertEqual(n.prior_abs_returns, ())
        self.assertFalse(d.permit_next_open)
        for i in range(68, 131):
            n, _ = step(n, Observation(f"{i:06d}", other, 1000, .99))
        n, d = step(n, Observation("000131", other, 1100, .99))
        self.assertTrue(d.permit_next_open)
        self.assertEqual(n.starts, 2)

    def test_repair_known_weak_breadth_ends_even_when_price_unknown(self):
        state, _ = run(series([110, 90]), "global:synthetic")
        n, d = step(state, Observation("000066", SRC, None, .6))
        self.assertEqual(n.mode, "ENDED")
        self.assertFalse(d.permit_next_open)
        self.assertEqual(n.failures, state.failures)

    def test_scale_prior_only_and_frozen_with_exact_formula(self):
        self.assertEqual(scale_from_prior((0,) * 63), S_FLOOR)
        self.assertIsNone(scale_from_prior((.01,) * 62))
        self.assertAlmostEqual(scale_from_prior((.01,) * 63), 1.4826 * .01)
        states, ds = trace(series([110, 125]))
        self.assertAlmostEqual(ds[-2].scale_before_close, 1.4826 * .01)
        self.assertAlmostEqual(ds[-1].next_line, 125 * math.exp(-K * states[-2].scale))
        self.assertEqual(states[-1].scale, ds[-1].scale_before_close)

    def test_frontier_credit_equals_displacement_and_no_range_recycling(self):
        states, ds = trace(series([110, 111, 110, 111, 110, 111]))
        s = states[-1]
        self.assertAlmostEqual(s.credit, math.log(s.frontier / s.anchor))
        self.assertAlmostEqual(s.credit, math.log(111 / 110))
        self.assertEqual(sum("price_advance" in d.events for d in ds), 0)

    def test_old_line_checked_before_new_line_is_created(self):
        state, _ = run(series([110]), "global:synthetic")
        n, d = step(state, Observation("000065", SRC, 125, .8))
        self.assertEqual(d.line_used, state.line)
        self.assertGreater(d.next_line, d.line_used)
        n2, d2 = step(n, Observation("000066", SRC, 110, .8))
        self.assertEqual(d2.line_used, d.next_line)
        self.assertEqual(n2.mode, "REPAIR")

    def test_equal_line_is_not_strict_breach(self):
        state, _ = run(series([110]), "global:synthetic")
        n, d = step(state, Observation("000065", SRC, state.line, .8))
        self.assertEqual(n.mode, "ACTIVE")
        self.assertTrue(d.permit_next_open)

    def test_checkpoint_resume_every_cut_matches_uninterrupted(self):
        seq = series([110, 125, 114, 112, 116, None, 120, 100, 90, 100, 130],
                     [.8, .8, .8, .8, .8, .8, None, .8, .4, .9, .9])
        expected_state, expected_ds = run(seq, "global:synthetic")
        for cut in range(len(seq) + 1):
            s, head = run(seq[:cut], "global:synthetic")
            s = loads(dumps(s))
            tail = []
            for o in seq[cut:]:
                s, d = step(s, o)
                tail.append(d)
            self.assertEqual(s, expected_state)
            self.assertEqual(head + tuple(tail), expected_ds)
        with self.assertRaises(ValueError):
            loads(dumps(expected_state).replace(VERSION, "incompatible"))

    def test_duplicate_or_out_of_order_input_is_rejected(self):
        s, _ = run(series([110]), "global:synthetic")
        for at in (s.last_at, "000000"):
            with self.assertRaises(ValueError):
                step(s, Observation(at, SRC, 111, .9))

    def test_physical_prefix_in_fresh_process_has_no_future_file(self):
        rng = random.Random(824)
        prices = [110]
        for _ in range(23):
            prices.append(prices[-1] * math.exp(rng.choice([-.08, -.02, .01, .04])))
        seq = series(prices, [.8 if i % 7 else .4 for i in range(len(prices))])
        _, expected = run(seq, "global:synthetic")
        with tempfile.TemporaryDirectory(prefix="physical-prefix-", dir=HERE) as tmp:
            root = Path(tmp)
            for cut in (0, 1, 63, 64, 65, 68, 74, len(seq)):
                p = root / f"only-prefix-{cut}.json"
                p.write_text(json.dumps([asdict(o) for o in seq[:cut]], allow_nan=False))
                result = subprocess.run([sys.executable, "-B", str(HERE / "synthetic_runner.py"), str(p)],
                                        capture_output=True, text=True, check=True)
                actual = json.loads(result.stdout)
                self.assertEqual(actual["decisions"], json.loads(json.dumps([asdict(d) for d in expected[:cut]])))
                self.assertEqual(actual["observations_read"], cut)


if __name__ == "__main__":
    unittest.main(verbosity=2)
