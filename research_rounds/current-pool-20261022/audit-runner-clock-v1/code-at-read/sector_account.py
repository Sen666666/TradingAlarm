"""Small CNY research ledger, without a market loop or a strategy search.

The caller supplies dated raw-price, quantity, fee, FX, capacity and settlement
facts. Unknown fields do not become executable defaults. All FX on a fill is
locked at its then-known reference quote: this is an explicit research proxy,
not a reconstruction of final Southbound broker settlement. First10's protocol
must approve that proxy before any historical account can use this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_UP
from typing import Callable, Mapping, Sequence

import sector_stock_admission as admission

ZERO = Decimal('0')
ONE = Decimal('1')
GROSS = Decimal('0.90')
FX_BASIS = 'known_trade_time_reference_locked_until_settlement'


def dec(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Finite amounts required')
    return result


def aware(t: datetime) -> None:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('Timezone-aware timestamps required')


def positive(value) -> Decimal:
    value = dec(value)
    if value <= 0:
        raise ValueError('Positive amount required')
    return value


@dataclass(frozen=True)
class FXQuote:
    cny_per_local: Decimal
    known_at: datetime
    source_id: str

    def read(self, at: datetime) -> Decimal:
        aware(at); aware(self.known_at)
        if self.known_at > at or not self.source_id:
            raise ValueError('Future or unidentified FX quote')
        return positive(self.cny_per_local)


@dataclass(frozen=True)
class QuantityRule:
    rule_id: str
    buy_minimum: int
    buy_step: int
    sell_step: int
    allow_full_exit_odd: bool
    fill_step: int  # Matching granularity, distinct from original order minimum.

    def __post_init__(self):
        if not self.rule_id or any(type(v) is not int or v <= 0
                                  for v in (self.buy_minimum, self.buy_step, self.sell_step, self.fill_step)):
            raise ValueError('Explicit positive integer quantity rules required')

    def buy_floor(self, maximum: int) -> int:
        return (0 if maximum < self.buy_minimum else
                self.buy_minimum + (maximum-self.buy_minimum)//self.buy_step*self.buy_step)

    def sell_floor(self, maximum: int, entire_holding: int) -> int:
        if self.allow_full_exit_odd and maximum >= entire_holding:
            return entire_holding
        return maximum//self.sell_step*self.sell_step


@dataclass(frozen=True)
class FeeComponent:
    name: str
    rate: Decimal
    minimum_local: Decimal = ZERO
    side: str = 'both'
    basis: str = 'order'  # Minimum applies per order or per fill, explicitly.
    stress_rate: bool = True
    stress_minimum: bool = False
    maximum_local: Decimal | None = None
    rounding_unit: Decimal | None = None
    rounding_mode: str = 'nearest'
    stress_maximum: bool = False
    amount_basis: str = 'notional'

    def __post_init__(self):
        if (not self.name or self.side not in ('buy', 'sell', 'both')
                or self.basis not in ('order', 'fill')
                or dec(self.rate) < 0 or dec(self.minimum_local) < 0
                or (self.maximum_local is not None and dec(self.maximum_local) < dec(self.minimum_local))
                or (self.rounding_unit is not None and dec(self.rounding_unit) <= 0)
                or self.rounding_mode not in ('ceil', 'nearest')
                or self.amount_basis not in ('notional', 'shares', 'par_value')):
            raise ValueError('Invalid fee component')


@dataclass(frozen=True)
class FeeSchedule:
    schedule_id: str
    components: tuple[FeeComponent, ...]

    def __post_init__(self):
        if not self.schedule_id or len({x.name for x in self.components}) != len(self.components):
            raise ValueError('Identified fee schedule with unique component names required')

    def incremental(self, side: str, local_notional: Decimal, paid: Mapping[str, Decimal],
                    accrued: Mapping[str, Decimal], multiplier: int, *, shares=None,
                    par_value=None) -> dict[str, Decimal]:
        if multiplier not in (1, 2):
            raise ValueError('Only base and frozen cost2 are supported')
        result = {}
        for c in self.components:
            if c.side not in ('both', side):
                continue
            rate = dec(c.rate) * (multiplier if c.stress_rate else 1)
            minimum = dec(c.minimum_local) * (multiplier if c.stress_minimum else 1)
            base = self.amount(c, local_notional, shares, par_value)
            if c.basis == 'order':
                total = max(minimum, accrued.get(c.name, ZERO)+base*rate)
            else:
                total = max(minimum, base*rate)
            if c.maximum_local is not None:
                maximum = dec(c.maximum_local)*(multiplier if c.stress_maximum else 1)
                total = min(total, maximum)
            if c.rounding_unit is not None:
                unit = dec(c.rounding_unit)
                rounding = ROUND_CEILING if c.rounding_mode == 'ceil' else ROUND_HALF_UP
                total = (total/unit).to_integral_value(rounding=rounding)*unit
            result[c.name] = max(ZERO, total-paid.get(c.name, ZERO)) if c.basis == 'order' else total
        return result

    @staticmethod
    def amount(c, local_notional, shares, par_value):
        if c.amount_basis == 'notional':
            return local_notional
        if shares is None or dec(shares) < 0:
            raise ValueError('Share-based fee needs explicit quantity')
        if c.amount_basis == 'shares':
            return dec(shares)
        if par_value is None:
            raise ValueError('Par-value fee cannot substitute market-price notional')
        return dec(shares)*positive(par_value)

    def rate_accrual(self, side, local_notional, multiplier, *, shares=None, par_value=None):
        return {c.name: self.amount(c, local_notional, shares, par_value)*dec(c.rate)*(multiplier if c.stress_rate else 1)
                for c in self.components if c.side in ('both', side)}


@dataclass(frozen=True)
class DecisionQuote:
    security_id: str
    issuer_id: str
    sector_id: str
    currency: str
    raw_price: Decimal
    known_at: datetime
    fx: FXQuote
    quantity: QuantityRule
    fees: FeeSchedule
    source_id: str
    par_value: Decimal | None = None

    def read_price(self, at: datetime) -> Decimal:
        aware(at); aware(self.known_at)
        if self.known_at > at or not self.source_id or self.currency not in ('CNY', 'HKD'):
            raise ValueError('Future/unidentified raw price or unsupported currency')
        self.fx.read(at)
        if self.currency == 'CNY' and dec(self.fx.cny_per_local) != ONE:
            raise ValueError('CNY conversion must equal one')
        return positive(self.raw_price)


@dataclass(frozen=True)
class Mark:
    raw_price: Decimal
    known_at: datetime
    fx: FXQuote
    source_id: str

    def cny_price(self, at: datetime) -> Decimal:
        aware(self.known_at)
        if self.known_at > at or not self.source_id:
            raise ValueError('Future or unidentified valuation mark')
        return positive(self.raw_price) * self.fx.read(at)


@dataclass(frozen=True)
class FillWindow:
    event_id: str
    security_id: str
    at: datetime
    raw_open: Decimal
    execution_price: Decimal  # Explicit protocol slippage already applied.
    fx: FXQuote
    quantity: QuantityRule
    fees: FeeSchedule
    capacity_shares: int
    market_open: bool | None
    buy_allowed: bool | None
    sell_allowed: bool | None
    sellable_at: datetime
    cash_due_at: datetime
    source_id: str
    execution_basis: str  # e.g. observed_open or explicit_daily_bar_proxy.
    par_value: Decimal | None = None

    def validate(self):
        for t in (self.at, self.sellable_at, self.cash_due_at):
            aware(t)
        if (not self.event_id or not self.source_id or not self.execution_basis
                or type(self.capacity_shares) is not int or self.capacity_shares < 0
                or self.sellable_at < self.at or self.cash_due_at < self.at):
            raise ValueError('Invalid execution event/availability/settlement facts')
        positive(self.raw_open); positive(self.execution_price); self.fx.read(self.at)


@dataclass
class BuyOrder:
    order_id: str
    quote: DecisionQuote
    created_at: datetime
    earliest_at: datetime
    budget_cny: Decimal
    remaining_budget_cny: Decimal
    fee_reserved_cny: Decimal
    target_shares: int
    remaining_shares: int
    delay_remaining: int
    purpose: str
    candidate_id: str = ''
    filled_shares: int = 0
    local_notional: Decimal = ZERO
    fees_local: dict[str, Decimal] = field(default_factory=dict)
    fee_accrued_local: dict[str, Decimal] = field(default_factory=dict)
    paused: bool = False
    submitted_remaining: int = 0


@dataclass
class InventoryLot:
    shares: int
    sellable_at: datetime


@dataclass
class Position:
    security_id: str
    issuer_id: str
    sector_id: str
    currency: str
    lots: list[InventoryLot] = field(default_factory=list)

    @property
    def shares(self) -> int:
        return sum(lot.shares for lot in self.lots)


@dataclass
class ExitOrder:
    event_id: str
    quote: DecisionQuote
    requested_at: datetime
    earliest_at: datetime
    delay_remaining: int
    local_notional: Decimal = ZERO
    fees_local: dict[str, Decimal] = field(default_factory=dict)
    fee_accrued_local: dict[str, Decimal] = field(default_factory=dict)
    submitted_remaining: int = 0
    remaining_target: int | None = None
    purpose: str = 'structure_exit'


@dataclass(frozen=True)
class Settlement:
    settlement_id: str
    cny_amount: Decimal
    debit: bool
    due_at: datetime
    local_amount: Decimal
    fx_rate: Decimal
    fx_source: str
    fx_basis: str = FX_BASIS


@dataclass
class DividendReceivable:
    event_id: str
    security_id: str
    currency: str
    net_local: Decimal
    ex_at: datetime
    paid_at: datetime | None
    source_id: str
    entitlement_basis: str


@dataclass(frozen=True)
class FillReceipt:
    receipt_id: str
    security_id: str
    side: str
    shares: int
    gross_cny: Decimal
    fees_cny: Decimal
    at: datetime
    settlement_id: str
    execution_basis: str
    fx_basis: str = FX_BASIS


@dataclass(frozen=True)
class DecisionAck:
    accepted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    occupancy: tuple[admission.Occupancy, ...]


@dataclass(frozen=True)
class CutoffAck:
    accepted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    occupancy: tuple[admission.Occupancy, ...]
    memories: tuple[admission.Memory, ...]
    decisions: tuple[admission.Decision, ...]


def commit_cutoff(account: 'SectorAccount', *, decision_factory: Callable,
                  clock: admission.Clock, quotes: Mapping[str, DecisionQuote],
                  marks: Mapping[str, Mark], previous=(), bootstrap=False,
                  completed_exits=(), currency_fx=None) -> CutoffAck:
    """Bounded same-cutoff top-up using real acknowledgements, not fake slots.

    decision_factory(**kwargs) returns the unchanged admission.Decision; a data
    bridge can close over fixed-pool inputs and return wrapper.decision. Rejected
    candidates are temporarily withheld from this cutoff's competition through
    a private copy of candidate waiting flags, never through fake market facts.
    Their original waiting memory is restored in the persisted return value.
    """
    occupancy = account.occupancy(clock.decision_at)
    first = decision_factory(previous=previous, occupied=occupancy,
                             bootstrap=bootstrap, completed_exits=completed_exits)
    base = {m.security_id: m for m in first.memories}
    blocked, accepted, rejected, decisions = set(), [], [], []
    current = first
    for _ in range(len(first.eligibility)+2):
        decisions.append(current)
        ack = account.apply_decision(current, clock=clock, quotes=quotes, marks=marks,
                                     currency_fx=currency_fx)
        accepted.extend(ack.accepted); rejected.extend(ack.rejected)
        blocked.update(sid for sid, _reason in ack.rejected)
        if not ack.accepted and not ack.rejected:
            restored = tuple(base[m.security_id] if m.security_id in blocked else m
                             for m in current.memories)
            return CutoffAck(tuple(accepted), tuple(rejected), ack.occupancy,
                              restored, tuple(decisions))
        temporary = tuple(replace(m, waiting=False) if sid in blocked else m
                          for sid, m in base.items())
        current = decision_factory(previous=temporary, occupied=ack.occupancy,
                                   bootstrap=False, completed_exits=())
    raise AssertionError('Same-cutoff admission must terminate within the finite candidate set')


class SectorAccount:
    """No allocator for B0 is implied; reserve_budget is its shared ledger API."""
    def __init__(self, *, initial_cash=Decimal('1000000'), cost_multiplier=1,
                 delay_events=0, unpaid_dividend_policy='receivable_no_reinvestment'):
        if cost_multiplier not in (1, 2) or delay_events not in (0, 1):
            raise ValueError('Only first10 base/cost2/delay1 configurations allowed')
        if unpaid_dividend_policy != 'receivable_no_reinvestment':
            raise ValueError('Missing-pay-date policy must be explicit and supported')
        self.available = positive(initial_cash)
        self.initial_cash = self.available
        self.cost_multiplier, self.delay_events = cost_multiplier, delay_events
        self.unpaid_dividend_policy = unpaid_dividend_policy
        self.buys: dict[str, BuyOrder] = {}
        self.positions: dict[str, Position] = {}
        self.exits: dict[str, ExitOrder] = {}
        self.settlements: dict[str, Settlement] = {}
        self.dividends: dict[str, DividendReceivable] = {}
        self.completed: list[admission.ExitCompletion] = []
        self.fills: list[FillReceipt] = []
        self.used_events: set[tuple[str, str]] = set()
        self.action_events: set[str] = set()
        self.paid_dividends: set[str] = set()
        self.fees_cny = ZERO
        self.audit_log: list[dict] = []
        self.as_of: datetime | None = None
        self.sequence = 0

    def _time(self, at):
        aware(at)
        if self.as_of is not None and at < self.as_of:
            raise ValueError('Account events cannot run backwards')
        self.as_of = at

    def _id(self, prefix, security):
        self.sequence += 1
        return f'{prefix}:{security}:{self.sequence}'

    def quantity(self, sid):
        return self.positions[sid].shares if sid in self.positions else 0

    def occupancy(self, at) -> tuple[admission.Occupancy, ...]:
        self._time(at)
        result = []
        for sid in sorted(set(self.positions) | set(self.buys) | set(self.exits)):
            pos = self.positions.get(sid)
            order = self.buys.get(sid)
            quote = order.quote if order else self.exits[sid].quote if not pos else None
            issuer = pos.issuer_id if pos else quote.issuer_id
            sector = pos.sector_id if pos else quote.sector_id
            result.append(admission.Occupancy(sid, issuer, sector, at,
                          has_position=bool(pos and pos.shares), pending_buy=order is not None,
                          partial_fill=bool(order and order.filled_shares), exit_latched=sid in self.exits))
        return tuple(result)

    def balance(self, at, marks: Mapping[str, Mark], currency_fx: Mapping[str, FXQuote] | None = None):
        self._time(at)
        for sid, pos in self.positions.items():
            if pos.currency == 'CNY' and marks[sid].fx.read(at) != ONE:
                raise ValueError('CNY inventory valuation FX must equal one')
        stock = sum((p.shares * marks[sid].cny_price(at) for sid, p in self.positions.items()), ZERO)
        reserved = sum((o.remaining_budget_cny+o.fee_reserved_cny for o in self.buys.values()), ZERO)
        locked = sum((s.cny_amount for s in self.settlements.values() if s.debit), ZERO)
        receivable = sum((s.cny_amount for s in self.settlements.values() if not s.debit), ZERO)
        dividend = ZERO
        for d in self.dividends.values():
            if d.currency == 'CNY':
                rate = ONE
            else:
                if currency_fx is None or d.currency not in currency_fx:
                    raise ValueError('Outstanding foreign dividend needs a known valuation FX')
                rate = currency_fx[d.currency].read(at)
            dividend += d.net_local * rate
        nav = self.available + reserved + locked + receivable - locked + stock + dividend
        result = dict(available=self.available, order_reserved=reserved, settlement_locked=locked,
                      payable=locked, sale_receivable=receivable, dividend_receivable=dividend,
                      inventory=stock, nav=nav, fees_cny=self.fees_cny)
        if min(self.available, reserved, locked, receivable, dividend, stock) < 0:
            raise AssertionError('Negative ledger component')
        return result

    def _fee(self, order, schedule, side, local, *, shares=None, par_value=None):
        return schedule.incremental(side, local, order.fees_local,
                                    order.fee_accrued_local, self.cost_multiplier,
                                    shares=shares, par_value=par_value)

    def _remember_fees(self, order, schedule, side, local, components, *, shares=None, par_value=None):
        order.local_notional += local
        for name, value in components.items():
            order.fees_local[name] = order.fees_local.get(name, ZERO)+value
        for name, value in schedule.rate_accrual(side, local, self.cost_multiplier,
                                               shares=shares, par_value=par_value).items():
            order.fee_accrued_local[name] = order.fee_accrued_local.get(name, ZERO)+value

    def reserve_budget(self, *, quote: DecisionQuote, clock: admission.Clock, gross_budget_cny,
                       purpose='initial', target_shares_cap: int | None = None,
                       candidate_id: str | None = None,
                       reservation_at: datetime | None = None) -> tuple[bool, str]:
        """Freeze gross budget and share cap; fees are a separate cash reservation.

        B0 may call this with explicit annual_rebalance targets; this function
        neither creates B0 targets nor imposes strategy 6-slot allocation on B0.
        """
        at = clock.decision_at
        if reservation_at is not None:
            aware(reservation_at)
            if purpose != 'annual_rebalance' or reservation_at < at:
                raise ValueError('Only frozen annual targets may wait for later funding')
        self._time(reservation_at or at)
        sid = quote.security_id
        if purpose not in ('initial', 'annual_rebalance'):
            raise ValueError('Unsupported order purpose')
        if sid in self.positions:
            pos = self.positions[sid]
            if (quote.issuer_id, quote.sector_id, quote.currency) != (pos.issuer_id, pos.sector_id, pos.currency):
                raise ValueError('Order identity/currency disagrees with existing inventory')
        if sid in self.buys or sid in self.exits or (purpose == 'initial' and self.quantity(sid)):
            return False, 'existing_position_or_order'
        price, fx = quote.read_price(at), quote.fx.read(at)
        cap = max(ZERO, min(dec(gross_budget_cny), self.available))
        # Solve gross cash + explicit estimated fees <= available, to one CNY cent.
        low, high = 0, int((cap*100).to_integral_value(rounding=ROUND_FLOOR))
        while low < high:
            mid = (low+high+1)//2
            budget = Decimal(mid)/100
            fee = sum(quote.fees.incremental('buy', budget/fx, {}, {}, self.cost_multiplier,
                      shares=budget/(price*fx), par_value=quote.par_value).values(), ZERO)*fx
            if budget+fee <= self.available:
                low = mid
            else:
                high = mid-1
        budget = Decimal(low)/100
        maximum = int(budget/(price*fx))
        if target_shares_cap is not None:
            if type(target_shares_cap) is not int or target_shares_cap < 0:
                raise ValueError('Explicit nonnegative integer target cap required')
            maximum = min(maximum, target_shares_cap)
        target = quote.quantity.buy_floor(maximum)
        if not target:
            return False, 'insufficient_budget_or_quantity'
        fee = sum(quote.fees.incremental('buy', budget/fx, {}, {}, self.cost_multiplier,
                  shares=budget/(price*fx), par_value=quote.par_value).values(), ZERO)*fx
        order = BuyOrder(self._id('buy', sid), quote, at, clock.earliest_execution_at,
                         budget, budget, fee, target, target, self.delay_events, purpose)
        order.candidate_id = candidate_id or f'{purpose}:{sid}:{at.isoformat()}'
        self.available -= budget+fee
        self.buys[sid] = order
        self.audit_log.append(dict(kind='reserve', at=reservation_at or at, decision_at=at,
                                  sid=sid, order_id=order.order_id,
                                  gross_budget_cny=budget, fee_reserved_cny=fee,
                                  target_shares=target, purpose=purpose,
                                  candidate_id=order.candidate_id,
                                  quote_source=quote.source_id, fee_schedule=quote.fees.schedule_id))
        return True, order.order_id

    def cancel_buy(self, sid):
        order = self.buys.pop(sid, None)
        if order:
            self.available += order.remaining_budget_cny+order.fee_reserved_cny
            self.audit_log.append(dict(kind='release_buy', at=self.as_of, sid=sid,
                                      order_id=order.order_id,
                                      gross_released=order.remaining_budget_cny,
                                      fee_released=order.fee_reserved_cny))

    def request_exit(self, quote: DecisionQuote, clock: admission.Clock):
        self._time(clock.decision_at)
        sid = quote.security_id
        if sid in self.positions:
            pos = self.positions[sid]
            if (quote.issuer_id, quote.sector_id, quote.currency) != (pos.issuer_id, pos.sector_id, pos.currency):
                raise ValueError('Exit identity/currency disagrees with existing inventory')
        self.cancel_buy(sid)
        if self.quantity(sid) and sid not in self.exits:
            quote.read_price(clock.decision_at)
            self.exits[sid] = ExitOrder(self._id('exit', sid), quote, clock.decision_at,
                                        clock.earliest_execution_at, self.delay_events)
            self.audit_log.append(dict(kind='exit_request', at=clock.decision_at, sid=sid,
                                      event_id=self.exits[sid].event_id))

    def request_reduction(self, quote: DecisionQuote, clock: admission.Clock, shares: int):
        """B0's frozen annual sell delta; never used for a strategy trend exit."""
        if type(shares) is not int or shares < 0 or shares > self.quantity(quote.security_id):
            raise ValueError('Annual sell delta must fit actual integer inventory')
        if not shares:
            return
        if quote.security_id in self.exits:
            raise ValueError('Cancel the old annual reduction before replacing its target')
        self.request_exit(quote, clock)
        order = self.exits[quote.security_id]
        order.remaining_target, order.purpose = shares, 'annual_rebalance'

    def cancel_reduction(self, sid):
        order = self.exits.get(sid)
        if order is not None:
            if order.purpose != 'annual_rebalance':
                raise ValueError('A structural exit is irrevocably latched')
            del self.exits[sid]

    def charge_expense(self, *, expense_id, at, cny_amount, source_id):
        self._time(at)
        amount = dec(cny_amount)
        if (not expense_id or not source_id or amount < 0 or expense_id in self.action_events
                or amount > self.available):
            raise ValueError('Invalid/duplicate expense or insufficient settled cash')
        self.available -= amount
        self.fees_cny += amount
        self.action_events.add(expense_id)
        self.audit_log.append(dict(kind='expense', at=at, expense_id=expense_id,
                                  cny_amount=amount, source_id=source_id))

    def apply_decision(self, decision: admission.Decision, *, clock: admission.Clock,
                       quotes: Mapping[str, DecisionQuote], marks: Mapping[str, Mark],
                       currency_fx: Mapping[str, FXQuote] | None = None) -> DecisionAck:
        if decision.decision_at != clock.decision_at:
            raise ValueError('Decision and cash cutoff must match')
        self._time(clock.decision_at)
        for sid in decision.exit_requests:
            if sid not in quotes or quotes[sid].security_id != sid:
                raise ValueError('Exit requires an identified fee/quantity quote')
            self.request_exit(quotes[sid], clock)
        for sid in decision.cancel_buys:
            self.cancel_buy(sid)
        for sid in decision.pause_buys:
            if sid in self.buys:
                self.buys[sid].paused = True
        for sid in decision.continue_buys:
            if sid in self.buys:
                self.buys[sid].paused = False
        bal = self.balance(clock.decision_at, marks, currency_fx)
        initial_cap = GROSS*bal['nav']/6
        eligibility = {e.security_id: e for e in decision.eligibility}
        memories = {m.security_id: m for m in decision.memories}
        accepted, rejected = [], []
        for sid in decision.selected:
            quote = quotes.get(sid)
            e = eligibility.get(sid)
            if quote is None:
                rejected.append((sid, 'decision_quote_unknown')); continue
            if quote.security_id != sid:
                raise ValueError('Recommendation and quote security IDs differ')
            if e is None or e.q is not True or (e.issuer_id, e.sector_id) != (quote.issuer_id, quote.sector_id):
                raise ValueError('Recommendation and execution identity/eligibility mismatch')
            occupied = self.occupancy(clock.decision_at)
            if any(o.issuer_id == quote.issuer_id for o in occupied):
                rejected.append((sid, 'issuer_already_committed')); continue
            sectors = {o.sector_id for o in occupied}
            if (len(occupied) >= 6 or sum(o.sector_id == quote.sector_id for o in occupied) >= 2
                    or (quote.sector_id not in sectors and len(sectors) >= 3)):
                rejected.append((sid, 'capacity_already_committed')); continue
            pending_gross = sum((o.remaining_budget_cny for o in self.buys.values()), ZERO)
            remaining = max(ZERO, GROSS*bal['nav']-bal['inventory']-pending_gross)
            memory = memories[sid]
            if memory.created_at is None or memory.origin is None:
                raise ValueError('Selected recommendation lacks a candidate identity')
            ok, reason = self.reserve_budget(quote=quote, clock=clock,
                       gross_budget_cny=min(initial_cap, remaining),
                       candidate_id=f'{sid}:{memory.created_at.isoformat()}:{memory.origin}')
            (accepted if ok else rejected).append(sid if ok else (sid, reason))
        return DecisionAck(tuple(accepted), tuple(rejected), self.occupancy(clock.decision_at))

    def _eligible_event(self, order, window: FillWindow, side):
        window.validate(); self._time(window.at)
        earliest = order.earliest_at
        if window.security_id != order.quote.security_id:
            raise ValueError('Order and execution security mismatch')
        if order.quote.currency == 'CNY' and dec(window.fx.cny_per_local) != ONE:
            raise ValueError('CNY execution FX must equal one')
        if window.at < earliest or window.market_open is not True:
            return False
        return (window.buy_allowed if side == 'buy' else window.sell_allowed) is True

    def _consume_event(self, order, window):
        identity = order.order_id if isinstance(order, BuyOrder) else order.event_id
        key = identity, window.event_id
        if key in self.used_events:
            return False
        self.used_events.add(key)
        if order.delay_remaining:
            order.delay_remaining -= 1
            return False
        return True

    def fill_buy(self, sid, window: FillWindow) -> FillReceipt | None:
        order = self.buys.get(sid)
        if order is None or order.paused or not self._eligible_event(order, window, 'buy'):
            return None
        price, fx = dec(window.execution_price), window.fx.read(window.at)
        cap = min(order.remaining_shares, int(order.remaining_budget_cny/(price*fx)))
        # The original order satisfied buy_minimum. Its continuing partial fills
        # obey explicit matching granularity, not a fresh minimum on every fill.
        step = window.quantity.fill_step
        low, high = 0, cap//step
        while low < high:
            mid = (low+high+1)//2
            costs = self._fee(order, window.fees, 'buy', mid*step*price,
                              shares=mid*step, par_value=window.par_value)
            if sum(costs.values(), ZERO)*fx <= order.fee_reserved_cny+self.available:
                low = mid
            else:
                high = mid-1
        affordable = low*step
        # First actual submission must still satisfy today's order minimum after
        # a gap. A committed partial remainder then uses fill granularity only.
        submitted = (order.submitted_remaining if order.submitted_remaining
                     else window.quantity.buy_floor(affordable))
        count = min(submitted, affordable, window.capacity_shares)//step*step
        if not count or not self._consume_event(order, window):
            return None
        local = count*price
        components = self._fee(order, window.fees, 'buy', local, shares=count, par_value=window.par_value)
        fee = sum(components.values(), ZERO)*fx
        gross = local*fx
        topup = max(ZERO, fee-order.fee_reserved_cny)
        self.available -= topup
        order.fee_reserved_cny += topup-fee
        order.remaining_budget_cny -= gross
        order.remaining_shares -= count
        order.submitted_remaining = submitted-count
        order.filled_shares += count
        self._remember_fees(order, window.fees, 'buy', local, components,
                           shares=count, par_value=window.par_value)
        pos = self.positions.setdefault(sid, Position(sid, order.quote.issuer_id,
                              order.quote.sector_id, order.quote.currency))
        pos.lots.append(InventoryLot(count, window.sellable_at))
        settlement_id = self._id('pay', sid)
        self.settlements[settlement_id] = Settlement(settlement_id, gross+fee, True,
                        window.cash_due_at, local+sum(components.values(), ZERO), fx, window.fx.source_id)
        receipt = FillReceipt(self._id('fill', sid), sid, 'buy', count, gross, fee, window.at,
                               settlement_id, window.execution_basis)
        self.fills.append(receipt); self.fees_cny += fee
        self.audit_log.append(dict(kind='fill', receipt=receipt, order_id=order.order_id,
                                  raw_open=window.raw_open, price=price, fx_rate=fx,
                                  fx_source=window.fx.source_id, source=window.source_id,
                                  fee_schedule=window.fees.schedule_id, fee_components=components,
                                  gross_budget_remaining=order.remaining_budget_cny,
                                  share_cap_remaining=order.remaining_shares))
        if not order.remaining_shares or not order.remaining_budget_cny:
            self.cancel_buy(sid)
        return receipt

    def fill_exit(self, sid, window: FillWindow) -> FillReceipt | None:
        order = self.exits.get(sid)
        if order is None or not self._eligible_event(order, window, 'sell'):
            return None
        pos = self.positions[sid]
        available = sum(lot.shares for lot in pos.lots if lot.sellable_at <= window.at)
        target = pos.shares if order.remaining_target is None else order.remaining_target
        available = min(available, target)
        additional_available = max(0, available-order.submitted_remaining)
        additional_order = window.quantity.sell_floor(additional_available,
                                                       pos.shares-order.submitted_remaining)
        submitted = order.submitted_remaining+additional_order
        count = min(submitted, available, window.capacity_shares)//window.quantity.fill_step*window.quantity.fill_step
        if not count:
            return None
        price, fx = dec(window.execution_price), window.fx.read(window.at)
        local = count*price
        components = self._fee(order, window.fees, 'sell', local, shares=count, par_value=window.par_value)
        fee = sum(components.values(), ZERO)*fx
        net = local*fx-fee
        if net < 0 and self.available < -net:
            return None
        if not self._consume_event(order, window):
            return None
        order.submitted_remaining = submitted-count
        if order.remaining_target is not None:
            order.remaining_target -= count
        remaining = count
        for lot in pos.lots:
            if lot.sellable_at <= window.at:
                sold = min(remaining, lot.shares); lot.shares -= sold; remaining -= sold
        pos.lots[:] = [lot for lot in pos.lots if lot.shares]
        self._remember_fees(order, window.fees, 'sell', local, components,
                           shares=count, par_value=window.par_value)
        settlement_id = self._id('sale', sid)
        if net < 0:
            self.available += net  # Lock only the excess fee; no borrowed cash.
        self.settlements[settlement_id] = Settlement(settlement_id, abs(net), net < 0,
                        window.cash_due_at, abs(local-sum(components.values(), ZERO)), fx, window.fx.source_id)
        receipt = FillReceipt(self._id('fill', sid), sid, 'sell', count, local*fx, fee,
                               window.at, settlement_id, window.execution_basis)
        self.fills.append(receipt); self.fees_cny += fee
        self.audit_log.append(dict(kind='fill', receipt=receipt, order_id=order.event_id,
                                  raw_open=window.raw_open, price=price, fx_rate=fx,
                                  fx_source=window.fx.source_id, source=window.source_id,
                                  fee_schedule=window.fees.schedule_id, fee_components=components))
        if not pos.shares:
            del self.positions[sid]; del self.exits[sid]
            self.completed.append(admission.ExitCompletion(sid, order.event_id, window.at))
        elif order.remaining_target == 0:
            del self.exits[sid]
        return receipt

    def settle_due(self, at) -> tuple[str, ...]:
        self._time(at)
        done = []
        for key, item in list(self.settlements.items()):
            if item.due_at <= at:
                if not item.debit:
                    self.available += item.cny_amount
                # Debit cash was already locked, never available for another buy.
                del self.settlements[key]; done.append(key)
                self.audit_log.append(dict(kind='settle', at=at, settlement=item))
        return tuple(done)

    def accrue_dividend(self, *, event_id, sid, currency, net_local, ex_at,
                        paid_at: datetime | None, source_id, entitlement_basis):
        self._time(ex_at)
        if event_id in self.action_events:
            raise ValueError('Duplicate corporate action event')
        if (not event_id or not source_id or not entitlement_basis
                or currency not in ('CNY', 'HKD') or dec(net_local) < 0):
            raise ValueError('Identified net cash entitlement required')
        if paid_at is not None:
            aware(paid_at)
            if paid_at < ex_at:
                raise ValueError('Dividend payment cannot precede accrual')
        self.action_events.add(event_id)
        self.dividends[event_id] = DividendReceivable(event_id, sid, currency, dec(net_local), ex_at,
                                                     paid_at, source_id, entitlement_basis)
        self.audit_log.append(dict(kind='dividend_accrual', receivable=self.dividends[event_id]))

    def pay_dividend(self, event_id, *, at, fx: FXQuote, payment_evidence_id, payment_known_at):
        self._time(at)
        aware(payment_known_at)
        if event_id in self.paid_dividends:
            raise ValueError('Dividend already paid')
        d = self.dividends[event_id]
        if (not payment_evidence_id or payment_known_at > at
                or (d.paid_at is not None and at < d.paid_at)):
            raise ValueError('Payment evidence and effective payment time required')
        rate = fx.read(at)
        if d.currency == 'CNY' and rate != ONE:
            raise ValueError('CNY dividend FX must equal one')
        self.available += d.net_local*rate
        del self.dividends[event_id]; self.paid_dividends.add(event_id)
        self.audit_log.append(dict(kind='dividend_payment', at=at, entitlement=d,
                                  payment_evidence_id=payment_evidence_id, fx_rate=rate,
                                  fx_source=fx.source_id))

    def split(self, *, event_id, sid, ratio, at, new_shares_sellable_at):
        """Integer split/bonus bridge only; unsupported fractions fail before edits."""
        self._time(at); aware(new_shares_sellable_at)
        ratio = positive(ratio)
        if event_id in self.action_events or not event_id or new_shares_sellable_at < at:
            raise ValueError('Invalid/duplicate split event')
        pos, order = self.positions.get(sid), self.buys.get(sid)
        quantities = ([lot.shares for lot in pos.lots] if pos else [])
        if order:
            quantities += [order.target_shares, order.remaining_shares, order.filled_shares,
                           order.submitted_remaining]
        if sid in self.exits and ratio < ONE:
            quantities.append(self.exits[sid].submitted_remaining)
        if sid in self.exits and self.exits[sid].remaining_target is not None:
            quantities.append(self.exits[sid].remaining_target)
        if any(dec(q)*ratio != int(dec(q)*ratio) for q in quantities):
            raise ValueError('Fractional corporate-action claim requires separate adapter')
        if pos:
            if ratio >= ONE:
                additions = [InventoryLot(int(dec(lot.shares)*(ratio-ONE)),
                                          max(lot.sellable_at, new_shares_sellable_at))
                             for lot in pos.lots if int(dec(lot.shares)*(ratio-ONE))]
                pos.lots.extend(additions)  # Existing sellable shares stay sellable.
            else:
                for lot in pos.lots:
                    lot.shares = int(dec(lot.shares)*ratio)
                    lot.sellable_at = max(lot.sellable_at, new_shares_sellable_at)
        if order:
            order.target_shares = int(dec(order.target_shares)*ratio)
            order.remaining_shares = int(dec(order.remaining_shares)*ratio)
            order.filled_shares = int(dec(order.filled_shares)*ratio)
            order.submitted_remaining = int(dec(order.submitted_remaining)*ratio)
        if sid in self.exits and ratio < ONE:
            submitted = dec(self.exits[sid].submitted_remaining)*ratio
            self.exits[sid].submitted_remaining = int(submitted)
        if sid in self.exits and self.exits[sid].remaining_target is not None:
            self.exits[sid].remaining_target = int(dec(self.exits[sid].remaining_target)*ratio)
        self.action_events.add(event_id)
        self.audit_log.append(dict(kind='split', at=at, sid=sid, event_id=event_id,
                                  ratio=ratio, new_shares_sellable_at=new_shares_sellable_at))
