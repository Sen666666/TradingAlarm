"""Synthetic PH1 contract cases only; never reads historical market data."""
from copy import deepcopy
from datetime import datetime, date
import hashlib
import io
import json
from pathlib import Path
import unittest

from phase_policy import step, compare, _ARITH


def initial(**changes):
    state = dict(phase="TRIAL", P=100., L_star=None, E_entry=100.,
                 entry_at="2025-01-02T09:30:00+08:00")
    state.update(changes)
    return state


def observation(**changes):
    obs = dict(at="2025-01-10T15:00:00+08:00", close=116., E=100., E_prev=100.,
               E_up=False, pivot=None, pivot_at=None, F_up=False, F_pivot=None,
               F_pivot_at=None, risk_on=True, original_up=True, exit_pending=False)
    obs.update(changes)
    return obs


def maturity(**changes):
    return observation(E=106., E_prev=100., E_up=True, pivot=106.,
                       pivot_at="2025-01-03T15:00:00+08:00", **changes)


class PhasePolicyTests(unittest.TestCase):
    def test_flat_no_market_requirement(self):
        self.assertEqual(step({"phase": "FLAT"}, {}, "PH")["state"], {"phase": "FLAT"})

    def test_no_fact_no_raise(self):
        self.assertEqual(step(initial(), observation(), "PH")["state"], initial())

    def test_input_is_not_mutated(self):
        state, obs = initial(), maturity()
        old = deepcopy((state, obs))
        step(state, obs, "PH")
        self.assertEqual((state, obs), old)

    def test_trial_f_raises(self):
        result = step(initial(), observation(F_up=True, F_pivot=108., F_pivot_at="2025-01-02"), "PH")
        self.assertEqual(result["state"]["P"], 108.)
        self.assertTrue(result["diagnostic"]["F_applied"])

    def test_f_before_entry_day_is_not_eligible(self):
        result = step(initial(), observation(F_up=True, F_pivot=108., F_pivot_at="2025-01-01"), "PH")
        self.assertEqual(result["state"]["P"], 100.)
        self.assertFalse(result["diagnostic"]["F_eligible"])

    def test_f_same_entry_date_is_eligible_even_date_only(self):
        result = step(initial(), observation(F_up=True, F_pivot=108., F_pivot_at=date(2025, 1, 2)), "F")
        self.assertEqual(result["state"]["P"], 108.)

    def test_f_never_lowers_protection(self):
        result = step(initial(P=110.), observation(F_up=True, F_pivot=108., F_pivot_at="2025-01-03"), "F")
        self.assertEqual(result["state"]["P"], 110.)

    def test_exit_at_exact_old_protection_before_m_and_f(self):
        result = step(initial(P=108.), maturity(close=108., F_up=True, F_pivot=111., F_pivot_at="2025-01-04"), "PH")
        self.assertEqual(result["state"]["phase"], "EXIT_PENDING")
        self.assertEqual(result["state"]["P"], 108.)
        self.assertFalse(result["diagnostic"]["handoff"])

    def test_exit_below_old_protection(self):
        self.assertEqual(step(initial(P=108.), maturity(close=107.), "PH")["diagnostic"]["exit_reason"], "protection")

    def test_act_exit_without_new_support(self):
        self.assertEqual(step(initial(), observation(risk_on=False, E=None), "PH")["diagnostic"]["exit_reason"], "ACT")

    def test_e0_invalid_exit_without_new_support(self):
        self.assertEqual(step(initial(), observation(original_up=False, E=None), "PH")["diagnostic"]["exit_reason"], "E0")

    def test_explicit_locked_exit_has_priority(self):
        result = step(initial(), observation(exit_pending=True, risk_on=False, original_up=False, E=None), "PH")
        self.assertEqual(result["diagnostic"]["exit_causes"], ["locked", "ACT", "E0"])
        self.assertEqual(result["diagnostic"]["exit_reason"], "locked")

    def test_pending_never_cancels(self):
        state = initial(phase="EXIT_PENDING", P=108.)
        self.assertEqual(step(state, maturity(), "PH")["state"], state)

    def test_m_before_same_day_f_freezes_bridge(self):
        result = step(initial(P=108.), maturity(F_up=True, F_pivot=111., F_pivot_at="2025-01-04"), "PH")
        self.assertEqual(result["state"]["phase"], "BRIDGE")
        self.assertEqual(result["state"]["P"], 108.)
        self.assertEqual(result["state"]["L_star"], 108.)
        self.assertFalse(result["diagnostic"]["F_applied"])

    def test_m_can_transition_directly_to_trend(self):
        result = step(initial(), maturity(), "PH")
        self.assertEqual(result["state"]["phase"], "TREND")
        self.assertEqual(result["state"]["L_star"], 106.)

    def test_m_allows_entry_day_closing_pivot_with_exact_ordering(self):
        obs = maturity()
        obs["pivot_at"] = "2025-01-02T15:00:00+08:00"
        self.assertTrue(step(initial(), obs, "PH")["diagnostic"]["handoff"])

    def test_date_only_entry_day_pivot_does_not_prove_later(self):
        obs = maturity()
        obs["pivot_at"] = "2025-01-02"
        self.assertFalse(step(initial(), obs, "PH")["diagnostic"]["handoff"])

    def test_pivot_equal_entry_timestamp_not_later(self):
        obs = maturity()
        obs["pivot_at"] = initial()["entry_at"]
        self.assertFalse(step(initial(), obs, "PH")["diagnostic"]["handoff"])

    def test_prior_entry_pivot_blocks_m_but_e0_support_still_raises(self):
        obs = maturity()
        obs["pivot_at"] = "2025-01-01T15:00:00+08:00"
        result = step(initial(), obs, "PH")
        self.assertFalse(result["diagnostic"]["handoff"])
        self.assertEqual(result["state"]["P"], 106.)

    def test_pivot_must_exceed_entry_support(self):
        obs = maturity()
        obs["pivot"] = 100.
        self.assertFalse(step(initial(), obs, "PH")["diagnostic"]["handoff"])

    def test_original_support_must_actually_rise(self):
        obs = maturity()
        obs["E_prev"] = 106.
        self.assertFalse(step(initial(), obs, "PH")["diagnostic"]["handoff"])

    def test_original_up_event_is_required(self):
        obs = maturity()
        obs["E_up"] = False
        self.assertFalse(step(initial(), obs, "PH")["diagnostic"]["handoff"])

    def test_m_does_not_require_profit(self):
        # Entry price is deliberately not a policy input; an entry at 115 can
        # hand off at 110 when its original support rises from 100 to 106.
        self.assertTrue(step(initial(P=108.), maturity(close=110.), "PH")["diagnostic"]["handoff"])

    def test_bridge_does_not_accept_new_f(self):
        state = initial(phase="BRIDGE", P=108., L_star=108.)
        result = step(state, observation(E=106., E_prev=106., F_up=True, F_pivot=111., F_pivot_at="2025-01-04"), "PH")
        self.assertEqual(result["state"], state)

    def test_e0_catches_bridge_floor_to_trend(self):
        state = initial(phase="BRIDGE", P=108., L_star=108.)
        result = step(state, observation(E=108., E_prev=106.), "PH")
        self.assertEqual(result["state"]["phase"], "TREND")
        self.assertEqual(result["state"]["P"], 108.)
        self.assertEqual(result["state"]["L_star"], 108.)

    def test_e0_above_bridge_floor_raises_protection(self):
        state = initial(phase="BRIDGE", P=108., L_star=108.)
        result = step(state, observation(E=110., E_prev=106.), "PH")
        self.assertEqual(result["state"]["phase"], "TREND")
        self.assertEqual(result["state"]["P"], 110.)

    def test_trend_never_restarts_f_or_trial(self):
        state = initial(phase="TREND", P=110., L_star=108.)
        result = step(state, observation(E=110., E_prev=110., F_up=True, F_pivot=114., F_pivot_at="2025-01-04"), "PH")
        self.assertEqual(result["state"], state)

    def test_f_mode_ignores_m_and_keeps_f(self):
        result = step(initial(P=108.), maturity(F_up=True, F_pivot=111., F_pivot_at="2025-01-04"), "F")
        self.assertEqual(result["state"]["phase"], "TRIAL")
        self.assertEqual(result["state"]["P"], 111.)
        self.assertIsNone(result["state"]["L_star"])

    def test_support_tie_retains_old_scalar(self):
        near = 100.00000000000001
        self.assertEqual(compare(100., near), 0)
        self.assertEqual(step(initial(), observation(E=near), "PH")["state"]["P"], 100.)

    def test_close_tie_exits(self):
        self.assertTrue(step(initial(), observation(close=100.00000000000001), "PH")["diagnostic"]["exit_required"])

    def test_missing_current_support_is_error_not_ffill(self):
        with self.assertRaises((TypeError, ValueError)):
            step(initial(), observation(E=None), "PH")

    def test_missing_event_flag_is_error(self):
        with self.assertRaises(ValueError):
            step(initial(), observation(F_up=None), "PH")

    def test_future_pivot_is_rejected(self):
        obs = maturity()
        obs["pivot_at"] = "2025-01-11T15:00:00+08:00"
        with self.assertRaises(ValueError):
            step(initial(), obs, "PH")

    def test_live_e0_support_decline_is_rejected(self):
        with self.assertRaises(ValueError):
            step(initial(), observation(E=99.), "PH")

    def test_mixed_timestamp_timezones_are_rejected(self):
        obs = maturity()
        obs["pivot_at"] = "2025-01-03T15:00:00"
        with self.assertRaises(ValueError):
            step(initial(), obs, "PH")

    def test_unknown_policy_and_phase_are_rejected(self):
        with self.assertRaises(ValueError):
            step(initial(), observation(), "other")
        with self.assertRaises(ValueError):
            step(initial(phase="other"), observation(), "PH")

    def test_sequence_preserves_frozen_handoff_and_protection(self):
        state = initial()
        events = [observation(F_up=True, F_pivot=108., F_pivot_at="2025-01-03"),
                  maturity(F_up=True, F_pivot=111., F_pivot_at="2025-01-04"),
                  observation(E=106., E_prev=106., F_up=True, F_pivot=112., F_pivot_at="2025-01-05"),
                  observation(E=110., E_prev=106.),
                  observation(E=110., E_prev=110., F_up=True, F_pivot=114., F_pivot_at="2025-01-06"),
                  observation(E=110., E_prev=110., close=109.)]
        states = []
        for obs in events:
            state = step(state, obs, "PH")["state"]
            states.append(deepcopy(state))
        self.assertEqual([s["phase"] for s in states], ["TRIAL", "BRIDGE", "BRIDGE", "TREND", "TREND", "EXIT_PENDING"])
        self.assertEqual([s["P"] for s in states], [108., 108., 108., 110., 110., 110.])
        self.assertEqual([s["L_star"] for s in states], [None, 108., 108., 108., 108., 108.])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PhasePolicyTests)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    root = Path(__file__).resolve().parents[1]
    source_paths = [Path(__file__).resolve(), Path(__file__).with_name("phase_policy.py"), _ARITH]
    report = {"scope": "synthetic phase policy only; no historical/account run", "passed": result.wasSuccessful(),
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "sources": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
              "details": stream.getvalue()}
    target = root / "tests.json"
    if target.exists():
        raise RuntimeError("tests.json already exists; preserve prior evidence")
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("passed", "tests_run", "failures", "errors")}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
