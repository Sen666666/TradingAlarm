"""Two complete saved OPEN OFF/ON private allocations, no Account or fills."""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import copy,difflib,hashlib,inspect,json,sys,textwrap,time,traceback
O=Path(__file__).resolve().parent;ROOT=O.parent.parent
sys.path.insert(0,str(ROOT/'core_confirmed_v1/funding'))
import confirmed_adapter as C
P=C.A.P;B=P.B;J=P.J;LR=J.LR
DATES=('2026-02-11','2026-06-30');EXPECTED_ADAPTER='66ac96d10722ae49c0910c08a11e22cdd567159cf1e2b63c6b6142fbf5f025bd'
START=None;LIMIT=60.;CURRENT={};RUNTIME_SHA={}
def read(p):return json.loads(Path(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(P.serial(v),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check():
 if START is not None and time.monotonic()-START>=LIMIT:raise TimeoutError('Two complete OFF+ON pureOPEN60seconds')
def exact(a,b,what):
 if P.digest(a)!=P.digest(b):
  save('FIRST_DIFFERENCE.json',dict(what=what,actual=a,expected=b));raise AssertionError(what)
def hydrate(v):
 return P.State(cash=v['cash'],receivables=v['receivables'],lots=[P.MOD.Lot(**x)for x in v['lots']],orders={k:P.MOD.Order(**x)for k,x in v['orders'].items()},sectors={k:P.MOD.Sector(**x)for k,x in v['sectors'].items()},prices=v['prices'],consumed=v['consumed'],stock_requests=v['stock_requests'],sector_by_sid=v['sector_by_sid'],decision_nav=D(v['decision_nav']),pending_sells=v['pending_sells'],available_exact=D(v['available_exact']),historical_shared_loss=v['historical_shared_loss'],core_epoch={k:tuple(x)for k,x in v['core_epoch'].items()},remove_confirmed60=True)
def load_intents(path):
 xs=[]
 for v in read(path):
  i={k:copy.deepcopy(z)for k,z in v.items()if k not in ['preview','preview_failure']}
  for k in ['budget','floor','risk_budget']:
   if k in i:i[k]=D(i[k])
  i['epoch']=tuple(i['epoch'])if i['epoch']is not None else None
  z=v['clock'];i['clock']=LR.A.Clock(J.M.N.iso(z['decision_at']),J.M.N.iso(z['earliest_execution_at']),J.pd.Timestamp(z['session_date']).date());i['quote']=NS(par_value=D(v['quote']['par_value']))
  x=copy.deepcopy(v['preview'])
  if x:
   for k in ['price','floor','known_open']:x[k]=D(x[k])
   x['rule']=LR.L.QuantityRule(**x['rule']);s=x['schedule'];x['schedule']=LR.L.FeeSchedule(s['schedule_id'],tuple(LR.L.FeeComponent(**p)for p in s['components']))
  i['_preview']=x;i['_preview_failure']=v['preview_failure'];xs.append(i)
 return xs

class TypedState(P.State):
 def request(self,*args,**kwargs):
  previous=self.phase;self.phase='request'
  try:return C.TYPED_REQUEST(self,*args,**kwargs)
  finally:self.phase=previous

class PrivateView(P.AccountView):
 def __init__(self,state):
  super().__init__(state)
  self.buys={o.stock:o for o in state.orders.values()if o.qty>0 and o.status in ('open','cancel_pending')}
  self.exits=set(state.pending_sells)

def factory(state):
 # __init__ is deliberately never invoked; only pure route methods are used.
 r=C.Runner.__new__(C.Runner);r.core_confirmed_mode='ON';r.sector_by_sid=state.sector_by_sid;r.core_confirmed_log=[];r.core_proof_log=[]
 CURRENT['runner']=r;return r

def route_checked(r,a,i,x,at):
 check();b=a.budget;sid=i['sid'];sector=b.sector_by_sid[sid];before_epoch=copy.deepcopy(a.core_epoch);before_consumed=set(b.consumed);floor=i['floor']
 before=dict(available=a.available,resources=b.resources(),sector_resources=b.resources(sector=sector),pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values()if o.status in ('open','cancel_pending')),budget_NAV=b.nav,stock_quantity=a.quantity(sid))
 result,why=C.Runner.route(r,a,i,x,at)
 assert before_epoch==a.core_epoch,'No actual fill means no CORE epoch may be consumed'
 if result:
  q,pool=result;fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);order=b.orders[i['budget_order']]
  assert x['rule'].buy_floor(q)==q and 0<q<=x['maxq']<=i['cap'] and D(q)*x['price']<=i['budget']
  assert i['floor']==floor and order.floor==float(x['floor'])and order.role==i['role']
  if i['role']=='core':
   assert a.core_epoch.get(sid)!=i['epoch']
   risk=LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value);assert risk<=i['risk_budget']
   if pool=='confirmed':
    proof=i['_confirmed_core_cp'];rid=proof['canonical_receipt']['receipt_id']
    assert i['CP1_id']==rid and rid not in before_consumed and b.consumed-before_consumed=={rid}
    assert order.role=='core' and i['kind']=='core' and proof['industry_level']>=1
   else:assert b.consumed==before_consumed
  CURRENT['checks'].append(dict(key=B.bid(i),sid=sid,role=i['role'],pool=pool,quantity=q,price=x['price'],I_or_Mobile_floor_raw=x['floor'],buy_fee=fee,original_frozen_cap=i['cap'],original_frozen_budget=i['budget'],original_CORE_risk_budget=i.get('risk_budget'),CORE_fee_protection_risk=LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value)if i['role']=='core'else None,before=before,after_resources=b.resources(),after_sector_resources=b.resources(sector=sector),epoch_unchanged_without_fill=True,token_delta=sorted(b.consumed-before_consumed)))
 return result,why

def compile_plan():
 original=textwrap.dedent(inspect.getsource(P.plan));derived=original
 old='a=AccountView(b);runner=NS(sector_by_sid=b.sector_by_sid);'
 assert derived.count(old)==1;derived=derived.replace(old,'a=AccountView(b);runner=RUNNER_FACTORY(b);')
 old='result,why=ROUTES[remove_confirmed60](runner,a,i,x,at)'
 assert derived.count(old)==1;derived=derived.replace(old,'result,why=CHECKED_ROUTE(runner,a,i,x,at)')
 needle='    for src in sorted(intents,key=B.key):\n';assert derived.count(needle)==1;derived=derived.replace(needle,needle+'        CHECK_BUDGET()\n')
 env=dict(P.__dict__,AccountView=PrivateView,RUNNER_FACTORY=factory,CHECKED_ROUTE=route_checked,CHECK_BUDGET=check)
 (O/'derived_private_plan.py').write_text(derived)
 (O/'PRIVATE_PLAN.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),derived.splitlines(True),fromfile='original_No60_private_singlepass',tofile='same_singlepass_typed_route_private_view')))
 exec(compile(derived,str(O/'derived_private_plan.py'),'exec'),env);return env['plan']

def main():
 global START
 prep=time.monotonic();assert sha(C.__file__)==EXPECTED_ADAPTER
 freeze_path=ROOT/'core_confirmed_v1/funding/SOURCE_FREEZE.json';freeze=read(freeze_path)
 assert freeze['sources'][str(Path(C.__file__).resolve())]==EXPECTED_ADAPTER
 for p,h in freeze['sources'].items():assert sha(p)==h,('adapter freeze mismatch',p)
 for manifest in ['INPUT_FREEZE.json','PROOF_FREEZE.json']:
  for p,h in read(O/manifest).items():assert sha(p)==h,('prepared input mismatch',p)
 prepared=read(O/'PROOF_PREPARATION.json');assert prepared['passed']and prepared['total_preparation_seconds']<20
 batches={}
 for day in DATES:
  raw=read(O/('S0_'+day+'.json'))['state'];s0=hydrate(raw);exact(s0.view(),raw,'exact S0 rehydrate '+day)
  xs=load_intents(O/('PREVIEWS_'+day+'.json'));expected=read(O/('EXPECTED_OFF_'+day+'.json'));proofs=read(O/('FROZEN_CORE_PROOFS_'+day+'.json'))
  exact(P.digest([s0.view(),[B.intent_view(i)for i in xs]]),expected['input_sha256'],'whole immutable input digest '+day)
  for sid,p in proofs.items():assert p['proof_sha256']==C.digest({k:v for k,v in p.items()if k!='proof_sha256'})and p['receipt_sha256']==(C.digest(p['canonical_receipt'])if p['canonical_receipt']else None)
  batches[day]=(s0,xs,J.M.N.iso(day+'T09:30:00+08:00'),expected,proofs)
 on_plan=compile_plan()
 RUNTIME_SHA.update(freeze['sources']);RUNTIME_SHA[str(freeze_path)]=sha(freeze_path)
 for p in O.iterdir():
  if p.is_file()and(p.suffix=='.py'or p.name in ['INPUT_FREEZE.json','PROOF_FREEZE.json','PRIVATE_PLAN.diff']):RUNTIME_SHA[str(p.resolve())]=sha(p)
 save('RUNTIME_SOURCE_SHA256.json',RUNTIME_SHA)
 save('RUNTIME_PREPARATION.json',dict(passed=True,rehydration_seconds=time.monotonic()-prep,prior_input_and_fact_preparation=prepared,total_preparation_seconds=prepared['total_preparation_seconds']+time.monotonic()-prep,preparation_limit_seconds=20,adapter_sha256=EXPECTED_ADAPTER,source_freeze_sha256=sha(freeze_path),Account_constructed=False,Runner_initialized=False,route_executed=False))
 assert prepared['total_preparation_seconds']+time.monotonic()-prep<20
 START=time.monotonic();completed=[];off={};on={};comparisons=[]
 for day,(s0,xs,at,expected,proofs)in batches.items():
  CURRENT.update(day=day,phase='OFF');check();begin=time.monotonic();result=P.plan(s0,xs,at,True);check()
  exact({k:v for k,v in result.items()if k!='final_state'},expected,'complete OFF orders/attempts/fees/resources '+day)
  save('OFF_'+day+'.json',result);off[day]=result
  completed.append(dict(day=day,phase='OFF',passed=True,intents=len(xs),orders=len(result['orders']),all_expected_fields_exact=True,seconds=time.monotonic()-begin,cumulative_compute_seconds=time.monotonic()-START));save('RUN_PROGRESS.json',completed)
 for day,(s0,xs,at,expected,proofs)in batches.items():
  CURRENT.update(day=day,phase='ON',checks=[]);check();begin=time.monotonic();state=copy.deepcopy(s0);state.__class__=TypedState;ix=copy.deepcopy(xs)
  for i in ix:
   if i['role']=='core':i['_confirmed_core_cp']=copy.deepcopy(proofs[i['sid']])
  result=on_plan(state,ix,at,True);check();runner=CURRENT['runner']
  assert len({z['sid']for z in result['orders']})==len(result['orders'])
  save('ON_'+day+'.json',dict(result,core_confirmed_log=runner.core_confirmed_log,reserve_checks=CURRENT['checks'],final_available_source='Use top-level available; final_state.available_exact is immutable S0 fixture field, not final private available.'))
  on[day]=result
  oldmap={z['key']:z for z in off[day]['orders']};newmap={z['key']:z for z in result['orders']}
  for i in xs:
   key=B.bid(i);a=oldmap.get(key);b=newmap.get(key)
   comparisons.append(dict(OPEN=day,key=key,sid=i['sid'],role=i['role'],rank=i['rank'],original_CP1_id=i.get('CP1_id'),same_day_CORE_CP_id=proofs[i['sid']]['canonical_receipt']['receipt_id']if i['role']=='core'and proofs[i['sid']]['canonical_receipt']else None,old_order=a,new_order=b,quantity_delta=(b['quantity']if b else 0)-(a['quantity']if a else 0)))
  completed.append(dict(day=day,phase='ON',passed=True,intents=len(xs),orders=len(result['orders']),all_reserves_validated=True,fallback_events=len(runner.core_confirmed_log),new_CORE_confirmed=sum(z['role']=='core'and z['pool']=='confirmed'for z in result['orders']),seconds=time.monotonic()-begin,cumulative_compute_seconds=time.monotonic()-START));save('RUN_PROGRESS.json',completed)
 assert all(sha(p)==h for p,h in RUNTIME_SHA.items())
 save('ALL496_COMPARISONS.json',comparisons)
 save('COMPLETION.json',dict(passed=True,dates=list(DATES),intents=sum(len(x[1])for x in batches.values()),compute_seconds=time.monotonic()-START,compute_limit_seconds=60,adapter_sha256=EXPECTED_ADAPTER,source_freeze_sha256=sha(freeze_path),OFF_exact_all_fields=True,inputs_unchanged=True,all_original_numeric_reserve_guards_rechecked=True,all_new_CORE_fee_risk_token_epoch_checks_passed=True,source_unchanged=True,completed=completed,native_Account_initializations=0,native_Runner_initializations=0,new_market_reads=0,new_fills=0,new_financial_paths=0,private_allocation_projections_only=True,not_PnL=True))
 save('OUTPUT_SHA256.json',{str(p.resolve()):sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(read(O/'COMPLETION.json'),ensure_ascii=False,indent=2))

if __name__=='__main__':
 try:main()
 except BaseException as error:
  save('RUN_FAILURE.json',dict(error=str(error),traceback=traceback.format_exc(),day=CURRENT.get('day'),phase=CURRENT.get('phase'),compute_seconds=time.monotonic()-START if START is not None else None,native_Account_initializations=0,native_Runner_initializations=0,no_new_market=True,no_new_fills=True,no_fallback_after_failure=True));raise
