"""Prepared-only private interfaces. Import/CLI never executes a projection.

The zero-extra-buffer case is an optimistic bound, not a proposed reserve rule.
Existing settled/locked/order responsibilities stay in authoritative available.
"""
from pathlib import Path
from decimal import Decimal as D
import copy,hashlib,inspect,json,sys,textwrap,time
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
OLD=ROOT/'reentry_v1/funding_agent';PR=OLD/'private_projection'
sys.path.insert(0,str(PR));from rebuild_off import hydrate
from run_confirmed_min_first import load_intents
import component as P
B=P.B;J=P.J
def read(p):return json.loads(Path(p).read_text())
def load_complete_batches():
 """Return all13 exact S0+4172 previews, not a focus-only candidate subset."""
 s0={k[:10]:v['state']for k,v in read(OLD/'PREOPEN_EXACT_STATE.json').items()};result={}
 for check in read(PR/'OFF_IDENTITY.json')['checks']:
  day=check['opening'];s=hydrate(s0[day]);xs=load_intents(PR/('PREVIEWS_'+day+'.json'))
  assert P.digest([s.view(),[B.intent_view(i)for i in xs]])==check['source_input_sha256']
  result[day]=(s,xs,J.M.N.iso(day+'T09:30:00+08:00'))
 assert len(result)==13 and sum(len(x[1])for x in result.values())==4172
 return result

def compile_bundle(allocation,buffer_mode,mandatory_residual_cny=D(0),budget_check=lambda:None):
 """Build a callable; this function does not run it.

 allocation: native_singlepass or confirmed_min_first.
 buffer_mode: reference_cash10 or optimistic_mandatory_only.
 mandatory_residual is an evidence input, not a fitted parameter; zero gives
 the optimistic bound after responsibilities already excluded by available.
 """
 assert allocation in['native_singlepass','confirmed_min_first']
 assert buffer_mode in['reference_cash10','optimistic_mandatory_only']
 mandatory=D(mandatory_residual_cny);assert mandatory>=0
 def required_buffer(a):return a.current_nav*D('.1')if buffer_mode=='reference_cash10'else mandatory
 def state_buffer(s):return s.decision_nav*D('.1')if buffer_mode=='reference_cash10'else mandatory
 src=P.NEW_ROUTE;needle="a.available-a.current_nav*D('.1')";assert src.count(needle)==1
 route_source=src.replace(needle,'a.available-required_buffer(a)')
 env=dict(J.__dict__,required_buffer=required_buffer);exec(compile(route_source,str(OUT/'derived_cash_bound_route.py'),'exec'),env);route=env['route']
 sources={'route':route_source}
 if allocation=='native_singlepass':
  plan_source=textwrap.dedent(inspect.getsource(P.plan));needle="pre_available-a.current_nav*D('.1')";assert plan_source.count(needle)==1
  plan_source=plan_source.replace(needle,'pre_available-required_buffer(a)')
  plan_source=plan_source.replace('    for src in sorted(intents,key=B.key):\n','    for src in sorted(intents,key=B.key):\n        budget_check()\n')
  pe=dict(P.__dict__,ROUTES={True:route},required_buffer=required_buffer,budget_check=budget_check);exec(compile(plan_source,str(OUT/'derived_cash_bound_singlepass.py'),'exec'),pe)
  raw_plan=lambda s,xs,at:pe['plan'](s,xs,at,True);sources['plan']=plan_source
 else:
  tail=route_source.index('  bid=');evaluation=route_source[:tail]+"  return dict(quantity=q,pool=pool,token=token,reasons=reasons,results=results),None\n"
  ee=dict(J.__dict__,required_buffer=required_buffer);exec(compile(evaluation,str(OUT/'derived_cash_bound_full_evaluation.py'),'exec'),ee)
  begin=route_source.index('   pc,pr,_=');end=route_source.index('   q=LR.maximum_quantity')
  predicate='def fixed_predicate(a,i,x,at,pool):\n b=a.budget;sid=i["sid"];sector=a.sector_by_sid[sid];s=b.sectors[sector];p=float(x["price"]);floor=float(x["floor"])\n'+''.join(line[2:]+'\n'for line in route_source[begin:end].splitlines())+' return allowed\n'
  ep=dict(J.__dict__,required_buffer=required_buffer);exec(compile(predicate,str(OUT/'derived_cash_bound_fixed_predicate.py'),'exec'),ep)
  def invalid(phase,failures,orders,attempts,migrations):
   raise RuntimeError(dict(invalid_plan=True,phase=phase,failures=failures,orders=orders,attempts=attempts,migrations=migrations,no_fallback=True))
  ve=dict(B.__dict__,AccountView=P.AccountView,NATIVE_ROUTE=route,EVAL_ROUTE=ee['route'],fixed_predicate=ep['fixed_predicate'],
   budget_check=budget_check,validation_count=budget_check,invalid=invalid,state_buffer=state_buffer)
  reserve=(PR/'retained_fixed_reservation.py').read_text();fixed=(PR/'fixed_combination_validation.py').read_text();plan=(PR/'confirmed_min_first_plan.py').read_text()
  needle="s0.decision_nav*D('.1')";assert plan.count(needle)==1;plan=plan.replace(needle,'state_buffer(s0)')
  for name,s in [('reserve',reserve),('fixed_validation',fixed),('plan',plan)]:exec(compile(s,str(OUT/('derived_cash_bound_'+name+'.py')),'exec'),ve);sources[name]=s
  sources.update(evaluation=evaluation,predicate=predicate);raw_plan=lambda s,xs,at:ve['plan'](s,xs,at,'two_pass')
 def project_one(s0,intents,at):
  """Caller must first prove both13 reference identities and freeze scope/budget."""
  assert s0.remove_confirmed60 is True
  before=P.digest([s0.view(),[B.intent_view(i)for i in intents]])
  orders_before=copy.deepcopy(s0.orders);lots_before=copy.deepcopy(s0.lots)
  result=raw_plan(s0,intents,at);budget_check()
  assert before==P.digest([s0.view(),[B.intent_view(i)for i in intents]])
  final=result['final_state']
  for oid,o in orders_before.items():assert P.digest(o)==P.digest(final['orders'][oid]),'existing committed order changed'
  lots={x['batch']:x for x in final['lots']}
  for old in lots_before:
   assert all(P.serial(getattr(old,k))==lots[old.batch][k]for k in['stock','sector','qty','cost','floor','role','attempt']),'existing inventory changed'
  result['cash_bound_scope']=dict(allocation=allocation,buffer_mode=buffer_mode,mandatory_residual_cny=str(mandatory),
   existing_committed_orders_preserved=True,no_inventory_liquidation=True,not_PnL=True,optimistic_bound_not_recommended_policy=buffer_mode=='optimistic_mandatory_only')
  return result
 return dict(project_one=project_one,generated_sources=sources,allocation=allocation,buffer_mode=buffer_mode,
  reference_identity_required=['all13 original singlepass cash10','all13 reviewed confirmed-min-first cash10'],
  not_executed_by_compilation=True)

if __name__=='__main__':
 batches=load_complete_batches();compiled=[]
 for allocation in ['native_singlepass','confirmed_min_first']:
  for mode in ['reference_cash10','optimistic_mandatory_only']:
   bundle=compile_bundle(allocation,mode);compiled.append(dict(allocation=allocation,buffer_mode=mode,mandatory_residual_cny='0',
    generated_sources=bundle['generated_sources'],source_sha256={k:hashlib.sha256(v.encode()).hexdigest()for k,v in bundle['generated_sources'].items()},projection_calls=0))
 (OUT/'INTERFACE_COMPILED_SOURCES.json').write_text(json.dumps(compiled,ensure_ascii=False,indent=2))
 result=dict(prepared=True,OPENs=len(batches),intents=sum(len(x[1])for x in batches.values()),compiled_interfaces=4,
  projection_calls=0,new_accounts=0,new_restores=0,market_reads=0)
 (OUT/'INTERFACE_PREPARATION.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
