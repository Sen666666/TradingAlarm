"""One new admission predicate, stock-wide remaining average cost, no live orders.

Main convention: buy fees enter remaining cost; sale proceeds, locked profit and
cash dividends never reduce it. Partial sale retires cost pro rata across the
whole stock, irrespective of layer/pool. A zero position permits a fresh trial.
"""
from decimal import Decimal as D
from pathlib import Path
import sys
O=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(O/'inputs'));import continuous_inputs as C
A,N,J=C.A,C.N,C.J
Z=D(0)
SUFFIX=':REMAINING_AVERAGE_COST_NET_LIQUIDATION_ADD_GATE_V1'

class RemainingCostBook:
    def __init__(self):self.states={};self.journal_cursor=0;self.processed=0
    def apply(self,row):
        kind=row['kind']
        if kind not in ('real_buy_fill','real_sell_fill','actual_split'):return
        sid=row['sid'];s=self.states.setdefault(sid,{'qty':0,'cost':Z,'round':0})
        if kind=='real_buy_fill':
            if s['qty']==0:
                assert s['cost']==0
                s['round']+=1
            s['qty']+=int(row['shares'])
            s['cost']+=D(row['shares'])*D(str(row['price']))+D(str(row['fees']))
        elif kind=='real_sell_fill':
            q=int(row['shares']);assert 0<q<=s['qty'],(sid,row,s)
            s['cost']=s['cost']*D(s['qty']-q)/D(s['qty'])
            s['qty']-=q
            if not s['qty']:s['cost']=Z
        else:
            # Same native aggregate fractional-share writeoff as original ledger.
            s['qty']=int(D(s['qty'])*D(str(row['ratio'])))
            if not s['qty']:s['cost']=Z
        assert s['qty']>=0 and s['cost']>=0
        self.processed+=1
    def sync(self,account):
        for row in account.journal[self.journal_cursor:]:self.apply(row)
        self.journal_cursor=len(account.journal)
        for sid in set(self.states)|set(account.positions):
            assert self.states.get(sid,{'qty':0})['qty']==account.quantity(sid),('average cost quantity bridge',account.label,sid,self.states.get(sid),account.quantity(sid))
        return self

def judge(q,cost,known_open,sell_fee,slip=D('.0005')):
    q=int(q);cost=D(str(cost))
    if q==0:return dict(allowed=True,reason='flat_original_trial_rules',qty=0,cost=Z,net_liquidation=Z,net_profit=Z)
    op=D(str(known_open));fee=D(str(sell_fee));assert op>0 and fee>=0 and cost>=0
    value=D(q)*op*(1-slip)-fee
    return dict(allowed=value>cost,reason='profitable_remaining_holding' if value>cost else 'nonprofitable_remaining_holding',qty=q,cost=cost,average_cost=cost/D(q),known_open=op,estimated_sell_price=op*(1-slip),estimated_sell_fee=fee,net_liquidation=value,net_profit=value-cost)

# Only two exact additions to the already-frozen No60 route: evaluate the new
# predicate once, then include it in the original allowed(q) conjunction. This
# preserves industry/receipt checks and migration even for rejected candidates.
SOURCE=A.P.NEW_ROUTE
ANCHOR="  routes=['probe']"
CHECK="    if sr+risk>.01*nav+1e-9:fails.append('sector_risk')"
assert SOURCE.count(ANCHOR)==SOURCE.count(CHECK)==1
DERIVED=SOURCE.replace(ANCHOR,"  profit_ok=self.profit_permission(a,i,x,at)\n"+ANCHOR).replace(CHECK,CHECK+"\n    if not profit_ok:fails.append('nonprofitable_remaining_holding')")
assert DERIVED.replace("  profit_ok=self.profit_permission(a,i,x,at)\n",'').replace("\n    if not profit_ok:fails.append('nonprofitable_remaining_holding')",'')==SOURCE
_env=dict(J.__dict__)
exec(compile(DERIVED,str(Path(__file__).with_name('derived_profit_route.py')),'exec'),_env)
PROFIT_ROUTE=_env['route']

class ProfitRunner(A.Runner):
    route=PROFIT_ROUTE
    def profit_permission(self,a,i,x,at):
        assert self.market.phase=='OPEN' and self.market.phase_at==at
        assert i['clock'].decision_at<at and i['clock'].earliest_execution_at==at
        book=self.cost_books[a.label].sync(a);s=book.states.get(i['sid'],{'qty':0,'cost':Z,'round':0})
        q=s['qty'];op=x['known_open'];sell_price=op*(1-J.LR.SLIP)
        fee=J.LR.fees(q,sell_price,x['schedule'],'sell',i['quote'].par_value) if q else Z
        verdict=judge(q,s['cost'],op,fee)
        self.profit_gate_events.append(dict(account=a.label,sid=i['sid'],role=i['role'],at=at,signal_at=i['clock'].decision_at,buy_proxy=x['price'],round=s['round'],dividend_cost_convention='EXCLUDED',**verdict))
        return verdict['allowed']
    def assert_native_wiring(self):
        assert self.integration_policy==A.POLICY+':'+self.rank_mode+SUFFIX
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is N.Runner.planning
        assert self.route.__func__ is PROFIT_ROUTE
        for a in self.accounts.values():
            assert type(a)is J.Account and type(a.budget)is A.NoConfirmed60Budget
            assert a.budget.request.__func__ is A.P.MOD.Contract.request
            assert a.budget.migrate.__func__ is A.NoConfirmed60Budget.migrate
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)

def install(r):
    # Initialize the unmodified original Runner first; never weaken bootstrap.
    r.assert_native_wiring();r.__class__=ProfitRunner
    r.integration_policy+=SUFFIX
    r.cost_books={k:RemainingCostBook()for k in r.accounts}
    r.profit_gate_events=[]
    r.assert_native_wiring()
