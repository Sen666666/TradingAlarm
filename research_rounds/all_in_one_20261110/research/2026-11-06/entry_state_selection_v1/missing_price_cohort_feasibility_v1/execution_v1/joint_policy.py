"""Import-safe JOINT_AB_PRICE_V1 policy primitives. No input I/O or simulation.

AB is never sized here: its original engine retains original flags/cache/semantics.
PRICE uses its own cache and price-valid checks, not native volume_eligible.
"""
from dataclasses import dataclass
from decimal import Decimal as D
from math import isfinite
from typing import Mapping

NAV = D('1200000')
INIT = D('24000')
SLOT = D('48000')
RISK = D('3000')
SLIP = D('.0005')
INDUSTRY_FIELDS = ('sector_known', 'sector_observed_today',
                   'sector_rs_ready_fresh', 'sector_up')


def finite(value):
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


def truth(value):
    # A missing/nullable fact is never false-by-default.
    if value is None:
        return None
    try:
        if value != value:
            return None
        if value in (True, 1):
            return True
        if value in (False, 0):
            return False
    except (TypeError, ValueError):
        pass
    return None


def industry_gate(row):
    values = [truth(row.get(k)) for k in INDUSTRY_FIELDS]
    if None in values:
        return 'INDUSTRY_UNKNOWN'
    return 'PASS' if all(values) else 'INDUSTRY_FALSE'


def known_pvr(row):
    return truth(row.get('PVR_known')) is True and finite(row.get('PVR_score'))


def rank_key(row):
    """Known AB+PRICE together; unknown PRICE last. No cross-stock AB priority."""
    if known_pvr(row):
        return (0, -float(row['PVR_score']), row['sid'])
    if row['owner_lane'] != 'PRICE':
        raise ValueError('AB_UNKNOWN_PVR_NOT_ELIGIBLE')
    return (1, 0.0, row['sid'])


def ab_legal(row, check):
    return bool(row and row.get('event_type') in (
        'A_SECTOR_BIRTH', 'B_STOCK_BIRTH_DURING_SECTOR') and
        truth(row.get('I_qualified')) is True and known_pvr(row) and
        check.get('close_check') == 'PASS')


def choose_same_stock(ab_row, ab_check, price_row, price_check, state='FLAT'):
    """Return one lane only. Known AB CLOSE failure may admit PRICE; OPEN never falls back."""
    if state != 'FLAT':
        return None, 'BLOCKED_' + state
    if ab_legal(ab_row, ab_check or {}):
        return 'AB', 'AB_VALID_CLOSE_PRIORITY'
    if price_row and industry_gate(price_row) == 'PASS' and price_check.get('close_check') == 'PASS':
        return 'PRICE', 'PRICE_VALID_CLOSE'
    return None, 'NO_LEGAL_CLOSE_OFFER'


@dataclass(frozen=True)
class OpenView:
    """Only O-at-OPEN fields. Deliberately has no H/L/C/amount/phase/root/S."""
    raw_open: object
    adjustment_factor: object
    source_kind: object
    source_path: object
    segment_id: object

    @classmethod
    def from_mapping(cls, row: Mapping):
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__})

    @property
    def lineage(self):
        return tuple(str(x) for x in (self.source_kind, self.source_path, self.segment_id))


class PriceSizing:
    def __init__(self, engine):
        self.s = engine
        self.close_cache = {}

    def close_check(self, row, *, window, role='PROBE', budget=INIT, risk=RISK):
        sid, day = row['sid'], row['day']
        # Opaque root/floor/target/budget inputs are part of the cache identity.
        key = (window, sid, str(day), role, str(row.get('root_id')),
               str(row.get('receipt_id')), str(row.get('S_new')),
               str(row.get('adjustment_factor')), str(row.get('raw_close')),
               str(row.get('price_valid')), str(row.get('capacity_shares')),
               str(row.get('target_version')), str(budget), str(risk))
        if key in self.close_cache:
            return dict(self.close_cache[key])
        if truth(row.get('price_valid')) is not True or not finite(row.get('raw_close')) or D(str(row['raw_close'])) <= 0:
            result = {'close_check': 'INVALID_PRICE_CLOSE_UNKNOWN'}
        elif not finite(row.get('adjustment_factor')) or D(str(row['adjustment_factor'])) <= 0 or not finite(row.get('S_new')) or D(str(row['S_new'])) <= 0:
            result = {'close_check': 'PRICE_COORDINATE_OR_S_UNKNOWN'}
        elif not finite(row.get('capacity_shares')):
            result = {'close_check': 'PRIOR_VOLUME_CAPACITY_UNKNOWN'}
        else:
            floor = D(str(row['S_new'])) / D(str(row['adjustment_factor']))
            op = D(str(row['raw_close']))
            if op <= floor:
                result = {'close_check': 'CLOSE_AT_OR_BELOW_PROTECTION'}
            else:
                try:
                    q, bf, plan_risk, _, _ = self.s.size(
                        sid, day, op * (1 + SLIP), floor, budget, risk,
                        int(row['capacity_shares']))
                    result = dict(close_check='PASS' if q > 0 else 'MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE',
                                  close_q=q, close_fee=float(bf), close_plan_risk=float(plan_risk),
                                  close_floor_raw=float(floor), prior20_capacity=int(row['capacity_shares']))
                except (self.s.RuleUnavailable, KeyError, ValueError) as error:
                    result = dict(close_check='DATED_RULE_UNKNOWN_AT_CLOSE', reason=str(error))
        self.close_cache[key] = dict(result)
        return result

    def initial_open(self, sid, day, view: OpenView, *, floor, capacity):
        # Lineage/factor/claim authorization is the consumer's prior validation.
        # No current daily market state can enter this function.
        if not finite(view.raw_open) or D(str(view.raw_open)) <= 0:
            return {'result': 'MISSING_OPEN_UNKNOWN'}
        if not finite(floor) or D(str(floor)) <= 0:
            return {'result': 'PROTECTION_UNKNOWN'}
        op, floor = D(str(view.raw_open)), D(str(floor))
        if op <= floor:
            return {'result': 'PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT'}
        if not finite(capacity):
            return {'result': 'PRIOR_VOLUME_CAPACITY_UNKNOWN'}
        try:
            q, bf, plan_risk, _, _ = self.s.size(sid, day, op * (1 + SLIP), floor,
                                                INIT, RISK, int(capacity))
        except (self.s.RuleUnavailable, KeyError, ValueError) as error:
            return dict(result='DATED_RULE_UNKNOWN_AT_OPEN', reason=str(error))
        return dict(result='PASS' if q else 'PRECHECK_Q0_NO_SUBMIT', q=q,
                    price=op * (1 + SLIP), fee=bf, risk=plan_risk, floor=floor,
                    raw_open=op, budget=INIT, remaining_risk=RISK)

    def add_open(self, sid, day, view: OpenView, *, floor, capacity, held_qty,
                 all_entry_fees, prior_net, add_spent=D(0), remaining_qty=None):
        """One target or its whole remainder. Existing combined inventory gets one sell fee."""
        if not finite(view.raw_open) or D(str(view.raw_open)) <= 0:
            return {'result': 'MISSING_OPEN_UNKNOWN'}
        if not finite(floor) or D(str(floor)) <= 0:
            return {'result': 'PROTECTION_UNKNOWN'}
        if not finite(capacity):
            return {'result': 'PRIOR_VOLUME_CAPACITY_UNKNOWN'}
        op, floor = D(str(view.raw_open)), D(str(floor))
        if prior_net <= 0:
            return {'result': 'PRECHECK_OPEN_NOT_PROFITABLE_NO_SUBMIT'}
        if op <= floor:
            return {'result': 'PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT'}
        try:
            _, fs, par = self.s.getmeta(sid, day)
            px = op * (1 + SLIP)
            existing = max(D(0), D(held_qty) * (px - floor * (1 - SLIP)) +
                           D(all_entry_fees) + self.s.fee(held_qty, floor * (1 - SLIP), fs, 'sell', par)) if held_qty else D(0)
            remrisk = max(D(0), RISK - existing)
            budget = max(D(0), min(INIT - D(add_spent), SLOT - D(held_qty) * op))
            q, bf, ar, _, _ = self.s.size(sid, day, px, floor, budget, remrisk, int(capacity))
            if remaining_qty is not None:
                qr, _, _ = self.s.getmeta(sid, day)
                if remaining_qty <= 0 or qr.buy_floor(remaining_qty) != remaining_qty or q < remaining_qty:
                    return dict(result='PRECHECK_FIXED_REMAINDER_NOT_FUNDED_NO_SUBMIT', q=0,
                                feasible_upper_q=q, fixed_remaining=remaining_qty)
                q = remaining_qty
                bf = self.s.fee(q, px, fs, 'buy', par)
                ar = max(D(0), D(q) * (px - floor * (1 - SLIP)) + bf + self.s.fee(q, floor * (1 - SLIP), fs, 'sell', par))
            return dict(result='PASS' if q else 'PRECHECK_Q0_NO_SUBMIT', q=q, price=px,
                        fee=bf, risk=ar, existing_risk=existing, remaining_risk=remrisk,
                        floor=floor, raw_open=op, budget=budget)
        except (self.s.RuleUnavailable, KeyError, ValueError) as error:
            return dict(result='DATED_RULE_UNKNOWN_AT_OPEN', reason=str(error))

    def probe_remaining(self, sid, day, view: OpenView, *, floor, capacity,
                        filled_qty, entry_fees, probe_spent, remaining_qty):
        """PROBE residual: no profitability or CONFIRMED gate, no new target budget."""
        if not finite(view.raw_open) or D(str(view.raw_open)) <= 0:
            return {'result': 'MISSING_OPEN_UNKNOWN'}
        if not finite(floor) or D(str(floor)) <= 0:
            return {'result': 'PROTECTION_UNKNOWN'}
        if not finite(capacity):
            return {'result': 'PRIOR_VOLUME_CAPACITY_UNKNOWN'}
        op, floor = D(str(view.raw_open)), D(str(floor))
        if op <= floor:
            return {'result': 'PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT'}
        try:
            qr, fs, par = self.s.getmeta(sid, day)
            px = op*(1+SLIP)
            existing = max(D(0), D(filled_qty)*(px-floor*(1-SLIP)) + D(entry_fees) +
                           self.s.fee(filled_qty,floor*(1-SLIP),fs,'sell',par)) if filled_qty else D(0)
            remrisk = max(D(0),RISK-existing)
            budget = max(D(0),INIT-D(probe_spent))
            upper,_,_,_,_ = self.s.size(sid,day,px,floor,budget,remrisk,int(capacity))
            if remaining_qty<=0 or qr.buy_floor(remaining_qty)!=remaining_qty or upper<remaining_qty:
                return dict(result='PRECHECK_FIXED_REMAINDER_NOT_FUNDED_NO_SUBMIT',q=0,
                            feasible_upper_q=upper,fixed_remaining=remaining_qty)
            q=remaining_qty;bf=self.s.fee(q,px,fs,'buy',par)
            risk=max(D(0),D(q)*(px-floor*(1-SLIP))+bf+self.s.fee(q,floor*(1-SLIP),fs,'sell',par))
            return dict(result='PASS',q=q,price=px,fee=bf,risk=risk,existing_risk=existing,
                        remaining_risk=remrisk,floor=floor,raw_open=op,budget=budget)
        except (self.s.RuleUnavailable,KeyError,ValueError) as error:
            return dict(result='DATED_RULE_UNKNOWN_AT_OPEN',reason=str(error))


def price_protection_close(*, held_root, prior_s, fact):
    """Source UNKNOWN wins; old S is tested before today's ratchet."""
    if truth(fact.get('price_valid')) is not True or truth(fact.get('root_unknown')) is True:
        return 'UNKNOWN', prior_s
    if fact.get('root_id') != held_root or not finite(fact.get('close')):
        return 'UNKNOWN', prior_s
    if D(str(fact['close'])) <= D(str(prior_s)):
        return 'EXIT', prior_s
    new_s = fact.get('S_new')
    if not finite(new_s) or D(str(new_s)) < D(str(prior_s)):
        return 'UNKNOWN', prior_s
    return 'HOLD', max(D(str(prior_s)), D(str(new_s)))


def add_market_permission(*, fact, healthy, probe_complete, complete_known_at,
                          receipt_known_at, add_parent_exists, net):
    if not healthy or not probe_complete or complete_known_at is None:
        return False
    return bool(not add_parent_exists and receipt_known_at > complete_known_at and
                truth(fact.get('receipt')) is True and fact.get('phase') == 'CONFIRMED' and
                industry_gate(fact) == 'PASS' and net > 0)
