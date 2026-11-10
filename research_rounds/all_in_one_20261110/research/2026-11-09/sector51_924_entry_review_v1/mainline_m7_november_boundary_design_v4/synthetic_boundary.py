from pathlib import Path
import sys,importlib.util,json,types,copy,contextlib,io
P=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('v4tests',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
static=e.self_check();ok('unchanged_method_identity');ok('atomic_new_state_fields',"keys=['paused_new_requests','execution_boundary_log','cash'" in e.source)
r=next(x for x in e.read(e.BASE/'once_20260630/PENDING_AT_END.json') if x['sid']==e.SID)
for k in ['nav0','budget','ifloor','factor']:r[k]=e.D(r[k])
r['origin']=tuple(r['origin']);original=copy.deepcopy(r)
class Fixture:
 def __init__(self):
  self.cal=e.pd.DatetimeIndex(['2024-11-06','2024-11-07','2024-11-08','2024-11-11']);self.days=self.cal[1:2];self.ids=[e.SID,'other'];self.sid_sector={e.SID:'sec','other':'sec'};self.sector_ids=['sec'];self.sectors={'sec':e.pd.DataFrame({'state':[1]*4},index=self.cal)};self.stock=e.pd.DataFrame({e.SID:[1]*4},index=self.cal);self.cap={e.SID:{d:10000 for d in self.cal}};self.events={};self.i=1
  self.obs=dict(raw_open=4.87,raw_high=4.87,raw_low=4.87,raw_close=4.87,raw_volume=1000,adjustment_factor=float(r['factor']),close=4.87*float(r['factor']),observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False,source_kind=r['origin'][0],source_path=r['origin'][1],segment_id=r['origin'][2])
  self.raw={e.SID:e.pd.DataFrame([dict(self.obs,raw_close=5.13),self.obs],index=self.cal[[0,2]])}
 def z(self,s,d):return e.pd.Series({}) if e.day(d)=='2024-11-07' else e.pd.Series(self.obs)
 def f(self,s,d):return {'i_target':self.i,'i_floor':float(r['ifloor'])}
 def action(self,s,d):return []
 def getmeta(self,s,d):return (types.SimpleNamespace(buy_minimum=100,buy_step=100,buy_floor=lambda q:q),None,None)
 def fee(self,*args):return e.D(0)
 def size(self,s,d,p,budget,cap):return min(100,cap)
d=Fixture();x=e.Engine(d);p=[copy.deepcopy(r)];pre=e.b.Engine.economic_preflight
try:
 e.b.Engine.economic_preflight=lambda *args:None
 x.economic_preflight(d.cal[1],p);ok('halt_original_preserved_no_cash',not p and x.paused_new_requests[e.SID]['original']==original and x.cash==e.D(1200000) and not x.tickets)
 p=[copy.deepcopy(r)];x.economic_preflight(d.cal[2],p);ok('resume_open_never_replays_old_request',not p)
finally:e.b.Engine.economic_preflight=pre
x.decorate=lambda req,dt:req
plans=x.revalidate_paused_close(d.cal[2]);ok('real_close_revalidation_next_open_only',len(plans)==1 and plans[0]['plan_day']=='2024-11-08' and plans[0]['signal_day']=='2024-11-06' and plans[0]['nav0']==r['nav0'] and plans[0]['budget']==r['budget'] and plans[0]['ticket_id']==x.tickets[e.SID]['ticket_id'] and x.paused_new_requests[e.SID]['status']=='TRANSFERRED_TO_RETAINED')
ok('no_cash_spent_by_revalidation',x.cash==e.D(1200000) and not x.orders)
d.i=0;x=e.Engine(d);x.capture_request(d.cal[1],copy.deepcopy(r),'test');ok('explicit_false_uses_existing_cancel',not x.revalidate_paused_close(d.cal[2]) and x.paused_new_requests[e.SID]['status']=='CANCELLED')
# Unknown state preserves identity.
d=Fixture();d.i=None;x=e.Engine(d);x.capture_request(d.cal[1],copy.deepcopy(r),'test');x.decorate=lambda req,dt:req
ok('unknown_I_pauses_no_fake_eligibility',not x.revalidate_paused_close(d.cal[2]) and x.paused_new_requests[e.SID]['status']=='PAUSED')
d.i=1;d.obs['adjustment_factor']*=1.1
try:x.revalidate_paused_close(d.cal[2])
except e.Blocked:ok('factor_discontinuity_stops')
else:raise AssertionError('factor fabricated')
# Known false takes priority even without a halt-day quote; unknown waits.
d=Fixture();d.i=0;x=e.Engine(d);x.capture_request(d.cal[1],copy.deepcopy(r),'test');ok('halt_known_false_cancels_without_quote',not x.revalidate_paused_close(d.cal[1]) and x.paused_new_requests[e.SID]['status']=='CANCELLED')
d=Fixture();d.i=None;x=e.Engine(d);x.capture_request(d.cal[1],copy.deepcopy(r),'test');ok('halt_unknown_waits_preserving_identity',not x.revalidate_paused_close(d.cal[1]) and x.paused_new_requests[e.SID]['status']=='PAUSED')
# Exact dated official bounds and non-anticipation.
ok('2024_bounds',e.price_bounds('5.13')==(e.D('4.87'),e.D('5.39')))
ok('minimum_tick_bounds',e.price_bounds('.01')==(e.D('.01'),e.D('.02')))
for date,rate in [('2024-11-07','.10'),('2024-11-08','.05'),('2025-11-08','.05'),('2025-11-11','.05'),('2025-11-12','.10'),('2026-06-30','.10')]:ok('dated_rate_'+date,e.security_rate(e.pd.Timestamp(date))==e.D(rate))
d=Fixture();x=e.Engine(d);ok('limitdown_sell_barred',x.no_fill(e.SID,d.cal[2],'sell'));ok('limitdown_buy_not_claimed_impossible',not x.no_fill(e.SID,d.cal[2],'buy'))
for k in ['raw_open','raw_high','raw_low','raw_close']:d.obs[k]=5.39
ok('limitup_buy_barred',x.no_fill(e.SID,d.cal[2],'buy'));ok('limitup_sell_conditional',not x.no_fill(e.SID,d.cal[2],'sell'))
# Atomic rollback actual loop with mutation.
class Fail(e.Engine):
 def economic_preflight(self,dt,p):self.paused_new_requests['test']={};self.execution_boundary_log.append({'test':1});self.cash-=e.D(10);raise e.Blocked('SYNTHETIC')
 def scan_restored_targets(self,*a):return []
y=Fail(Fixture())
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(y,False)
ok('rollback_cash_paused_and_log',y.cash==e.D(1200000) and not y.paused_new_requests and not y.execution_boundary_log and not y.ledger)
# Exercise actual patched reservation/commit function, not a helper imitation.
class Alloc(e.Engine):
 def begin_open(self,*a):pass
 def info_open(self,*a):pass
 def nav(self,*a):return e.D(100)
 def qvalue(self,*a):return e.D(0)
 def request_key_groups(self,rs):return rs
 def execute_transfers(self,*a):return e.D(0)
 def reserve_phase_cash(self,*a):pass
 def reference_cap(self,*a):return e.D(1000)
 def event_cap(self,*a):return e.D(1000)
 def no_fill(self,s,d,side):return s==e.SID and side=='buy'
 def noncash(self,r,*a):return dict(q=100,p=e.D(1),caps=dict(attempt_budget=e.D(1000)),reason='PASS',net=e.D(5),structural=True)
 def order(self,*a,**kw):raise AssertionError('barred buy executed')
def req(s):
 a=copy.deepcopy(r);a.update(sid=s,planned_q=100,capacity=1000,econ_q=100,plan_day='2024-11-08',M=0,E=1,M_streak=0,event_id='e',allocation_phase='EVENT');return a
z=Alloc(Fixture());z.cash=e.D(150);z.alloc_open(e.pd.Timestamp('2024-11-11'),[req(e.SID),req('other')]);ok('failed_buy_no_real_debit',z.cash==e.D(150) and not z.orders);ok('failed_buy_reservation_not_reassigned',len(z.request_details)==2 and z.request_details[1]['decision'].startswith('MIN_LOT_CAPITAL_REJECT') and z.request_details[1]['executed_q']==0);ok('failed_seed_preserves_original_NAV',z.paused_new_requests[e.SID]['original']['nav0']==r['nav0'])
z=Alloc(Fixture());z.cash=e.D(1000);a=req(e.SID);a['kind']='ADD';a['cp_id']='cp';a['close_net']='5';cp=dict(id='cp',consumed=False);z.active[e.SID]=dict(sid=e.SID,id='active',plan=a,cp=cp,lots=[],exit=None);z.alloc_open(e.pd.Timestamp('2024-11-11'),[]);ok('failed_ADD_no_CP_consumption',z.active[e.SID]['cp'] is cp and cp['consumed']==False and z.cash==e.D(1000) and not z.orders)
# Canonical ownership routes structural OPEN rejection through original cancellation.
d=Fixture();x=e.Engine(d);x.capture_request(d.cal[1],copy.deepcopy(r),'test');x.decorate=lambda a,b:a;planned=x.revalidate_paused_close(d.cal[2]);t=x.tickets[e.SID]
e.m4.rules.retry_open_outcome(t,filled=False,structural_pass=False,all_in_cost=e.D(100),caps={'cash_reserve':e.D(1000)})
ok('canonical_OPEN_failure_cancels_no_revival',t['status']=='CANCELLED' and not x.revalidate_paused_close(d.cal[2]))
ok('canonical_transfer_does_not_suppress_future_births',"['CANCELLED','CONSUMED','TRANSFERRED_TO_RETAINED']" in Path(P/'engine.py').read_text())
newborn=copy.deepcopy(r);newborn['signal_day']='2024-11-11';newborn['plan_day']='2024-11-11';x.capture_request(e.pd.Timestamp('2024-11-12'),newborn,'new_birth_limit_nofill');ok('fresh_birth_after_canonical_cancel_keeps_new_identity',x.paused_new_requests[e.SID]['original']['signal_day']=='2024-11-11')
# Actual patched protective SELL keeps the full lot and cash on lower limit.
class Sell(e.Engine):
 def invalidate_cp(self,*a):pass
 def no_fill(self,s,d,side):return s==e.SID and side=='sell'
 def order(self,*a,**k):raise AssertionError('barred sell executed')
x=Sell(Fixture());lot=dict(id='lot',q=100,kind='SEED',bought='2024-11-06',exit=None);x.active[e.SID]=dict(sid=e.SID,id='r',factor=e.D(1),ifloor=e.D(10),exit='I_INVALID',lots=[lot],plan={'kind':'ADD'})
x.exit_open(e.pd.Timestamp('2024-11-08'));ok('protective_sell_no_cash_and_locked_lot',x.cash==e.D(1200000) and x.active[e.SID]['lots']==[lot] and lot['exit']=='ST_LIMIT_UNFILLED_LOCKED_EXIT' and not x.orders)
# Real donor hook, rather than simulated accounting.
class Donor(Sell):
 def demand(self,*a):return e.D(100),[]
 def sector_values(self,sv):return {'sec':sum(sv.values(),e.D(0))}
x=Donor(Fixture());x.cash=e.D(0);lot=dict(id='lot',q=100,kind='SEED',capital_role='INITIAL',bought='2024-11-06',exit=None);x.active[e.SID]=dict(sid=e.SID,id='r',factor=e.D(1),ifloor=e.D(1),exit=None,lots=[lot],plan=None);x.reference={'frozen_lot_qty':{}};x.d.getmeta=lambda s,d:(types.SimpleNamespace(sell_floor=lambda q,h:q),None,None)
x.transfer_plan=[dict(sid=e.SID,sector51='sec',lot_id='lot',close_sector_floor='0',max_q=100,frozen_lot_qty=0,reason='NON_MAINLINE_EXPANSION',signal_day='2024-11-06',rank=1)]
proceeds=x.execute_transfers(e.pd.Timestamp('2024-11-08'),[],e.D(100),{e.SID:e.D(487)})
ok('donor_nofill_no_proceeds_no_qty_loss',proceeds==0 and x.cash==0 and lot['q']==100 and not x.orders and x.transfers[0]['executed_q']==0)
# Mixed actual failed donor and competing BUY cannot invent financing.
class Mixed(Alloc):
 execute_transfers=e.Engine.execute_transfers
 def demand(self,*a):return e.D(100),[]
 def sector_values(self,sv):return {'sec':sum(sv.values(),e.D(0))}
 def qvalue(self,a,*args):return e.D(487) if a['sid']==e.SID else e.D(0)
 def no_fill(self,s,d,side):return s==e.SID
z=Mixed(Fixture());z.cash=e.D(0);lot=dict(id='lot',q=100,kind='SEED',capital_role='INITIAL',bought='2024-11-06',exit=None);z.active[e.SID]=dict(sid=e.SID,id='donor',factor=e.D(1),ifloor=e.D(1),exit=None,lots=[lot],plan=None);z.reference={'frozen_lot_qty':{}};z.d.getmeta=lambda s,d:(types.SimpleNamespace(sell_floor=lambda q,h:q,buy_minimum=100,buy_floor=lambda q:q),None,None);z.transfer_plan=[dict(sid=e.SID,sector51='sec',lot_id='lot',close_sector_floor='0',max_q=100,frozen_lot_qty=0,reason='NON_MAINLINE_EXPANSION',signal_day='2024-11-06',rank=1)]
z.alloc_open(e.pd.Timestamp('2024-11-08'),[req('other')]);ok('mixed_failed_donor_cannot_fund_other_buy',z.cash==0 and lot['q']==100 and not z.orders and z.request_details[0]['executed_q']==0 and any(row.get('event')=='DONOR_EXECUTION' and row['decision']=='ST_LIMIT_DONOR_NO_FILL' for row in z.transfers))
# A later announced halt cannot accidentally use removal-era10% one day early.
d=Fixture();d.raw[e.SID]=e.pd.DataFrame([dict(d.obs,raw_close=5.13)],index=e.pd.DatetimeIndex(['2025-11-10']));x=e.Engine(d)
try:x.no_fill(e.SID,e.pd.Timestamp('2025-11-11'),'buy')
except e.Blocked:ok('2025_official_halt_fails_closed')
else:raise AssertionError('halt simulated fill')
# Actual source cash bridge and zero registered holding entitlement.
ev=e.read(P/'CASH_EVENT.json');s=ev['sid'];raw=e.pd.read_parquet(ev['signal_path'])
if not isinstance(raw.index,e.pd.DatetimeIndex):raw=raw.set_index('date' if 'date' in raw else 'trade_date')
data=types.SimpleNamespace(end=e.pd.Timestamp('2026-06-30'),actions={s:e.read(Path(ev['local_action_path']))},raw={s:raw},events={},admission=[],sid_sector={s:'医疗器械'})
def checked(p,h):assert e.sha(Path(p))==h
e.admit_cash(data,ev,checked,{(s,ev['ex_date'],ev['economic_event_id_candidate'])});ok('actual_cash_bridge',len(data.events)==1)
x=e.Engine(data);x.register_pay(e.pd.Timestamp(ev['record_date']));x.accrue(e.pd.Timestamp(ev['ex_date']));x.register_pay(e.pd.Timestamp(ev['pay_date']));ok('zero_record_no_dividend',x.cash==e.D(1200000) and x.receivable==0)
qa=dict(result='PASS',total=len(checks),checks=checks,history_run=False,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'));e.save(P/'STATIC_QA.json',static);e.save(P/'SYNTHETIC_QA.json',qa);print(json.dumps(qa))
