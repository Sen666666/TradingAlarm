"""M6 narrow actual-method admission. Synthetic only."""
import pathlib,sys,importlib.util,inspect,copy,json,contextlib,io,textwrap,ast
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_candidate_v6_mature_round_cap').resolve()
sp=importlib.util.spec_from_file_location('audit_m6',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
sys.path.insert(0,str(e.m4.O));ns={'frozen':e.m4};exec(compile((e.m4.O/'synthetic_m4.py').read_text().replace('import engine as e','e=frozen'),'fixtures','exec'),ns)
D=e.D;dt=ns['dt'];nxt=ns['nxt'];prev=ns['prev'];checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
class Engine(e.Engine):
 def representative_score(self,s,d):return (D(1),2)
 def attribute(self,*args):pass
class Stub(ns['Stub']):pass
def setup(q=6000):
 x=Engine(Stub());a=ns['add'](x,'a',q,'SEED',True);a['lots'][0]['capital_role']='INITIAL';a['cp']=ns['cp']();return x,a
newclose=e.m3.Engine.close;newnoncash=e.m3.Engine.noncash
oldns=dict(e.m3.__dict__);exec(compile(textwrap.dedent(e.original_close),'oldclose','exec'),oldns);oldclose=oldns['close'];exec(compile(textwrap.dedent(e.original_noncash),'oldnoncash','exec'),oldns);oldnoncash=oldns['noncash']
def mode(new):
 e.m3.Engine.close=newclose if new else oldclose;e.m3.Engine.noncash=newnoncash if new else oldnoncash
ok('only_CLOSE_expression',e.close_source==e.original_close.replace(' def close','def close',1).replace("budget=min(D('.02')*a['nav0'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,'raw_close')))","budget=D('.02')*a['nav0']",1))
ok('only_noncash_expression',e.noncash_source==e.original_noncash.replace(' def noncash','def noncash',1).replace("budget=min(r['budget'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,field))) if a else ZERO","budget=r['budget'] if a else ZERO",1))
# Real CLOSE plan then OPEN fill; appreciated value above old 4% floor.
states=[]
for new in [False,True]:
 mode(new);x,a=setup();x.close(dt,prev);planned=copy.deepcopy(a['plan']);before=len(x.orders);x.alloc_open(nxt,[]);buys=[o for o in x.orders[before:] if o['side']=='BUY_ADD'];states.append((planned,buys))
 if new:
  ok('appreciated_CLOSE_2pct',planned and planned['budget']==D(24000))
  ok('appreciated_OPEN_real_ADD',bool(buys))
  ok('ADD_within_2pct',D(buys[0]['all_in_cost'])<=D(24000))
  ok('ADD_role_expansion',buys[0]['capital_role']=='EXPANSION')
  ok('CP_consumed_only_fill',a['cp'] is None)
ok('old_4pct_blocks_same_winner',states[0]==(None,[]))
# Below old round bound, generated plans/orders identical.
out=[]
for new in [False,True]:
 mode(new);x,a=setup(100);x.close(dt,prev);x.alloc_open(nxt,[]);out.append((x.orders,x.candidates,x.cash,x.active,x.reference))
ok('below_bound_exact_equivalence',out[0]==out[1]);mode(True)
# OPEN-only gap increases marked position beyond old 4%; frozen q still obeyed.
x,a=setup(3000);x.close(dt,prev);q=a['plan']['planned_q'];x.d.prices['a']=D(20);before=len(x.orders);x.alloc_open(nxt,[]);buys=[o for o in x.orders[before:] if o['side']=='BUY_ADD'];ok('OPEN_appreciation_no_4pct',bool(buys));ok('OPEN_frozen_q_not_increased',buys[0]['qty']<=q and D(buys[0]['all_in_cost'])<=D(24000))
# Guardrails at actual CLOSE/OPEN.
for gate in ['no_cp','no_profit','sector_unknown','M_unknown','I_unknown','CP_unknown','locked']:
 x,a=setup()
 if gate=='no_cp':a['cp']=None
 if gate=='no_profit':a['cashflow']=D(-1000000)
 if gate=='sector_unknown':x.d.sectors['A'].at[dt,'state']=-1
 if gate=='M_unknown':x.d.M['a']=-1
 if gate=='I_unknown':x.d.f=lambda s,d:dict(i_target=None,i_floor=None)
 if gate=='CP_unknown':x.d.c=lambda s,d:dict(receipt=None,candidate=None)
 if gate=='locked':a['exit']='I_INVALID'
 x.close(dt,prev);before=len(x.orders);x.alloc_open(nxt,[]);ok('gate_'+gate,not any(o['side']=='BUY_ADD' for o in x.orders[before:]))
for gate in ['stock','reference','cash','open_profit','cp_replaced']:
 x,a=setup();x.close(dt,prev);plan=a['plan']
 if gate=='stock':x.d.prices['a']=D(25)
 if gate=='reference':x.reference['envelope']['A']=D(0)
 if gate=='cash':x.cash=D(1)
 if gate=='open_profit':a['cashflow']=D(-1000000)
 if gate=='cp_replaced':a['cp']['id']='OTHER'
 before=len(x.orders);x.alloc_open(nxt,[]);ok('OPEN_guard_'+gate,not any(o['side']=='BUY_ADD' for o in x.orders[before:]))
# Seed and event path unchanged exactly by mode switching.
out=[]
for new in [False,True]:
 mode(new);x=Engine(Stub());r=ns['seed']('a');x.plan_transfers(dt,[r]);x.alloc_open(nxt,[r]);out.append((x.orders,x.cash,x.events,x.active,x.event_log))
ok('SEED_event_exact_equivalence',out[0]==out[1]);mode(True)
# Atomic inventory source differs from inherited loop only in global Engine/output bindings.
ok('atomic_inventory_source_unchanged',e.source==inspect.getsource(e.m4.run_loop))
class Fail(Engine):
 def economic_preflight(self,*a):pass
 def accrue(self,*a):pass
 def exit_open(self,*a):pass
 def alloc_open(self,*args):self.cash-=99;self.active['a']['lots'][0]['capital_role']='BAD';self.orders.append({'bad':True});self.reference={'bad':True};self.events['bad']={};self.event_log.append({'bad':True})
 def close(self,*a):raise e.Blocked('M6_TEST_ROLLBACK')
 def scan_restored_targets(self,*a):return []
x=Fail(Stub());a=ns['add'](x,'a',100,'SEED',True);a['lots'][0]['capital_role']='INITIAL';before=copy.deepcopy(x.__dict__)
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(x,False)
for key in ['cash','active','archive','orders','reference','events','event_log']:ok('rollback_'+key,getattr(x,key)==before[key])
out=dict(result='PASS',total=len(checks),checks=checks,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),historical_outcomes_not_used=True,base_M5_234_checks_reused_by_unchanged_method_scope=True)
print(json.dumps(out))
