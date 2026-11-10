"""Actual account-method synthetic integration tests, not historical returns."""
from pathlib import Path
from decimal import Decimal as D
import copy,sys,json,hashlib
sys.dont_write_bytecode=True
from ablation_engine import *
import synthetic_allocation as policy
joint=policy.joint
checks=[]
def ck(name,condition):
 assert condition,name
 checks.append(name)
def attempt(s='a',q=100):return joint.attempt(s,q)
def seed(s='a'):return joint.seed(s)
def plan(s='a'):
 r=joint.plan(s);r['planned_q']=2400;r['capacity']=2400;return r
class Scenario(joint.Stub):
 def __init__(self):
  self.names={'a':'a','b':'b','old':'old'};self.sid_sector={'a':'A','b':'B','old':'OLD'};self.sector_ids=['A','B','OLD'];self.ids=['a','b','old'];self.events={};self.hashes={};self.excluded=[];self.admission=[]
  self.cal=pd.DatetimeIndex(['2024-09-02','2024-09-03','2024-09-04','2024-09-05']);self.days=self.cal[1:]
  self.stock=pd.DataFrame(1,index=self.cal,columns=self.ids);self.cap={s:pd.Series(10000,index=self.cal) for s in self.ids}
  self.sectors={g:pd.DataFrame(dict(N=3,K=3,n=3,U=0,paired_K=3,entered3=1,left3=0,diff=1,state=1,strength=True),index=self.cal) for g in self.sector_ids}
  self.factors={};self.actions_by={};self.missing=set();self.origins={}
 def z(self,s,d):
  if (s,day(d)) in self.missing:return {}
  o=self.origins.get((s,day(d)),('s','p','0'))
  return dict(raw_open=10,raw_close=10,adjustment_factor=self.factors.get((s,day(d)),1),source_kind=o[0],source_path=o[1],segment_id=o[2],observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
 def f(self,s,d):return dict(i_target=True,i_floor=5)
 def c(self,s,d):return dict(receipt=False,candidate=None)
 def action(self,s,d):return self.actions_by.get((s,day(d)),[])
 def getmeta(self,*args):return (base.QuantityRule('x',100,100,100,True,1),None,None)

def run():
 pure=policy.run();dt=pd.Timestamp('2024-09-03');prev=pd.Timestamp('2024-09-02')
 # A shared real allocator must retain every original row, including tie labels.
 stub=Scenario();old=attempt('old',11900);stub.sid_sector['old']='A'
 a0=base.Engine(stub);a1=AblationEngine(stub,'A')
 for e in (a0,a1):e.active['old']=copy.deepcopy(old);e.archive[e.active['old']['id']]=e.active['old'];e.cash=D(1081000);e.alloc_open(dt,[seed('b'),seed('a')])
 ck('A_actual_allocator_stub_rows_exact',a0.orders==a1.orders and a0.candidates==a1.candidates and a0.cash==a1.cash)
 kw=dict(budget=D(0),nav=D(1200000),stock_value=D(120000),sector_value=D(120000),cash=D(120000))
 caps=buy_capital_limits(arm_config('A'),**kw)
 ck('A_original_min_tie_order_preserved',list(caps)==['attempt_budget','stock_cap','sector_cap','cash_reserve'])
 # B uses actual close and actual OPEN paths, not a detached sizing helper.
 e=AblationEngine(Scenario(),'B');a=attempt();a['cp']=joint.cp();e.active['a']=a;e.archive[a['id']]=a
 e.close(dt,prev);ck('B_actual_CLOSE_plan_limited_to_held',a['plan']['planned_q']==100)
 e.alloc_open(pd.Timestamp('2024-09-04'),[])
 ck('B_actual_OPEN_fill_limited_and_CP_consumed',e.orders[-1]['side']=='BUY_ADD' and e.orders[-1]['qty']==100 and a['add_count']==1 and a['cp'] is None)
 e=AblationEngine(Scenario(),'B');a=attempt();a['cp']=joint.cp();a['plan']=plan();e.active['a']=a;e.archive[a['id']]=a;e.alloc_open(dt,[])
 ck('B_OPEN_independently_rechecks_oversized_plan',e.orders[-1]['qty']==100)
 # F can fill an otherwise purely sector-capped seed, while A cannot.
 outcomes={}
 for name in ('A','F'):
  stub=Scenario();stub.sid_sector['old']='A';e=AblationEngine(stub,name);a=attempt('old',11900);e.active['old']=a;e.archive[a['id']]=a;e.cash=D(1081000);e.alloc_open(dt,[seed('a')]);outcomes[name]=e
 ck('F_actual_fill_only_after_sector_cap_removed',not outcomes['A'].orders and outcomes['F'].orders[-1]['side']=='BUY_SEED')
 ck('F_actual_other_caps_retained',set(outcomes['F'].cap_violations[-1])>= {'attempt_budget','stock_cap','cash_reserve'} and 'sector_cap' not in outcomes['F'].cap_violations[-1])
 # E source state passes through the real CLOSE + T+1 OPEN mechanics.
 stub=Scenario();stub.stock.at[dt,'a']=0;e=AblationEngine(stub,'E');a=attempt();e.active['a']=a;e.archive[a['id']]=a;e.close(dt,prev)
 ck('E_actual_CLOSE_new_exit_logged',a['exit']=='UNCONFIRMED_STOCK_M3_FALSE' and e.extra_exits[-1]['incremental_exit'] and e.holdings[-1]['locked_exit']==a['exit'])
 e.exit_open(pd.Timestamp('2024-09-04'));ck('E_actual_next_OPEN_fee_and_cash',not e.active and e.orders[-1]['reason']=='UNCONFIRMED_STOCK_M3_FALSE' and D(e.orders[-1]['cash_delta'])==D('994.5000'))
 # First capital refusal on an admitted ex-date. Original ticket factor stays 1,
 # retained current factor becomes actual ex-OPEN 2; next day is not rebridged.
 stub=Scenario();ex=dt;stub.events[('a',ex)]=dict(record_date='2024-09-02',ex_date='2024-09-03',pay_date='2024-09-04',d_cash='1',factor_old='1',factor_new='2',economic_event_id_candidate='test-ex')
 for date in ('2024-09-03','2024-09-04','2024-09-05'):stub.factors[('a',date)]=2
 stub.actions_by[('a','2024-09-03')]=[dict(effective_date='2024-09-03')]
 e=AblationEngine(stub,'D');a=attempt('old',107910);e.active['old']=a;e.archive[a['id']]=a;e.cash=D(120900);r=seed('a')
 e.economic_preflight(dt,[r]);e.accrue(dt);e.alloc_open(dt,[r]);t=e.retained['a']
 ck('D_first_exday_capital_reject_updates_current_not_original_factor',t['original_factor']==1 and t['current_factor']==2 and t['status']=='RETAINED')
 ck('D_pending_exday_zero_dividend',e.receivable==0 and not e.claims)
 pending=e.close(dt,prev);ck('D_original_signal_and_nav_survive_real_CLOSE',next(r for r in pending if r['sid']=='a')['signal_day']=='2024-09-02' and t['nav0']==INITIAL)
 e.economic_preflight(pd.Timestamp('2024-09-04'),pending)
 ck('D_next_day_no_duplicate_factor_bridge',t['current_factor']==2 and sum(x['event']=='FACTOR_BRIDGE' for x in e.equity)==1)
 # With newly available cash the same ticket fills once at original NAV.
 e.cash+=D(5000);e.alloc_open(pd.Timestamp('2024-09-04'),pending)
 ck('D_actual_retry_fill_consumes_once_and_preserves_nav0','a' not in e.retained and e.active['a']['nav0']==INITIAL and e.active['a']['signal_day']=='2024-09-02' and sum(x['event']=='ACTUAL_SEED_CONSUMED_ONCE' for x in e.retry_log)==1)
 # Paused retained tickets remain fact responsibilities. Missing row blocks.
 stub=Scenario();e=AblationEngine(stub,'D');t=policy.ticket();t['sid']='a';t['origin']=('s','p','0');t['status']='PAUSED';e.retained['a']=t;stub.missing.add(('a','2024-09-03'))
 ck('D_paused_ticket_missing_OPEN_is_hard_block',policy.raises(Blocked,lambda:e.economic_preflight(dt,[])))
 # Known source changes cancel retained tickets and remove executable request.
 stub=Scenario();e=AblationEngine(stub,'D');t=policy.ticket();t['sid']='a';t['origin']=('s','p','0');e.retained['a']=t;stub.origins[('a','2024-09-03')]=('changed','p','0');r=seed('a');r['ticket_id']=t['ticket_id'];pending=[r];e.economic_preflight(dt,pending)
 ck('D_source_cancel_removes_current_OPEN_request',not pending and not e.retained)
 # All actual capital failures inspected: stock cap failure cannot sneak in.
 stub=Scenario();e=AblationEngine(stub,'D');e.cash=D(100);e.alloc_open(dt,[seed('a')]);ck('D_actual_combined_stock_cash_reject_not_retained',not e.retained and 'stock_cap' in e.cap_violations[-1]['all_violated_caps'])
 # Atomic rollback restores new retry state and all extra log lengths.
 class Rollback(AblationEngine):
  def alloc_open(self,d,pending):return super().alloc_open(d,[seed('a')])
  def close(self,d,prev):raise Blocked('SYNTHETIC_AFTER_RETRY_CREATION')
  def export_ablation(self,path):pass
 stub=Scenario();stub.days=stub.cal[1:2];e=Rollback(stub,'D');a=attempt('old',107910);e.active['old']=a;e.archive[a['id']]=a;e.cash=D(120900);e.run_ablation(Path('/not-used'))
 ck('D_atomic_rollback_restores_retry_queue_logs_cash',not e.retained and not e.retry_log and not e.cap_violations and e.cash==D(120900) and e.active['old'] is e.archive[a['id']])
 ck('C_stays_hard_disabled_in_real_engine',policy.raises(ValueError,lambda:AblationEngine(Scenario(),'C')))
 result=dict(result='PASS',integration_checks=checks,integration_checks_count=len(checks),policy_checks_count=pure['checks_count'],original_baseline_checks_count=pure['baseline_original_checks_count'],historical_account_runs=0,baseline='joint51_candidate_v9_facts',effective_arms=['A','B','D','E','F'],C='DISABLED')
 base.save(O/'SYNTHETIC_INTEGRATION_QA.json',result);print(json.dumps(result,ensure_ascii=False));return result
if __name__=='__main__':run()
