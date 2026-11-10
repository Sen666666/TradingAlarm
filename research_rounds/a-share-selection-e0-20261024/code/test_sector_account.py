"""Synthetic accounting contracts. No historical prices or accounts are run."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

import sector_stock_admission as admission
from current_fixed_pool import (PoolLine, HistoricalInputs, SelectionEvidence, decide_current_pool)
from sector_account import (SectorAccount, FXQuote, QuantityRule, FeeComponent, FeeSchedule,
                            DecisionQuote, Mark, FillWindow, FX_BASIS, commit_cutoff)

T = datetime(2020, 1, 2, 7, tzinfo=timezone.utc)
CLOCK = admission.Clock(T, T+timedelta(days=1), T.date())
RULE = QuantityRule('synthetic-100', 100, 100, 100, True, 1)
FREE = FeeSchedule('synthetic-free', ())
MINIMUM = FeeSchedule('synthetic-fees', (FeeComponent('commission', D('.001'), D('5')),))


def fx(rate=1, at=T):
    return FXQuote(D(str(rate)), at, 'synthetic-reference')


def quote(sid='A', price=10, currency='CNY', rate=1, fees=FREE, rule=RULE, issuer=None, sector='G'):
    return DecisionQuote(sid, issuer or sid, sector, currency, D(str(price)), T,
                         fx(rate), rule, fees, 'synthetic-raw-decision')


def window(sid='A', price=10, at=T+timedelta(days=1), capacity=10**8, rate=1,
           fees=FREE, rule=RULE, eid='open-1', **kw):
    fields = dict(event_id=eid, security_id=sid, at=at, raw_open=D(str(price)),
                  execution_price=D(str(price)), fx=fx(rate, at), quantity=rule,
                  fees=fees, capacity_shares=capacity, market_open=True,
                  buy_allowed=True, sell_allowed=True, sellable_at=at+timedelta(days=1),
                  cash_due_at=at+timedelta(days=2), source_id='synthetic-raw',
                  execution_basis='explicit_daily_bar_proxy')
    fields.update(kw)
    return FillWindow(**fields)


def marks(at, price=10, rate=1, sid='A'):
    return {sid: Mark(D(str(price)), at, fx(rate, at), 'synthetic-mark')}


def decision(ids=('A',), issuer=None, sector='G'):
    def f(v):
        return admission.Fact(v, T, T, source_id='synthetic')
    lines = [PoolLine(sid, 'A', issuer or sid, sector, 20e9, True) for sid in ids]
    hist = [HistoricalInputs(sid, f(True), f(True), f(True)) for sid in ids]
    evidence = SelectionEvidence('synthetic', 'a'*64, T+timedelta(days=2500), 'synthetic')
    return decide_current_pool(evidence=evidence, lines=lines, historical=hist, clock=CLOCK,
        variant='S0', sectors=[admission.Sector(sector, f(True))], bootstrap=True).decision


class LedgerTests(unittest.TestCase):
    def start(self, q=None, budget=1500, **kw):
        a = SectorAccount(initial_cash=10000, **kw)
        self.assertTrue(a.reserve_budget(quote=q or quote(), clock=CLOCK,
                                         gross_budget_cny=budget)[0])
        return a

    def test_zero_quantity_has_no_reservation_or_slot(self):
        a = SectorAccount(initial_cash=10000)
        ok, reason = a.reserve_budget(quote=quote(price=1000), clock=CLOCK, gross_budget_cny=1500)
        self.assertFalse(ok)
        self.assertEqual(a.available, D(10000))
        self.assertEqual(a.occupancy(T), ())

    def test_reservation_budget_and_share_cap_are_both_fixed(self):
        a = self.start()
        order = a.buys['A']
        self.assertEqual((order.budget_cny, order.target_shares), (D(1500), 100))
        fill = a.fill_buy('A', window(price=5))
        self.assertEqual(fill.shares, 100)  # Cheaper execution cannot buy 300 shares.
        self.assertEqual(a.available, D(9500))
        self.assertNotIn('A', a.buys)
        self.assertEqual(a.balance(fill.at, marks(fill.at, price=5))['nav'], D(10000))

    def test_high_gap_cannot_exceed_order_gross_budget(self):
        a = self.start(budget=2500)
        fill = a.fill_buy('A', window(price=20))
        self.assertEqual(fill.shares, 100)
        self.assertEqual(fill.gross_cny, D(2000))
        self.assertEqual(a.buys['A'].remaining_budget_cny, D(500))
        b = self.start()
        self.assertIsNone(b.fill_buy('A', window(price=20)))  # Cannot submit a fresh 75-share order.
        self.assertEqual(b.available, D(8500))

    def test_partial_fill_remainder_below_order_minimum_can_complete(self):
        r = QuantityRule('synthetic-200-step1', 200, 1, 1, True, 1)
        a = self.start(quote(rule=r), budget=2500)
        f1 = a.fill_buy('A', window(rule=r, capacity=200))
        f2 = a.fill_buy('A', window(rule=r, capacity=50, at=T+timedelta(days=2), eid='open-2'))
        self.assertEqual((f1.shares, f2.shares, a.quantity('A')), (200, 50, 250))
        self.assertNotIn('A', a.buys)

    def test_partial_fees_minimum_once_per_order(self):
        a = self.start(quote(fees=MINIMUM), budget=2000)
        f1 = a.fill_buy('A', window(fees=MINIMUM, capacity=100))
        f2 = a.fill_buy('A', window(fees=MINIMUM, capacity=100, at=T+timedelta(days=2), eid='open-2'))
        self.assertEqual((f1.fees_cny, f2.fees_cny), (D(5), D(0)))
        self.assertEqual(a.balance(f2.at, marks(f2.at))['nav'], D(9995))

    def test_dated_fee_change_does_not_reprice_previous_notional(self):
        old = FeeSchedule('old', (FeeComponent('tax', D('.01')),))
        new = FeeSchedule('new', (FeeComponent('tax', D('.02')),))
        a = self.start(quote(fees=old), budget=2000)
        first = a.fill_buy('A', window(fees=old, capacity=100))
        second = a.fill_buy('A', window(fees=new, capacity=100, at=T+timedelta(days=2), eid='open-2'))
        self.assertEqual((first.fees_cny, second.fees_cny), (D(10), D(20)))

    def test_cost2_multiplies_only_named_variable_fields(self):
        fees = FeeSchedule('explicit-cost2', (FeeComponent('commission', D('.001'), D('5')),
                                             FeeComponent('fixed', D('0'), D('3'), stress_rate=False)))
        base = self.start(quote(fees=fees), budget=1000)
        cost = self.start(quote(fees=fees), budget=1000, cost_multiplier=2)
        self.assertEqual(base.fill_buy('A', window(fees=fees)).fees_cny, D(8))
        self.assertEqual(cost.fill_buy('A', window(fees=fees)).fees_cny, D(8))

    def test_same_event_id_never_fills_or_delays_twice(self):
        a = self.start(budget=2000)
        w = window(capacity=50)
        self.assertEqual(a.fill_buy('A', w).shares, 50)
        self.assertIsNone(a.fill_buy('A', w))
        self.assertEqual(a.quantity('A'), 50)

    def test_delay_counts_only_eligible_execution_events(self):
        a = self.start(delay_events=1)
        self.assertIsNone(a.fill_buy('A', window(market_open=False, eid='closed')))
        self.assertEqual(a.buys['A'].delay_remaining, 1)
        w = window(eid='first-valid')
        self.assertIsNone(a.fill_buy('A', w))
        self.assertIsNone(a.fill_buy('A', w))
        self.assertEqual(a.fill_buy('A', window(at=T+timedelta(days=2), eid='second-valid')).shares, 100)

    def test_sale_is_receivable_and_tplus1_is_enforced(self):
        a = self.start()
        buy = a.fill_buy('A', window())
        exit_clock = admission.Clock(buy.at, buy.at+timedelta(hours=1), buy.at.date())
        a.request_exit(quote(), exit_clock)
        early = window(at=buy.at+timedelta(hours=1), eid='too-early')
        self.assertIsNone(a.fill_exit('A', early))
        sell_at = T+timedelta(days=2)
        sell = a.fill_exit('A', window(price=12, at=sell_at, eid='sell', cash_due_at=sell_at+timedelta(days=2)))
        self.assertEqual(a.available, D(9000))
        b = a.balance(sell_at, {})
        self.assertEqual((b['sale_receivable'], b['nav']), (D(1200), D(10200)))
        a.settle_due(sell_at+timedelta(days=2))
        self.assertEqual(a.available, D(10200))
        self.assertEqual(a.settle_due(sell_at+timedelta(days=2)), ())
        self.assertEqual(len(a.completed), 1)

    def test_cancel_partial_releases_only_unused_cash_and_keeps_shares(self):
        a = self.start(budget=2000)
        f = a.fill_buy('A', window(capacity=50))
        a.cancel_buy('A')
        self.assertEqual((a.available, a.quantity('A')), (D(9500), 50))
        self.assertEqual(a.balance(f.at, marks(f.at))['nav'], D(10000))

    def test_unknown_pause_then_continue_does_not_reset_budget(self):
        a = self.start()
        d = replace(decision(), selected=(), pause_buys=('A',))
        a.apply_decision(d, clock=CLOCK, quotes={'A': quote()}, marks={})
        self.assertTrue(a.buys['A'].paused)
        d = replace(d, pause_buys=(), continue_buys=('A',))
        a.apply_decision(d, clock=CLOCK, quotes={'A': quote()}, marks={})
        self.assertFalse(a.buys['A'].paused)
        self.assertEqual(a.buys['A'].budget_cny, D(1500))

    def test_bad_ah_quote_key_is_not_acknowledged_as_another_line(self):
        a = SectorAccount(initial_cash=10000)
        d = decision(issuer='same-company')
        with self.assertRaises(ValueError):
            a.apply_decision(d, clock=CLOCK, quotes={'A': quote('H', issuer='same-company')}, marks={})
        self.assertEqual(a.available, D(10000))
        self.assertEqual(a.buys, {})

    def test_initial_allocation_and_real_occupancy_ack(self):
        a = SectorAccount(initial_cash=10000)
        ack = a.apply_decision(decision(('A', 'B')), clock=CLOCK,
                               quotes={'A': quote(), 'B': quote('B')}, marks={})
        self.assertEqual(ack.accepted, ('A', 'B'))
        self.assertEqual([o.budget_cny for o in a.buys.values()], [D(1500), D(1500)])
        self.assertTrue(all(o.pending_buy and not o.has_position for o in ack.occupancy))

    def test_dividend_no_pay_date_never_becomes_reinvestable_by_waiting(self):
        a = SectorAccount(initial_cash=10000)
        a.accrue_dividend(event_id='div', sid='A', currency='CNY', net_local=100, ex_at=T,
                           paid_at=None, source_id='synthetic-action', entitlement_basis='record-date 100 shares')
        later = T+timedelta(days=30)
        a.settle_due(later)
        self.assertEqual(a.available, D(10000))
        self.assertEqual(a.balance(later, {})['nav'], D(10100))
        a.pay_dividend('div', at=later, fx=fx(1, later), payment_evidence_id='actual-payment', payment_known_at=later)
        self.assertEqual(a.available, D(10100))
        with self.assertRaises(ValueError):
            a.pay_dividend('div', at=later, fx=fx(1, later), payment_evidence_id='repeat', payment_known_at=later)

    def test_bonus_does_not_lock_preexisting_sellable_shares(self):
        a = self.start()
        a.fill_buy('A', window())
        when = T+timedelta(days=2)
        a.split(event_id='bonus', sid='A', ratio=2, at=when, new_shares_sellable_at=when+timedelta(days=5))
        a.request_exit(quote(price=5), admission.Clock(when, when+timedelta(hours=1), when.date()))
        sale = a.fill_exit('A', window(price=5, at=when+timedelta(hours=1), eid='sell-old'))
        self.assertEqual(sale.shares, 100)
        self.assertEqual(a.quantity('A'), 100)
        self.assertEqual(len(a.completed), 0)

    def test_partial_exit_keeps_previously_submitted_odd_remainder(self):
        a = self.start()
        a.fill_buy('A', window())
        when = T+timedelta(days=2)
        a.split(event_id='bonus', sid='A', ratio=2, at=when, new_shares_sellable_at=when+timedelta(days=5))
        a.request_exit(quote(price=5), admission.Clock(when, when+timedelta(hours=1), when.date()))
        first = a.fill_exit('A', window(price=5, capacity=50, at=when+timedelta(hours=1), eid='sell-old-1'))
        second = a.fill_exit('A', window(price=5, capacity=50, at=when+timedelta(hours=2), eid='sell-old-2'))
        self.assertEqual((first.shares, second.shares, a.quantity('A')), (50, 50, 100))
        self.assertEqual(a.exits['A'].submitted_remaining, 0)

    def test_same_cutoff_rejected_zero_lot_gets_replaced_without_false_q(self):
        a = SectorAccount(initial_cash=10000)
        def f(v):
            return admission.Fact(v, T, T, source_id='synthetic')
        evidence = SelectionEvidence('synthetic', 'a'*64, T+timedelta(days=2500), 'synthetic')
        ids = ('A', 'B', 'C')
        def factory(**kw):
            return decide_current_pool(evidence=evidence,
                lines=[PoolLine(s, 'A', s, 'G', 20e9, True) for s in ids],
                historical=[HistoricalInputs(s, f(True), f(True), f(True)) for s in ids],
                sectors=[admission.Sector('G', f(True))], clock=CLOCK, variant='S0', **kw).decision
        ack = commit_cutoff(a, decision_factory=factory, clock=CLOCK,
                            quotes={'A': quote(price=1000), 'B': quote('B'), 'C': quote('C')},
                            marks={}, bootstrap=True)
        self.assertEqual(ack.accepted, ('B', 'C'))
        memory = {m.security_id:m for m in ack.memories}
        self.assertTrue(memory['A'].waiting)
        self.assertTrue(memory['A'].last_known_q)
        self.assertFalse(memory['B'].waiting)
        self.assertFalse(memory['C'].waiting)
        self.assertTrue(all(e.q for d in ack.decisions for e in d.eligibility))

    def test_fx_proxy_is_explicit_and_future_fx_rejected(self):
        a = self.start(quote(currency='HKD', rate='.9'), budget=1500)
        f = a.fill_buy('A', window(rate='.9', capacity=100))
        self.assertEqual(f.fx_basis, FX_BASIS)
        self.assertEqual(f.gross_cny, D(900))
        self.assertEqual(a.balance(f.at, marks(f.at, rate='.8'))['nav'], D(9900))
        b = self.start()
        with self.assertRaises(ValueError):
            b.fill_buy('A', window(fx=fx(1, T+timedelta(days=5))))

    def test_cny_mark_cannot_accidentally_use_hkd_rate(self):
        a = self.start()
        f = a.fill_buy('A', window())
        with self.assertRaises(ValueError):
            a.balance(f.at, marks(f.at, rate='.9'))


if __name__ == '__main__':
    unittest.main()
