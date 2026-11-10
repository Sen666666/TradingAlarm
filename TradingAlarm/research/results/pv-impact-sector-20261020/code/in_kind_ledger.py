"""Non-cash distribution subledger. No automatic liquidation or inferred delivery date.
Whole-share claims are valued using dated recipient prices and FX. Fractional
claims require explicit cash-in-lieu terms before valuation/settlement.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from datetime import date

def valid_date(value):
    date.fromisoformat(value)
    return value

@dataclass
class SecurityClaim:
    event_id:str
    recipient:str
    ex_date:str
    whole:int
    fraction:Fraction
    delivered:bool=False
    delivered_at:str|None=None

class InKindLedger:
    def __init__(self):
        self.claims={};self.holdings={}
    def accrue(self,event_id,recipient,ex_date,eligible_parent_shares,numerator,denominator):
        valid_date(ex_date)
        if event_id in self.claims:raise ValueError('duplicate distribution')
        if not event_id or not recipient or not isinstance(eligible_parent_shares,int) or eligible_parent_shares<0 or not isinstance(numerator,int) or not isinstance(denominator,int) or numerator<=0 or denominator<=0:raise ValueError('invalid entitlement')
        entitlement=Fraction(eligible_parent_shares*numerator,denominator)
        whole=entitlement.numerator//entitlement.denominator
        claim=SecurityClaim(event_id,recipient,ex_date,whole,entitlement-whole)
        self.claims[event_id]=claim
        return claim
    def deliver(self,event_id,asof,confirmed_delivery_date):
        valid_date(asof)
        c=self.claims[event_id]
        if confirmed_delivery_date is None:return 0
        valid_date(confirmed_delivery_date)
        if confirmed_delivery_date<c.ex_date:raise ValueError('delivery before entitlement')
        if asof<confirmed_delivery_date or c.delivered:return 0
        self.holdings[c.recipient]=self.holdings.get(c.recipient,0)+c.whole
        c.delivered=True;c.delivered_at=asof
        return c.whole
    def value(self,asof,marks,fraction_policy="strict"):
        """marks: recipient -> (price_date,raw_price,fx_date,fx_to_base).
        Marks may be stale; caller must report market calendar/valuation staleness.
        No cash is created. Unresolved fraction fails closed even after delivery.
        """
        valid_date(asof);claim_value=0.;holding_value=0.
        active=[c for c in self.claims.values() if c.ex_date<=asof]
        if fraction_policy not in ('strict','zero_floor'):raise ValueError('unknown fraction policy')
        if fraction_policy=='strict' and any(c.fraction for c in active):raise ValueError('fractional cash-in-lieu terms unresolved')
        if any(c.delivered_at is not None and c.delivered_at>asof for c in self.claims.values()):raise ValueError('cannot value state before delivery history')
        def price(symbol):
            pd,p,fd,fx=marks[symbol];valid_date(pd);valid_date(fd)
            if pd>asof or fd>asof or not all(isfinite(x) and x>0 for x in (p,fx)):raise ValueError('invalid or future valuation mark')
            return p*fx
        for c in active:
            if not c.delivered and c.whole:claim_value+=c.whole*price(c.recipient)
        for symbol,qty in self.holdings.items():
            if qty:holding_value+=qty*price(symbol)
        return dict(security_receivables=claim_value,delivered_holdings=holding_value,total=claim_value+holding_value,spendable_cash=0.)
