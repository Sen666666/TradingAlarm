"""Pure admission projection; no Account, execution, market loader or PnL.

Native sources are read and compiled in memory. Only the three related
confirmed60 predicates differ when enabled. Caller supplies the complete
original pre-admission state and original precomputed LR previews.
"""
from pathlib import Path
from types import SimpleNamespace as NS, ModuleType
from decimal import Decimal as D
import copy, dataclasses, difflib, hashlib, inspect, json, sys

O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(W/'probe-batch-local-preview-20261101'))
import planner as B
J=B.J; N=B.N; LR=J.LR
MODEL=(W/'account-risk-ablation-20261031/model_without_account_check.py').read_text()
ROUTE=(W/'account-risk-ablation-20261031/route_without_account_check.py').read_text()
assert inspect.getsource(N.Contract.migrate)==inspect.getsource(J.V.Contract.migrate)
MG="        if self.resources('confirmed')[0] + moved > .60*(self.nav-pending_fees) + 1e-9:\n            s.status = 'confirmed_unfunded'\n            return False\n"
PG="        if pc+cap > (0.10 if pool == 'probe' else 0.60)*budget_nav + 1e-9: failures.append('pool_capital')"
PN="        if pool == 'probe' and pc+cap > 0.10*budget_nav + 1e-9: failures.append('pool_capital')"
RG="    if pc+cap>(.10 if pool=='probe' else .60)*nav+1e-9:fails.append('pool_capital')"
RN="    if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')"
assert MODEL.count(MG)==MODEL.count(PG)==ROUTE.count(RG)==1
NEW_MODEL=MODEL.replace(MG,'').replace(PG,PN)
NEW_ROUTE=ROUTE.replace(RG,RN)
assert NEW_MODEL.replace(PN,PG).replace('        before = (self.cash, self.nav, self.resources(), self.shared_loss)',MG+'        before = (self.cash, self.nav, self.resources(), self.shared_loss)')==MODEL
assert NEW_ROUTE.replace(RN,RG)==ROUTE
MOD=ModuleType('pvr_private_no_confirmed60_model');sys.modules[MOD.__name__]=MOD
exec(compile(NEW_MODEL,str(O/'derived_model_no_confirmed60.py'),'exec'),MOD.__dict__)
ROUTES={}
for flag,source in [(False,ROUTE),(True,NEW_ROUTE)]:
    env=dict(J.__dict__);exec(compile(source,str(O/('derived_route_on.py' if flag else 'derived_route_off.py')),'exec'),env);ROUTES[flag]=env['route']

def serial(x):return B.serial(x)
def digest(x):return B.digest(x)
def source_diff():
    return ''.join(difflib.unified_diff(MODEL.splitlines(True),NEW_MODEL.splitlines(True),fromfile='original_no_account_model',tofile='private_no_confirmed60_model'))+'\n'+''.join(difflib.unified_diff(ROUTE.splitlines(True),NEW_ROUTE.splitlines(True),fromfile='original_no_account_route',tofile='private_no_confirmed60_route'))

class State(B.State):
    def __init__(self,*args,remove_confirmed60=False,core_epoch=None,**kwargs):
        super().__init__(*args,**kwargs);self.remove_confirmed60=remove_confirmed60;self.core_epoch=copy.deepcopy(core_epoch or {})
    def migrate(self,sector):
        before={x.batch:x.pool for x in self.lots};old=self.sectors[sector].status
        result=(MOD.Contract.migrate if self.remove_confirmed60 else N.Contract.migrate)(self,sector)
        self.migrations.append(dict(candidate=self.context,phase=self.phase,sector=sector,result=result,old_status=old,new_status=self.sectors[sector].status,moved=sorted(x.batch for x in self.lots if before[x.batch]!=x.pool)))
        return result
    def request(self,*args,**kwargs):
        old=self.phase;self.phase='request'
        try:return (MOD.Contract.request if self.remove_confirmed60 else N.Contract.request)(self,*args,**kwargs)
        finally:self.phase=old
    def view(self):return dict(super().view(),core_epoch=self.core_epoch)

class AccountView(B.AccountView):
    def __init__(self,state):super().__init__(state);self.core_epoch=state.core_epoch

def snapshot(a):
    b=a.budget
    return State(cash=b.cash,receivables=b.receivable_equity,lots=b.lots,orders=b.orders,sectors=b.sectors,prices=b.prices,
        consumed=b.consumed,stock_requests=b.stock_requests,sector_by_sid=a.sector_by_sid,decision_nav=a.current_nav,
        pending_sells=a.exits,available_exact=a.available,historical_shared_loss=b.shared_loss,core_epoch=a.core_epoch)

def plan(s0,intents,at,remove_confirmed60=False):
    """Original single pass/max quantity. Private reserve feedback; no fills."""
    before=digest([s0.view(),[B.intent_view(i) for i in intents]])
    b=copy.deepcopy(s0);b.remove_confirmed60=remove_confirmed60;b.migrations=[]
    a=AccountView(b);runner=NS(sector_by_sid=b.sector_by_sid);orders=[];attempts=[];done=set();validations=[]
    for src in sorted(intents,key=B.key):
        i=copy.deepcopy(src);sid=i['sid'];x=i.get('_preview');key=B.bid(i)
        if sid in done or sid in s0.pending_sells or any(o.stock==sid and o.qty>0 and o.status in ['open','cancel_pending'] for o in s0.orders.values()):
            attempts.append(dict(sid=sid,role=i['role'],skip=True));continue
        if x is None:
            attempts.append(dict(sid=sid,role=i['role'],result=i['_preview_failure']));continue
        b.context=key;b.phase='evaluation';pre=copy.deepcopy(b);pre_available=a.available
        result,why=ROUTES[remove_confirmed60](runner,a,i,x,at)
        if result:
            q,pool=result
            # Native route/request already checked all rules; independently
            # inspect the retained numerical predicates at the admission clock.
            pending_fees=sum(o.qty*o.fee_per_share for o in pre.orders.values() if o.status in ['open','cancel_pending'])
            fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value)
            nav=pre.nav-pending_fees-float(fee);cap=q*float(x['price']);risk=q*max(0.,float(x['price']-x['floor']))
            # route migration changes only pool, so sector/global checks use pre.
            sc,sr,_=pre.resources(sector=pre.sector_by_sid[sid]);s=pre.sectors[pre.sector_by_sid[sid]]
            pc,pr,_=b.resources(pool);new=b.orders[i['budget_order']]
            assert x['rule'].buy_floor(q)==q and 0<q<=x['maxq'] and D(q)*x['price']<=i['budget']
            assert cap+float(fee)<=min(float(pre_available-a.current_nav*D('.1')),pre.cash-pre.resources()[2])+1e-7
            assert sc+cap<=(.02 if pool=='probe' else (.02,.1,.2)[s.level])*nav+1e-7
            assert sr+risk<=.01*nav+1e-7
            assert a.quantity(sid)*float(x['known_open'])+cap<=.10*float(a.current_nav)+1e-7
            if pool=='probe':assert pc<=.10*nav+1e-7 and pr<=.005*nav+1e-7
            elif not remove_confirmed60:assert pc<=.60*nav+1e-7
            assert new.role==i['role'] and new.floor==float(x['floor'])
            paid=a.reserve_private(i,q,pool,x);assert paid==fee
            orders.append(B.order_record(i,q,pool,x,fee));done.add(sid)
            attempts.append(dict(sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
            validations.append(dict(key=key,quantity=q,pool=pool,capital=cap,risk=risk,fee=fee,budget_NAV=nav,all_retained_admission_guards_passed=True))
        else:attempts.append(dict(sid=sid,role=i['role'],result=why))
    assert before==digest([s0.view(),[B.intent_view(i) for i in intents]])
    for oid,o in s0.orders.items():assert b.orders[oid]==o
    return dict(orders=orders,attempts=attempts,migrations=b.migrations,validations=validations,final_state=serial(b.view()),
        capital=b.resources()[0],nominal_risk=b.resources()[1],cash_reserve=b.resources()[2],available=a.available,
        fees=sum((x['fee'] for x in orders),D(0)),input_sha256=before,inputs_unchanged=True,
        native_Account_initializations=0,real_fills=0,new_financial_paths=0,not_PnL=True)

def source_hashes():
    ps=[Path(__file__),W/'probe-batch-local-preview-20261101/planner.py',W/'account-risk-ablation-20261031/model_without_account_check.py',W/'account-risk-ablation-20261031/route_without_account_check.py',Path(J.__file__),J.BASE/'budget_v3/model.py',Path(LR.__file__)]
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ps}
