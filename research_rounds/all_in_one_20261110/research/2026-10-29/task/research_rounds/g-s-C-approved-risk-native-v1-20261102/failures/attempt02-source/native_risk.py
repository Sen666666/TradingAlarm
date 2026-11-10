"""C-only approved nominal-risk preservation. Isolated synthetic-native adapter.

One switch over the frozen mixed runner. No historical account entry point.
The original ledger alone owns cash, fees, inventory, settlements and exits.
"""
from pathlib import Path
import sys, importlib.util, hashlib, copy, pickle, json
from fractions import Fraction

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'g-s-C-native-mixed-order-v1-20261102'
BASE_SHA = '236b6caea999afec115a9d09caa21a49c297330f007c30b29353315e74e520dd'
if hashlib.sha256((BASE / 'native_c.py').read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('frozen mixed native source changed')
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location('approved_risk_frozen_mixed', BASE / 'native_c.py')
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
for name in dir(M):
    if not name.startswith('_'):
        globals()[name] = getattr(M, name)
HERE = Path(__file__).resolve().parent
F = Fraction


def approved_payload(r, cid, sid):
    """Only previously recomputed C certificates, never metadata risk_budget."""
    c = r.authority.certificates[cid]
    r.verify_native(c)
    v = r.trusted[c['trusted_id']]
    ds = [d for d in v['demands'] if d['sid'] == sid]
    require(len(ds) == 1 and c['Q'][sid] > 0, 'missing trusted concrete C quantity')
    d = ds[0]
    require(d['role'] == 'mobile' and d['pool'] == 'confirmed' and d['use'] in ('G', 'S'), 'R0 C confirmed mobile only')
    p = D(d['mark']) * (ONE + LR.SLIP)
    floor = D(d['floor'])
    require(p > floor >= 0, 'invalid approved risk floor')
    return dict(cid=cid, sid=sid, receipt=c['receipt_bindings'][sid]['event_id'],
                known_at=c['known_at'], deadline=c['deadline'], Q0=int(c['Q'][sid]),
                p0=p, f0=floor, R0=F(c['Q'][sid]) * (F(p) - F(floor)),
                trusted_id=c['trusted_id'], currency='CNY', source_binding=c['source_binding'])


class RiskBook:
    """Currency-risk and shrink-only quantity observer; not a financial ledger."""
    def __init__(self):
        self.approvals = {}
        self.orders = {}
        self.fills = {}
        self.audit = []

    def register(self, r, cid):
        for sid, q in r.authority.certificates[cid]['Q'].items():
            if not q:
                continue
            key = cid + '|' + sid
            p = approved_payload(r, cid, sid)
            if key in self.approvals:
                require(self.approvals[key]['approved'] == p, 'changed approved R0')
                continue
            self.approvals[key] = dict(approved=copy.deepcopy(p), remaining=F(q), spent=F(0),
                                       ratio=F(1), order=None, attempted=False, closed=False)

    def key(self, cid, sid):
        key = cid + '|' + sid
        require(key in self.approvals, 'missing pre-opening trusted R0')
        return key

    def bound(self, key, price, floor, cap):
        z = self.approvals[key]
        p, f = F(price), F(floor)
        if p <= f:
            return 0
        credit = z['approved']['R0'] - z['spent']
        require(credit >= 0, 'negative remaining approved risk')
        return max(0, min(int(cap), int(z['remaining'] * z['ratio']), int(credit // (p - f))))

    def shrink(self, key, raw_q, reason, at):
        z = self.approvals[key]
        anchor = F(raw_q) / z['ratio']
        require(0 <= anchor <= z['remaining'], 'approved remaining quantity cannot regrow')
        if anchor != z['remaining']:
            self.audit.append(dict(kind='permanent_quantity_shrink', key=key, at=at,
                                   before=z['remaining'], after=anchor, reason=reason))
            z['remaining'] = anchor

    def bind(self, key, oid):
        z = self.approvals[key]
        require(z['order'] is None and oid not in self.orders and not z['closed'], 'one order per certificate/receipt')
        z['order'] = oid
        self.orders[oid] = key

    def consume(self, oid, fill, price, floor, factor):
        key = self.orders[oid]
        z = self.approvals[key]
        require(fill.receipt_id not in self.fills, 'risk consumption replay')
        q = F(fill.shares) / z['ratio']
        cost = F(fill.shares) * max(F(0), F(price) - F(floor))
        require(0 < q <= z['remaining'] and z['spent'] + cost <= z['approved']['R0'], 'pre-fill approved risk invariant violated')
        z['remaining'] -= q
        z['spent'] += cost
        self.fills[fill.receipt_id] = dict(key=key, oid=oid, shares=fill.shares,
                anchor_q=q, at=fill.at, price=price, floor=floor, factor=factor,
                ratio=z['ratio'], consumed=cost)

    def check(self, r):
        a = r.account
        for key, z in self.approvals.items():
            p = z['approved']
            require(p == approved_payload(r, p['cid'], p['sid']), 'R0 observer source/certificate mismatch')
            fs = [v for v in self.fills.values() if v['key'] == key]
            require(z['spent'] == sum((v['consumed'] for v in fs), F(0)), 'filled risk not conserved')
            require(0 <= z['spent'] <= p['R0'] and z['remaining'] >= 0, 'risk/quantity bound')
            require(z['remaining'] + sum((v['anchor_q'] for v in fs), F(0)) <= p['Q0'], 'original approved quantity exceeded')
            oid = z['order']
            if oid:
                require(self.orders[oid] == key and r.authority.orders[oid]['receipt'] == p['receipt'], 'order/receipt risk mapping')
                au = r.authority.orders[oid]
                require(z['ratio'] == au['ratio'], 'split coordinate mismatch')
                o = a.buys.get(p['sid'])
                if o and o.order_id == oid:
                    if p['sid'] not in a.cancel_requests:
                        require(F(o.remaining_shares) <= z['remaining'] * z['ratio'], 'native remaining exceeds permanent cap')
                else:
                    require(z['remaining'] == 0, 'closed order retained quantity authority')
            for eid, v in self.fills.items():
                if v['key'] != key:
                    continue
                f = next(f for f in a.fills if f.receipt_id == eid)
                t = next(t for t in a.trades if t.get('receipt_id') == eid)
                require(f.side == 'buy' and f.shares == v['shares'] and f.gross_cny == D(f.shares) * v['price'], 'actual fill/risk event differs')
                require(t['floor'] / v['factor'] == v['floor'] and t['price'] == v['price'], 'risk uses different actual fill floor/price')
                require(v['consumed'] == F(f.shares) * max(F(0), F(v['price']) - F(v['floor'])), 'wrong permanent fill debit')


class Account(M.Account):
    def __init__(self, owner):
        super().__init__(owner)
        self._risk_submit = None
        self._risk_fill = None

    def _risk_key(self, i, exclude_order):
        if exclude_order and exclude_order in self.owner.risk.orders:
            return self.owner.risk.orders[exclude_order]
        if self._risk_submit:
            cid, sid = self._risk_submit
            require(sid == i['sid'], 'transient risk stock mismatch')
            return self.owner.risk.key(cid, sid)
        return None

    def _preview(self, i, use, role, at, *, exclude_order=None, cap=None):
        if not self.owner.keep_approved_risk:
            return super()._preview(i, use, role, at, exclude_order=exclude_order, cap=cap)
        key = self._risk_key(i, exclude_order)
        if key is None:
            return super()._preview(i, use, role, at, exclude_order=exclude_order, cap=cap)
        require(role == 'mobile', 'C risk cannot relabel core')
        # Original actual ledger floor. Do not ratchet a core/mobile line here.
        p = self.market.prices[i['sid']] * (ONE + LR.SLIP)
        factor = self.facts.factor(i['sid'], at)
        floor = (self.order_meta[exclude_order]['floor'] / factor if exclude_order
                 else max(i['I_floor'], D(i['cp_floor'])) / factor)
        if self._risk_fill and self._risk_fill['oid'] == exclude_order:
            p, floor = self._risk_fill['price'], self._risk_fill['floor']
        hard = self.owner.risk.bound(key, p, floor, cap if cap is not None else 10**18)
        if not hard:
            return dict(q=0, why=['approved_R0_or_permanent_quantity'], use=use, role=role)
        x = super()._preview(i, use, role, at, exclude_order=exclude_order, cap=hard)
        # A pure preview NEVER consumes/shrinks authorization (e.g. G backup).
        x['approved_risk_keep'] = dict(key=key, R0=self.owner.risk.approvals[key]['approved']['R0'],
                spent=self.owner.risk.approvals[key]['spent'], preview_price=p, floor=floor, hard_cap=hard)
        return x

    def submit_fixed(self, i, at, *, use, role, q, cid=None):
        if not self.owner.keep_approved_risk or cid is None:
            return super().submit_fixed(i, at, use=use, role=role, q=q, cid=cid)
        key = self.owner.risk.key(cid, i['sid'])
        z = self.owner.risk.approvals[key]
        require(not z['closed'] and z['order'] is None, 'risk authorization already bound/closed')
        self._risk_submit = (cid, i['sid'])
        try:
            x = super().submit_fixed(i, at, use=use, role=role, q=q, cid=cid)
        finally:
            self._risk_submit = None
        z['attempted'] = True
        self.owner.risk.shrink(key, x['q'], 'actual_native_reserve_or_rejection', at)
        if x['q']:
            self.owner.risk.bind(key, x['order_id'])
            self.supports[x['order_id']]['approved_risk_key'] = key
        return x

    def revalidate(self, sid, at):
        oid = self.buys[sid].order_id if sid in self.buys else None
        x = super().revalidate(sid, at)
        if self.owner.keep_approved_risk and oid in self.owner.risk.orders:
            key = self.owner.risk.orders[oid]
            if x['status'] == 'amended':
                self.owner.risk.shrink(key, x['q'], 'atomic_native_amend_before_fill', at)
            elif x['status'] == 'cancel_requested':
                self.owner.risk.shrink(key, 0, 'cancel_requested_no_receipt_refund', at)
        return x

    def cancel_buy(self, sid):
        o = self.buys.get(sid)
        oid = o.order_id if o else None
        result = super().cancel_buy(sid)
        # The native full-fill cleanup runs before its fill callback. Do NOT
        # erase remaining authority ahead of consumption of this actual fill.
        if (self.owner.keep_approved_risk and oid in self.owner.risk.orders
                and getattr(self, '_native_fill_order', None) != oid):
            key = self.owner.risk.orders[oid]
            self.owner.risk.shrink(key, 0, 'native_cancel_ack', self.last_cursor)
            self.owner.risk.approvals[key]['closed'] = True
        return result

    def fill_buy(self, sid, w):
        o = self.buys.get(sid)
        oid = o.order_id if o else None
        if not self.owner.keep_approved_risk or oid not in self.owner.risk.orders:
            return super().fill_buy(sid, w)
        require(w.fx.read(w.at) == ONE, 'R0 CNY only; unsupported FX')
        factor = self.facts.factor(sid, w.at)
        floor = self.order_meta[oid]['floor'] / factor
        self._risk_fill = dict(oid=oid, price=D(w.execution_price), floor=floor)
        try:
            f = super().fill_buy(sid, w)  # revalidate -> atomic amend -> ledger
        finally:
            self._risk_fill = None
        if f:
            self.owner.risk.consume(oid, f, D(w.execution_price), floor, factor)
        current = self.buys.get(sid)
        if not current or current.order_id != oid:
            key = self.owner.risk.orders[oid]
            self.owner.risk.shrink(key, 0, 'native_order_terminal', w.at)
            self.owner.risk.approvals[key]['closed'] = True
        return f

    def split(self, **kw):
        sid, eid = kw['sid'], kw['event_id']
        if not self.owner.keep_approved_risk:
            return super().split(**kw)
        if eid in self.owner.action_ids:
            return super().split(**kw)
        # Do not expand unsupported corporate action scope. An unsubmitted
        # concrete C approval has no native quantity-amend mechanism yet.
        for z in self.owner.risk.approvals.values():
            p = z['approved']
            if p['sid'] == sid and z['order'] is None and z['remaining'] and kw['at'] <= iso(p['deadline']):
                raise ValueError('UNSUPPORTED split of unsubmitted C approval; atomic stop')
        super().split(**kw)
        for z in self.owner.risk.approvals.values():
            if z['approved']['sid'] == sid and z['order']:
                z['ratio'] *= F(kw['ratio'])
        # Currency R0 and already consumed risk never scale/refund.


class Runner(M.Runner):
    def __init__(self, mode='C10', *, keep_approved_risk=True):
        require(type(keep_approved_risk) is bool, 'explicit risk switch bool required')
        self.keep_approved_risk = keep_approved_risk
        self.risk = RiskBook()
        super().__init__(mode)
        self.account = Account(self)

    def source_binding(self):
        out = super().source_binding()
        out[str(HERE / 'native_risk.py')] = hashlib.sha256((HERE / 'native_risk.py').read_bytes()).hexdigest()
        out['C_APPROVED_RISK_SWITCH_V1'] = digest(dict(enabled=self.keep_approved_risk, scope='C-only'))
        return out

    def plan(self, intents, clock):
        result = super().plan(intents, clock)
        if self.keep_approved_risk and result.get('certificate'):
            self.risk.register(self, result['certificate'])
            self.assert_observers()
        return result

    def assert_observers(self):
        super().assert_observers()
        if self.keep_approved_risk:
            self.risk.check(self)

    def binding(self):
        return dict(super().binding(), approved_risk_switch=self.keep_approved_risk,
                    research_scope='synthetic-native integration only; no historical account execution')

    def observable(self, at):
        return dict(super().observable(at), approved_risk_switch=self.keep_approved_risk,
                    approved_risk=self.risk.__dict__)

    @classmethod
    def restore(cls, path):
        path = Path(path)
        side = json.loads(path.with_suffix('.provenance.json').read_text())
        probe = cls(side['binding']['mode'], keep_approved_risk=side['binding']['approved_risk_switch'])
        IO.assert_checkpoint_identity(probe, path)
        require(probe.binding() == side['binding'], 'source/policy binding changed')
        with path.open('rb') as f:
            r = pickle.load(f)
        require(r.binding() == side['binding'], 'restored policy binding changed')
        r.account.owner = r
        r.assert_observers()
        for c in r.authority.certificates.values():
            r.verify_native(c)
        return r
