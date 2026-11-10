"""Actual M4 call-level tests. No M4 historical outcomes used."""
import engine as e
from types import SimpleNamespace
import copy,json
D=e.D;Z=e.ZERO;pd=e.pd
src=(e.V3/'synthetic_reference.py').read_text().replace('import engine as e','e=frozen');ns={'frozen':e.m3};exec(compile(src,'inherited62','exec'),ns)
Base=ns['Stub'];attempt=ns['attempt'];seed0=ns['seed'];cp=ns['cp'];plan=ns['plan'];add=ns['add'];dt=ns['day'];nxt=ns['nxt'];prev=pd.Timestamp('2024-09-02')
class Fee:
 components=[SimpleNamespace(name='net_brokerage',side='both')]
 def incremental(self,side,value,*a,**kw):return {'net_brokerage':max(D(5),value*D('.0002'))}
 def rate_accrual(self,side,value,*a,**kw):return {'net_brokerage':value*D('.0002')}
class Stub(Base):
 def __init__(self):
  super().__init__();self.sectors={s:fr.copy() for s,fr in self.sectors.items()}
  for fr in self.sectors.values():fr.loc[prev,'state']=0
 def getmeta(self,*args):return (e.b.QuantityRule('x',100,100,100,True,1),Fee(),D(1))
 def fee(self,s,d,q,p,side):return max(D(5),q*p*D('.0002')) if q else Z
class TestEngine(e.Engine):
 def representative_score(self,s,d):return (D(1),2)
def seed(s,M=1,E=1):
 r=seed0(s,M,E);r.update(capacity=100000,signal_day=str(dt.date()),plan_day=str(dt.date()));return r
def setup(requests=None,cash=e.INITIAL):
 x=TestEngine(Stub());x.cash=cash
 if requests is not None:x.plan_transfers(dt,requests)
 return x

def run():
 prior=ns['run']();assert prior['total']==62;checks=[]
 def ok(name,cond=True):assert cond,name;checks.append(name)
 x=setup();q=x.economic_q('a',nxt,D(10),100000);ok('economic_quantity_exact_mainboard',q==800);ok('economic_predecessor_fails',x.surcharge('a',nxt,700,D(10))>D(7));ok('economic_q_passes',x.surcharge('a',nxt,q,D(10))<=D(8));ok('capacity_no_partial_econ',x.economic_q('a',nxt,D(10),700)==0)
 x.d.getmeta=lambda *args:(e.b.QuantityRule('star',200,1,1,True,1),Fee(),D(1));ok('star_exact_economic_unit',x.economic_q('a',nxt,D(10),10000)==715)
 r=seed('a');x=setup([r]);ev=x.events[r['event_id']];ok('event_identity_born_NAV_once',ev['birth_day']==str(dt.date()) and ev['capital_cap']==D(24000));ok('event_reservation_not_spend',ev['reserved']>0 and ev['spent']==0 and not ev['priority_attempted']);ok('actual_event_deducts_mature_budget',x.reference['budget']==x.reference['budget_before_event']-r['_reference_close_cost']);before=copy.deepcopy(ev);x.alloc_open(nxt,[r]);ok('actual_seed_full_economic_quantity',x.orders[0]['qty']==800);ok('attempt_and_spend_separate',ev['priority_attempted'] and ev['spent']==-D(x.orders[0]['cash_delta']));ok('OPEN_cost_DIAG_not_filter',x.seed_execution_cost[0]['not_an_OPEN_gate']);ok('risk_real_new_principal',x.seed_floor_risk[0]['new_principal_risk'])
 r=seed('a');x=setup([r]);add(x,'old',20000,'SEED',True);x.cash=D(1);ev=x.events[r['event_id']];x.alloc_open(nxt,[r]);ok('cash_reject_consumes_once_not_spent',ev['priority_attempted'] and ev['spent']==0 and not any(o.get('side')=='BUY_SEED' and o.get('sid')=='a' for o in x.orders));ok('cash_reject_keeps_original_ticket_identity',x.tickets['a']['event_id']==r['event_id'] and x.tickets['a']['nav0']==r['nav0'])
 r=seed('a');x=setup([r]);r['_ref_q']=0;ev=x.events[r['event_id']];x.alloc_open(nxt,[r]);ok('CLOSE_zero_capital_plan_still_attempts',ev['priority_attempted'] and ev['spent']==0 and x.candidates[-1]['executed_q']==0)
 r=seed('a');x=setup([r]);x.d.prices['a']=D('9.9');x.alloc_open(nxt,[r]);ok('lower_OPEN_no_new_economic_gate',x.orders[0]['qty']==r['econ_q'])
 r=seed('a');x=setup([r]);x.d.prices['a']=D(11);x.alloc_open(nxt,[r]);ok('higher_OPEN_full_qty_if_caps_allow',x.orders[0]['qty']==800 and -D(x.orders[0]['cash_delta'])>r['_reference_close_cost'])
 r=seed('a');x=setup([r]);x.events[r['event_id']]['spent']=D(16000);x.d.prices['a']=D(11);x.alloc_open(nxt,[r]);ok('actual_event_remaining_caps_high_OPEN',not x.orders and 'event_cap' in x.candidates[-1]['violated_caps']);ok('event_rejection_no_spend',x.events[r['event_id']]['spent']==16000)
 r=seed('a');x=setup([r]);r['capacity']=700;x.alloc_open(nxt,[r]);ok('OPEN_capacity_clip_below_econ_cancels',not x.orders and x.candidates[-1]['decision']=='DATED_LOT_OR_CAPACITY_CHANGED')
 r=seed('a',M=-1);x=setup();x.d.M['a']=-1;x.plan_transfers(dt,[r]);ev=x.events[r['event_id']];x.alloc_open(nxt,[r]);ok('M_UNKNOWN_does_not_consume_priority',not ev['priority_attempted'] and not x.orders and x.tickets['a']['status']=='PAUSED')
 r=seed('a');x=setup([r]);old=x.d.z;x.d.z=lambda s,d:dict(old(s,d),raw_open=float('nan'));x.begin_open(nxt,[r]);ok('unknown_quote_no_fake_attempt',not x.events[r['event_id']]['priority_attempted'])
 x=setup();x.d.sectors['A'].loc[:,'state']=1;x.d.sectors['A'].loc[pd.Timestamp('2024-08-30'),'state']=0;x.sync_events(dt);eid=x.current_event['A'];ok('cold_start_real_birth_initial_anchor',x.events[eid]['birth_day']=='2024-09-02' and x.events[eid]['budget_anchor']=='INITIAL_ACCOUNT_OPEN_ONCE');r=seed('a');r['birth_type']='B';x.prepare_requests(dt,[r]);ok('cold_B_not_fabricated_A',r['birth_type']=='B');x.events[eid]['priority_reserved_day']=None;x.sync_events(nxt);ok('unused_startup_not_late_priority',x.events[eid]['priority_expired'])
 x=setup();fr=x.d.sectors['A'];fr.loc[:,'state']=1;fr.loc[pd.Timestamp('2024-08-30'),'state']=0;fr.loc[prev,'state']=-1;x.sync_events(dt);ok('UNKNOWN_cold_chain_not_invented','A' not in x.current_event)
 x=setup();x.sync_events(dt);eid=x.current_event['A'];r=seed('a');r['event_id']='OLD_EVENT';x.prepare_requests(dt,[r]);ok('old_ticket_not_rebound',r['event_id']=='OLD_EVENT' and r['allocation_phase']=='PAUSED' and r['_event_identity_mismatch'])
 # No mature positive-E set must not block legitimate event probes.
 r=seed('a',M=0);x=setup();x.d.M={s:0 for s in x.d.ids};x.plan_transfers(dt,[r]);ok('empty_J_event_budget_allowed',not x.reference['E'] and r['_ref_q']==800 and x.reference['event_reserve']>0);x.alloc_open(nxt,[r]);ok('empty_J_event_fill',len(x.orders)==1)
 # Existing event priority is distinct from amount left and goes to ordinary queues.
 r=seed('a');x=setup();x.sync_events(dt);ev=x.events[x.current_event['A']];ev['priority_attempted']=True;x.prepare_requests(dt,[r]);ok('old_positive_M_uses_mature_path',r['allocation_phase']=='MATURE');r=seed('a',M=0);x.prepare_requests(dt,[r]);ok('old_nonM_residual_not_priority',r['allocation_phase']=='RESIDUAL')
 # Same event two frozen representatives keep EVENT after first flag changes.
 x=setup();x.d.sid_sector['b']='A';x.d.sector_ids=['A','OLD','X'];r1=seed('a');r2=seed('b');x.plan_transfers(dt,[r1,r2]);x.alloc_open(nxt,[r1,r2]);ok('same_batch_flag_does_not_change_second_phase',len(x.orders)==2 and all(o['allocation_phase']=='EVENT' for o in x.orders));ev=x.events[r1['event_id']];ok('same_batch_spent_exact_actual',ev['spent']==sum((-D(o['cash_delta']) for o in x.orders),Z));ok('event_never_more_than_cap',ev['spent']<=ev['capital_cap'])
 # Previously confirmed, now non-M seed can retire; UNKNOWN cannot; current winner core stays.
 x=setup();a=add(x,'old',800,'SEED',True);x.d.M['old']=0;ref=x.classify_reference(dt);row=next(r for r in ref['rows'] if r['sid']=='old');ok('current_nonM_seed_retirement_after_confirmation',row['mobile_qty']==800 and row['donor_reason']=='CURRENT_NON_MAINLINE_SEED_RETIREMENT');x.d.M['old']=-1;ref=x.classify_reference(dt);ok('UNKNOWN_seed_not_retired',ref['rows'][0]['mobile_qty']==0);x.d.M['old']=1;ref=x.classify_reference(dt);ok('current_M_profitable_seed_is_core',ref['rows'][0]['core_qty']==800 and ref['rows'][0]['mobile_qty']==0)
 # Receivable excluded and T1/exit protected.
 a['lots'][0]['bought']=str(nxt.date());x.d.M['old']=0;ref=x.classify_reference(dt);ok('T1_seed_frozen',ref['rows'][0]['mobile_qty']==0);a['lots'][0]['bought']=str(prev.date());a['exit']='I_INVALID';ref=x.classify_reference(dt);ok('locked_seed_not_donor',ref['rows'][0]['mobile_qty']==0);x.receivable=D(999);ref=x.classify_reference(dt);ok('receivable_not_budget_cash',ref['budget_before_event']==ref['NAV']-ref['reserve']-x.receivable-ref['outside_fixed']-ref['stress'])
 # Multi-cap rejection cannot use reference/event-only retention loophole.
 r=seed('a');r['budget']=D(500);x=setup([r]);x.alloc_open(nxt,[r]);ok('attempt_plus_reference_denial_not_retained','a' not in x.live_tickets() and 'attempt_budget' in x.candidates[-1]['violated_caps'])
 r=seed('a');x=setup();x.d.sectors['A'].loc[:,'state']=-1;x.d.sectors['A'].loc[dt,'state']=1;x.plan_transfers(dt,[r]);ok('UNKNOWN_birth_cannot_bypass_to_MATURE',r['event_id'] is None and r['allocation_phase']=='PAUSED' and r['_ref_q']==0)
 r=seed('a',M=1,E=0);x=setup();x.d.Es['a']=0;x.plan_transfers(dt,[r]);ok('M_TRUE_E_ZERO_not_EVENT_fallback',r['allocation_phase']=='PAUSED' and not r['_priority_candidate'])
 # Exact account rollback for event registry, stage map and logs.
 class Fail(TestEngine):
  def economic_preflight(self,*a):pass
  def accrue(self,*a):pass
  def exit_open(self,*a):pass
  def alloc_open(self,*args):self.events['bad']={'spent':99};self.current_event['x']='bad';self._event_open_reserved['bad']=D(99);self._execution_requests['bad']={};self._donor_sectors={'bad'};self._probe_receiver_sectors={'bad'};self.event_log.append({'bad':1});self.event_plans.append({'bad':1});self.seed_floor_risk.append({'bad':1});self.seed_execution_cost.append({'bad':1});self.cash-=99
  def close(self,*a):raise e.Blocked('FORCED_M4_STATE_ROLLBACK')
  def scan_restored_targets(self,*a):return []
 x=Fail(Stub()).run(False);ok('all_new_state_and_logs_atomic_rollback',x.cash==e.INITIAL and not any([x.events,x.current_event,x._event_open_reserved,x._execution_requests,x._donor_sectors,x._probe_receiver_sectors,x.event_log,x.event_plans,x.seed_floor_risk,x.seed_execution_cost]))
 return dict(result='PASS',inherited=prior,new_checks=checks,new_count=len(checks),total=prior['total']+len(checks),engine_sha256=e.sha(e.O/'engine.py'),contract_sha256=e.sha(e.O/'CONTRACT.md'))
if __name__=='__main__':
 out=run();e.save(e.O/'SYNTHETIC_QA.json',out);print(json.dumps(out,default=str))
