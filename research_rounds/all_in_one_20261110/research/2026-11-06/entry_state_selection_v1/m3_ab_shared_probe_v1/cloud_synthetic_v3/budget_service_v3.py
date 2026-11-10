"""Synthetic Decimal-only M3 A+B shared-obligation scaffold.

No original-source import, price sizing, M3 calculation, CP verification, NAV
certification or AB profit computation. Inputs are external evidence envelopes.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Iterable, Mapping

ZERO = Decimal('0')

class ContractError(ValueError):
    pass

def amount(value, name='amount'):
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise ContractError(f'{name}: finite nonnegative Decimal required')
    return value

def signed_amount(value, name='amount'):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ContractError(f'{name}: finite Decimal required')
    return value

def identifier(value, name='identifier'):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f'{name}: nonempty text required')
    return value

@dataclass(frozen=True)
class Charge:
    cash: Decimal
    capital: Decimal
    slot: Decimal
    nominal_risk: Decimal
    fee_risk: Decimal
    def __post_init__(self):
        for name in self.__dataclass_fields__:
            amount(getattr(self, name), name)
    def __add__(self, other):
        return Charge(*(getattr(self, n) + getattr(other, n) for n in self.__dataclass_fields__))
    def subtract(self, other):
        return Charge(*(getattr(self, n) - getattr(other, n) for n in self.__dataclass_fields__))
    def within(self, other):
        return all(getattr(self, n) <= getattr(other, n) for n in self.__dataclass_fields__)
    @property
    def is_zero(self):
        return all(getattr(self, n) == ZERO for n in self.__dataclass_fields__)

EMPTY = Charge(ZERO, ZERO, ZERO, ZERO, ZERO)

@dataclass(frozen=True)
class RoundLimits:
    nd: Decimal
    initial_cash_budget: Decimal
    add_cash_budget: Decimal
    slot_cap: Decimal
    fee_risk_cap: Decimal
    signal_close_ref: str
    def __post_init__(self):
        for name in ('nd', 'initial_cash_budget', 'add_cash_budget', 'slot_cap', 'fee_risk_cap'):
            amount(getattr(self, name), name)
        for name, ratio in (('initial_cash_budget', '.02'), ('add_cash_budget', '.02'), ('slot_cap', '.04'), ('fee_risk_cap', '.0025')):
            if getattr(self, name) > self.nd * Decimal(ratio):
                raise ContractError(f'{name} exceeds frozen Nd research limit')
        identifier(self.signal_close_ref)

@dataclass(frozen=True)
class WalletLimits:
    n: Decimal
    effective_nav_after_unbooked_buy_fees: Decimal
    probe_capital_cap: Decimal
    probe_nominal_risk_cap: Decimal
    probe_industry_all_capital_cap: Decimal
    confirmed_industry_all_capital_cap: Decimal | None
    nav_certified: bool
    snapshot_ref: str
    def __post_init__(self):
        for name in ('n', 'effective_nav_after_unbooked_buy_fees', 'probe_capital_cap', 'probe_nominal_risk_cap', 'probe_industry_all_capital_cap'):
            amount(getattr(self, name), name)
        if self.effective_nav_after_unbooked_buy_fees > self.n:
            raise ContractError('post-fee effective NAV cannot exceed supplied current N')
        if self.probe_capital_cap > self.effective_nav_after_unbooked_buy_fees * Decimal('.10') or self.probe_nominal_risk_cap > self.effective_nav_after_unbooked_buy_fees * Decimal('.005'):
            raise ContractError('probe caps exceed explicit post-fee effective NAV research limits')
        if self.probe_industry_all_capital_cap > self.n * Decimal('.02'):
            raise ContractError('PROBE-candidate industry ALL cap exceeds 2% current certified N')
        if self.confirmed_industry_all_capital_cap is not None:
            amount(self.confirmed_industry_all_capital_cap, 'confirmed_industry_all_capital_cap')
        identifier(self.snapshot_ref)
        if type(self.nav_certified) is not bool:
            raise ContractError('nav_certified must be bool; its truth is externally established')

@dataclass(frozen=True)
class Asset:
    lot_id: str
    stock: str
    round_id: str
    sector: str
    pool: str
    charge: Charge
    filled_session: int
    known: bool = True
    def __post_init__(self):
        for name in ('lot_id', 'stock', 'round_id', 'sector'):
            identifier(getattr(self, name), name)
        if self.pool not in ('PROBE', 'CORE'):
            raise ContractError('invalid pool')
        if type(self.filled_session) is not int or self.filled_session < 0:
            raise ContractError('filled_session must be nonnegative int')
        if type(self.known) is not bool:
            raise ContractError('known must be bool')

@dataclass(frozen=True)
class Claim:
    claim_id: str
    stock: str
    round_id: str
    value: Decimal
    source_ref: str
    def __post_init__(self):
        for name in ('claim_id', 'stock', 'round_id', 'source_ref'):
            identifier(getattr(self, name), name)
        amount(self.value)

@dataclass(frozen=True)
class Intent:
    order_id: str
    stock: str
    round_id: str
    sector: str
    kind: str
    pool: str
    charge: Charge
    initial_sector_slot: int | None
    evidence_ref: str
    def __post_init__(self):
        for name in ('order_id', 'stock', 'round_id', 'sector', 'evidence_ref'):
            identifier(getattr(self, name), name)
        if self.kind not in ('INIT', 'ADD') or self.pool not in ('PROBE', 'CORE'):
            raise ContractError('invalid action or pool')
        if self.kind == 'INIT' and (type(self.initial_sector_slot) is not int or self.initial_sector_slot not in (1, 2)):
            raise ContractError('INIT needs original industry opportunity slot 1 or 2')
        if self.kind == 'ADD' and self.initial_sector_slot is not None:
            raise ContractError('ADD is not an initial opportunity slot')
        if self.charge.cash <= ZERO:
            raise ContractError('new buy requires positive cash charge')

@dataclass(frozen=True)
class Reservation:
    intent: Intent
    remaining: Charge
    status: str = 'live'

@dataclass(frozen=True)
class PromotionProof:
    stock: str
    round_id: str
    snapshot_ref: str
    close_net80: Decimal
    open_net80: Decimal
    fresh_cp_after_first_fill: bool
    m3_true: bool
    proof_ref: str
    def __post_init__(self):
        for name in ('stock', 'round_id', 'snapshot_ref', 'proof_ref'):
            identifier(getattr(self, name), name)
        signed_amount(self.close_net80)
        signed_amount(self.open_net80)
        if type(self.fresh_cp_after_first_fill) is not bool or type(self.m3_true) is not bool:
            raise ContractError('eligibility evidence flags must be bool')

class SharedBudget:
    """One modeled OPEN. No hidden strategy ordering or financial formula defaults.

    Call known exits/settlements, freeze the supplied NAV and promotion evidence,
    apply per-stock grants, then freeze/process the exact external queue. All
    evidence values remain unverified by this scaffold.
    """
    def __init__(self, *, session: int, seed_cash: Decimal,
                 cash_by_round: Mapping[str, Decimal],
                 round_limits: Mapping[str, RoundLimits], assets: Iterable[Asset] = (),
                 claims: Iterable[Claim] = (), add_used: Iterable[str] = ()):
        if type(session) is not int or session < 0:
            raise ContractError('session must be a nonnegative trading-session index')
        self.session = session
        self.seed_cash = amount(seed_cash)
        self._round_cash = {identifier(k): signed_amount(v) for k, v in cash_by_round.items()}
        self._round_limits = dict(round_limits)
        if not all(isinstance(v, RoundLimits) for v in self._round_limits.values()):
            raise ContractError('explicit RoundLimits required')
        alist, clist = tuple(assets), tuple(claims)
        if len({a.lot_id for a in alist}) != len(alist) or len({c.claim_id for c in clist}) != len(clist):
            raise ContractError('duplicate asset/claim id')
        self._assets = {a.lot_id: a for a in alist}
        self._claims = {c.claim_id: c for c in clist}
        self._reserves = {}
        self._used_add = set(add_used)
        self._events = set()
        self._decisions = []
        self._queue = None
        self._index = 0
        self._limits = None
        self._proofs = {}
        self._prequeue_rounds = {(a.stock, a.round_id) for a in alist}
        self._promoted = set()
        if self.cash < ZERO:
            raise ContractError('negative supplied available cash')
        for a in alist:
            if a.round_id not in self._round_limits or a.filled_session > session:
                raise ContractError('asset requires round limits and nonfuture fill session')

    @property
    def cash(self):
        return self.seed_cash + sum(self._round_cash.values(), ZERO)
    @property
    def available_cash(self):
        return self.cash - sum((r.remaining.cash for r in self._reserves.values()), ZERO)
    @property
    def assets(self):
        return tuple(self._assets.values())
    @property
    def claims(self):
        return tuple(self._claims.values())
    @property
    def reservations(self):
        return tuple(self._reserves.values())
    @property
    def decisions(self):
        return tuple(self._decisions)
    @property
    def unknown(self):
        return any(not a.known for a in self._assets.values())
    def round_cash(self, round_id):
        return self._round_cash.get(round_id, ZERO)
    def round_claims(self, round_id):
        return sum((c.value for c in self._claims.values() if c.round_id == round_id), ZERO)
    def usage(self, *, pool=None, sector=None, stock=None, round_id=None):
        total = EMPTY
        for item, charge in [(a, a.charge) for a in self._assets.values()] + [(r.intent, r.remaining) for r in self._reserves.values()]:
            if all(v is None or getattr(item, k) == v for k, v in (('pool', pool), ('sector', sector), ('stock', stock), ('round_id', round_id))):
                total = total + charge
        return total
    def _new_event(self, event_id):
        identifier(event_id)
        if event_id in self._events:
            raise ContractError('duplicate event id')
    def _before_snapshot(self):
        if self._limits is not None:
            raise ContractError('known exits and settlements must precede admission NAV snapshot')
    def record_exit(self, *, event_id, lot_id, net_cash, source_ref):
        self._before_snapshot()
        self._new_event(event_id)
        identifier(source_ref)
        amount(net_cash)
        a = self._assets[lot_id]
        if not a.known:
            raise ContractError('UNKNOWN asset has no certified exit fact')
        if a.filled_session >= self.session:
            raise ContractError('T+1 is per fill: same-session lot cannot be sold')
        # Exact net cash must come from original whole-order dated fee allocator.
        del self._assets[lot_id]
        self._round_cash[a.round_id] = self.round_cash(a.round_id) + net_cash
        self._events.add(event_id)
    def record_claim(self, *, event_id, claim):
        self._before_snapshot()
        self._new_event(event_id)
        if claim.claim_id in self._claims:
            raise ContractError('duplicate claim id')
        self._claims[claim.claim_id] = claim
        self._events.add(event_id)
    def settle_claim(self, *, event_id, claim_id, value, effective_session, source_ref):
        self._before_snapshot()
        self._new_event(event_id)
        identifier(source_ref)
        amount(value)
        if type(effective_session) is not int or effective_session != self.session:
            raise ContractError('settlement is not effective at this OPEN')
        c = self._claims[claim_id]
        if value <= ZERO or value > c.value:
            raise ContractError('invalid settled amount')
        rest = c.value - value
        if rest == ZERO:
            del self._claims[claim_id]
        else:
            self._claims[claim_id] = replace(c, value=rest)
        self._round_cash[c.round_id] = self.round_cash(c.round_id) + value
        self._events.add(event_id)
    def freeze_snapshot(self, limits, proofs=()):
        if self._limits is not None:
            raise ContractError('snapshot already frozen')
        if not isinstance(limits, WalletLimits):
            raise ContractError('WalletLimits required')
        proofs = tuple(proofs)
        keys = [(p.stock, p.round_id) for p in proofs]
        if len(set(keys)) != len(keys) or any(p.snapshot_ref != limits.snapshot_ref for p in proofs):
            raise ContractError('duplicate proof or mismatched eligibility snapshot')
        self._limits, self._proofs = limits, dict(zip(keys, proofs))
        # Re-evaluate after all known exits; same-session new holdings are excluded.
        self._prequeue_rounds = {(a.stock, a.round_id) for a in self._assets.values() if a.filled_session < self.session}
    def promote_stock(self, stock, round_id):
        if self._limits is None or self._queue is not None:
            raise ContractError('promotion must use frozen snapshot before queue')
        if self.unknown or not self._limits.nav_certified:
            raise ContractError('uncertified evidence: new-risk/promotion freeze')
        key = (stock, round_id)
        if key not in self._prequeue_rounds or key in self._promoted:
            raise ContractError('no existing eligible round or already promoted')
        proof = self._proofs.get(key)
        if proof is None or proof.close_net80 <= ZERO or proof.open_net80 <= ZERO or not proof.fresh_cp_after_first_fill or not proof.m3_true:
            raise ContractError('missing positive round-specific AB promotion evidence')
        matches = [a for a in self._assets.values() if (a.stock, a.round_id) == key]
        if not any(a.pool == 'PROBE' for a in matches):
            raise ContractError('promotion requires an existing PROBE layer')
        for a in matches:
            self._assets[a.lot_id] = replace(a, pool='CORE')
        self._promoted.add(key)
    def freeze_queue(self, queue, *, policy_ref):
        if self._limits is None or self._queue is not None:
            raise ContractError('freeze snapshot first; queue can be frozen once')
        identifier(policy_ref)
        queue = tuple(queue)
        if len({i.order_id for i in queue}) != len(queue):
            raise ContractError('duplicate order id')
        slots = [(i.sector, i.initial_sector_slot) for i in queue if i.kind == 'INIT']
        if len(set(slots)) != len(slots):
            raise ContractError('duplicate original industry opportunity slot')
        if any(i.round_id not in self._round_limits for i in queue):
            raise ContractError('missing signal-CLOSE frozen round limits')
        round_stocks = {}
        stock_sectors = {}
        for item in list(self._assets.values()) + list(self._claims.values()) + list(queue):
            if item.round_id in round_stocks and round_stocks[item.round_id] != item.stock:
                raise ContractError('one original round cannot belong to different stocks')
            round_stocks[item.round_id] = item.stock
            if hasattr(item, 'sector'):
                if item.stock in stock_sectors and stock_sectors[item.stock] != item.sector:
                    raise ContractError('stock has conflicting same-session sector charges')
                stock_sectors[item.stock] = item.sector
        self._queue = queue
        self.queue_policy_ref = policy_ref
    def reserve_next(self, order_id, *, allocation_limits):
        if self._queue is None or self._index >= len(self._queue):
            raise ContractError('no remaining frozen queue entry')
        i = self._queue[self._index]
        if i.order_id != order_id:
            raise ContractError('cannot reorder or insert into frozen global queue')
        if not isinstance(allocation_limits, WalletLimits) or allocation_limits.snapshot_ref != self._limits.snapshot_ref:
            raise ContractError('each allocation requires explicit matching post-fee NAV/caps')
        if allocation_limits.n > self._limits.n:
            raise ContractError('allocation NAV exceeds frozen certified snapshot')
        self._index += 1
        reason = self._admission_reason(i, allocation_limits)
        if reason is None:
            self._reserves[i.order_id] = Reservation(i, i.charge)
        self._decisions.append((i.order_id, 'reserved' if reason is None else reason))
        return reason is None
    def _admission_reason(self, i, caps):
        if self.unknown or not self._limits.nav_certified or not caps.nav_certified:
            return 'UNCERTIFIED_EVIDENCE_FREEZE'
        r = self._round_limits[i.round_id]
        items = [a for a in self._assets.values() if a.stock == i.stock] + [v.intent for v in self._reserves.values() if v.intent.stock == i.stock]
        if i.kind == 'INIT':
            if i.pool != 'PROBE' or items or i.round_id in self._round_cash or any(c.round_id == i.round_id for c in self._claims.values()):
                return 'INIT_REQUIRES_EMPTY_STOCK_AND_PROBE'
            if i.charge.cash > r.initial_cash_budget:
                return 'INITIAL_FEE_INCLUSIVE_CASH_BUDGET'
        else:
            if (i.stock, i.round_id) not in self._prequeue_rounds:
                return 'ADD_REQUIRES_PREQUEUE_HELD_ROUND'
            proof = self._proofs.get((i.stock, i.round_id))
            if proof is None or proof.close_net80 <= ZERO or proof.open_net80 <= ZERO or not proof.fresh_cp_after_first_fill or not proof.m3_true:
                return 'ADD_REQUIRES_CURRENT_ROUND_AB_PROOF'
            if i.round_id in self._used_add or any(v.intent.kind == 'ADD' and v.intent.round_id == i.round_id for v in self._reserves.values()):
                return 'ADD_ALREADY_USED_OR_LIVE'
            if any(a.round_id != i.round_id or a.pool != i.pool for a in items):
                return 'ROUND_OR_POOL_MISMATCH'
            if i.charge.cash > r.add_cash_budget:
                return 'ADD_FEE_INCLUSIVE_CASH_BUDGET'
        if i.charge.cash > self.available_cash:
            return 'INSUFFICIENT_UNRESERVED_CASH'
        combined = self.usage(stock=i.stock, round_id=i.round_id) + i.charge
        if combined.slot > r.slot_cap:
            return 'ROUND_SLOT_CAP'
        if combined.fee_risk > r.fee_risk_cap:
            return 'ROUND_FEE_INCLUSIVE_RISK_CAP'
        sector = self.usage(sector=i.sector) + i.charge
        industry_cap = caps.probe_industry_all_capital_cap if i.pool == 'PROBE' else caps.confirmed_industry_all_capital_cap
        if industry_cap is None:
            return 'CONFIRMED_INDUSTRY_CAP_NOT_FROZEN'
        if sector.capital > industry_cap:
            return 'INDUSTRY_ALL_CAPITAL_CAP'
        if i.pool == 'PROBE':
            probe = self.usage(pool='PROBE') + i.charge
            if probe.capital > caps.probe_capital_cap:
                return 'GLOBAL_PROBE_CAPITAL_CAP'
            if probe.nominal_risk > caps.probe_nominal_risk_cap:
                return 'GLOBAL_PROBE_NOMINAL_RISK_CAP'
        return None
    def request_cancel(self, order_id):
        r = self._reserves[order_id]
        self._reserves[order_id] = replace(r, status='cancel_pending')
    def confirm_cancel(self, *, event_id, order_id):
        self._new_event(event_id)
        r = self._reserves[order_id]
        if r.status != 'cancel_pending':
            raise ContractError('cancel must be pending before confirmation')
        del self._reserves[order_id]
        self._events.add(event_id)
    def record_fill(self, *, event_id, order_id, lot_id, filled: Charge, source_ref):
        self._new_event(event_id)
        identifier(source_ref)
        identifier(lot_id)
        r = self._reserves[order_id]
        if lot_id in self._assets or filled.cash <= ZERO or not filled.within(r.remaining):
            raise ContractError('duplicate lot, empty fill or fill exceeds reservation')
        rest = r.remaining.subtract(filled)
        if rest.cash == ZERO and not rest.is_zero:
            raise ContractError('fully consumed cash with residual noncash obligations')
        i = r.intent
        asset = Asset(lot_id, i.stock, i.round_id, i.sector, i.pool, filled, self.session)
        self._round_cash[i.round_id] = self.round_cash(i.round_id) - filled.cash
        self._assets[lot_id] = asset
        if rest.is_zero:
            del self._reserves[order_id]
        else:
            self._reserves[order_id] = replace(r, remaining=rest)
        if i.kind == 'ADD':
            self._used_add.add(i.round_id)
        self._events.add(event_id)
