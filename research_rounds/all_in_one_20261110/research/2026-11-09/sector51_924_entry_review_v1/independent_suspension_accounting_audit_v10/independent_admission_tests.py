"""Separately written adversarial tests for narrow suspension accounting only."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,copy,json,hashlib,sys
import pandas as pd
sys.dont_write_bytecode=True
A=Path(__file__).resolve().parent;C=A.parent/'joint51_candidate_v10_suspension_accounting';spec=importlib.util.spec_from_file_location('v10_audit_target',C/'engine.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
T=pd.Timestamp('2024-10-28');P=pd.Timestamp('2024-10-25');OR=('audit','frozen','0')
class Quotes:
 names={'a':'a','b':'b'};sid_sector={'a':'A','b':'B'};sector_ids=['A','B'];ids=['a','b']
 def __init__(self):
  self.cal=pd.DatetimeIndex([P,T,pd.Timestamp('2024-10-29')]);self.days=self.cal[1:2];self.events={};self.actions={};self.invalid_b=False;self.inject_row=False
  self.policy=dict(sid='a',covered_dates=['2024-10-28'],known_from_date='2024-10-28',raw_mark='12.02',factor='1',origin=OR,mark_source_day='2024-10-25')
  self.stock=pd.DataFrame({'a':[-1,-1,-1],'b':[0,0,0]},index=self.cal)
  self.sectors={sec:pd.DataFrame(dict(N=3,K=2,n=2,U=1,paired_K=2,entered3=0,left3=0,diff=0,state=1,strength=False),index=self.cal) for sec in self.sector_ids};self.cap={s:pd.Series(100,index=self.cal) for s in self.ids}
 def suspension(self,s,d):return self.policy if s=='a' and str(d.date()) in self.policy['covered_dates'] else None
 def z(self,s,d):
  if s=='a':return {'raw_open':12.02} if self.inject_row else {}
  if self.invalid_b:return {}
  return dict(raw_open=1,raw_close=1,adjustment_factor=1,source_kind=OR[0],source_path=OR[1],segment_id=0,observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
 def f(self,s,d):return dict(i_target=False,i_floor=30) if s=='a' else dict(i_target=True,i_floor=.1)
 def c(self,s,d):return dict(receipt=True,candidate=30) if s=='a' else dict(receipt=False)
 def fee(self,*args):return D(5)
 def getmeta(self,*args):return m.QuantityRule('q',100,100,100,True,1),None,None
 def size(self,s,d,p,budget,cap):return max(0,min(int(cap)//100,int((budget-D(5))/p)//100))*100
 def action(self,s,d):return self.actions.get(s,[])
def holding():
 return dict(id='a|R',sid='a',signal_day='2024-10-22',birth_type='A',nav0=D(1200000),seed_day='2024-10-23',cashflow=D(-1000),dividend=D(0),fees=D(5),lots=[dict(id='a|L',kind='SEED',q=100,bought='2024-10-23',floor=D(20),cp_id=None)],ifloor=D(20),factor=D(1),origin=OR,exit=None,plan=None,cp=dict(id='cp',date='2024-10-25',floor=D(18),origin=OR,consumed=False,invalid=False),add_count=0)
def engine():
 e=m.Engine(Quotes());a=holding();e.active['a']=a;e.archive[a['id']]=a;return e,a
def seed(s='b'):return dict(kind='SEED',sid=s,birth_type='A',signal_day='2024-10-25',budget=D(24000),planned_q=100,capacity=100,ifloor=D('.1'),factor=D(1),origin=OR,nav0=D(1200000))
def block(fn,part):
 try:fn()
 except m.Blocked as ex:assert part in str(ex);return
 raise AssertionError('no block: '+part)
checks=[]
e,a=engine();old=copy.deepcopy(a);e.economic_preflight(T,[]);e.exit_open(T);e.close(T,P);assert a==old and not e.orders and not e.cp_log;assert e.holdings[0]['raw_mark']=='12.02' and e.holdings[0]['stale'] and not e.holdings[0]['tradable'];assert e.ledger[0]['net_liquidation_NAV'] is None and e.ledger[0]['tradable_subset_net_liquidation_value']==str(m.INITIAL);assert e.ledger[0]['stale_market_value']=='1202.00';checks.append('stale_below_I_CP_floors_and_ghost_receipt_never_trigger_price_or_CP_actions')
e,a=engine();e.cash=D(240);e.alloc_open(T,[seed()]);assert not e.orders and e.candidates[0]['decision']=='MIN_LOT_CAPITAL_REJECT:cash_reserve';assert D(e.candidates[0]['cash_reserve'])==D('95.8');assert e.cash==240;checks.append('1202_stale_value_in_NAV_enforces_original_cash_floor_not_freed_funding')
e,a=engine();e.cash=D(10000);e.d.sid_sector={'a':'A','b':'A'};e.alloc_open(T,[seed()]);assert not e.orders and e.candidates[0]['decision']=='MIN_LOT_CAPITAL_REJECT:sector_cap';assert D(e.candidates[0]['sector_cap'])==0;checks.append('1202_stale_value_remains_sector_exposure')
e,a=engine();a['exit']='I_INVALID';a['lots'][0]['exit']='CP_LAYER';before=copy.deepcopy(a);e.exit_open(T);assert a==before and e.cash==m.INITIAL and not e.orders;assert e.suspension_log[-1]['event']=='EXIT_DEFERRED_NONTRADABLE';checks.append('existing_round_and_lot_exit_locks_survive_without_sale_cash')
for side in ['BUY_SEED','BUY_ADD','SELL_ALL','SELL_LAYERS']:
 e,a=engine();before=copy.deepcopy(a);block(lambda:e.order(a,T,side,100,D('12.02'),'forbidden'),'SUSPENDED_ORDER_FORBIDDEN');assert a==before and not e.orders and e.cash==m.INITIAL
checks.append('order_sink_blocks_all_four_suspended_sides')
e,a=engine();block(lambda:e.net(a,T,'raw_open'),'NONTRADABLE_NET_NOT_DEFINED');block(lambda:e.net(a,T,'raw_close'),'NONTRADABLE_NET_NOT_DEFINED');checks.append('stale_mark_cannot_be_used_as_positive_profit_quote')
for kind in ['action','event','source','factor','row','uncovered','other_missing','unknown']:
 e,a=engine()
 if kind=='action':e.d.actions['a']=[{'unreviewed':True}];fn=lambda:e.economic_preflight(T,[]);msg='SUSPENSION_EQUITY_REQUIRES_SEPARATE_BRIDGE'
 elif kind=='event':e.d.events[('a',T)]={'reviewed':True};fn=lambda:e.economic_preflight(T,[]);msg='SUSPENSION_EQUITY_REQUIRES_SEPARATE_BRIDGE'
 elif kind=='source':a['origin']=('different','frozen','0');fn=lambda:e.economic_preflight(T,[]);msg='SUSPENSION_ANCHOR_SOURCE_MISMATCH'
 elif kind=='factor':a['factor']=D(2);fn=lambda:e.economic_preflight(T,[]);msg='SUSPENSION_ANCHOR_FACTOR_MISMATCH'
 elif kind=='row':e.d.inject_row=True;fn=lambda:e.economic_preflight(T,[]);msg='SUSPENSION_UNEXPECTED_ROW'
 elif kind=='uncovered':fn=lambda:e.economic_preflight(pd.Timestamp('2024-10-29'),[]);msg='OPEN_MISSING'
 elif kind=='other_missing':e.d.invalid_b=True;fn=lambda:e.economic_preflight(T,[seed()]);msg='b OPEN_MISSING'
 else:e.d.stock.at[T,'a']=1;fn=lambda:e.close(T,P);msg='SUSPENDED_STOCK_STATE_NOT_UNKNOWN'
 block(fn,msg)
checks.append('eight_admission_violations_fail_closed_without_general_missing_data_amnesty')
e,a=engine();e.d.sectors['A'].at[T,'state']=0;e.close(T,P);assert a['exit']=='TRIAL_SECTOR_FALSE' and not e.orders and not e.cp_log;checks.append('independent_sector_FALSE_only_records_exit_intent')
class FailAfterClose(m.Engine):
 def close(self,d,prev):super().close(d,prev);raise m.Blocked('unrelated_bad_mark')
e=FailAfterClose(Quotes());a=holding();e.active['a']=a;e.archive[a['id']]=a;e.d.sectors['A'].at[T,'state']=0;old=copy.deepcopy(a);e.run();assert e.active['a']==old and e.active['a'] is e.archive[a['id']];assert not e.ledger and not e.preflight_log and not e.suspension_log and not e.candidates and not e.holdings;checks.append('unrelated_failure_rolls_back_stale_disclosure_new_logs_and_sector_lock')
pol=json.loads((C/'SUSPENSION_POLICY.json').read_text());assert 'retrospectively_confirmed_resume_date' not in pol and 'resume_date' not in pol and 'future_resume_date' not in pol;assert pol['future_notices_or_resume_date_used_for_decisions'] is False;checks.append('real_operational_policy_contains_no_future_resume_date')
result=dict(status='PASS',checks=checks,test_groups=len(checks),engine_sha256=hashlib.sha256((C/'engine.py').read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Independently constructed micro-cases only; not a historical strategy run or real-fill certification.')
p=A/'INDEPENDENT_ADMISSION_TESTS.json';assert not p.exists();p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
