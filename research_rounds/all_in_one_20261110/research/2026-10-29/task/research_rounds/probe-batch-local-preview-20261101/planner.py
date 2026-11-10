"""Isolated allocation-only planner. No native Account, submission, fill or PnL.

Uses the frozen Bdiag route predicates and native budget methods on PRIVATE
resource projections. Input resources/intents are immutable to this interface.
"""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as NS
import sys,copy,json,hashlib,dataclasses
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'case-stage-ledger-20261031/v3'))
import joint_v3 as J
N=J.W.load('probe_preview_native_no_account_model',W/'account-risk-ablation-20261031/model_without_account_check.py')
LR=J.LR;Z=D(0)
ROUTE_PATH=W/'account-risk-ablation-20261031/route_without_account_check.py'
ROUTE_SOURCE=ROUTE_PATH.read_text();ENV=dict(J.__dict__)
exec(compile(ROUTE_SOURCE,str(ROUTE_PATH),'exec'),ENV)
NATIVE_ROUTE=ENV['route']
# Exact native full-target comparison, with only the admission tail removed.
TAIL=ROUTE_SOURCE.index('  bid=')
EVAL_SOURCE=ROUTE_SOURCE[:TAIL]+"  return dict(quantity=q,pool=pool,token=token,reasons=reasons,results=results),None\n"
assert EVAL_SOURCE.split('  return dict(quantity=')[0]==ROUTE_SOURCE[:TAIL]
ENV2=dict(J.__dict__);exec(compile(EVAL_SOURCE,str(O/'derived_full_target_evaluation.py'),'exec'),ENV2)
EVAL_ROUTE=ENV2['route']
# Exact native pool/stock/cash predicates, without migration or argmax over pools.
BEGIN=ROUTE_SOURCE.index('   pc,pr,_=')
END=ROUTE_SOURCE.index('   q=LR.maximum_quantity')
PRED_SOURCE='def fixed_predicate(a,i,x,at,pool):\n b=a.budget;sid=i["sid"];sector=a.sector_by_sid[sid];s=b.sectors[sector];p=float(x["price"]);floor=float(x["floor"])\n'+''.join(line[2:]+'\n' for line in ROUTE_SOURCE[BEGIN:END].splitlines())+' return allowed\n'
ENV3=dict(J.__dict__);exec(compile(PRED_SOURCE,str(O/'derived_fixed_pool_predicate.py'),'exec'),ENV3)
fixed_predicate=ENV3['fixed_predicate']

def serial(x):
    if isinstance(x,State):return x.view()
    if dataclasses.is_dataclass(x):return serial(dataclasses.asdict(x))
    if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [serial(y) for y in x]
    if isinstance(x,set):return sorted(serial(y) for y in x)
    if isinstance(x,NS):return serial(vars(x))
    if isinstance(x,D):return str(x)
    if hasattr(x,'isoformat'):return x.isoformat()
    return x
def digest(x):return hashlib.sha256(json.dumps(serial(x),sort_keys=True,ensure_ascii=False,default=str,allow_nan=False).encode()).hexdigest()
def intent_view(i):
    x=i.get('_preview');r={k:v for k,v in i.items() if k not in ['_preview','quote','CP1_trace']}
    r['quote']=dict(par_value=i['quote'].par_value)
    r['CP1_trace']=i.get('CP1_trace')
    r['preview']=None if x is None else {k:x[k] for k in ['price','floor','rule','schedule','maxq','minq','known_open']}
    r['preview_failure']=i.get('_preview_failure')
    return r

class State:
    """Only fields read by original allocation predicates, not an account clone."""
    resources=N.Contract.resources
    valid=N.Contract.valid
    def __init__(self,*,cash,receivables=0,lots=None,orders=None,sectors=None,prices=None,consumed=(),stock_requests=(),sector_by_sid=None,decision_nav=1000000,pending_sells=(),available_exact=None,historical_shared_loss=0):
        self.cash=float(cash);self.receivable_equity=float(receivables);self.lots=copy.deepcopy(lots or []);self.orders=copy.deepcopy(orders or {});self.sectors=copy.deepcopy(sectors or {});self.prices=dict(prices or {})
        self.consumed=set(consumed);self.stock_requests=set(stock_requests);self.expand=True;self.exhausted_policy='record_only';self.losses={('read_only','recorded_history'):float(historical_shared_loss)};self.loss_budget=20000;self.audit=[]
        self.available_exact=D(str(available_exact)) if available_exact is not None else D(str(self.cash-self.resources()[2]))
        self.sector_by_sid=dict(sector_by_sid or {});self.decision_nav=D(str(decision_nav));self.pending_sells=set(pending_sells);self.migrations=[];self.context=None;self.phase=None
    @property
    def nav(self):return self.cash+sum(x.qty*self.prices[x.stock] for x in self.lots)+self.receivable_equity
    @property
    def shared_loss(self):return sum(self.losses.values())
    def migrate(self,sector):
        before={x.batch:x.pool for x in self.lots};old=self.sectors[sector].status
        answer=N.Contract.migrate(self,sector)
        self.migrations.append(dict(candidate=self.context,phase=self.phase,sector=sector,result=answer,old_status=old,new_status=self.sectors[sector].status,moved=sorted(k for k,p in before.items() if p!=next(x.pool for x in self.lots if x.batch==k))))
        return answer
    def request(self,*args,**kwargs):
        old=self.phase;self.phase='request'
        try:return N.Contract.request(self,*args,**kwargs)
        finally:self.phase=old
    def view(self):
        return dict(cash=self.cash,available_exact=self.available_exact,receivables=self.receivable_equity,nav=self.nav,lots=self.lots,orders=self.orders,sectors=self.sectors,prices=self.prices,consumed=self.consumed,stock_requests=self.stock_requests,sector_by_sid=self.sector_by_sid,decision_nav=self.decision_nav,pending_sells=self.pending_sells,migrations=self.migrations,historical_shared_loss=self.shared_loss)

class AccountView:
    """No execution API and no native Account initialization."""
    def __init__(self,state):
        self.budget=state;self.current_nav=state.decision_nav;self.available=state.available_exact;self.core_epoch={};self.sector_by_sid=state.sector_by_sid;self.label='B';self._budget_sync_pending=False
    def quantity(self,sid):return sum(x.qty for x in self.budget.lots if x.stock==sid)
    def pools_from_model(self):pass
    def reserve_private(self,i,q,pool,x):
        fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value)
        self.available-=D(q)*x['price']+fee
        assert self.available>=0
        return fee

def key(i):return i['rank'],i['role']!='core'
def bid(i):return 'B|'+i['clock'].decision_at.isoformat()+'|'+i['sid']+'|'+i['role']
def token_for(state,i):
    if i['role']=='core':return None
    s=state.sectors[state.sector_by_sid[i['sid']]];bar=J.ordinal(i['clock'].decision_at.date());cp=i['CP1_trace']
    return J.V.Evidence(i['CP1_id'],state.sector_by_sid[i['sid']],'stock_cp1','21',J.ordinal(cp['formation_start_exclusive']),bar,bar,s.episode,i['sid'],s.attempt)
def order_record(i,q,pool,x,fee):
    return dict(key=bid(i),sid=i['sid'],role=i['role'],pool=pool,quantity=q,rank=i['rank'],price=x['price'],floor=x['floor'],gross=D(q)*x['price'],fee=fee,CP1_id=i.get('CP1_id'))
def reserve_fixed(a,i,x,q,pool,at):
    if x['rule'].buy_floor(q)!=q or not 0<q<=x['maxq'] or D(q)*x['price']>i['budget']:
        return None,'original_minimum_step_or_frozen_target'
    if i['role']=='core' and LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value)>i['risk_budget']:
        return None,'original_core_risk'
    predicate=fixed_predicate(a,i,x,at,pool)
    if predicate(q,True):return None,','.join(predicate(q,True))
    b=a.budget;fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);bar=J.ordinal(i['clock'].decision_at.date());sector=b.sector_by_sid[i['sid']]
    b.phase='request';result=b.request(bid(i),i['sid'],sector,q,float(x['price']),float(x['floor']),token_for(b,i),bar,float(fee/D(q)),probe_request=pool=='probe',role=i['role'],order_expiry_bar=J.ordinal(at.date()),core_epoch_locked=False)
    if result!='reserved':return None,result
    a.reserve_private(i,q,pool,x);return order_record(i,q,pool,x,fee),None
def migration_signature(xs):return [(x['candidate'],x['phase'],x['sector'],x['result'],x['new_status'],tuple(x['moved'])) for x in xs]

def fixed_validation(s0,intents,attempts,plan,at,expected_migrations):
    """Validate fixed quantities/pools, never call full route or choose an argmax."""
    b=copy.deepcopy(s0);b.migrations=[];a=AccountView(b);by={bid(i):i for i in intents};pmap={x['key']:x for x in plan};failures=[]
    for attempt in attempts:
        i=copy.deepcopy(by[attempt['key']]);x=i['_preview'];b.context=bid(i)
        if attempt['eval_migrate']:
            b.phase='evaluation';b.migrate(b.sector_by_sid[i['sid']])
        if bid(i) in pmap:
            o=pmap[bid(i)];r,why=reserve_fixed(a,i,x,o['quantity'],o['pool'],at)
            if why:failures.append(dict(key=bid(i),reason=why));break
    if not failures and migration_signature(b.migrations)!=migration_signature(expected_migrations):failures.append(dict(reason='migration_sequence_differs_from_first_pass'))
    return dict(valid=not failures,failures=failures,state=b,available=a.available)

def plan(s0,intents,at,mode='two_pass'):
    assert mode in ['single_pass','two_pass']
    before=digest([s0.view(),[intent_view(i) for i in intents]])
    b=copy.deepcopy(s0);b.migrations=[];a=AccountView(b);runner=NS(sector_by_sid=b.sector_by_sid);orders=[];attempts=[];rejected=[];done=set();input_by={bid(i):i for i in intents}
    for source in sorted(intents,key=key):
        i=copy.deepcopy(source);sid=i['sid'];x=i.get('_preview')
        if sid in done:
            rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason='same_stock_earlier_role_reserved'));continue
        if sid in s0.pending_sells or any(o.stock==sid and o.qty>0 and o.status in ['open','cancel_pending'] for o in s0.orders.values()):
            rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason='original_pending_buy_or_exit'));continue
        if x is None:
            rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason=i['_preview_failure']));continue
        b.context=bid(i);b.phase='evaluation';n=len(b.migrations)
        if mode=='single_pass':
            result,why=NATIVE_ROUTE(runner,a,i,x,at)
            if result:
                q,pool=result;fee=a.reserve_private(i,q,pool,x);orders.append(order_record(i,q,pool,x,fee));done.add(sid)
        else:
            result,why=EVAL_ROUTE(runner,a,i,x,at)
            if result:
                q=x['minq'] if result['pool']=='probe' else result['quantity'];pool=result['pool']
                r,why=reserve_fixed(a,i,x,q,pool,at)
                if why:raise AssertionError(('private minimum reservation failed',bid(i),why))
                orders.append(r);done.add(sid)
        new=b.migrations[n:]
        attempts.append(dict(key=bid(i),eval_migrate=any(z['phase']=='evaluation' for z in new)))
        if why:rejected.append(dict(key=bid(i),sid=sid,role=i['role'],reason=why))
    first_pass=copy.deepcopy(orders);expected=copy.deepcopy(b.migrations)
    if mode=='two_pass':
        initial=fixed_validation(s0,intents,attempts,orders,at,expected)
        if not initial['valid']:raise AssertionError(('initial fixed plan invalid',initial['failures']))
        for old in list(orders):
            if old['pool']!='probe':continue
            i=input_by[old['key']];x=i['_preview'];lo=(old['quantity']-x['minq'])//x['rule'].buy_step;hi=(x['maxq']-x['minq'])//x['rule'].buy_step
            def trial(k):
                q=x['minq']+k*x['rule'].buy_step;fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);candidate=order_record(i,q,'probe',x,fee);os=[candidate if z['key']==old['key'] else z for z in orders]
                return os,fixed_validation(s0,intents,attempts,os,at,expected)
            while lo<hi:
                mid=(lo+hi+1)//2;_,v=trial(mid)
                if v['valid']:lo=mid
                else:hi=mid-1
            orders,v=trial(lo);assert v['valid']
        final=fixed_validation(s0,intents,attempts,orders,at,expected);assert final['valid'];b=final['state'];a=AccountView(b);a.available=final['available']
    after=digest([s0.view(),[intent_view(i) for i in intents]]);assert before==after
    return dict(mode=mode,orders=orders,first_pass=first_pass,rejected=rejected,attempts=attempts,migrations=b.migrations,final_state=serial(b.view()),input_before_sha256=before,input_after_sha256=after,available=a.available,capital=b.resources()[0],nominal_risk=b.resources()[1],cash_reserve=b.resources()[2],fees=sum((z['fee'] for z in orders),Z),proposed_stock_receipt_consumptions=sorted(b.consumed-s0.consumed),original_inputs_unchanged=True,native_Account_constructed=False,real_submissions=0,real_fills=0)
