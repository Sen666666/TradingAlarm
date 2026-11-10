"""Synthetic state contract only: no feeds, brokers, history, or execution forecast."""
from dataclasses import dataclass
from math import isclose, isfinite

@dataclass(frozen=True)
class Evidence:
    event_id: str  # Canonical UNDERLYING evidence ID, not a per-symbol alias.
    sector: str
    source: str
    scale: str
    start: int
    end: int
    confirmed_time: int
    epoch: str
    stock: str = None
    attempt: str = None

@dataclass
class Sector:
    episode: str
    started: int
    level: int = 0
    last_bar: int = -1
    last_end: int = -1
    last_evidence_time: int = -1
    status: str = 'probe'
    active: bool = False
    attempt: str = None
    failed_bar: int = -1
    episode_started: int = 0

@dataclass
class Grant:
    gid: str
    sector: str
    episode: str
    decision_batch: str
    decision_bar: int
    capital_limit: float
    risk_limit: float
    attempt: str = None
    active: bool = True
    filled_capital: float = 0.
    filled_risk: float = 0.
    expired_capital: float = 0.
    expired_risk: float = 0.

@dataclass
class Lot:
    batch: str
    stock: str
    sector: str
    episode: str
    pool: str
    qty: float
    cost: float
    floor: float
    role: str = 'core'
    grant_id: str = None
    attempt: str = None

@dataclass
class Order:
    oid: str
    stock: str
    sector: str
    episode: str
    pool: str
    qty: float  # Unfilled quantity, including cancel-pending quantity.
    limit: float
    floor: float
    fee_per_share: float = 0
    status: str = 'open'
    role: str = 'core'
    grant_id: str = None
    decision_batch: str = None
    created_bar: int = 0
    expiry_bar: int = 0
    attempt: str = None

class Contract:
    def __init__(self, nav=1000., cash=1000., prices=None, lots=None,
                 shared_loss_budget=20., exhausted_policy='record_only'):
        assert exhausted_policy in ('record_only', 'probe_only', 'all_new_risk')
        self.cash = cash
        self.prices = dict(prices or {})
        self.lots = list(lots or [])
        self.orders = {}
        self.grants = {}
        self.sectors = {}
        self.consumed = set()
        self.stock_requests = set()
        self.losses = {}  # (sector, original episode) -> gross negative realized PnL + fees
        self.loss_budget = shared_loss_budget
        self.exhausted_policy = exhausted_policy
        self.audit = []
        assert isclose(nav, self.nav), 'NAV must reconcile to supplied cash + marked lots'

    @property
    def nav(self):
        return self.cash + sum(x.qty*self.prices[x.stock] for x in self.lots)

    @property
    def shared_loss(self):
        return sum(self.losses.values())

    def loss(self, sector, episode, amount):
        key = (sector, episode)
        self.losses[key] = self.losses.get(key, 0.) + amount
        if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget:
            for order in self.orders.values():
                if order.pool == 'probe' or self.exhausted_policy == 'all_new_risk':
                    self.cancel(order.oid)  # Never release reservation without ack.

    def start(self, sector, episode, bar):
        old = self.sectors.get(sector)
        if old and old.episode == episode:
            return
        if old:
            self.invalidate(sector, old.episode, bar=bar)
        # Old positions/orders continue to consume resources and preserve original episode.
        self.sectors[sector] = Sector(episode, bar, status='awaiting_first_cp1',
                                      failed_bar=old.failed_bar if old else -1, episode_started=bar)
        self.audit.append(('episode', sector, episode))

    def resources(self, pool=None, sector=None):
        lots = [x for x in self.lots if (pool is None or x.pool == pool)
                and (sector is None or x.sector == sector)]
        orders = [x for x in self.orders.values() if x.qty > 0 and
                  x.status in ('open', 'cancel_pending') and
                  (pool is None or x.pool == pool) and
                  (sector is None or x.sector == sector)]
        capital = sum(x.qty*self.prices[x.stock] for x in lots) + sum(x.qty*x.limit for x in orders)
        risk = sum(x.qty*max(0., self.prices[x.stock]-x.floor) for x in lots)
        risk += sum(x.qty*max(0., x.limit-x.floor) for x in orders)
        reserve = sum(x.qty*(x.limit+x.fee_per_share) for x in orders)
        return capital, risk, reserve

    def valid(self, token, source, bar):
        s = self.sectors.get(token.sector)
        return bool(s and (source == 'industry_cp1' or s.active) and token.source == source and token.scale == '21' and
                    token.epoch == s.episode and
                    token.end >= s.episode_started and token.confirmed_time >= s.episode_started and
                    (source == 'industry_cp1' or (token.attempt == s.attempt and token.end >= s.started)) and
                    token.start <= token.end <= token.confirmed_time <= bar)

    def industry(self, token, bar, *, grant_id=None, grant_capital=None, grant_risk=None,
                 decision_batch=None, decision_bar=None):
        if not self.valid(token, 'industry_cp1', bar) or token.event_id in self.consumed:
            return 'rejected'
        if grant_id is not None:
            assert grant_id == token.event_id and grant_id not in self.grants
            assert grant_capital is not None and grant_capital > 0 and grant_risk is not None and grant_risk >= 0
            assert isfinite(grant_capital) and isfinite(grant_risk)
            assert decision_batch and decision_bar is not None
        s = self.sectors[token.sector]
        if token.confirmed_time <= s.failed_bar or token.end <= s.failed_bar:
            return 'not_new_progress'
        if bar <= s.last_bar or token.end <= s.last_end or token.confirmed_time <= s.last_evidence_time:
            return 'not_new_progress'
        if token.confirmed_time != bar:
            self.audit.append(('late_industry_evidence_audit_only', token.event_id, bar))
            return 'late_evidence_audit_only'
        if grant_id is not None and not (decision_bar == bar == token.confirmed_time):
            return 'stale_grant_evidence'
        self.consumed.add(token.event_id)
        s.last_bar, s.last_end = bar, token.end
        s.last_evidence_time = token.confirmed_time
        if not s.active:
            s.active, s.level, s.started = True, 0, token.confirmed_time
            s.attempt = f'{s.episode}:{token.event_id}'
            s.status = 'probe'
        else:
            s.level = min(2, s.level + 1)
        for g in self.grants.values():
            if g.sector == token.sector: self.close_grant(g.gid)
        for order in self.orders.values():
            if s.level > 0 and order.sector == token.sector and order.attempt == s.attempt and order.pool == 'probe' and order.qty > 0:
                self.cancel(order.oid)
        self.migrate(token.sector)
        if grant_id is not None and s.level > 0:
            # Snapshot residual capacity ONCE, counting every old attempt and pending order.
            pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
                               if o.status in ('open', 'cancel_pending'))
            budget_nav = self.nav-pending_fees
            sc, sr, _ = self.resources(sector=token.sector)
            cc, _, _ = self.resources('confirmed')
            _, ar, reserve = self.resources()
            cap = max(0., min(grant_capital, (0.02,.10,.20)[s.level]*budget_nav-sc,
                              .60*budget_nav-cc, self.cash-reserve))
            risk = max(0., min(grant_risk, .01*budget_nav-sr, .03*budget_nav-ar))
            self.grants[grant_id] = Grant(grant_id, token.sector, s.episode, decision_batch,
                                           decision_bar, cap, risk, attempt=s.attempt)
        self.audit.append(('industry_confirmation', token.event_id, s.level))
        return s.status

    def observe(self, sector, bar, *, failure=False, token=None, **grant_terms):
        if failure:
            self.invalidate(sector, self.sectors[sector].episode, bar=bar)
            return 'invalidated'  # Same-observation CP1 never restarts.
        if token is None: return self.sectors[sector].status
        assert token.sector == sector
        return self.industry(token, bar, **grant_terms)

    def grant_usage(self, gid):
        g = self.grants[gid]
        pending = [o for o in self.orders.values() if o.grant_id == gid and
                   o.status in ('open', 'cancel_pending')]
        pc = sum(o.qty*o.limit for o in pending)
        pr = sum(o.qty*max(0., o.limit-o.floor) for o in pending)
        return {'filled_capital': g.filled_capital, 'filled_risk': g.filled_risk,
                'pending_capital': pc, 'pending_risk': pr,
                'expired_capital': g.expired_capital, 'expired_risk': g.expired_risk,
                'remaining_capital': g.capital_limit-g.filled_capital-pc-g.expired_capital,
                'remaining_risk': g.risk_limit-g.filled_risk-pr-g.expired_risk}

    def close_grant(self, gid):
        g = self.grants[gid]
        if not g.active: return
        u = self.grant_usage(gid)
        g.expired_capital += u['remaining_capital']
        g.expired_risk += u['remaining_risk']
        g.active = False

    def end_batch(self, decision_batch):
        # v2: decision-day end is audit only; remaining grant lasts for the attempt.
        self.audit.append(('decision_batch_ended', decision_batch))

    def expire_orders(self, bar):
        for o in self.orders.values():
            if bar > o.expiry_bar: self.cancel(o.oid)

    def invalidate(self, sector, episode, *, bar):
        s = self.sectors[sector]
        assert s.episode == episode
        s.active, s.status = False, 'invalidated'
        s.failed_bar = max(s.failed_bar, bar)
        for g in self.grants.values():
            if g.sector == sector and g.episode == episode: self.close_grant(g.gid)
        for o in self.orders.values():
            if o.sector == sector and o.episode == episode: self.cancel(o.oid)

    def cancel(self, oid):
        o = self.orders[oid]
        if o.qty > 0 and o.status == 'open':
            o.status = 'cancel_pending'

    def cancel_ack(self, oid):
        o = self.orders[oid]
        if o.status in ('filled', 'cancelled') and o.qty == 0:
            self.migrate(o.sector)  # Full fill can win the cancel race; never erase the lot.
            return
        assert o.status == 'cancel_pending'
        if o.grant_id:
            g = self.grants[o.grant_id]
            g.expired_capital += o.qty*o.limit
            g.expired_risk += o.qty*max(0., o.limit-o.floor)
        o.qty, o.status = 0., 'cancelled'
        self.migrate(o.sector)

    def migrate(self, sector):
        s = self.sectors[sector]
        if s.level == 0 or not s.active:
            return False
        if any(o.sector == sector and o.attempt == s.attempt and o.pool == 'probe' and o.qty > 0
               and o.status in ('open', 'cancel_pending') for o in self.orders.values()):
            s.status = 'confirmed_unfunded'
            return False
        moved = sum(x.qty*self.prices[x.stock] for x in self.lots if x.sector == sector and x.attempt == s.attempt and x.pool == 'probe')
        pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
                           if o.status in ('open', 'cancel_pending'))
        if self.resources('confirmed')[0] + moved > .60*(self.nav-pending_fees) + 1e-9:
            s.status = 'confirmed_unfunded'
            return False
        before = (self.cash, self.nav, self.resources(), self.shared_loss)
        for x in self.lots:
            if x.sector == sector and x.attempt == s.attempt and x.pool == 'probe':
                x.pool = 'confirmed'
        s.status = 'confirmed' if s.level == 1 else 'expanded'
        assert before == (self.cash, self.nav, self.resources(), self.shared_loss)
        return True

    def request(self, oid, stock, sector, qty, limit, floor, stock_token=None,
                bar=0, fee_per_share=0., *, probe_request=False, role='core',
                grant_id=None, decision_batch=None, order_expiry_bar=None,
                core_epoch_locked=False):
        assert qty > 0 and limit > 0 and 0 <= floor <= limit and fee_per_share >= 0
        assert role in ('core', 'mobile')
        if order_expiry_bar is None: order_expiry_bar = bar
        assert order_expiry_bar >= bar
        if oid in self.orders or oid in self.stock_requests:
            return 'duplicate_request'
        self.stock_requests.add(oid)  # Failed request is not silently replayed every day.
        s = self.sectors[sector]
        if not s.active: return 'industry_invalidated'
        if probe_request and role == 'core' and core_epoch_locked: return 'core_epoch_locked'
        pool = 'probe' if probe_request else 'confirmed'
        if probe_request and grant_id is not None: return 'invalid_probe_request'
        if not probe_request and s.level == 0: return 'explicit_probe_request_required'
        if not probe_request and role != 'mobile': return 'mobile_role_required'
        if role == 'mobile':
            if stock_token is None:
                return 'no_fresh_stock_signal'
            if not self.valid(stock_token, 'stock_cp1', bar) or stock_token.confirmed_time != bar or stock_token.sector != sector or stock_token.stock != stock or stock_token.event_id in self.consumed:
                return 'no_fresh_stock_signal'
            self.consumed.add(stock_token.event_id)
        if pool == 'confirmed':
            if not self.migrate(sector):
                return 'confirmed_unfunded'
            g = self.grants.get(grant_id)
            if not g or not g.active or g.sector != sector or g.episode != s.episode or g.attempt != s.attempt or g.decision_bar > bar or stock_token.confirmed_time < g.decision_bar:
                return 'no_current_grant'
            u = self.grant_usage(grant_id)
            if qty*limit > u['remaining_capital'] + 1e-9 or qty*(limit-floor) > u['remaining_risk'] + 1e-9:
                return 'grant_exhausted'
        if self.exhausted_policy != 'record_only' and self.shared_loss >= self.loss_budget and (pool == 'probe' or self.exhausted_policy == 'all_new_risk'):
            if pool == 'confirmed': s.status = 'confirmed_unfunded'
            return 'shared_loss_exhausted'
        cap, risk = qty*limit, qty*(limit-floor)
        pc, pr, _ = self.resources(pool)
        sc, sr, _ = self.resources(sector=sector)
        _, ar, reserve = self.resources()
        pending_fees = sum(o.qty*o.fee_per_share for o in self.orders.values()
                           if o.status in ('open', 'cancel_pending'))
        # Known execution fees cannot make an at-cap reservation violate its own cap on fill.
        budget_nav = self.nav - pending_fees - qty*fee_per_share
        failures = []
        if reserve + qty*(limit+fee_per_share) > self.cash + 1e-9: failures.append('cash')
        if pc+cap > (0.10 if pool == 'probe' else 0.60)*budget_nav + 1e-9: failures.append('pool_capital')
        if pool == 'probe' and pr+risk > .005*budget_nav + 1e-9: failures.append('probe_risk')
        sector_fraction = .02 if probe_request else (0.02, 0.10, 0.20)[s.level]
        if sc+cap > sector_fraction*budget_nav + 1e-9: failures.append('sector_capital')
        if sr+risk > .01*budget_nav + 1e-9: failures.append('sector_risk')
        if ar+risk > .03*budget_nav + 1e-9: failures.append('account_risk')
        if failures:
            if pool == 'confirmed': s.status = 'confirmed_unfunded'
            return ','.join(failures)
        self.prices.setdefault(stock, limit)
        self.orders[oid] = Order(oid, stock, sector, s.episode, pool, qty, limit, floor, fee_per_share)
        self.orders[oid].role, self.orders[oid].grant_id = role, grant_id
        self.orders[oid].decision_batch = decision_batch
        self.orders[oid].created_bar, self.orders[oid].expiry_bar = bar, order_expiry_bar
        self.orders[oid].attempt = s.attempt
        return 'reserved'

    def fill(self, oid, qty, price, *, execution_bar=None):
        o = self.orders[oid]
        if execution_bar is None: execution_bar = o.created_bar  # Same-day synthetic fixture.
        assert o.created_bar <= execution_bar <= o.expiry_bar
        assert o.status in ('open', 'cancel_pending') and 0 < qty <= o.qty and 0 < price <= o.limit
        assert self.cash + 1e-9 >= qty*(price+o.fee_per_share)
        self.cash -= qty*(price+o.fee_per_share)
        self.loss(o.sector, o.episode, qty*o.fee_per_share)
        self.lots.append(Lot(o.oid, o.stock, o.sector, o.episode, o.pool, qty, price, o.floor, o.role, o.grant_id, o.attempt))
        if o.grant_id:
            g = self.grants[o.grant_id]
            g.filled_capital += qty*price
            g.filled_risk += qty*max(0., price-o.floor)
            g.expired_capital += qty*(o.limit-price)
            g.expired_risk += qty*(max(0., o.limit-o.floor)-max(0., price-o.floor))
        o.qty -= qty
        if o.qty == 0: o.status = 'filled'
        self.audit.append(('fill', oid, qty, o.pool))

    def sell(self, batch, qty, price, fee=0.):
        assert qty > 0 and price > 0 and fee >= 0
        assert self.cash + qty*price >= fee
        available = sum(x.qty for x in self.lots if x.batch == batch)
        assert qty <= available
        remaining = qty
        for x in self.lots:
            if x.batch != batch or remaining <= 0: continue
            sold = min(x.qty, remaining)
            self.cash += sold*price
            self.loss(x.sector, x.episode, max(0., x.cost-price)*sold + fee*sold/qty)
            x.qty -= sold
            remaining -= sold
        self.cash -= fee
        self.lots = [x for x in self.lots if x.qty > 0]
        self.audit.append(('sell', batch, qty, price, fee))
