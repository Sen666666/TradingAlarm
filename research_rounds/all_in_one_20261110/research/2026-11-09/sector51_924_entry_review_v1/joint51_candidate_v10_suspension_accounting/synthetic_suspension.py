from decimal import Decimal as D
import copy
import pandas as pd
from engine import Engine,Data,Blocked,INITIAL,day
from synthetic_joint import Stub,attempt,seed,cp,plan,origin
DT=pd.Timestamp('2024-10-28');PREV=pd.Timestamp('2024-10-25')
class Susp(Stub):
 ids=['a','b'];cal=pd.DatetimeIndex(['2024-10-25','2024-10-28','2024-10-29']);days=cal[1:];events={}
 def __init__(self):
  self.policy=dict(sid='a',covered_dates=['2024-10-28','2024-10-29'],raw_mark='12.02',factor='1',origin=origin,mark_source_day='2024-10-25')
  self.stock=pd.DataFrame({'a':[-1,-1,-1],'b':[0,0,0]},index=self.cal)
  self.sectors={s:pd.DataFrame(dict(N=3,K=3,n=0,U=0,paired_K=3,entered3=0,left3=0,diff=0,state=0,strength=False),index=self.cal) for s in ['A','B']}
  self.cap={s:pd.Series(100,index=self.cal) for s in self.ids}
 def suspension(self,s,d):return self.policy if s=='a' and day(d) in self.policy['covered_dates'] else None
 def z(self,s,d):
  if self.suspension(s,d):return {}
  return dict(raw_open=10,raw_close=10,adjustment_factor=1,source_kind='s',source_path='p',segment_id=0,observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
 def f(self,s,d):return {} if self.suspension(s,d) else dict(i_target=True,i_floor=5)
 def c(self,s,d):return {} if self.suspension(s,d) else dict(receipt=False)
def held():
 e=Engine(Susp());a=attempt('a');a['cp']=cp();e.active['a']=a;e.archive[a['id']]=a;return e,a
def blocked(fn,needle):
 try:fn()
 except Blocked as ex:assert needle in str(ex),(str(ex),needle);return
 raise AssertionError('Expected '+needle)
def run():
 checks=[]
 e,a=held();assert e.qvalue(a,DT,'raw_open')==D('1202') and e.qvalue(a,DT,'raw_close')==D('1202');assert e.nav(DT,'raw_open')==INITIAL+D('1202');assert e.liquidation_value(DT) is None and e.liquidation_value(DT,True)==INITIAL;assert e.d.z('a',DT)=={};checks.append('stale_value_NAV_only_no_synthetic_bar_or_liquidation')
 blocked(lambda:e.net(a,DT,'raw_close'),'NONTRADABLE_NET_NOT_DEFINED');checks.append('stale_mark_never_whole_round_profit_quote')
 e.economic_preflight(DT,[seed('b')]);assert len(e.preflight_log)==2 and e.preflight_log[0]['observed_factor'] is False;checks.append('all_held_pending_preflight_obligations_logged')
 e,a=held();a['exit']='I_CLOSE_PROTECTION';a['lots'][0]['exit']='CP_CLOSE_PROTECTION';old=copy.deepcopy(a);e.exit_open(DT);assert a==old and not e.orders and e.cash==INITIAL and e.suspension_log[-1]['event']=='EXIT_DEFERRED_NONTRADABLE';checks.append('suspended_locked_exit_retained_no_cash_share_or_fee_change')
 e,a=held();a['plan']=plan('a');oldcp=copy.deepcopy(a['cp']);e.alloc_open(DT,[seed('b')]);assert e.candidates[0]['allocation_rank']==1 and e.candidates[0]['decision']=='SUSPENDED_NONTRADABLE';assert e.candidates[1]['allocation_rank']==2 and e.orders[0]['sid']=='b';assert a['cp']==oldcp and a['plan'] is None;assert D(e.candidates[0]['cash_reserve'])==INITIAL-D('.10')*(INITIAL+D(1202));checks.append('suspended_ADD_original_rank_no_reservation_no_CP_consumption_other_seed_proceeds')
 e=Engine(Susp());e.alloc_open(DT,[seed('a'),seed('b')]);assert len(e.orders)==1 and e.orders[0]['sid']=='b' and e.candidates[0]['executed_q']==0 and 'a' not in e.active;checks.append('suspended_SEED_rejected_no_delayed_or_fake_attempt')
 e,a=held();old=copy.deepcopy(a);out=e.close(DT,PREV);assert not out and a['exit']=='TRIAL_SECTOR_FALSE';assert a['cp']==old['cp'] and a['ifloor']==old['ifloor'] and a['lots']==old['lots'];assert e.ledger[-1]['net_liquidation_NAV'] is None and e.ledger[-1]['stale_market_value']=='1202.00';assert e.holdings[-1]['stale'] and not e.holdings[-1]['tradable'];assert not e.cp_log and not e.orders;checks.append('suspended_CLOSE_unknown_no_price_signal_sector_only_exit_and_tagged_marks')
 e,a=held();e.d.action=lambda s,d:[{'event':'unadmitted'}] if s=='a' else [];blocked(lambda:e.economic_preflight(DT,[]),'SUSPENSION_EQUITY_REQUIRES_SEPARATE_BRIDGE');checks.append('suspension_does_not_waive_unadmitted_corporate_action')
 e,a=held();e.d.events={('a',DT):{'reviewed':'but no observed bridge'}};blocked(lambda:e.economic_preflight(DT,[]),'SUSPENSION_EQUITY_REQUIRES_SEPARATE_BRIDGE');checks.append('suspension_does_not_waive_even_reviewed_event_bridge')
 e,a=held();a['origin']=('bad','p','0');blocked(lambda:e.economic_preflight(DT,[]),'SUSPENSION_ANCHOR_SOURCE_MISMATCH');e,a=held();a['factor']=D(2);blocked(lambda:e.economic_preflight(DT,[]),'SUSPENSION_ANCHOR_FACTOR_MISMATCH');checks.append('anchor_origin_and_factor_must_match_all_exposures')
 e,a=held();r=seed('a');r['factor']=D(2);blocked(lambda:e.economic_preflight(DT,[r]),'SUSPENSION_ANCHOR_FACTOR_MISMATCH');checks.append('suspended_pending_factor_also_checked_when_held')
 e,a=held();original=e.d.z;e.d.z=lambda s,d:{} if s=='b' else original(s,d);blocked(lambda:e.economic_preflight(DT,[seed('b')]),'b OPEN_MISSING');checks.append('other_missing_pending_still_hard_blocks')
 e,a=held();e.d.z=lambda s,d:{};blocked(lambda:e.economic_preflight(pd.Timestamp('2024-10-30'),[]),'a OPEN_MISSING');checks.append('uncovered_date_still_hard_blocks')
 e,a=held();e.d.z=lambda s,d:{'raw_open':12.02};blocked(lambda:e.economic_preflight(DT,[]),'SUSPENSION_UNEXPECTED_ROW');checks.append('no_suspension_override_when_raw_row_unexpected')
 e,a=held();e.d.stock.at[DT,'a']=1;blocked(lambda:e.close(DT,PREV),'SUSPENDED_STOCK_STATE_NOT_UNKNOWN');checks.append('nonUNKNOWN_input_not_silently_overwritten')
 # A cash payment from an earlier admitted ex-date survives suspension; registration is still actual held quantity.
 e,a=held();ex=pd.Timestamp('2024-10-24');e.d.events={('a',ex):dict(record_date='2024-10-23',ex_date='2024-10-24',pay_date='2024-10-28',d_cash='1')};e.snapshots[('a','2024-10-23')]={'q':100,'round':a['id']};e.accrue(ex);e.economic_preflight(DT,[]);e.register_pay(DT);assert e.cash==INITIAL+80 and e.receivable==0 and a['dividend']==80;e.register_pay(DT);assert e.cash==INITIAL+80;checks.append('prior_admitted_cash_receivable_still_paid_once_while_suspended')
 class Failing(Engine):
  def close(self,d,prev):
   super().close(d,prev);raise Blocked('synthetic other failure')
 e=Failing(Susp());a=attempt('a');e.active['a']=a;e.archive[a['id']]=a;e.run();assert not e.orders and not e.ledger and not e.suspension_log and not e.preflight_log and e.active['a']['exit'] is None;checks.append('atomic_rollback_includes_new_audit_logs_and_sector_exit')
 e,a=held();snapshot=copy.deepcopy(a);blocked(lambda:e.order(a,DT,'SELL_ALL',100,D('12.02'),'illegal_direct_call'),'SUSPENDED_ORDER_FORBIDDEN');assert e.cash==INITIAL and a==snapshot and not e.orders;checks.append('order_sink_rejects_any_suspended_fill')
 fake=object.__new__(Data);fake.suspension_policy=dict(sid='a',covered_dates=['2024-10-28'],future_resume_date='2099-01-01');assert fake.suspension('a',DT);fake.suspension_policy['future_resume_date']='2024-10-29';assert fake.suspension('a',DT);assert fake.suspension('a',pd.Timestamp('2024-10-29')) is None;checks.append('operational_coverage_does_not_consult_future_resume_date')
 return checks
