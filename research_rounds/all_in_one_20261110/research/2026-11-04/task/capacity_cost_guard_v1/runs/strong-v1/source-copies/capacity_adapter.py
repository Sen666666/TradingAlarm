"""One cost-cap factor added to the frozen No60 native strategy."""
from pathlib import Path
from decimal import Decimal as D
import copy, gzip, hashlib, json, sys

O = Path(__file__).resolve().parent
sys.path.insert(0, str(O.parent/'pvr_pool_feasibility'))
import native_adapter as A
import guard as G
N,J,L,IO,P = A.N,A.J,A.L,A.IO,A.P
ARMS = {'B': (None, True), 'G10': ('.10', True), 'G20': ('.20', True), 'G40': ('.40', True), 'NR20': ('.20', False)}
POLICY = 'NO60_UNPROTECTED_FEE_INCLUSIVE_COST_V1'


class GuardAccount(J.Account):
    def capacity_context(self, at):
        return G.context(self, at, J.LR.SLIP)

    def capacity_allowed(self, c, q, x, intent):
        fee = J.LR.fees(q, x['price'], x['schedule'], 'buy', intent['quote'].par_value)
        return G.reserve_allowed(self, c, q, x['price'], x['known_open'], fee)

    def reserve_quantity(self, intent, q, price, schedule, at):
        c = self.capacity_context(at)
        mark = self.market.marks(at, [intent['sid']])[intent['sid']].cny_price(at)
        fee = J.LR.fees(q, price, schedule, 'buy', intent['quote'].par_value)
        assert G.reserve_allowed(self, c, q, price, mark, fee), 'non-atomic cost reservation'
        oid = super().reserve_quantity(intent, q, price, schedule, at)
        post = self.capacity_context(at)
        assert post['used_cost'] + post['pending_cost'] <= self.capacity_alpha * post['guard_NAV']
        G.snapshot(self, post, 'actual_reserve', sid=intent['sid'], order_id=oid, budget_order=intent['budget_order'], quantity=q, fee=fee)
        return oid

    def fill_buy(self, sid, window):
        order = self.buys.get(sid)
        if order is None:
            return
        c = self.capacity_context(window.at)
        # Read the original cumulative native fee calculator, not a new fee
        # model. Full remaining quantity is a conservative pre-fill bound.
        q = min(order.remaining_shares, int(order.remaining_budget_cny/window.execution_price))
        fx = window.fx.read(window.at)
        assert fx == D(1), 'this frozen experiment is A-share/CNY only'
        fees = self._fee(order, window.fees, 'buy', D(q)*window.execution_price,
                         shares=q, par_value=window.par_value)
        fullfee = sum(fees.values(), D(0)) * fx
        mark = self.market.marks(window.at, [sid])[sid].cny_price(window.at)
        # A partial fill must not lose the still-unfilled reservation buffer.
        # Preserve the old full-gross slippage cushion even when today's fill
        # price is below the reservation limit.
        slippage_bound = max(order.remaining_budget_cny*J.LR.SLIP/(D(1)+J.LR.SLIP),
                             D(q)*max(D(0), window.execution_price*fx-mark))
        actualdrag = max(order.fee_reserved_cny,fullfee)+slippage_bound
        projected_NAV = c['NAV'] - (c['pending_drag']-c['orders'][sid]['drag']) - actualdrag
        projected_cost = c['used_cost']+c['pending_cost']+max(D(0),fullfee-order.fee_reserved_cny)
        if not projected_NAV.is_finite() or projected_NAV <= 0 or projected_cost > self.capacity_alpha*projected_NAV:
            G.snapshot(self, c, 'fill_cost_cap_cancel', sid=sid, projected_NAV=projected_NAV, projected_cost=projected_cost)
            self.cancel_buy(sid)
            return
        self.capacity_in_callback = True
        try:
            r = super().fill_buy(sid, window)
            if r:
                G.after_buy(self, r, self.layers[-1])
        finally:
            self.capacity_in_callback = False
        if r:
            post = self.capacity_context(window.at)
            assert post['used_cost']+post['pending_cost'] <= self.capacity_alpha*post['guard_NAV'], 'cost cap violated by actual native fill'
            G.snapshot(self, post, 'actual_buy_fill', sid=sid, layer=self.layers[-1]['id'], quantity=r.shares, actual_cost=r.gross_cny+r.fees_cny)
        return r

    def fill_exit(self, sid, window):
        before = {x['id']: x['qty'] for x in self.live(sid)}
        self.capacity_in_callback = True
        try:
            r = super().fill_exit(sid, window)
            if r:
                G.after_sell(self, before, self.trades[-1]['parts'], window.at)
        finally:
            self.capacity_in_callback = False
        return r

    def split(self, **kw):
        before = {x['id']: x['qty'] for x in self.live(kw['sid'])}
        self.capacity_in_callback = True
        try:
            super().split(**kw)
            G.after_split(self, before, kw['ratio'], kw['at'])
        finally:
            self.capacity_in_callback = False


OLD_ROUTE = P.NEW_ROUTE
NEW_ROUTE = OLD_ROUTE.replace('results=[];reasons={}', 'results=[];reasons={};cost_context=a.capacity_context(at);cost_diagnostic=[]')
NEW_ROUTE = NEW_ROUTE.replace('def allowed(q,detail=False):', 'def allowed(q,detail=False,guard=True):')
needle = '    return fails if detail else not fails'
assert NEW_ROUTE.count(needle) == 1
NEW_ROUTE = NEW_ROUTE.replace(needle, "    if guard and not a.capacity_allowed(cost_context,q,x,i):fails.append('unprotected_cost_cap')\n"+needle)
needle = 'q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)'
assert NEW_ROUTE.count(needle) == 1
NEW_ROUTE = NEW_ROUTE.replace(needle, needle+";cost_diagnostic.append(dict(pool=pool,quantity=q,pre_guard_legal_quantity=LR.maximum_quantity(rule,maxq,lambda v:allowed(v,guard=False)),minimum_reasons=reasons[pool]))")
needle = "q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))"
NEW_ROUTE = NEW_ROUTE.replace(needle, needle+"\n  G.snapshot(a,cost_context,'route',sid=sid,role=role,decision_at=i['clock'].decision_at,budget_order_hint=rid,selected_quantity=q,selected_pool=pool,routes=cost_diagnostic)")
env = dict(J.__dict__, G=G)
exec(compile(NEW_ROUTE, str(O/'derived_route.py'), 'exec'), env)
guard_route = env['route']


class Runner(A.Runner):
    def __init__(self, *args, arms=None, compact_opportunities=True, **kwargs):
        self._guard_ready = False
        super().__init__(*args, **kwargs)
        base = self.accounts['B']
        requested = arms or list(ARMS)
        self.accounts = {}
        for name in requested:
            alpha, release = ARMS[name]
            a = copy.copy(base)
            a.__dict__ = copy.deepcopy({k:v for k,v in base.__dict__.items() if k not in ('market','facts')})
            a.market, a.facts, a.label = base.market, base.facts, name
            if alpha is not None:
                a.__class__ = GuardAccount
                G.init(a, alpha, release)
            self.accounts[name] = a
        self.compact_opportunities = compact_opportunities
        self.opportunity_denominators = []
        self.capacity_daily = []
        self._guard_ready = True
        self.integration_policy = POLICY+':'+self.rank_mode
        self.assert_native_wiring()

    def assert_native_wiring(self):
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is Runner.planning
        assert self.route.__func__ is Runner.route
        for name,a in self.accounts.items():
            expected = GuardAccount if getattr(self,'_guard_ready',False) and ARMS[name][0] is not None else J.Account
            assert type(a) is expected
            assert a.budget.request.__func__ is P.MOD.Contract.request or getattr(self,'_cap_bootstrap',False)
            for meth in ('sync','assert_budget_view','expire_day_buys','cancel_buy'):
                assert getattr(a,meth).__func__ is getattr(J.Account,meth)

    def route(self, a, intent, x, at):
        if type(a) is J.Account:
            return P.ROUTES[True](self,a,intent,x,at)
        return guard_route(self,a,intent,x,at)

    def planning(self, at):
        first = len(self.opportunities)
        N.Runner.planning(self, at)
        if self.compact_opportunities:
            rows = self.opportunities[first:]
            self.opportunity_denominators.append(dict(at=at, full_rows=len(rows), retained_role_candidates=sum(bool(x['roles']) for x in rows), accounts=len(self.accounts)))
            self.opportunities[first:] = [x for x in rows if x['roles']]
        for name,a in self.accounts.items():
            if type(a) is GuardAccount:
                self.capacity_daily.append(dict(account=name, **{k:v for k,v in G.context(a,at,J.LR.SLIP).items() if k not in ('orders','layers')}))

    def dump_joint(self, path):
        J.Runner.dump_joint(self, path)
        for name,a in self.accounts.items():
            if type(a) is GuardAccount:
                IO.write_gzip_jsonl(Path(path)/(name+'-cost-guard.jsonl.gz'), a.capacity_events, encoder=J.C.encoded)
        IO.write_gzip_jsonl(Path(path)/'cost-capacity-daily.jsonl.gz', self.capacity_daily, encoder=J.C.encoded)
        IO.write_gzip_jsonl(Path(path)/'opportunity-denominators.jsonl.gz', self.opportunity_denominators, encoder=J.C.encoded)
