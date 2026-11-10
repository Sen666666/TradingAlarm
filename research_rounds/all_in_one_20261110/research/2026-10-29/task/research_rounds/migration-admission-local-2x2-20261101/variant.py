"""New policy variant: best-effort migration is separate from new admission.
Only isolated synthetic budgets and audited allocation projections are used.
Never initializes a native Account or offers a real submission/fill API.
"""
from pathlib import Path
import sys,inspect,copy,json,difflib,hashlib
from decimal import Decimal as D
from types import SimpleNamespace as NS
O=Path(__file__).resolve().parent;W=O.parent;OLD=W/'probe-batch-local-preview-20261101'
sys.path.insert(0,str(OLD))
import planner as B

def ensure(p,s):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert p.read_text()==s,('generated source drift',str(p))
    else:p.write_text(s)
def load(n,p):return B.J.W.load(n,p)

MODEL_OLD=(W/'account-risk-ablation-20261031/model_without_account_check.py').read_text()
MG="        if pool == 'confirmed':\n            if not self.migrate(sector):\n                return 'confirmed_unfunded'\n"
MN="        if pool == 'confirmed':\n            self.migrate(sector)  # Best effort; failure is not new-order ineligibility.\n"
assert MODEL_OLD.count(MG)==1
MODEL_NEW=MODEL_OLD.replace(MG,MN);assert MODEL_NEW.replace(MN,MG)==MODEL_OLD
ensure(O/'sources/model_decoupled.py',MODEL_NEW)
DECOUPLED=load('new_policy_migration_admission_decoupled',O/'sources/model_decoupled.py')
RG="   if b.migrate(sector):a.pools_from_model();routes.append('confirmed')"
RN="   if b.migrate(sector):a.pools_from_model()\n   routes.append('confirmed')"
assert B.ROUTE_SOURCE.count(RG)==1
ROUTE_NEW=B.ROUTE_SOURCE.replace(RG,RN);assert ROUTE_NEW.replace(RN,RG)==B.ROUTE_SOURCE
ensure(O/'sources/route_decoupled.py',ROUTE_NEW)
env=dict(B.J.__dict__);exec(compile(ROUTE_NEW,str(O/'sources/route_decoupled.py'),'exec'),env);ROUTE=env['route']
ev=ROUTE_NEW[:ROUTE_NEW.index('  bid=')]+"  return dict(quantity=q,pool=pool,token=token,reasons=reasons,results=results),None\n"
ensure(O/'sources/full_target_evaluation_decoupled.py',ev)
env2=dict(B.J.__dict__);exec(compile(ev,str(O/'sources/full_target_evaluation_decoupled.py'),'exec'),env2);EVAL=env2['route']
ensure(O/'POLICY_SOURCE.diff',''.join(difflib.unified_diff(MODEL_OLD.splitlines(True),MODEL_NEW.splitlines(True),fromfile='frozen-model-coupled.py',tofile='new-policy-model-decoupled.py'))+'\n'+''.join(difflib.unified_diff(B.ROUTE_SOURCE.splitlines(True),ROUTE_NEW.splitlines(True),fromfile='frozen-route-coupled.py',tofile='new-policy-route-decoupled.py')))

class TraceState(B.State):
    """Same resource view; diagnostic-only context is excluded from input view."""
    def __init__(self,*args,decoupled=False,**kwargs):
        super().__init__(*args,**kwargs);self.decoupled=decoupled;self.intent_diagnostics={};self.request_diagnostics=None
    def request(self,*args,**kwargs):
        oldphase=self.phase;oldrequest=self.request_diagnostics;self.phase='request'
        self.request_diagnostics=dict(quantity=args[3],price=args[4],floor=args[5],fee_per_share=args[8] if len(args)>8 else kwargs.get('fee_per_share',0))
        try:return (DECOUPLED.Contract.request if self.decoupled else B.N.Contract.request)(self,*args,**kwargs)
        finally:self.phase=oldphase;self.request_diagnostics=oldrequest
    def migrate(self,sector):
        s=self.sectors[sector];pending=[o for o in self.orders.values() if o.sector==sector and o.attempt==s.attempt and o.pool=='probe' and o.qty>0 and o.status in ['open','cancel_pending']]
        oldlots=[x for x in self.lots if x.sector==sector and x.attempt==s.attempt and x.pool=='probe'];needed=sum(x.qty*self.prices[x.stock] for x in oldlots)
        cc=self.resources('confirmed')[0];fees=sum(o.qty*o.fee_per_share for o in self.orders.values() if o.status in ['open','cancel_pending']);capacity=.60*(self.nav-fees)-cc
        reason='stage_not_authorized' if s.level==0 or not s.active else 'same_attempt_probe_pending' if pending else 'confirmed_capacity_for_whole_old_transfer' if needed>capacity+1e-9 else 'legal_transfer'
        rq=self.request_diagnostics;newgross=rq['quantity']*rq['price'] if rq else None;newfee=rq['quantity']*rq['fee_per_share'] if rq else None
        info=dict(primary_reason=reason,current_nav=self.nav,current_confirmed_capital=cc,current_pending_fees=fees,remaining_confirmed_capacity=capacity,old_filled_probe_transfer_required=needed,old_transfer_deficit=max(0.,needed-capacity),
            pending_probe=[dict(oid=o.oid,stock=o.stock,role=o.role,qty=o.qty,status=o.status,gross=o.qty*o.limit,risk=o.qty*max(0.,o.limit-o.floor)) for o in pending],
            old_probe_layers=[dict(batch=x.batch,stock=x.stock,role=x.role,capital=x.qty*self.prices[x.stock],risk=x.qty*max(0.,self.prices[x.stock]-x.floor)) for x in oldlots],
            request_new_gross=newgross,request_new_fee=newfee,
            request_gross_fits_pool_after_fee=(newgross<=capacity-.60*newfee+1e-9) if rq else None,
            candidate_frozen_target=self.intent_diagnostics.get(self.context),
            capacity_is_recomputed_now=True,local_pool_capacity_is_not_full_admission=True)
        result=super().migrate(sector);self.migrations[-1]['diagnostic']=info
        assert result==(reason=='legal_transfer')
        return result

PLAN_SOURCE=inspect.getsource(B.plan)
needle='first_pass=copy.deepcopy(orders);expected=copy.deepcopy(b.migrations)'
replacement=needle+';first_pass_migrations=copy.deepcopy(b.migrations)'
assert PLAN_SOURCE.count(needle)==1 and PLAN_SOURCE.count('first_pass=first_pass,rejected=')==1
LOGGED_SOURCE=PLAN_SOURCE.replace(needle,replacement).replace('first_pass=first_pass,rejected=','first_pass=first_pass,first_pass_migrations=first_pass_migrations,rejected=')
assert LOGGED_SOURCE.replace(replacement,needle).replace('first_pass=first_pass,first_pass_migrations=first_pass_migrations,rejected=','first_pass=first_pass,rejected=')==PLAN_SOURCE
ensure(O/'sources/planner_body_logging_only.py',LOGGED_SOURCE)
def make_plan(decoupled):
    e=dict(B.__dict__);e.update(NATIVE_ROUTE=ROUTE if decoupled else B.NATIVE_ROUTE,EVAL_ROUTE=EVAL if decoupled else B.EVAL_ROUTE)
    exec(compile(LOGGED_SOURCE,str(O/'sources/planner_body_logging_only.py'),'exec'),e);return e['plan']
PLANS={False:make_plan(False),True:make_plan(True)}
def plan(state,intents,at,mode='single_pass'):
    # Copy the private projection before attaching purely diagnostic target data.
    s=copy.deepcopy(state)
    s.intent_diagnostics={B.bid(i):None if i['_preview'] is None else dict(maximum_quantity=i['_preview']['maxq'],minimum_quantity=i['_preview']['minq'],maximum_gross=float(i['_preview']['maxq']*i['_preview']['price']),minimum_gross=float(i['_preview']['minq']*i['_preview']['price'])) for i in intents}
    return PLANS[s.decoupled](s,intents,at,mode)
def old_observable(result):
    r=copy.deepcopy(result);r.pop('first_pass_migrations',None)
    for events in [r['migrations'],r['final_state']['migrations']]:
        for e in events:e.pop('diagnostic',None)
    return r
def decode(view,decoupled=False):
    v=view['state'];s=TraceState(cash=v['cash'],available_exact=v['available_exact'],receivables=v['receivables'],lots=[B.N.Lot(**x) for x in v['lots']],orders={k:B.N.Order(**x) for k,x in v['orders'].items()},sectors={k:NS(**x) for k,x in v['sectors'].items()},prices=v['prices'],consumed=v['consumed'],stock_requests=v['stock_requests'],sector_by_sid=v['sector_by_sid'],decision_nav=v['decision_nav'],pending_sells=v['pending_sells'],historical_shared_loss=v['historical_shared_loss'],decoupled=decoupled)
    out=[]
    for src in view['intents']:
        i=copy.deepcopy(src);x=i.pop('preview');i['_preview_failure']=i.pop('preview_failure');i['quote']=NS(par_value=i['quote']['par_value']);i['clock']=NS(**{k:B.J.M.N.iso(t) for k,t in i['clock'].items()})
        for k in ['floor','budget','risk_budget']:
            if k in i:i[k]=D(i[k])
        if x:
            for k in ['price','floor','known_open']:x[k]=D(x[k])
            x['rule']=B.J.LR.L.QuantityRule(**x['rule']);sd=x['schedule'];x['schedule']=B.J.LR.L.FeeSchedule(sd['schedule_id'],tuple(B.J.LR.L.FeeComponent(**r) for r in sd['components']))
        i['_preview']=x;out.append(i)
    return s,out

def source_hashes():
    ps=[Path(__file__),OLD/'planner.py',B.ROUTE_PATH,W/'account-risk-ablation-20261031/model_without_account_check.py',O/'sources/model_decoupled.py',O/'sources/route_decoupled.py',O/'sources/full_target_evaluation_decoupled.py',O/'sources/planner_body_logging_only.py']
    return {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in ps}
