"""Adversarial integration tests for the explicit v3 semantics; no history."""
from pathlib import Path
import sys,copy,json
sys.dont_write_bytecode=True
from engine import *
import synthetic_integrated as oldtests
import synthetic_allocation as pure
Scenario0=oldtests.Scenario
checks=[]
def ck(name,cond):assert cond,name;checks.append(name)
def raises(cls,fn):
 try:fn()
 except cls:return True
 return False
class Scenario(Scenario0):
 def __init__(self):
  super().__init__();self.actions={s:{'events':[]} for s in self.ids};self.policies={};self.custom={};self.resume_known=False
 def z(self,s,d):return self.custom.get((s,day(d)),super().z(s,d))
 def suspension(self,s,d):return self.policies.get((s,day(d)))
 def resume_notice_available(self,s,d):return self.resume_known
 def action(self,s,d):return [e for e in self.actions[s]['events'] if e['effective_date']==day(d)]
def ticket():
 t=pure.ticket();t.update(sid='a',origin=('s','p','0'),last_verified_day='2024-09-02');return t
DT=pd.Timestamp('2024-09-03');NEXT=pd.Timestamp('2024-09-04');PREV=pd.Timestamp('2024-09-02')
def setup_pause():
 d=Scenario();d.missing.add(('a','2024-09-03'));e=Engine(d,'D');t=ticket();e.retained['a']=t;r=oldtests.seed('a');r['ticket_id']=t['ticket_id'];return d,e,t,[r]
def run():
 # Rerun the exact prior suite without writing its sealed report.
 saved=oldtests.base.save;captured={}
 oldtests.base.save=lambda p,v:captured.setdefault(str(p),v)
 try:old=oldtests.run()
 finally:oldtests.base.save=saved
 ck('all_prior_19_integrated_60_policy_16_base_pass',old['result']=='PASS' and old['integration_checks_count']==19)
 d,e,t,p=setup_pause();ident=pure.immutable_identity(t);e.economic_preflight(DT,p)
 ck('Q0_current_OPEN_missing_pauses_removes_old_request',t['status']=='PAUSED_NO_QUOTE' and p==[] and t['plan'] is None)
 ck('pause_preserves_identity_and_last_real_factor_day',pure.immutable_identity(t)==ident and t['last_verified_day']=='2024-09-02' and t['current_factor']==1)
 before=e.cash;e.alloc_open(DT,p);e.close(DT,PREV)
 ck('pause_no_cash_shares_dividend_or_close_plan',e.cash==before and not e.active and not e.orders and not t['plan'] and t['status']=='PAUSED_NO_QUOTE')
 d,e,t,p=setup_pause();z=Scenario0.z(d,'a',DT);z['raw_open']=None;z['raw_close']=999;d.custom[('a','2024-09-03')]=z;e.economic_preflight(DT,p);e.close(DT,PREV)
 ck('OPEN_pause_does_not_use_today_known_CLOSE',t['status']=='PAUSED_NO_QUOTE' and t['ifloor']==5 and not t['plan'])
 d,e,t,p=setup_pause();d.custom[('a','2024-09-03')]={'raw_open':10,'adjustment_factor':1,'source_kind':None,'source_path':'p','segment_id':'0'};e.economic_preflight(DT,p)
 ck('missing_identity_not_known_source_change',t['status']=='PAUSED_NO_QUOTE' and 'a' in e.retained)
 d,e,t,p=setup_pause();d.custom[('a','2024-09-03')]=dict(raw_open=10,adjustment_factor=1,source_kind='CHANGED',source_path='p',segment_id='0');e.economic_preflight(DT,p)
 ck('known_source_change_cancels_original_ticket',not e.retained and not p)
 d,e,t,p=setup_pause();e.economic_preflight(DT,p);d.stock.at[DT,'a']=0;e.close(DT,PREV)
 ck('known_M3_FALSE_cancels_while_no_quote',not e.retained and not e.quote_gaps)
 d,e,t,p=setup_pause();e.economic_preflight(DT,p);d.stock.at[DT,'a']=-1;e.close(DT,PREV)
 ck('UNKNOWN_remains_paused_no_I_ratcheting',t['status']=='PAUSED_NO_QUOTE' and t['ifloor']==5)
 # Reappearance cannot fill old pending; only new CLOSE can generate next OPEN.
 d,e,t,p=setup_pause();e.economic_preflight(DT,p);r=oldtests.seed('a');r['ticket_id']=t['ticket_id'];p=[r];e.economic_preflight(NEXT,p);e.alloc_open(NEXT,p)
 ck('resume_OPEN_reverified_without_old_fill',not p and not e.orders and not e.quote_gaps and t['last_verified_day']=='2024-09-04')
 p=e.close(NEXT,DT);ck('resume_new_CLOSE_can_plan_original_ticket',len([r for r in p if r['sid']=='a'])==1 and p[0]['signal_day']==t['signal_day'])
 e.economic_preflight(pd.Timestamp('2024-09-05'),p);e.alloc_open(pd.Timestamp('2024-09-05'),p)
 ck('earliest_real_fill_is_following_OPEN_once','a' in e.active and 'a' not in e.retained and len(e.orders)==1)
 d,e,t,p=setup_pause();d.actions['a']['events']=[dict(effective_date='2024-09-03')];e.economic_preflight(DT,p)
 ck('gap_unreviewed_action_kept_pending_not_fabricated',len(e.quote_gaps['a']['action_inventory'])==1 and t['current_factor']==1)
 ck('gap_unreviewed_action_blocks_on_reappearance',raises(Blocked,lambda:e.economic_preflight(NEXT,p)))
 d,e,t,p=setup_pause();d.actions['a']['events']=[dict(effective_date='2024-09-03')];d.events[('a',DT)]=dict(factor_old='1',factor_new='2',economic_event_id_candidate='synthetic',record_date='2024-09-02',ex_date='2024-09-03',pay_date='2024-09-03',d_cash='1');d.factors[('a','2024-09-04')]=2;e.economic_preflight(DT,p);e.economic_preflight(NEXT,p)
 ck('gap_reviewed_factor_chain_passes_no_entitlement',t['current_factor']==2 and e.receivable==0 and not e.orders)
 d,e,t,p=setup_pause();e.economic_preflight(DT,p);d.factors[('a','2024-09-04')]=2
 ck('unexplained_resume_factor_blocks',raises(Blocked,lambda:e.economic_preflight(NEXT,p)))
 d,e,t,p=setup_pause();d.actions['a']['events']=[dict(effective_date='2024-09-03')];d.cal=d.cal[d.cal!=DT];e.economic_preflight(DT,p)
 ck('noncommon_effective_action_not_lost_in_gap',raises(Blocked,lambda:e.economic_preflight(NEXT,p)))
 # Actual holding cannot be relabeled as a zero-share ticket.
 d,e,t,p=setup_pause();a=oldtests.attempt();e.active['a']=a;e.archive[a['id']]=a
 ck('held_stock_cannot_use_Q0_pause',raises(Blocked,lambda:e.economic_preflight(DT,p)))
 d=Scenario();d.missing.add(('a','2024-09-03'));e=Engine(d,'B');a=oldtests.attempt();e.active['a']=a;e.archive[a['id']]=a
 ck('uncovered_held_missing_quote_hard_stops',raises(Blocked,lambda:e.economic_preflight(DT,[])))
 d=Scenario();d.missing.add(('a','2024-09-03'));e=Engine(d,'A')
 ck('fresh_seed_has_no_retained_pause_exception',raises(Blocked,lambda:e.economic_preflight(DT,[oldtests.seed('a')])))
 # Approved held suspension: valuation only, no source row or liquidation claim.
 d=Scenario();d.missing.add(('a','2024-09-03'));d.stock.at[DT,'a']=-1;d.policies[('a','2024-09-03')]=dict(raw_mark='22.78',factor='1',origin=('s','p','0'),mark_source_day='2024-09-02')
 e=Engine(d,'B');a=oldtests.attempt();a['exit']='I_INVALID';a['cp']=oldtests.joint.cp();a['plan']=oldtests.plan();e.active['a']=a;e.archive[a['id']]=a;cash=e.cash;floor=a['ifloor'];cp=copy.deepcopy(a['cp']);e.economic_preflight(DT,[]);e.exit_open(DT);e.alloc_open(DT,[]);e.close(DT,PREV)
 ck('held_suspension_100_times_22_78_stale_mark',e.ledger[-1]['stale_market_value']=='2278.00' and e.quantity(a)==100)
 ck('held_suspension_no_sale_cash_fee_or_CP_change',not e.orders and e.cash==cash and a['ifloor']==floor and a['cp']==cp)
 ck('whole_account_liquidation_null_tradable_subset_separate',e.ledger[-1]['net_liquidation_NAV'] is None and e.ledger[-1]['whole_account_liquidation_available'] is False and e.ledger[-1]['tradable_subset_net_liquidation_value']==str(cash))
 ck('stale_holding_explicit_tags_and_capital_occupancy',e.holdings[-1]['stale'] and not e.holdings[-1]['tradable'] and e.qvalue(a,DT,'raw_open')==D('2278.00'))
 ck('no_synthetic_raw_row_inserted',not len(d.z('a',DT)))
 ck('held_resume_requires_known_prior_notice',raises(Blocked,lambda:e.economic_preflight(NEXT,[])))
 # A buy followed by missing CLOSE is not allowed to become a pending pause.
 class MissingClose(Scenario):
  def z(self,s,d):
   z=super().z(s,d)
   if s=='a' and day(d)=='2024-09-03':z['raw_close']=None
   return z
 class RollbackEngine(Engine):
  def alloc_open(self,d,p):return super().alloc_open(d,[oldtests.seed('a')])
  def export_ablation(self,path):pass
 d=MissingClose();d.days=d.cal[1:2];e=RollbackEngine(d,'D');saved=base.save;base.save=lambda *a,**k:None
 try:e.run_new(Path('/not-used'),'2024-09-03')
 finally:base.save=saved
 ck('OPEN_buy_missing_CLOSE_rolls_back_cash_shares_orders',e.cash==INITIAL and not e.active and not e.orders and bool(e.blockers) and not e.quote_gaps)
 result=dict(result='PASS',new_integration_checks=checks,new_integration_count=len(checks),prior_integration_count=19,prior_policy_count=60,prior_baseline_count=16,new_semantics_not_fact_only=True,historical_accounts_run=0)
 base.save(O/'SYNTHETIC_QA.json',result);print(json.dumps(result,ensure_ascii=False));return result
if __name__=='__main__':run()
