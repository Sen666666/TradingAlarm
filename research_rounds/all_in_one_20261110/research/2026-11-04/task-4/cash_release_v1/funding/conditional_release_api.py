"""Frozen per-candidate conditional cash buffer. No import-time projections."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as NS
import copy,difflib,inspect,json,sys,textwrap
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
PR=ROOT/'reentry_v1/funding_agent/private_projection'
sys.path.insert(0,str(OUT));from static_upper_api import load_complete_batches
import component as P
B=P.B;J=P.J

class FrozenPermission:
 def __init__(self,path):
  self.path=Path(path);self.value=json.loads(self.path.read_text());assert self.value['known_extra_U_cny']=='0'
 def describe(self,a,i,at):
  assert at==i['clock'].earliest_execution_at and i['clock'].decision_at<at
  day=str(i['clock'].decision_at.date());sector=a.sector_by_sid[i['sid']];row=self.value['dates'][day]
  assert type(row['ACT_on'])is bool
  stage=row['sectors'][sector]['stage_name'];assert stage in['observe','probe','confirmed','expanded']
  eligible=row['ACT_on']and stage in['confirmed','expanded']
  return dict(signal_day=day,sector=sector,ACT_on=row['ACT_on'],frozen_signal_industry_stage=stage,
   cash_release_eligible=eligible,U_cny='0',buy_eligibility_unchanged=True)
 def buffer(self,a,i,at,mode):
  d=self.describe(a,i,at);assert mode in['reference_cash10','ACT_mature_U0']
  return D(0)if mode=='ACT_mature_U0'and d['cash_release_eligible']else a.current_nav*D('.1')

def compile_conditional(allocation,mode,permission,budget_check=lambda:None):
 """Prepare a callable only. Original quota/risk/CP1/stock gates stay intact."""
 assert allocation in['native_singlepass','confirmed_min_first'];assert mode in['reference_cash10','ACT_mature_U0']
 def required_buffer(a,i,at):return permission.buffer(a,i,at,mode)
 def suffix_cash_slack(s0,orders,current_key,input_by,at):
  # Valid for mixed buffers; final_available minus own buffer is not valid.
  available=s0.available_exact;seen=False;slack=None
  a=NS(current_nav=s0.decision_nav,sector_by_sid=s0.sector_by_sid)
  for o in orders:
   available-=o['gross']+o['fee'];seen=seen or o['key']==current_key
   if seen:
    x=available-required_buffer(a,input_by[o['key']],at);slack=x if slack is None else min(slack,x)
  assert seen and slack is not None
  return max(D(0),slack)
 src=P.NEW_ROUTE;needle="a.available-a.current_nav*D('.1')";assert src.count(needle)==1
 route_source=src.replace(needle,'a.available-required_buffer(a,i,at)')
 env=dict(J.__dict__,required_buffer=required_buffer);exec(compile(route_source,str(OUT/'conditional_route.py'),'exec'),env);route=env['route'];sources={'route':route_source}
 if allocation=='native_singlepass':
  original=textwrap.dedent(inspect.getsource(P.plan));plan=original;needle="pre_available-a.current_nav*D('.1')";assert plan.count(needle)==1
  plan=plan.replace(needle,'pre_available-required_buffer(a,i,at)');needle='    for src in sorted(intents,key=B.key):\n';assert plan.count(needle)==1
  plan=plan.replace(needle,needle+'        budget_check()\n')
  pe=dict(P.__dict__,ROUTES={True:route},required_buffer=required_buffer,budget_check=budget_check);exec(compile(plan,str(OUT/'conditional_singlepass.py'),'exec'),pe)
  run=lambda s,xs,at:pe['plan'](s,xs,at,True);sources['plan']=plan
 else:
  tail=route_source.index('  bid=');evaluation=route_source[:tail]+"  return dict(quantity=q,pool=pool,token=token,reasons=reasons,results=results),None\n"
  ee=dict(J.__dict__,required_buffer=required_buffer);exec(compile(evaluation,str(OUT/'conditional_full_evaluation.py'),'exec'),ee)
  begin=route_source.index('   pc,pr,_=');end=route_source.index('   q=LR.maximum_quantity')
  predicate='def fixed_predicate(a,i,x,at,pool):\n b=a.budget;sid=i["sid"];sector=a.sector_by_sid[sid];s=b.sectors[sector];p=float(x["price"]);floor=float(x["floor"])\n'+''.join(line[2:]+'\n'for line in route_source[begin:end].splitlines())+' return allowed\n'
  ep=dict(J.__dict__,required_buffer=required_buffer);exec(compile(predicate,str(OUT/'conditional_fixed_predicate.py'),'exec'),ep)
  def invalid(phase,failures,orders,attempts,migrations):
   raise RuntimeError(dict(invalid_plan=True,phase=phase,failures=failures,orders=orders,attempts=attempts,migrations=migrations,no_fallback=True))
  ve=dict(B.__dict__,AccountView=P.AccountView,NATIVE_ROUTE=route,EVAL_ROUTE=ee['route'],fixed_predicate=ep['fixed_predicate'],
   required_buffer=required_buffer,suffix_cash_slack=suffix_cash_slack,budget_check=budget_check,validation_count=budget_check,invalid=invalid)
  reserve=(PR/'retained_fixed_reservation.py').read_text();fixed=(PR/'fixed_combination_validation.py').read_text();original=(PR/'confirmed_min_first_plan.py').read_text();plan=original
  needle="max(Z,latest_valid['available']-s0.decision_nav*D('.1'))";assert plan.count(needle)==1
  plan=plan.replace(needle,"suffix_cash_slack(s0,orders,old['key'],input_by,at)")
  for name,s in [('reserve',reserve),('fixed_validation',fixed),('plan',plan)]:exec(compile(s,str(OUT/('conditional_'+name+'.py')),'exec'),ve);sources[name]=s
  sources.update(evaluation=evaluation,predicate=predicate);run=lambda s,xs,at:ve['plan'](s,xs,at,'two_pass')
 def project_one(s0,intents,at):
  assert s0.remove_confirmed60 is True
  before=P.digest([s0.view(),[B.intent_view(i)for i in intents]]);oldorders=copy.deepcopy(s0.orders);oldlots=copy.deepcopy(s0.lots)
  result=run(s0,intents,at);budget_check();assert before==P.digest([s0.view(),[B.intent_view(i)for i in intents]])
  final=result['final_state'];lots={x['batch']:x for x in final['lots']}
  for oid,o in oldorders.items():assert P.digest(o)==P.digest(final['orders'][oid]),'original committed order changed'
  for lot in oldlots:assert all(P.serial(getattr(lot,k))==lots[lot.batch][k]for k in['stock','sector','qty','cost','floor','role','attempt']),'original inventory changed'
  return result
 return dict(project_one=project_one,generated_sources=sources,allocation=allocation,mode=mode,projection_started=False,
  source_diffs={'route':''.join(difflib.unified_diff(src.splitlines(True),route_source.splitlines(True),fromfile='No60_native_route',tofile='conditional_route')),
   'plan':''.join(difflib.unified_diff(original.splitlines(True),plan.splitlines(True),fromfile='reviewed_reference_plan',tofile='conditional_plan'))})

def compare_candidates(day,s0,intents,old,new,permission):
 """Fixed join schema; no new price or return labels are calculated here."""
 by={(i['sid'],i['role']):B.bid(i)for i in intents};a=P.AccountView(s0)
 def outcomes(result):
  orders={x['key']:x for x in result['orders']};reasons={x['key']:x['reason']for x in result.get('rejected',[])}
  for t in result.get('attempts',[]):
   if 'sid'in t:reasons[by[(t['sid'],t['role'])]]=t.get('result','original_skip')
  return orders,reasons
 oldorders,oldwhy=outcomes(old);neworders,newwhy=outcomes(new);rows=[]
 for i in intents:
  k=B.bid(i);o=oldorders.get(k);n=neworders.get(k);d=permission.describe(a,i,i['clock'].earliest_execution_at)
  rows.append(dict(opening=day,key=k,sid=i['sid'],role=i['role'],CP1_id=i.get('CP1_id'),rank=i['rank'],**d,
   old_order=o,new_order=n,quantity_delta=(n['quantity']if n else 0)-(o['quantity']if o else 0),
   gross_delta=str((n['gross']if n else D(0))-(o['gross']if o else D(0))),fee_delta=str((n['fee']if n else D(0))-(o['fee']if o else D(0))),
   old_result='reserved'if o else oldwhy.get(k),new_result='reserved'if n else newwhy.get(k),
   required_buffer_old=str(a.current_nav*D('.1')),required_buffer_new=str(permission.buffer(a,i,i['clock'].earliest_execution_at,'ACT_mature_U0')),
   new_price_labels_computed=False,new_PnL_computed=False))
 assert len(rows)==len(intents)
 return rows
