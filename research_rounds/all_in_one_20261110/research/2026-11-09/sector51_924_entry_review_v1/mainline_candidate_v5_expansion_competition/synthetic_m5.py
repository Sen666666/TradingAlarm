"""Independent M5 actual-method boundary tests. Synthetic fixtures only, no historical outcomes."""
import sys,pathlib,importlib.util,copy,itertools,json,contextlib,io
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_candidate_v5_expansion_competition').resolve()
sp=importlib.util.spec_from_file_location('audited_m5',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
sys.path.insert(0,str(e.BASE));ns={'frozen':e.m4};exec(compile((e.BASE/'synthetic_m4.py').read_text().replace('import engine as e','e=frozen'),'m4_fixtures','exec'),ns)
D=e.D;ZERO=e.ZERO;dt=ns['dt'];nxt=ns['nxt'];prev=ns['prev'];seed=ns['seed'];checks=[]
def ok(name,value=True):
 assert value,name
 checks.append(name)
class Stub(ns['Stub']):
 def __init__(self):
  super().__init__();self.previous={}
 @property
 def main(self):
  out=super().main
  for s in out:
   out[s].at[prev,'E']=float(self.previous.get(s,out[s].at[prev,'E']))
  return out
class Engine(e.Engine):
 def representative_score(self,s,d):return (D(1),2)
 def create_event(self,*args,**kw):
  ev=super().create_event(*args,**kw)
  if getattr(self,'test_phase','EVENT')!='EVENT':ev['priority_attempted']=True
  return ev
def setup():return Engine(Stub())
def add(x,s='old',q=1000,kind='SEED',role='INITIAL',confirmed=True):
 a=ns['add'](x,s,q,kind,confirmed);a['lots'][0]['capital_role']=role
 return a
# Acquisition roles must originate in real execution, not synthetic labels alone.
for phase,role in [('EVENT','INITIAL'),('RESIDUAL','INITIAL'),('MATURE','EXPANSION')]:
 x=setup();r=seed('a',M=0 if phase=='RESIDUAL' else 1);x.d.M['a']=r['M'];x.test_phase=phase
 x.plan_transfers(dt,[r]);ok('planned_'+phase,r['allocation_phase']==phase);x.alloc_open(nxt,[r])
 ok('actual_acquisition_'+phase,x.orders[-1]['capital_role']==role and x.active['a']['lots'][0]['capital_role']==role)
 x.active['a']['confirmed_history']=True;x.d.M['a']=1;x.d.prices['a']=D(12)
 rr=x.classify_reference(dt)['rows'][0]
 ok('no_reclassification_'+phase,rr['capital_role']==role and (rr['core_qty']==rr['qty'] if role=='INITIAL' else rr['core_qty']==0))
x=setup();a=add(x,'a',100);a['cp']=ns['cp']();a['plan']=ns['plan']('a',2000);x.info_close(a,dt,a['cp'],D(95));x.plan_transfers(dt,[]);x.alloc_open(nxt,[])
ok('actual_ADD_always_expansion',x.orders[-1]['side']=='BUY_ADD' and x.orders[-1]['capital_role']=='EXPANSION' and a['lots'][-1]['capital_role']=='EXPANSION')
# Full role/M/industry/lock boundary matrix.
for role,kind,M,state,restriction in itertools.product(['INITIAL','EXPANSION'],['SEED','ADD'],[-1,0,1],[-1,0,1],['none','T1','locked']):
 if role=='INITIAL' and kind=='ADD':continue
 x=setup();a=add(x,kind=kind,role=role);x.d.M['old']=M;x.d.W['old']=False;x.d.sectors['OLD'].at[dt,'state']=state
 if restriction=='T1':a['lots'][0]['bought']=str(nxt.date())
 if restriction=='locked':a['exit']='I_INVALID'
 ref=x.classify_reference(dt);r=ref['rows'][0]
 if M==-1 or state==-1 or restriction!='none':ok('boundary_frozen_'+str((role,kind,M,state,restriction)),r['mobile_qty']==0)
 elif role=='EXPANSION':ok('expansion_no_W_needed_'+str((kind,M,state)),r['mobile_qty']==1000 and r['core_qty']==0)
 elif M==1:ok('initial_winner_core_'+str(state),r['core_qty']==1000 and r['mobile_qty']==0)
 else:ok('initial_nonM_whole_'+str(state),r['mobile_qty']==1000)
 ok('core_within_fixed_'+str((role,kind,M,state,restriction)),r['core_qty']<=r['frozen_qty'])
# Other uncertainty sources block expansion.
for field in ['stock','E','I','CP','source']:
 x=setup();add(x,role='EXPANSION')
 if field=='stock':x.d.stock.at[dt,'old']=-1
 if field=='E':x.d.Es['old']=float('nan')
 if field=='I':x.d.f=lambda s,d:dict(i_target=None,i_floor=None)
 if field=='CP':x.d.c=lambda s,d:dict(receipt=None,candidate=None)
 if field=='source':
  original=x.d.z;x.d.z=lambda s,d:dict(original(s,d),source_path='different')
 r=x.classify_reference(dt)['rows'][0];ok('uncertainty_'+field,r['mobile_qty']==0 and bool(r['unknown']))
x=setup();add(x,role='EXPANSION');x._probe_receiver_sectors={'OLD'};ok('same_sector_event_freeze',x.classify_reference(dt)['rows'][0]['mobile_qty']==0)
# Additive budget, previous E known/unknown, no future values used.
for previous in [D('.5'),D(2),float('nan')]:
 x=setup();add(x,'a',800,role='INITIAL');add(x,'old',1000,role='EXPANSION');x.receivable=D(123);x.d.previous['A']=previous
 ref=x.classify_reference(dt);x.reference=ref;x.finalize_reference(dt,{'B':D(1000)})
 free=ref['NAV']-ref['reserve']-x.receivable-sum(ref['fixed'].values(),ZERO)-ref['stress']-D(1000)
 ok('exact_free_budget_'+str(previous),free==ref['expansion_budget'])
 target_weight=D('1.5') if previous==D('.5') else D(1)
 ok('weight_previous_'+str(previous),ref['W']['A']==target_weight and ref['evidence']['A']['previous_E_known']==e.finite(float(previous)))
 for s in ref['E']:
  ok('additive_target_'+str((previous,s)),abs(ref['T'][s]-(ref['fixed'][s]+free*ref['W'][s]/sum(ref['W'].values(),ZERO)+ref['event_by_sector'].get(s,ZERO)))<D('1e-18'))
 ok('no_double_budget_'+str(previous),abs(sum(ref['T'].values(),ZERO)-(ref['NAV']-ref['reserve']-x.receivable-ref['stress']))<D('1e-18'))
# Actual planner and OPEN: expansion partial, initial whole, never merely top up reserve.
for role in ['INITIAL','EXPANSION']:
 x=setup();a=add(x,q=100000,role=role);x.d.M['old']=0;x.cash=D(1);r=seed('a');x.plan_transfers(dt,[r]);pl=copy.deepcopy(x.transfer_plan)
 ok('donor_planned_'+role,bool(pl))
 ok('donor_quantity_'+role,(pl[0]['max_q']==100000 if role=='INITIAL' else 0<pl[0]['max_q']<100000))
 n=len(x.orders);x.alloc_open(nxt,[r]);sells=[o for o in x.orders[n:] if o['side'].startswith('SELL')]
 ok('actual_donor_quantity_'+role,bool(sells) and (sells[0]['qty']==100000 if role=='INITIAL' else 0<sells[0]['qty']<100000))
 ok('frozen_max_'+role,sells[0]['qty']<=pl[0]['max_q'])
 x=setup();add(x,q=100000,role=role);x.d.M['old']=0;x.cash=D(1);x.plan_transfers(dt,[]);ok('no_request_no_sale_'+role,not x.transfer_plan)
 x=setup();add(x,q=100000,role=role);x.d.M['old']=0;x.cash=D(1);r=seed('a');x.plan_transfers(dt,[r]);x.d.prices['a']=D(4);n=len(x.orders);x.alloc_open(nxt,[r]);ok('OPEN_receiver_failure_no_sale_'+role,len(x.orders)==n)
# Explicit reduced CLOSE max forces INITIAL cancel, but allows partial EXPANSION.
for role in ['INITIAL','EXPANSION']:
 x=setup();add(x,q=100000,role=role);x.d.M['old']=0;x.cash=D(1);r=seed('a');x.plan_transfers(dt,[r]);x.transfer_plan[0]['max_q']=1000;n=len(x.orders);x.alloc_open(nxt,[r]);sells=[o for o in x.orders[n:] if o['side'].startswith('SELL')]
 ok('OPEN_all_or_none_vs_partial_'+role,not sells if role=='INITIAL' else bool(sells) and sells[0]['qty']<=1000)
# Empty J and infeasible fixed capital never invent expansion budget.
x=setup();x.d.M={s:0 for s in x.d.ids};x.reference=x.classify_reference(dt);x.finalize_reference(dt,{});ok('empty_J_status',x.reference['status']=='NO_POSITIVE_E_M' and all(v==0 for v in x.reference['envelope'].values()))
x=setup();add(x,q=100000,role='INITIAL');x.cash=D(0);x.reference=x.classify_reference(dt);x.finalize_reference(dt,{});ok('infeasible_fixed_no_expansion',x.reference['status']=='INFEASIBLE_LOWER_EXCEEDS_BUDGET' and all(v==0 for v in x.reference['envelope'].values()))
# Every mutable M5 field belongs to M4 atomic inventory; role fields live in active/archive lots and orders.
class Fail(Engine):
 def economic_preflight(self,*args):pass
 def accrue(self,*args):pass
 def exit_open(self,*args):pass
 def alloc_open(self,*args):
  self.active['old']['lots'][0]['capital_role']='BROKEN';self.orders.append({'capital_role':'BROKEN'});self.events['bad']={};self.current_event['bad']='bad';self._event_open_reserved['bad']=D(99);self._execution_requests['bad']={};self._donor_sectors={'bad'};self._probe_receiver_sectors={'bad'};self.reference={'W':{'bad':99}};self._ref_spent={'bad':99}
  for name in ['event_log','event_plans','seed_floor_risk','seed_execution_cost','capital_lots','reference_log','reference_requests']:getattr(self,name).append({'bad':True})
  self.cash-=D(99)
 def close(self,*args):raise e.Blocked('M5_FORCED_ROLLBACK')
 def scan_restored_targets(self,*args):return []
x=Fail(Stub());add(x,role='INITIAL');before=copy.deepcopy(x.__dict__)
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(x,False)
for name in ['cash','active','archive','orders','events','current_event','_event_open_reserved','_execution_requests','_donor_sectors','_probe_receiver_sectors','reference','_ref_spent','event_log','event_plans','seed_floor_risk','seed_execution_cost','capital_lots','reference_log','reference_requests']:ok('rollback_'+name,getattr(x,name)==before[name])
out=dict(result='PASS',total=len(checks),checks=checks,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),historical_outcomes_not_used=True,historical_run_not_started=True)
print(json.dumps(out,default=str))
