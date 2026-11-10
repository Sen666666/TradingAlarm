"""Finite synthetic PH1 risk/partial-fill cases, using the real Decimal ledger.

Only Account class definitions are extracted from adapter sources.  setup/run
are never called, and no historical data is prepared or replayed.
"""
import ast
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research_rounds/pvr-act-comparison-20261027/code'))
import experiment as P
from test_sector_account import quote, window, T, RULE, FREE
from sector_account import QuantityRule, FeeComponent, FeeSchedule

SOURCES = [OUT / 'code/study.py', ROOT / 'research_rounds/strict-entry-fast-support-20261027/code/study.py',
           Path(P.E.__file__), Path(P.E.ledger.__file__)]


def class_from_file(path, env):
    tree = ast.parse(path.read_text(), filename=str(path))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'Account')
    mod = ast.Module(body=[node], type_ignores=[])
    exec(compile(mod, str(path), 'exec'), env)
    return env['Account']


Parent = class_from_file(SOURCES[1], {'E': P.E})
Account = class_from_file(SOURCES[0], dict(Parent=Parent, D=D, replace=replace,
                                          risk_sizing=True, variant='R_PH', exit_policy='PH'))


class Facts:
    def __init__(self, floor, factor=1):
        self.f, self.k = D(str(floor)), D(str(factor))
    def floor(self, *args): return self.f
    def factor(self, *args): return self.k
    def row(self, *args): return SimpleNamespace(i_buy=True, segment_id='synthetic')


def account(floor=9, cash=1000000):
    a = Account(initial_cash=cash)
    a.mode = 'S'; a.facts = Facts(floor); a.current_nav = D(cash)
    return a


def reserve(a, price=10, budget=150000, fees=FREE, rule=RULE):
    c = P.E.admission.Clock(T, T+timedelta(days=1), T.date())
    return a.reserve_budget(quote=quote(price=price, fees=fees, rule=rule), clock=c,
                            gross_budget_cny=D(budget))


def fill(a, raw=10, capacity=10**8, n=1, fees=FREE, rule=RULE):
    price = D(str(raw)) * (1 + D('.0005') * a.cost_multiplier)
    return a.fill_buy('A', window(price=raw, execution_price=price, capacity=capacity,
                                 at=T+timedelta(days=1, minutes=n), eid=f'event-{n}',
                                 fees=fees, rule=rule))


def frozen(a):
    return next(iter(a.intents.values()))


class RiskEdges(unittest.TestCase):
    def test_far_support_limits_nominal_loss_includes_sell_slippage(self):
        a = account(floor=100)
        self.assertTrue(reserve(a, price=115)[0])
        self.assertEqual(a.buys['A'].target_shares, 600)
        fill(a, raw=115)
        check = [r for r in a.audit_log if r['kind'] == 'ph_risk_fill_check'][-1]
        self.assertEqual(check['nominal_loss'], D('9064.5000'))
        self.assertEqual(D(check['R_a']), D(10000))

    def test_up_gap_can_only_reduce_shares(self):
        a = account()
        self.assertTrue(reserve(a)[0])
        before = a.buys['A'].target_shares
        receipt = fill(a, raw=12)
        self.assertLess(receipt.shares, before)
        self.assertLessEqual([r for r in a.audit_log if r['kind'] == 'ph_risk_fill_check'][-1]['nominal_loss'], D(10000))

    def test_down_gap_does_not_expand_frozen_target(self):
        a = account()
        reserve(a)
        before = a.buys['A'].target_shares
        receipt = fill(a, raw=9.5)
        self.assertEqual(receipt.shares, before)

    def test_partial_risk_consumption_is_cumulative(self):
        a = account()
        reserve(a)
        first = fill(a, capacity=5000)
        self.assertEqual(first.shares, 5000)
        state = dict(a.ph_states['A'])
        order = a.buys['A']
        independent_new_budget_cap = a.risk_cap(order.quote, order.remaining_shares, D('12.006'), D(9), D(10000))
        second = fill(a, raw=12, n=2)
        self.assertLess(second.shares, independent_new_budget_cap)
        self.assertEqual(a.ph_states['A']['entry_at'], state['entry_at'])
        self.assertEqual(a.ph_states['A']['cycle_id'], state['cycle_id'])
        self.assertEqual(a.ph_states['A']['R_a'], state['R_a'])
        check = [r for r in a.audit_log if r['kind'] == 'ph_risk_fill_check'][-1]
        self.assertLessEqual(check['nominal_loss'], D(10000))
        self.assertEqual(check['filled_shares'], first.shares + second.shares)

    def test_partial_gross_budget_not_granted_twice(self):
        a = account(floor=9.99)
        reserve(a, budget=15000)
        first = fill(a, capacity=700)
        second = fill(a, raw=12, n=2)
        self.assertLessEqual(first.gross_cny + second.gross_cny, D(frozen(a)['budget']))
        self.assertLessEqual(a.quantity('A'), 1499)

    def test_minimum_quantity_is_not_forced_when_risk_too_small(self):
        a = account(floor=1, cash=1000)
        ok, _ = reserve(a, budget=150, price=10)
        self.assertFalse(ok)
        self.assertFalse(a.buys)
        self.assertEqual(a.available, D(1000))

    def test_non_100_minimum_and_committed_partial_remainder(self):
        rule = QuantityRule('synthetic-200-step1', 200, 1, 1, True, 1)
        a = account()
        self.assertTrue(reserve(a, budget=2490, rule=rule)[0])
        target = a.buys['A'].target_shares
        self.assertEqual(target, 248)
        first = fill(a, capacity=200, rule=rule)
        second = fill(a, n=2, rule=rule)
        self.assertEqual((first.shares, second.shares), (200, 48))
        self.assertEqual(a.quantity('A'), target)

    def test_minimum_fee_once_per_order_and_counted_in_nominal_loss(self):
        fees = FeeSchedule('synthetic-minimum', (FeeComponent('commission', D('.000001'), D('5')),))
        rule = QuantityRule('synthetic-200-step1', 200, 1, 1, True, 1)
        a = account()
        reserve(a, budget=2490, fees=fees, rule=rule)
        first = fill(a, capacity=200, fees=fees, rule=rule)
        second = fill(a, n=2, fees=fees, rule=rule)
        self.assertEqual((first.fees_cny, second.fees_cny), (D(5), D(0)))
        check = [r for r in a.audit_log if r['kind'] == 'ph_risk_fill_check'][-1]
        expected = (first.gross_cny + second.gross_cny) + D(5) - D(248) * D('8.9955') + D(5)
        self.assertEqual(check['nominal_loss'], expected)

    def test_cash_including_fees_and_other_reservations(self):
        fees = FeeSchedule('synthetic-minimum', (FeeComponent('commission', D('.000001'), D('5')),))
        a = account(floor=9.999, cash=2000)
        # Actual available cash can be less than NAV because another order is reserved.
        a.available = D(1100)
        self.assertTrue(reserve(a, budget=1500, fees=fees)[0])
        receipt = fill(a, fees=fees)
        self.assertLessEqual(receipt.gross_cny + receipt.fees_cny, D(1100))
        self.assertGreaterEqual(a.available, 0)

    def test_open_at_support_cancels_and_releases_reservation(self):
        a = account()
        reserve(a)
        self.assertIsNone(fill(a, raw=9))
        self.assertFalse(a.positions)
        self.assertFalse(a.buys)
        self.assertEqual(a.available, D(1000000))

    def test_down_gap_after_partial_cancels_remaining_without_reset(self):
        a = account()
        reserve(a)
        first = fill(a, capacity=100)
        state = dict(a.ph_states['A'])
        self.assertIsNone(fill(a, raw=8, n=2))
        self.assertFalse(a.buys)
        self.assertEqual(a.quantity('A'), first.shares)
        self.assertEqual(a.ph_states['A'], state)

    def test_one_percent_nominal_is_not_actual_gap_loss_limit(self):
        a = account(floor=100)
        reserve(a, price=115)
        bought = fill(a, raw=115)
        c = P.E.admission.Clock(T+timedelta(days=2), T+timedelta(days=3), (T+timedelta(days=2)).date())
        a.request_exit(quote(price=105), c)
        sold = a.fill_exit('A', window(price=90, execution_price=D('89.955'), at=T+timedelta(days=3), eid='sell-gap'))
        loss = bought.gross_cny + bought.fees_cny - sold.gross_cny + sold.fees_cny
        self.assertGreater(loss, D(frozen(a)['risk_budget']))
        self.assertEqual(loss, D('15061.5000'))
        self.assertFalse(a.ph_states)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RiskEdges)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    report = dict(scope='synthetic real Decimal ledger, no historical/account replay', passed=result.wasSuccessful(),
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES + [Path(__file__).resolve()]},
                  details=output.getvalue())
    target = OUT / 'risk-tests.json'
    if target.exists():
        raise RuntimeError('risk-tests.json exists; preserve previous evidence')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('passed', 'tests_run', 'failures', 'errors')}))
    if not result.wasSuccessful():
        print(output.getvalue())
    raise SystemExit(0 if result.wasSuccessful() else 1)
