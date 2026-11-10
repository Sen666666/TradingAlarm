"""Narrow M7 allocation-cap admission. No historical data or strategy run."""
import pathlib,sys,importlib.util,copy,json,inspect,itertools,contextlib,io
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_candidate_v7_demand_capped').resolve()
sp=importlib.util.spec_from_file_location('audit_m7',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
sys.path.insert(0,str(e.m4.O));ns={'frozen':e.m4};exec(compile((e.m4.O/'synthetic_m4.py').read_text().replace('import engine as e','e=frozen'),'fixtures','exec'),ns)
D=e.D;Z=e.ZERO;dt=ns['dt'];nxt=ns['nxt'];checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
class Engine(e.Engine):
 def representative_score(self,s,d):return (D(1),2)
 def attribute(self,*a):pass
def setup():
 return Engine(ns['Stub']())
def add(x,s='a',q=6000,role='INITIAL'):
 a=ns['add'](x,s,q,'SEED',True);a['lots'][0]['capital_role']=role;a['cp']=ns['cp']();return a
def req(x,a):
 r=ns['plan'](a['sid'],2000);x.decorate(r,dt);r['allocation_phase']='MATURE';return r
def demand(x,rs):
 x.reference=x.classify_reference(dt);x._m7_raw_requests=rs
 try:return x.independent_mature_demand(dt)
 finally:del x._m7_raw_requests
# Water conservation, caps, deterministic order, proportional uncapped remainder.
for w1,w2,u1,u2,b in itertools.product([1,3],[1,7],[0,2,100],[0,5,90],[-1,0,1,30,500]):
 w={'A':D(w1),'B':D(w2)};u={'A':D(u1),'B':D(u2)};x,lam,left=e.capped_water(w,u,D(b));y,yl,ylft=e.capped_water(dict(reversed(list(w.items()))),dict(reversed(list(u.items()))),D(b));target=min(max(Z,D(b)),sum(u.values()))
 ok('water_'+str((w1,w2,u1,u2,b)),abs(sum(x.values())-target)<D('1e-18') and all(Z<=x[s]<=u[s] and abs(x[s]-min(u[s],lam*w[s]))<D('1e-18') for s in x) and x==y and lam==yl and left==max(Z,D(b)-target))
ok('empty_water',e.capped_water({}, {}, D(10))==({},Z,D(10)))
# Demand uses legal raw requests, independent of reference/cash.
x=setup();a=add(x);r=req(x,a);base,details=demand(x,[r]);ok('raw_ADD_positive',base['A']>0)
x.reference['T']={s:Z for s in x.d.sector_ids};x.reference['envelope']={s:Z for s in x.d.sector_ids};x.cash=D(0);x.transfer_plan=[{'fake':True}];x._m7_raw_requests=[r];d2,t=x.independent_mature_demand(dt);del x._m7_raw_requests
ok('D_ignores_reference_cash_donor',d2==base)
x.cash=e.INITIAL;dup,ds=demand(x,[r,copy.deepcopy(r)]);ok('duplicate_CP_once',dup==base and ds[1]['decision']=='DUPLICATE_CURRENT_REQUEST')
bad=copy.deepcopy(r);bad['cp_id']='INVALID';d3,ds=demand(x,[bad,r]);ok('different_CP_must_be_current',d3==base and sum(v['independent_q']>0 for v in ds)==1)
# EVENT reservations consume shared stock budget but never mature demand.
ev=dict(r,kind='SEED',allocation_phase='EVENT',_ref_q=800,_reference_close_cost=D(70000))
d4,ds=demand(x,[ev,r]);ok('EVENT_stock_budget_decrement',d4['A']<base['A'] and ds[0]['stock_value_before']==D(130000))
d5,ds=demand(x,[dict(r,allocation_phase='RESIDUAL')]);ok('RESIDUAL_not_D',all(v==0 for v in d5.values()) and not ds)
x=setup();r=ns['seed']('a');x.sync_events(dt);x.events[x.current_event['A']]['priority_attempted']=True;x.prepare_requests(dt,[r]);d6,ds=demand(x,[r,r.copy()]);ok('mature_SEED_deduplicated',d6['A']>0 and sum(v['independent_q']>0 for v in ds)==1)
r['score_known']=False;d6,ds=demand(x,[r]);ok('unknown_score_not_D',d6['A']==0)
# Actual finalization: event budget accounted once, no-demand U=K, capped X no invented demand.
x=setup();a=add(x,'old',1000,'EXPANSION');r=ns['seed']('a');x.plan_transfers(dt,[r]);ref=x.reference
ok('temporary_context_removed_success',not hasattr(x,'_m7_raw_requests'))
ok('no_request_U_equals_K',ref['D']['OLD']==0 and ref['U']['OLD']==ref['K']['OLD'] and ref['X']['OLD']<=ref['K']['OLD'])
ok('no_request_no_buy_envelope',ref['envelope']['OLD']==0)
ok('event_reserved_once',ref['event_reserve']==r['_reference_close_cost'] and ref['T']['A']==ref['fixed']['A']+ref['X']['A']+r['_reference_close_cost'])
free=ref['NAV']-ref['reserve']-x.receivable-sum(ref['fixed'].values(),Z)-ref['stress']-ref['event_reserve']
ok('G_exact',ref['expansion_budget']==free)
ok('target_conservation',abs(sum(ref['X'].values())-min(max(Z,free),sum(ref['U'][s] for s in ref['W'])))<D('1e-18'))
ok('all_saturated_leftover',ref['unallocated_expansion_budget']>0 and all(ref['X'][s]==ref['U'][s] for s in ref['W']))
x=setup();x.d.M={s:0 for s in x.d.ids};x.plan_transfers(dt,[]);ok('empty_J',x.reference['status']=='NO_POSITIVE_E_M' and not any(x.reference['X'].values()))
x=setup();add(x,'a',100000);x.cash=Z;x.plan_transfers(dt,[]);ok('negative_G',x.reference['status']=='INFEASIBLE_LOWER_EXCEEDS_BUDGET' and not any(x.reference['X'].values()) and not any(x.reference['envelope'].values()))
# Next-dated ADD sizing caps demand before allocation.
x=setup();a=add(x);r=req(x,a);orig=x.d.size
x.d.size=lambda s,d,p,budget,cap:0 if d==nxt else orig(s,d,p,budget,cap)
dd,ds=demand(x,[r]);ok('next_dated_ADD_resize',dd['A']==0 and ds[0]['decision']=='ADD_NO_LEGAL_Q_NEXT_DATED_RULES')
# Exceptions cannot leak request context; reference/log mutation rolls back through inherited loop.
class Fail(Engine):
 def finalize_reference(self,d,event_by_sector):
  self.reference['D']={'bad':1};self.reference_log.append({'bad':1});raise e.Blocked('M7_FORCED')
x=Fail(ns['Stub']())
try:x.plan_transfers(dt,[])
except e.Blocked:pass
else:raise AssertionError('expected failure')
ok('context_removed_on_exception',not hasattr(x,'_m7_raw_requests'))
class AtomicFail(Fail):
 def economic_preflight(self,*a):pass
 def accrue(self,*a):pass
 def exit_open(self,*a):pass
 def alloc_open(self,*a):pass
 def close(self,d,prev):self.plan_transfers(d,[])
 def scan_restored_targets(self,*a):return []
x=AtomicFail(ns['Stub']())
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(x,False)
ok('reference_logs_rollback',x.reference=={} and x.reference_log==[] and x.capital_lots==[] and not hasattr(x,'_m7_raw_requests'))
ok('atomic_source_unchanged',e.source==inspect.getsource(e.m4.run_loop))
ok('unchanged_execution_and_roles',e.Engine.alloc_open is e.m6.Engine.alloc_open and e.Engine.order is e.m6.Engine.order and e.Engine.classify_reference is e.m6.Engine.classify_reference and e.Engine.execute_transfers is e.m6.Engine.execute_transfers)
out=dict(result='PASS',total=len(checks),checks=checks,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),historical_outcomes_not_used=True)
print(json.dumps(out))
