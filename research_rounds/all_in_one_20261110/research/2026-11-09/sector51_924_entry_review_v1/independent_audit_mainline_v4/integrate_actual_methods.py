"""Independent M4 call-level adversarial tests. Fabricated inputs only; no Data/history run."""
from pathlib import Path
import sys,importlib.util,copy,json,hashlib,traceback
from types import SimpleNamespace
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;P=O.parent;source=P/'mainline_candidate_v4_event_representatives/engine.py'
sp=importlib.util.spec_from_file_location('independent_m4_current',source);m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
D=m.D;pd=m.pd;Z=m.ZERO;dt=pd.Timestamp('2024-09-03');nxt=pd.Timestamp('2024-09-04')
base=(m.v1.O/'synthetic_m.py').read_text().split('def run():')[0].replace('import engine as m','# injected m');ns={'m':m};exec(compile(base,'frozen_fixture_definitions','exec'),ns);Base=ns['Stub'];attempt=ns['attempt'];orig_seed=ns['seed']
class Fee:
 components=[SimpleNamespace(name='net_brokerage',side='both')]
 def incremental(self,side,notional,*a,**kw):return {'net_brokerage':max(D(5),D('.0002')*notional)}
 def rate_accrual(self,side,notional,*a,**kw):return {'net_brokerage':D('.0002')*notional}
class Stub(Base):
 def __init__(self):
  super().__init__();self.cal=pd.bdate_range('2024-08-26','2024-09-04');self.days=pd.DatetimeIndex([dt]);self.stock=pd.DataFrame(1,index=self.cal,columns=self.ids);self.cap={s:pd.Series(100000,index=self.cal) for s in self.ids};self.raw={s:pd.DataFrame([dict(self.z(s,d),raw_high=10.,raw_low=10.,raw_volume=100000.,close=10.) for d in self.cal],index=self.cal) for s in self.ids};self.sectors={sec:pd.DataFrame(dict(state=[0 if d<dt else 1 for d in self.cal],N=3,K=3,n=3,U=0,paired_K=3,entered3=0,left3=0,diff=0,strength=False),index=self.cal) for sec in self.sector_ids}
 @property
 def main(self):return {sec:pd.DataFrame(dict(M=[self.M[s]]*len(self.cal),E=[self.Es[s]]*len(self.cal),return5_median=0),index=self.cal) for s,sec in self.sid_sector.items()}
 def getmeta(self,*args):return (m.b.QuantityRule('x',100,100,100,True,1),Fee(),D(1))
def seed(s='a',M=1):
 r=orig_seed(s,M=M);r.update(signal_day='2024-09-03',plan_day='2024-09-03',capacity=100000);return r
def add(x,s='old',q=100000):
 a=attempt(s,q);x.active[s]=a;x.archive[a['id']]=a;x.orders.append(dict(side='BUY_SEED',round_id=a['id'],lot_id=s+'|original',qty=q,order_seq=1));return a
def prepare(x,rs):x.plan_transfers(dt,rs);return rs
def selected_orders(x):return [o for o in x.orders if o.get('day')=='2024-09-04' and o['side']=='BUY_SEED']
checks=[]
def test(name,fn):
 try:detail=fn();checks.append(dict(name=name,status='PASS',detail=detail))
 except Exception as ex:checks.append(dict(name=name,status='FAIL',error=repr(ex),traceback=traceback.format_exc(limit=3)))
def filled(price=10):
 x=m.Engine(Stub());r=seed();prepare(x,[r]);assert r['econ_q']==800;x.d.prices['a']=D(str(price));x.alloc_open(nxt,[r]);oo=selected_orders(x);assert len(oo)==1 and oo[0]['qty']==800;return x,r,oo[0]
def basic_fill():
 x,r,o=filled();e=x.events[r['event_id']];assert e['priority_attempted'] and e['spent']==-D(o['cash_delta']);assert e['capital_cap']==D(24000);return dict(q=o['qty'],spent=str(e['spent']))
test('actual_fill_debits_all_in_and_consumes_priority',basic_fill)
def low():
 x,r,o=filled(7.5);diag=x.seed_execution_cost[-1];assert D(diag['excess'])>0 and diag['not_an_OPEN_gate'];return diag
test('low_OPEN_same_frozen_q_not_rejected_by_fee_ratio',low)
test('high_OPEN_same_q_not_capped_by_CLOSE_cost',lambda:filled(11)[2]['all_in_cost'])
def cashreject():
 x=m.Engine(Stub());x.cash=D(200000);add(x);x.d.M['old']=-1;r=seed();prepare(x,[r]);assert r['_ref_q']==800 and not x.transfer_plan;x.d.prices['old']=D(30);x.alloc_open(nxt,[r]);e=x.events[r['event_id']];assert not selected_orders(x) and e['priority_attempted'] and e['spent']==0;assert x.candidates[-1]['violated_caps']==['cash_reserve'];return x.candidates[-1]
test('actual_cash_reject_consumes_priority_without_spend',cashreject)
def clip():
 x=m.Engine(Stub());r=seed();prepare(x,[r]);r['capacity']=700;x.alloc_open(nxt,[r]);assert not selected_orders(x);assert x.events[r['event_id']]['spent']==0
test('below_frozen_econ_capacity_cancels_whole_seed',clip)
def eventcap():
 x=m.Engine(Stub());r=seed();prepare(x,[r]);e=x.events[r['event_id']];e['spent']=D(20000);x.alloc_open(nxt,[r]);assert not selected_orders(x) and e['spent']==20000 and e['priority_attempted'];assert 'event_cap' in x.candidates[-1]['violated_caps']
test('actual_event_remaining_cap_not_CLOSE_price_cap',eventcap)
def cohort():
 x=m.Engine(Stub());x.d.sid_sector['b']='A';x.d.sector_ids.remove('B');rs=[seed('a'),seed('b')];prepare(x,rs);x.alloc_open(nxt,rs);assert len(selected_orders(x))==2 and len({o['event_id'] for o in selected_orders(x)})==1;return len(selected_orders(x))
test('same_priority_batch_multiple_representatives_stay_EVENT',cohort)
def emptyj():
 x=m.Engine(Stub());x.d.M={s:0 for s in x.d.ids};r=seed(M=0);prepare(x,[r]);assert not x.reference['E'] and r['_ref_q']==800;x.alloc_open(nxt,[r]);assert selected_orders(x)
test('empty_J_event_seed_can_execute',emptyj)
def deduction():
 x=m.Engine(Stub());r=seed();prepare(x,[r]);a=x.reference;assert a['budget']==a['budget_before_event']-a['event_reserve'];assert a['event_reserve']==r['_reference_close_cost'];assert abs(sum(a['T_residual'][s] for s in a['E'])-a['budget'])<D('1e-16');return str(a['event_reserve'])
test('actual_reservation_deducted_before_lambda',deduction)
def unknowncold():
 x=m.Engine(Stub());f=x.d.sectors['A'];f['state']=1;f.iloc[0,f.columns.get_loc('state')]=0;f.iloc[3,f.columns.get_loc('state')]=-1;x.sync_events(dt);assert 'A' not in x.current_event,'UNKNOWN_CHAIN_CREATED_COLD_EVENT'
test('cold_start_UNKNOWN_chain_not_invented',unknowncold)
def coldB():
 x=m.Engine(Stub());f=x.d.sectors['A'];f['state']=1;f.iloc[0,f.columns.get_loc('state')]=0;r=seed();r['birth_type']='B';prepare(x,[r]);e=x.events[r['event_id']];assert e['cold_start'] and e['birth_NAV']==m.INITIAL and e['birth_day']<'2024-09-03' and r['birth_type']=='B'
test('cold_start_old_birth_and_TRUE_B_identity',coldB)
def id_keep():
 x=m.Engine(Stub());x.sync_events(dt);r=seed();r['event_id']='A|2024-08-01';x.prepare_requests(dt,[r]);assert r['event_id']=='A|2024-08-01','OLD_EVENT_ID_OVERWRITTEN'
test('existing_request_event_id_not_reassigned',id_keep)
def quote_unknown():
 x=m.Engine(Stub());r=seed();prepare(x,[r]);original=x.d.z;x.d.z=lambda s,d:dict(original(s,d),raw_open=float('nan'));x.begin_open(nxt,[r]);assert not x.events[r['event_id']]['priority_attempted']
test('unobservable_OPEN_does_not_consume_priority',quote_unknown)
def oldpriority():
 x=m.Engine(Stub());r=seed();prepare(x,[r]);eid=r['event_id'];x.events[eid]['priority_attempted']=True;r2=seed('b');r2['sid']='a';x.prepare_requests(dt,[r2]);assert r2['allocation_phase']=='MATURE' and not r2['_priority_candidate']
test('used_priority_old_ticket_cannot_reenter_EVENT',oldpriority)
def multicaps():
 x=m.Engine(Stub());r=seed();r['budget']=D(500);prepare(x,[r]);x.alloc_open(nxt,[r]);assert not x.live_tickets() and 'attempt_budget' in x.candidates[-1]['violated_caps']
test('event_plus_attempt_failure_not_retainable',multicaps)
def ref0():
 x=m.Engine(Stub());r=seed();prepare(x,[r]);r['_ref_q']=0;x.alloc_open(nxt,[r]);assert x.events[r['event_id']]['priority_attempted'] and not selected_orders(x) and x.tickets['a']['status']=='RETAINED'
test('zero_reference_real_attempt_consumes_priority_retains_identity',ref0)
def noexpand():
 x,r,o=filled(20);assert o['qty']==800
# 20*800 stays below original2% and event2%, q remains frozen.
test('high_OPEN_under_true_caps_no_quantity_increase',noexpand)
def rollback():
 class Fail(m.Engine):
  def economic_preflight(self,*a):pass
  def accrue(self,*a):pass
  def exit_open(self,*a):pass
  def alloc_open(self,*a):
   self.cash-=D(99);self.events['bad']={'spent':D(99)};self.current_event['bad']='bad';self._event_open_reserved['bad']=D(99);self._execution_requests['bad']={};self._donor_sectors.add('bad');self._probe_receiver_sectors.add('bad');self.event_log.append({});self.event_plans.append({});self.seed_floor_risk.append({});self.seed_execution_cost.append({})
  def close(self,*a):raise m.Blocked('INDEPENDENT_FORCED_M4_ATOMIC_FAILURE')
  def scan_restored_targets(self,*a):return []
 x=Fail(Stub()).run(False);assert x.cash==m.INITIAL;assert all(not getattr(x,k) for k in ['events','current_event','_event_open_reserved','_execution_requests','_donor_sectors','_probe_receiver_sectors','event_log','event_plans','seed_floor_risk','seed_execution_cost'])
test('real_run_loop_restores_all_new_state_and_logs',rollback)
def core_shortage():
 x=m.Engine(Stub());x.cash=D(1000);a=add(x,q=200000);a['confirmed_history']=True;r=seed();prepare(x,[r]);assert x.reference['budget_before_event']<sum(x.reference['lower'].values());assert r['_ref_q']==0 and not x.transfer_plan;row=next(z for z in x.reference['rows'] if z['sid']=='old');assert row['core_qty']==200000 and row['mobile_qty']==0;x.alloc_open(nxt,[r]);assert not selected_orders(x)
test('insufficient_core_budget_never_forces_core_sale',core_shortage)
def bigcore():
 x=m.Engine(Stub());a=add(x,q=800);a['confirmed_history']=True;a['lots'].append(dict(id='large_add',kind='ADD',q=2000,bought='2024-09-02',floor=D(5)));x.orders.append(dict(side='BUY_ADD',round_id=a['id'],lot_id='large_add',qty=2000,order_seq=2));ref=x.classify_reference(dt);rows=[r for r in ref['rows'] if r['sid']=='old'];assert sum(r['core_qty'] for r in rows)==1600;assert next(r for r in rows if r['lot_id']=='large_add')['mobile_qty']==1200
test('larger_economic_seed_core_equivalent_exact_not_entire_ADD',bigcore)
def known_role():
 x=m.Engine(Stub());a=add(x,q=1000);a['confirmed_history']=True;x.d.M['old']=0;ref=x.classify_reference(dt);assert next(r for r in ref['rows'] if r['sid']=='old')['mobile_qty']==1000;x.d.M['old']=-1;ref=x.classify_reference(dt);assert next(r for r in ref['rows'] if r['sid']=='old')['mobile_qty']==0
test('confirmed_nonM_seed_current_role_mobile_but_UNKNOWN_frozen',known_role)
def t1():
 x=m.Engine(Stub());a=add(x,q=1000);a['lots'][0]['bought']='2024-09-04';x.d.M['old']=0;ref=x.classify_reference(dt);assert next(r for r in ref['rows'] if r['sid']=='old')['mobile_qty']==0
test('actual_T1_lot_excluded_from_new_mobile_role',t1)
def receivable():
 x=m.Engine(Stub());x.cash=D(1000);x.receivable=D(1000000);a=add(x,q=120000);x.d.M['old']=0;r=seed();prepare(x,[r]);ref=x.reference;assert ref['budget_before_event']==ref['NAV']-ref['reserve']-x.receivable-ref['outside_fixed']-ref['stress'];tr=x.transfers[-1];assert D(tr['initial_gap'])==D(tr['M_desired_cost'])+ref['reserve']-x.cash;assert x.transfer_plan and x.cash==1000
test('receivable_not_donor_cash_or_reference_budget',receivable)
def donor_bound():
 x=m.Engine(Stub());x.cash=D(1000);a=add(x,q=100000);a['lots'][0]['kind']='ADD';a['confirmed_history']=True;x.d.M['old']=0;x.d.W['old']=True;r=seed();prepare(x,[r]);frozen=copy.deepcopy(x.transfer_plan);assert frozen;x.d.prices['a']=D(12);x.alloc_open(nxt,[r]);sales=[o for o in x.orders if o.get('transfer_rank')];assert sales and all(o['qty']<=next(t['max_q'] for t in frozen if t['lot_id'] in o['lots']) for o in sales);assert not selected_orders(x),'UP_GAP_MUST_NOT_EXPAND_DONOR';return dict(maxq=[t['max_q'] for t in frozen],sold=[o['qty'] for o in sales],buy_reason=x.candidates[-1]['decision'])
test('higher_OPEN_cannot_expand_CLOSE_donor_qty_to_fund_seed',donor_bound)
def current_role_exit():
 class Close(m.Engine):
  def plan_transfers(self,*a):pass
  def attribute(self,*a):pass
 x=Close(Stub());a=add(x,q=1000);a['confirmed_history']=True;a['add_count']=2;x.d.M['old']=0;x.d.sectors['OLD'].at[dt,'state']=0;x.close(dt,x.d.cal[x.d.cal.get_loc(dt)-1]);assert a['exit']=='CURRENT_SEED_TRIAL_SECTOR_FALSE'
test('historically_confirmed_now_seed_only_known_FALSE_exit',current_role_exit)
def unknown_event_no_mature():
 x=m.Engine(Stub());x.d.sectors['A']['state']=1;r=seed();prepare(x,[r]);assert 'A' not in x.current_event and r['allocation_phase']=='PAUSED' and r['_ref_q']==0;x.alloc_open(nxt,[r]);assert not selected_orders(x)
test('unknown_event_cannot_enter_via_MATURE_seed',unknown_event_no_mature)
def zeroE_no_event():
 x=m.Engine(Stub());x.d.Es['a']=0;r=seed();r['E']=D(0);prepare(x,[r]);assert r['allocation_phase']=='PAUSED' and not r['_priority_candidate'];x.alloc_open(nxt,[r]);assert not selected_orders(x) and not x.events[r['event_id']]['priority_attempted']
test('M_TRUE_E_zero_cannot_enter_via_EVENT',zeroE_no_event)
report=dict(status='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL',engine_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),actual_method_tests=len(checks),passed=sum(x['status']=='PASS' for x in checks),failed=sum(x['status']=='FAIL' for x in checks),tests=checks,historical_runs=0,limitations='Fabricated bounded market inputs. Actual Engine methods called, not a historical run or full suite substitute.')
(O/'ACTUAL_METHOD_QA.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
