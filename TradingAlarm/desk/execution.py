"""Quantity/fee primitives copied from the frozen ledger, with close-price guidance sizing."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Mapping
ZERO=Decimal('0')

def dec(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Finite amounts required')
    return result

def positive(value) -> Decimal:
    value = dec(value)
    if value <= 0:
        raise ValueError('Positive amount required')
    return value

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

class RuleBook:
    def __init__(self, rules): self.rules=rules
    def quantity(self, symbol, day):
        candidates=[x for x in self.rules['quantity_versions'][symbol] if x['from']<=day and (not x['to'] or day<x['to'])]
        if not candidates: raise ValueError('数量规则未覆盖 '+symbol)
        return QuantityRule(**candidates[-1]['rule'])
    def fees(self, symbol, day):
        venue=[x for x in self.rules['venue_versions'][symbol] if x['from']<=day and (not x['to'] or day<x['to'])][-1]['venue']
        candidates=[x for x in self.rules['fee_versions'][venue] if x['from']<=day]
        # This is a reference estimate only. Real fees are entered from the broker fill.
        spec=candidates[-1]['schedule']
        return FeeSchedule(spec['schedule_id'],tuple(FeeComponent(**x) for x in spec['components']))
    def size(self,symbol,day,price,budget,cash):
        rule=self.quantity(symbol,day);fees=self.fees(symbol,day);maximum=int(budget/price)
        lo,hi=0,max(0,(maximum-rule.buy_minimum)//rule.buy_step+1)
        while lo<hi:
            mid=(lo+hi+1)//2;qty=rule.buy_minimum+(mid-1)*rule.buy_step
            gross=qty*price;fee=sum(fees.incremental('buy',gross,{}, {},1,shares=qty,par_value=Decimal(1)).values(),ZERO)
            if gross+fee<=cash:lo=mid
            else:hi=mid-1
        qty=rule.buy_minimum+(lo-1)*rule.buy_step if lo else 0
        gross=qty*price;fee=sum(fees.incremental('buy',gross,{}, {},1,shares=qty,par_value=Decimal(1)).values(),ZERO) if qty else ZERO
        return qty,gross,fee

    def reserve(self,symbol,day,price,cap,cash):
        rule=self.quantity(symbol,day);fees=self.fees(symbol,day)
        low,high=0,int(min(cap,cash)*100)
        while low<high:
            mid=(low+high+1)//2;budget=Decimal(mid)/100
            fee=sum(fees.incremental('buy',budget,{}, {},1,shares=budget/price,par_value=Decimal(1)).values(),ZERO)
            if budget+fee<=cash:low=mid
            else:high=mid-1
        budget=Decimal(low)/100
        qty=rule.buy_floor(int(budget/price))
        fee=sum(fees.incremental('buy',budget,{}, {},1,shares=budget/price,par_value=Decimal(1)).values(),ZERO)
        return qty,budget,fee
