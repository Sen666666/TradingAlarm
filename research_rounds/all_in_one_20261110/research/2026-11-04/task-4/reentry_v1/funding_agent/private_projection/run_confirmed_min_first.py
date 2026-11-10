"""Reviewed confirmed-only minimum-first; private reservation projections only."""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import copy,difflib,hashlib,inspect,json,sys,textwrap,time,traceback
OUT=Path(__file__).resolve().parent;FUND=OUT.parent
sys.path.insert(0,str(OUT));from rebuild_off import hydrate
import component as P
B=P.B;J=P.J;LR=J.LR
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact(a,b,n):assert P.digest(a)==P.digest(b),n
CURRENT={};COUNTS={};START=None;LIMIT=131.57905040495098
def budget_check():
 if START is not None and time.monotonic()-START>=LIMIT:raise TimeoutError('remaining OFF+ON131.579sec exhausted')
def validation_count():
 budget_check();COUNTS['fixed_validations']=COUNTS.get('fixed_validations',0)+1
def invalid(phase,failures,orders,attempts,migrations):
 save('INVALID_PLAN.json',dict(opening=CURRENT['opening'],phase=phase,failures=failures,orders=orders,attempts=attempts,migrations=migrations,compute_seconds=time.monotonic()-START,
  no_fallback=True,no_dropped_later_minimum=True,no_rerouting=True))
 raise RuntimeError('invalid fixed plan: '+phase)

def compile_policy():
 # Every evaluation predicate comes from the frozen No60 route, never old60.
 tail=P.NEW_ROUTE.index('  bid=')
 evaluation=P.NEW_ROUTE[:tail]+"  return dict(quantity=q,pool=pool,token=token,reasons=reasons,results=results),None\n"
 e=dict(J.__dict__);exec(compile(evaluation,str(OUT/'no60_full_target_evaluation.py'),'exec'),e)
 begin=P.NEW_ROUTE.index('   pc,pr,_=');end=P.NEW_ROUTE.index('   q=LR.maximum_quantity')
 predicate='def fixed_predicate(a,i,x,at,pool):\n b=a.budget;sid=i["sid"];sector=a.sector_by_sid[sid];s=b.sectors[sector];p=float(x["price"]);floor=float(x["floor"])\n'+''.join(line[2:]+'\n'for line in P.NEW_ROUTE[begin:end].splitlines())+' return allowed\n'
 ep=dict(J.__dict__);exec(compile(predicate,str(OUT/'no60_fixed_pool_predicate.py'),'exec'),ep)
 reserve=textwrap.dedent(inspect.getsource(B.reserve_fixed))
 assert reserve.count('core_epoch_locked=False')==1
 reserve=reserve.replace('core_epoch_locked=False',"core_epoch_locked=i['role']=='core' and a.core_epoch.get(i['sid'])==i['epoch']")
 fixed=textwrap.dedent(inspect.getsource(B.fixed_validation))
 needle='    b=copy.deepcopy(s0);';assert fixed.count(needle)==1;fixed=fixed.replace(needle,'    validation_count();b=copy.deepcopy(s0);')
 needle="    for attempt in attempts:\n";assert fixed.count(needle)==1;fixed=fixed.replace(needle,needle+'        budget_check()\n')
 original=textwrap.dedent(inspect.getsource(B.plan));policy=original
 edits=[("q=x['minq'] if result['pool']=='probe' else result['quantity']","q=x['minq'] if result['pool']=='confirmed' else result['quantity']"),
  ("if old['pool']!='probe':continue","if old['pool']!='confirmed':continue"),
  ("candidate=order_record(i,q,'probe',x,fee)","candidate=order_record(i,q,'confirmed',x,fee)"),
  ("if not initial['valid']:raise AssertionError(('initial fixed plan invalid',initial['failures']))","if not initial['valid']:invalid('initial',initial['failures'],orders,attempts,expected)\n        latest_valid=initial"),
  ("orders,v=trial(lo);assert v['valid']","orders,v=trial(lo)\n            if not v['valid']:invalid('accepted_topup',v['failures'],orders,attempts,expected)\n            latest_valid=v"),
  ("final=fixed_validation(s0,intents,attempts,orders,at,expected);assert final['valid'];b=final['state'];a=AccountView(b);a.available=final['available']","final=fixed_validation(s0,intents,attempts,orders,at,expected)\n        if not final['valid']:invalid('final',final['failures'],orders,attempts,expected)\n        b=final['state'];a=AccountView(b);a.available=final['available']")]
 for old,new in edits:assert policy.count(old)==1,old;policy=policy.replace(old,new)
 needle='    for source in sorted(intents,key=key):\n';assert policy.count(needle)==1;policy=policy.replace(needle,needle+'        budget_check()\n')
 needle="            def trial(k):\n";assert policy.count(needle)==1
 optimization="            # F(q) is nondecreasing; cash alone is a necessary upper bound.\n            cash_left=max(Z,latest_valid['available']-s0.decision_nav*D('.1'))\n            hi=min(hi,lo+int(cash_left//(x['price']*x['rule'].buy_step)))\n            if hi==lo:continue  # Current complete combination is already validated.\n"
 policy=policy.replace(needle,optimization+needle)
 env=dict(B.__dict__,AccountView=P.AccountView,NATIVE_ROUTE=P.ROUTES[True],EVAL_ROUTE=e['route'],fixed_predicate=ep['fixed_predicate'],
  budget_check=budget_check,validation_count=validation_count,invalid=invalid)
 exec(compile(reserve,str(OUT/'retained_fixed_reservation.py'),'exec'),env)
 exec(compile(fixed,str(OUT/'fixed_combination_validation.py'),'exec'),env)
 exec(compile(policy,str(OUT/'confirmed_min_first_plan.py'),'exec'),env)
 for name,src in [('no60_full_target_evaluation.py',evaluation),('no60_fixed_pool_predicate.py',predicate),('retained_fixed_reservation.py',reserve),('fixed_combination_validation.py',fixed),('confirmed_min_first_plan.py',policy)]:
  (OUT/name).write_text(src)
 diff=''.join(difflib.unified_diff(original.splitlines(True),policy.splitlines(True),fromfile='old_probe_two_pass',tofile='confirmed_only_min_first'))
 diff+='\n'+''.join(difflib.unified_diff(inspect.getsource(B.reserve_fixed).splitlines(True),reserve.splitlines(True),fromfile='old_fixed_reservation',tofile='original_native_core_epoch_gate_retained'))
 (OUT/'POLICY_SOURCE.diff').write_text(diff)
 return env['plan']

def load_intents(path):
 xs=[]
 for v in read(path):
  i={k:copy.deepcopy(x)for k,x in v.items()if k not in ['preview','preview_failure']}
  for k in ['budget','floor','risk_budget']:
   if k in i:i[k]=D(i[k])
  i['epoch']=tuple(i['epoch'])if i['epoch']is not None else None;c=v['clock'];i['clock']=LR.A.Clock(J.M.N.iso(c['decision_at']),J.M.N.iso(c['earliest_execution_at']),J.pd.Timestamp(c['session_date']).date());i['quote']=NS(par_value=D(v['quote']['par_value']))
  x=v['preview']
  if x:
   x=copy.deepcopy(x)
   for k in ['price','floor','known_open']:x[k]=D(x[k])
   x['rule']=LR.L.QuantityRule(**x['rule']);s=x['schedule'];x['schedule']=LR.L.FeeSchedule(s['schedule_id'],tuple(LR.L.FeeComponent(**p)for p in s['components']))
   assert all(D(p.rate)>=0 for p in x['schedule'].components),'cash hi monotone fee prerequisite'
  i['_preview']=x;i['_preview_failure']=v['preview_failure'];xs.append(i)
 return xs

def main():
 global START
 prep=time.monotonic();review=FUND.parent/'review/PRIVATE_OFF_13OPEN_IDENTITY_AUDIT.json';card=FUND.parent/'CONFIRMED_MIN_FIRST_CARD.txt'
 assert read(review)['status']=='PASS_ON_PRIVATE_PROJECTION_ONLY'
 identity=read(OUT/'OFF_IDENTITY.json');done=read(OUT/'COMPLETION.json');assert done['passed']and done['ON_started']is False and done['remaining_OFF_ON_budget_seconds']==LIMIT
 sources={str(p):sha(p)for p in [review,card,Path(__file__),OUT/'OFF_IDENTITY.json',OUT/'COMPLETION.json',OUT/'ARTIFACT_SHA256.json',FUND/'PREOPEN_EXACT_STATE.json']}
 for p,h in read(review)['source_sha256'].items():assert sha(p)==h;sources[p]=h
 s0={k[:10]:v for k,v in read(FUND/'PREOPEN_EXACT_STATE.json').items()};batches={}
 for check in identity['checks']:
  day=check['opening'];pp=OUT/('PREVIEWS_'+day+'.json');sources[str(pp)]=sha(pp);state=hydrate(s0[day]['state']);xs=load_intents(pp)
  exact(P.digest([state.view(),[B.intent_view(i)for i in xs]]),check['source_input_sha256'],'reviewed OFF entire input digest '+day)
  batches[day]=(state,xs,J.M.N.iso(day+'T09:30:00+08:00'))
 policy=compile_policy();save('ON_SOURCE_SHA256.json',sources);save('ON_PREPARATION.json',dict(seconds=time.monotonic()-prep,batches=13,intents=sum(len(x[1])for x in batches.values()),used_only_saved_S0_PREVIEWS=True,market_reads=0,remaining_compute_limit_seconds=LIMIT))
 print('ON PREPARED',round(time.monotonic()-prep,3),flush=True);START=time.monotonic();summaries=[]
 for day,(state,xs,at)in sorted(batches.items()):
  CURRENT['opening']=day;COUNTS.clear();t=time.monotonic();before=P.digest([state.view(),[B.intent_view(i)for i in xs]])
  on=policy(state,xs,at,'two_pass');budget_check()
  assert before==P.digest([state.view(),[B.intent_view(i)for i in xs]])
  assert len({x['sid']for x in on['orders']})==len(on['orders'])
  by={B.bid(i):i for i in xs}
  for order in on['orders']:
   i=by[order['key']];x=i['_preview'];assert order['fee']==LR.fees(order['quantity'],x['price'],x['schedule'],'buy',i['quote'].par_value)
   assert x['rule'].buy_floor(order['quantity'])==order['quantity'] and order['quantity']<=x['maxq']
  assert sorted(o['CP1_id']for o in on['orders']if o['role']=='mobile')==on['proposed_stock_receipt_consumptions']
  save('ON_'+day+'.json',on)
  summaries.append(dict(opening=day,passed=True,orders=len(on['orders']),fixed_validations=COUNTS.get('fixed_validations',0),seconds=time.monotonic()-t,cumulative_compute_seconds=time.monotonic()-START,
   fixed_combination_and_migration_signature_valid=True,all_aggregate_fees_recomputed_exact=True,inputs_unchanged=True))
  save('ON_PROGRESS.json',summaries);print('ON VALID',day,len(on['orders']),COUNTS,round(time.monotonic()-START,3),flush=True)
 assert all(sha(p)==h for p,h in sources.items())
 save('ON_COMPLETION.json',dict(passed=True,OPENs=13,intents=4172,compute_seconds=time.monotonic()-START,OFF_compute_seconds=done['compute_seconds'],
  OFF_ON_compute_seconds=done['compute_seconds']+time.monotonic()-START,limit_seconds=180,source_unchanged=True,input_digests_unchanged=True,
  final_fixed_plan_and_migrations_valid=True,no_fallback=True,no_later_minima_dropped=True,no_pool_reroute_on_validation_failure=True,
  new_accounts=0,new_restores=0,real_fills=0,new_financial_paths=0,not_PnL=True,independent_review_required=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ON_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),opening=CURRENT.get('opening'),compute_seconds=time.monotonic()-START if START else None,
  no_fallback=True,no_new_accounts=True,no_new_restores=True));raise
