"""Finite annual B0 targets over the shared ledger; no market data or loop.

The caller supplies eligible quotes without trend gating and invokes advance
after that event's sales and due settlements, before buys. Targets never use
strategy slot limits or get re-sized between annual common decision cutoffs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_FLOOR
from typing import Mapping

import sector_stock_admission as admission
from sector_account import DecisionQuote, Mark, SectorAccount, FXQuote, dec, aware

ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")


@dataclass
class AnnualLine:
    security_id: str
    issuer_id: str
    original_quote: DecisionQuote
    annual_cap_cny: Decimal
    initial_shares: int
    target_shares: int
    addition_shares_cap: int
    addition_gross_cap_cny: Decimal
    reduction_shares: int
    status: str
    share_scale: Decimal = ONE
    order_id: str | None = None
    committed_shares: int = 0
    committed_gross_cny: Decimal = ZERO

    def quote_in_current_units(self) -> DecisionQuote:
        if self.share_scale == ONE:
            return self.original_quote
        # This is the original decision price expressed per current share, not
        # a new raw observation. Original quote, known_at and gross cap survive.
        return replace(self.original_quote,
                       raw_price=dec(self.original_quote.raw_price)/self.share_scale,
                       source_id=f"{self.original_quote.source_id};split_unit_scale={self.share_scale}")


class B0Controller:
    def __init__(self):
        self.year: int | None = None
        self.clock: admission.Clock | None = None
        self.frozen_nav_cny: Decimal | None = None
        self.plans: dict[str, AnnualLine] = {}
        self.audit_log: list[dict] = []
        self._last_status: dict[str, str] = {}

    def _status(self, sid, status, at, **extra):
        if self._last_status.get(sid) != status:
            self.audit_log.append(dict(kind="annual_wait_status", year=self.year,
                                       sid=sid, status=status, at=at, **extra))
            self._last_status[sid] = status

    def begin_year(self, account: SectorAccount, clock: admission.Clock,
                   eligible_quotes: Mapping[str, DecisionQuote], marks: Mapping[str, Mark],
                   currency_fx: Mapping[str, FXQuote] | None = None,
                   holding_quotes: Mapping[str, DecisionQuote] | None = None):
        """Freeze the start/year target and submit sells only.

        holding_quotes supplies dated sale rules for all existing positions,
        including excluded and duplicate-issuer lines. The caller identifies
        the year's first common decision, with a shared availability universe.
        """
        year = clock.session_date.year
        if self.year is not None and year <= self.year:
            raise ValueError("B0 targets freeze once per increasing annual decision year")
        holding_quotes = holding_quotes or {}
        all_quotes = dict(holding_quotes) | dict(eligible_quotes)
        for sid, quote in all_quotes.items():
            if sid != quote.security_id or not quote.issuer_id:
                raise ValueError("Annual quote requires matching stable security/issuer identity")
            quote.read_price(clock.decision_at)
        for sid, pos in account.positions.items():
            if sid not in all_quotes:
                raise ValueError(f"Missing dated sale quote for existing B0 holding: {sid}")
            q = all_quotes[sid]
            if (q.issuer_id, q.sector_id, q.currency) != (pos.issuer_id, pos.sector_id, pos.currency):
                raise ValueError("Annual sale quote disagrees with actual inventory")
        if any(o.purpose != "annual_rebalance" for o in account.buys.values()):
            raise ValueError("B0 cannot replace a strategy buy order")
        if any(o.purpose != "annual_rebalance" for o in account.exits.values()):
            raise ValueError("B0 cannot cancel a latched structural exit")
        # Release only the old annual instructions. Inventory and unsettled
        # balances remain real and are included in this year's valuation.
        for sid in list(account.buys):
            account.cancel_buy(sid)
        for sid in list(account.exits):
            account.cancel_reduction(sid)
        balance = account.balance(clock.decision_at, marks, currency_fx)
        nav = balance["nav"]
        if nav <= 0:
            raise ValueError("Positive B0 decision NAV required")
        chosen, issuers, duplicates = {}, set(), []
        for sid in sorted(eligible_quotes):
            quote = eligible_quotes[sid]
            if quote.issuer_id in issuers:
                duplicates.append(sid)
            else:
                chosen[sid] = quote
                issuers.add(quote.issuer_id)
        cap = ((Decimal("0.90")*nav/len(chosen)).quantize(CENT, rounding=ROUND_FLOOR)
               if chosen else ZERO)
        plans = {}
        for sid in sorted(set(chosen) | set(account.positions)):
            quote = all_quotes[sid]
            held = account.quantity(sid)
            annual_cap = cap if sid in chosen else ZERO
            unit = quote.read_price(clock.decision_at)*quote.fx.read(clock.decision_at)
            target = quote.quantity.buy_floor(int(annual_cap/unit)) if sid in chosen else 0
            difference = max(0, target-held)
            addition = quote.quantity.buy_floor(difference)
            add_budget = (max(ZERO, annual_cap-held*unit).quantize(CENT, rounding=ROUND_FLOOR)
                          if addition else ZERO)
            desired_reduction = max(0, held-target)
            reduction = quote.quantity.sell_floor(desired_reduction, held) if desired_reduction else 0
            status = ("waiting_funding" if addition else
                      "addition_below_order_minimum" if difference else
                      "target_below_order_minimum" if sid in chosen and not target else
                      "no_addition")
            plans[sid] = AnnualLine(sid, quote.issuer_id, quote, annual_cap, held,
                                    target, addition, add_budget, reduction, status)
            if desired_reduction != reduction:
                self.audit_log.append(dict(kind="annual_reduction_quantity_gap", year=year,
                                           sid=sid, desired=desired_reduction, submitted=reduction))
        self.year, self.clock, self.frozen_nav_cny = year, clock, nav
        self.plans, self._last_status = plans, {}
        self.audit_log.append(dict(kind="annual_targets_frozen", year=year,
                                   at=clock.decision_at, nav_cny=nav,
                                   eligible_line_count=len(eligible_quotes), issuers=len(chosen),
                                   duplicate_issuer_lines=tuple(duplicates), per_issuer_cap_cny=cap))
        for sid, plan in self.plans.items():
            self.audit_log.append(dict(kind="annual_line_target", year=year, sid=sid,
                                       issuer_id=plan.issuer_id, cap_cny=plan.annual_cap_cny,
                                       initial_shares=plan.initial_shares, target_shares=plan.target_shares,
                                       addition_shares_cap=plan.addition_shares_cap,
                                       addition_gross_cap_cny=plan.addition_gross_cap_cny,
                                       reduction_shares=plan.reduction_shares, status=plan.status,
                                       quote_source=plan.original_quote.source_id))
            if plan.reduction_shares:
                account.request_reduction(plan.original_quote, clock, plan.reduction_shares)
        return self.snapshot(account)

    def advance(self, account: SectorAccount, at,
                market_buyable: Mapping[str, bool | None],
                marks: Mapping[str, Mark] | None = None,
                currency_fx: Mapping[str, FXQuote] | None = None) -> tuple[str, ...]:
        """Fund each frozen annual addition at most once, after sells/settlement.

        A shortage waits for settled cash; it cannot borrow pending proceeds,
        shrink then repeatedly top up a target, or transfer another name's cap.
        False/unknown current market availability pauses an existing order.
        """
        aware(at)
        if self.clock is None:
            raise ValueError("begin_year must freeze B0 targets first")
        if at < self.clock.earliest_execution_at:
            return ()
        if account.as_of is not None and at < account.as_of:
            raise ValueError("B0 funding cannot precede the account clock")
        accepted = []
        for sid, plan in self.plans.items():
            available = market_buyable.get(sid)
            if available is not None and type(available) is not bool:
                raise ValueError("Market buyability must be bool or explicit unknown")
            if plan.order_id is not None:
                order = account.buys.get(sid)
                if order is None:
                    plan.status = "annual_order_finished_no_reissue"
                elif order.order_id != plan.order_id:
                    raise ValueError("Unexpected replacement of a frozen annual order")
                else:
                    order.paused = available is not True
                    plan.status = "reserved" if available is True else "paused_market_availability"
                self._status(sid, plan.status, at)
                continue
            if not plan.addition_shares_cap:
                self._status(sid, plan.status, at)
                continue
            if available is not True:
                plan.status = "market_unknown" if available is None else "market_not_buyable"
                self._status(sid, plan.status, at)
                continue
            if sid in account.exits:
                plan.status = "waiting_annual_sale"
                self._status(sid, plan.status, at)
                continue
            if any(other != sid and pos.issuer_id == plan.issuer_id and pos.shares
                   for other, pos in account.positions.items()):
                plan.status = "waiting_other_issuer_line_exit"
                self._status(sid, plan.status, at)
                continue
            if account.positions and (marks is None or set(account.positions)-set(marks)):
                raise ValueError("B0 funding gross capacity requires dated marks for all actual holdings")
            balance = account.balance(at, marks or {}, currency_fx)
            reserved_gross = sum((o.remaining_budget_cny for o in account.buys.values()), ZERO)
            gross_room = max(ZERO, Decimal("0.90")*balance["nav"]
                             - balance["inventory"]-reserved_gross)
            if plan.addition_gross_cap_cny > gross_room:
                plan.status = "waiting_gross_capacity"
                self._status(sid, plan.status, at, frozen_addition_gross=plan.addition_gross_cap_cny,
                             gross_capacity_cny=gross_room)
                continue
            quote = plan.quote_in_current_units()
            fx = quote.fx.read(self.clock.decision_at)
            fee = sum(quote.fees.incremental("buy", plan.addition_gross_cap_cny/fx,
                                             {}, {}, account.cost_multiplier,
                                             shares=plan.addition_gross_cap_cny/(dec(quote.raw_price)*fx),
                                             par_value=quote.par_value).values(), ZERO)*fx
            required = plan.addition_gross_cap_cny+fee
            if account.available < required:
                plan.status = "insufficient_settled_cash"
                self._status(sid, plan.status, at, required_cny=required,
                             available_cny=account.available)
                continue
            ok, reason = account.reserve_budget(
                quote=quote, clock=self.clock, gross_budget_cny=plan.addition_gross_cap_cny,
                purpose="annual_rebalance", target_shares_cap=plan.addition_shares_cap,
                reservation_at=at)
            if not ok:
                plan.status = f"reservation_rejected:{reason}"
                self._status(sid, plan.status, at)
                continue
            order = account.buys[sid]
            plan.order_id = order.order_id
            plan.committed_shares = order.target_shares
            plan.committed_gross_cny = order.budget_cny
            plan.status = "reserved"
            accepted.append(sid)
            self.audit_log.append(dict(kind="annual_addition_reserved", year=self.year, sid=sid,
                                       at=at, annual_decision_at=self.clock.decision_at,
                                       order_id=order.order_id, shares=order.target_shares,
                                       gross_cny=order.budget_cny))
        return tuple(accepted)

    def apply_split(self, sid, ratio):
        """Transform only controller share units; the caller updates the ledger."""
        if sid not in self.plans:
            return
        ratio = dec(ratio)
        if ratio <= 0:
            raise ValueError("Positive split ratio required")
        plan = self.plans[sid]
        fields = ("initial_shares", "target_shares", "addition_shares_cap",
                  "reduction_shares", "committed_shares")
        updates = {name: dec(getattr(plan, name))*ratio for name in fields}
        if any(value != int(value) for value in updates.values()):
            raise ValueError("Fractional B0 annual target units require an explicit unsupported-event adapter")
        for name, value in updates.items():
            setattr(plan, name, int(value))
        plan.share_scale *= ratio
        self.audit_log.append(dict(kind="annual_target_split_units", year=self.year,
                                   sid=sid, ratio=ratio, share_scale=plan.share_scale,
                                   target_shares=plan.target_shares,
                                   addition_shares_cap=plan.addition_shares_cap,
                                   gross_cap_unchanged=plan.addition_gross_cap_cny,
                                   original_quote_source=plan.original_quote.source_id))

    def snapshot(self, account: SectorAccount) -> dict:
        """Actual residual targets/cash deviations, without changing allocations."""
        lines = []
        for sid, plan in self.plans.items():
            order = account.buys.get(sid)
            lines.append(dict(security_id=sid, issuer_id=plan.issuer_id,
                              target_shares=plan.target_shares, actual_shares=account.quantity(sid),
                              remaining_target_shares=plan.target_shares-account.quantity(sid),
                              annual_cap_cny=plan.annual_cap_cny,
                              addition_shares_cap=plan.addition_shares_cap,
                              addition_gross_cap_cny=plan.addition_gross_cap_cny,
                              reserved_remaining_gross_cny=order.remaining_budget_cny if order else ZERO,
                              reserved_remaining_shares=order.remaining_shares if order else 0,
                              status=plan.status, order_id=plan.order_id,
                              share_scale=plan.share_scale))
        return dict(year=self.year, frozen_nav_cny=self.frozen_nav_cny,
                    decision_at=self.clock.decision_at if self.clock else None, lines=lines)
