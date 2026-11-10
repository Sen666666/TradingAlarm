"""Synthetic annual-target/ledger integration; no historical accounts."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

import sector_stock_admission as admission
from b0_rebalance import B0Controller
from sector_account import (SectorAccount, DecisionQuote, FXQuote, Mark, QuantityRule,
                            FeeSchedule, FillWindow, Position, InventoryLot)

T = datetime(2020, 1, 2, 7, tzinfo=timezone.utc)
CLOCK = admission.Clock(T, T+timedelta(days=1), T.date())
RULE = QuantityRule("synthetic-100", 100, 100, 100, True, 1)
FREE = FeeSchedule("synthetic-free", ())


def quote(sid="A", price=10, issuer=None, at=T, rule=RULE):
    return DecisionQuote(sid, issuer or sid, "G", "CNY", D(str(price)), at,
                         FXQuote(D(1), at, "synthetic-fx"), rule, FREE, "synthetic-decision")


def mark(price=10, at=T):
    return Mark(D(str(price)), at, FXQuote(D(1), at, "synthetic-fx"), "synthetic-mark")


def window(sid="A", price=10, at=T+timedelta(days=1), eid="w1", due=None, capacity=10**6):
    return FillWindow(event_id=eid, security_id=sid, at=at, raw_open=D(str(price)),
                      execution_price=D(str(price)), fx=FXQuote(D(1), at, "synthetic-fx"),
                      quantity=RULE, fees=FREE, capacity_shares=capacity, market_open=True,
                      buy_allowed=True, sell_allowed=True, sellable_at=at,
                      cash_due_at=due or at+timedelta(days=2), source_id="synthetic-event",
                      execution_basis="synthetic_only")


def holding(account, sid, shares, price=10, issuer=None):
    # Explicit synthetic starting inventory, not a fabricated fill/history.
    account.positions[sid] = Position(sid, issuer or sid, "G", "CNY",
                                      [InventoryLot(shares, T-timedelta(days=1))])
    account.available -= D(shares)*D(str(price))


class B0Tests(unittest.TestCase):
    def test_more_than_six_targets_and_no_buys_at_annual_decision(self):
        a, b = SectorAccount(initial_cash=100000), B0Controller()
        qs = {f"S{i:02}": quote(f"S{i:02}") for i in range(10)}
        b.begin_year(a, CLOCK, qs, {})
        self.assertEqual(len(b.plans), 10)
        self.assertEqual(a.buys, {})
        self.assertTrue(all(p.annual_cap_cny == 9000 and p.target_shares == 900
                            for p in b.plans.values()))
        self.assertEqual(len(b.advance(a, CLOCK.earliest_execution_at, {s: True for s in qs})), 10)

    def test_stable_issuer_route_and_later_selection_does_not_rebudget(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        b.begin_year(a, CLOCK, {"H": quote("H", issuer="AH"),
                                "A": quote("A", issuer="AH")}, {})
        self.assertEqual(set(b.plans), {"A"})
        self.assertEqual(b.plans["A"].target_shares, 900)
        b.advance(a, CLOCK.earliest_execution_at, {"A": True})
        a.fill_buy("A", window(price=5))
        b.advance(a, T+timedelta(days=2), {"A": True})
        self.assertEqual(a.quantity("A"), 900)
        self.assertNotIn("A", a.buys)
        self.assertEqual(b.plans["A"].annual_cap_cny, D(9000))
        self.assertEqual(b.plans["A"].status, "annual_order_finished_no_reissue")

    def test_below_one_lot_keeps_explicit_target_and_cash(self):
        a, b = SectorAccount(initial_cash=1000), B0Controller()
        b.begin_year(a, CLOCK, {"A": quote(price=100)}, {})
        self.assertEqual(b.plans["A"].status, "target_below_order_minimum")
        self.assertEqual(b.advance(a, CLOCK.earliest_execution_at, {"A": True}), ())
        self.assertEqual(a.available, 1000)
        self.assertEqual(a.quantity("A"), 0)

    def test_sell_first_and_unsettled_proceeds_cannot_fund_new_annual_buy(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "OLD", 900)
        b.begin_year(a, CLOCK, {"NEW": quote("NEW")}, {"OLD": mark()},
                     holding_quotes={"OLD": quote("OLD")})
        self.assertIn("OLD", a.exits)
        self.assertEqual(a.buys, {})
        when, due = CLOCK.earliest_execution_at, T+timedelta(days=3)
        a.fill_exit("OLD", window("OLD", at=when, due=due))
        self.assertEqual(b.advance(a, when, {"NEW": True}), ())
        self.assertEqual(b.plans["NEW"].status, "insufficient_settled_cash")
        a.settle_due(due)
        self.assertEqual(b.advance(a, due, {"NEW": True}), ("NEW",))
        self.assertEqual(a.buys["NEW"].budget_cny, 9000)
        self.assertEqual(a.buys["NEW"].created_at, T)

    def test_finite_reduction_preserves_target_position_and_no_trend_exit_event(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "A", 1000)
        b.begin_year(a, CLOCK, {"A": quote()}, {"A": mark()}, holding_quotes={"A": quote()})
        self.assertEqual(a.exits["A"].remaining_target, 100)
        a.fill_exit("A", window())
        self.assertEqual(a.quantity("A"), 900)
        self.assertNotIn("A", a.exits)
        self.assertEqual(a.completed, [])

    def test_route_change_cannot_hold_two_lines_of_same_issuer_while_sale_waits(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "H", 100, issuer="AH")
        b.begin_year(a, CLOCK, {"A": quote("A", issuer="AH"),
                                "H": quote("H", issuer="AH")}, {"H": mark()},
                     holding_quotes={"H": quote("H", issuer="AH")})
        self.assertEqual(a.available, 9000)  # Enough cash alone cannot authorize duplicate exposure.
        self.assertEqual(b.advance(a, CLOCK.earliest_execution_at, {"A": True}), ())
        self.assertEqual(b.plans["A"].status, "waiting_other_issuer_line_exit")
        a.fill_exit("H", window("H"))
        self.assertEqual(b.advance(a, CLOCK.earliest_execution_at, {"A": True}), ("A",))

    def test_blocked_old_sale_cannot_stack_old_inventory_and_new_ninety_percent(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "OLD", 100)
        b.begin_year(a, CLOCK, {"A": quote("A"), "B": quote("B")}, {"OLD": mark()},
                     holding_quotes={"OLD": quote("OLD")})
        when = CLOCK.earliest_execution_at
        # OLD's sale is blocked. A can use real room; B would take invested
        # inventory plus reservations to 100%, so the entire frozen B leg waits.
        self.assertEqual(b.advance(a, when, {"A": True, "B": True}, {"OLD": mark(at=when)}), ("A",))
        self.assertEqual(b.plans["B"].status, "waiting_gross_capacity")
        self.assertEqual(b.plans["B"].addition_gross_cap_cny, 4500)
        self.assertEqual(a.buys["A"].budget_cny, 4500)
        a.fill_exit("OLD", window("OLD", at=when))
        self.assertEqual(b.advance(a, when, {"A": True, "B": True}, {}), ("B",))
        self.assertEqual(a.buys["B"].budget_cny, 4500)

    def test_new_funding_with_unmarked_existing_inventory_fails_explicitly(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "OLD", 100)
        b.begin_year(a, CLOCK, {"A": quote("A"), "B": quote("B")}, {"OLD": mark()},
                     holding_quotes={"OLD": quote("OLD")})
        with self.assertRaisesRegex(ValueError, "dated marks"):
            b.advance(a, CLOCK.earliest_execution_at, {"A": True, "B": True})
        self.assertEqual(a.buys, {})

    def test_unknown_and_false_market_pause_without_replacing_budget(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        b.begin_year(a, CLOCK, {"A": quote()}, {})
        when = CLOCK.earliest_execution_at
        self.assertEqual(b.advance(a, when, {}), ())
        self.assertEqual(b.plans["A"].status, "market_unknown")
        b.advance(a, when, {"A": True})
        oid = a.buys["A"].order_id
        b.advance(a, when, {"A": False})
        self.assertTrue(a.buys["A"].paused)
        b.advance(a, when, {"A": True})
        self.assertFalse(a.buys["A"].paused)
        self.assertEqual(a.buys["A"].order_id, oid)
        self.assertEqual(a.buys["A"].budget_cny, 9000)

    def test_new_year_cancels_only_old_annual_instructions_and_refreezes(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        b.begin_year(a, CLOCK, {"A": quote()}, {})
        b.advance(a, CLOCK.earliest_execution_at, {"A": True})
        old_id = a.buys["A"].order_id
        next_t = T.replace(year=2021)
        next_clock = admission.Clock(next_t, next_t+timedelta(days=1), next_t.date())
        b.begin_year(a, next_clock, {"B": quote("B", at=next_t)}, {})
        self.assertNotIn("A", a.buys)
        self.assertEqual(set(b.plans), {"B"})
        b.advance(a, next_clock.earliest_execution_at, {"B": True})
        self.assertNotEqual(a.buys["B"].order_id, old_id)
        with self.assertRaises(ValueError):
            b.begin_year(a, next_clock, {"B": quote("B", at=next_t)}, {})

    def test_split_adjusts_frozen_units_not_original_evidence_or_gross(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        original = quote()
        b.begin_year(a, CLOCK, {"A": original}, {})
        b.apply_split("A", 2)
        self.assertEqual(b.plans["A"].target_shares, 1800)
        self.assertEqual(b.plans["A"].addition_gross_cap_cny, 9000)
        b.advance(a, CLOCK.earliest_execution_at, {"A": True})
        self.assertEqual(a.buys["A"].target_shares, 1800)
        self.assertEqual(a.buys["A"].quote.raw_price, 5)
        self.assertEqual(original.raw_price, 10)
        self.assertEqual(a.buys["A"].quote.known_at, original.known_at)
        self.assertIn("split_unit_scale=2", a.buys["A"].quote.source_id)

    def test_fractional_target_units_fail_without_partial_controller_edit(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        b.begin_year(a, CLOCK, {"A": quote()}, {})
        with self.assertRaises(ValueError):
            b.apply_split("A", D("1.0001"))
        self.assertEqual(b.plans["A"].share_scale, 1)
        self.assertEqual(b.plans["A"].target_shares, 900)

    def test_missing_sale_quote_fails_before_old_instructions_are_cancelled(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "OLD", 900)
        with self.assertRaisesRegex(ValueError, "Missing dated sale quote"):
            b.begin_year(a, CLOCK, {"NEW": quote("NEW")}, {"OLD": mark()})
        self.assertIsNone(b.year)
        self.assertEqual(a.quantity("OLD"), 900)

    def test_empty_pool_requests_exit_and_retains_no_hidden_buy_target(self):
        a, b = SectorAccount(initial_cash=10000), B0Controller()
        holding(a, "OLD", 900)
        b.begin_year(a, CLOCK, {}, {"OLD": mark()}, holding_quotes={"OLD": quote("OLD")})
        self.assertEqual(a.exits["OLD"].remaining_target, 900)
        self.assertEqual(b.plans["OLD"].target_shares, 0)
        self.assertEqual(b.advance(a, CLOCK.earliest_execution_at, {}), ())


if __name__ == "__main__":
    unittest.main()
