from decimal import Decimal as D
from types import SimpleNamespace
from collections import defaultdict
import copy
import pandas as pd
from engine import Engine,Blocked,sector_frame,INITIAL,QuantityRule
Z=D(0);dt=pd.Timestamp('2024-09-03');origin=('s','p','0')
class Stub:
 names={s:s for s in ['a','b','old','x']};sid_sector={'a':'A','b':'B','old':'A','x':'B'};sector_ids=['A','B'];events={};hashes={};excluded=[];admission=[]
 def z(self,s,d):return dict(raw_open=10,raw_close=10,adjustment_factor=1,source_kind='s',source_path='p',segment_id=0)
 def fee(self,*args):return D(5)
 def getmeta(self,*args):return (QuantityRule('x',100,100,100,True,1),None,None)
 def size(self,s,d,p,budget,cap):return max(0,min(int(cap)//100,int((budget-D(5))/p)//100))*100
 def action(self,s,d):return []
def attempt(s,q=100):
 return dict(id=s+'|1',sid=s,lots=[dict(id=s+'|lot',q=q,kind='SEED',bought='2024-09-02',floor=D(5))],ifloor=D(5),factor=D(1),origin=origin,exit=None,plan=None,cp=None,cashflow=D(-900),dividend=Z,fees=D(5),nav0=INITIAL,add_count=0,seed_day='2024-09-02')
def seed(s):return dict(kind='SEED',sid=s,birth_type='A',signal_day='2024-09-02',budget=D(24000),planned_q=100,capacity=100,ifloor=D(5),factor=D(1),origin=origin,nav0=INITIAL)
def cp():return dict(id='CP1',date='2024-09-02',floor=D(5),origin=origin,consumed=False,invalid=False)
def plan(s):return dict(kind='ADD',sid=s,signal_day='2024-09-02',cp_date='2024-09-02',cp_id='CP1',budget=D(24000),planned_q=100,capacity=100,close_net='95',origin=origin,factor=D(1))
def run():
 checks=[]
 # Fixed-N common-known aggregation is independent per sector.
 idx=pd.date_range('2024-09-01',periods=5);k=pd.DataFrame(True,index=idx,columns=list('abc'));r=pd.DataFrame(False,index=idx,columns=list('abc'));r.iloc[-2:]=True
 sf=sector_frame(k,r);assert sf.iloc[-1]['state']==1 and bool(sf.iloc[-1]['strength']);sf2=sector_frame(k,r&False);assert sf2.iloc[-1]['state']==0;checks.append('sector_states_independent_fixed_members')
 # Sector A is at 119,000 while the global account is 1,200,000: A rejects and B still fills.
 e=Engine(Stub());a=attempt('old',11900);e.active['old']=a;e.archive[a['id']]=a;e.cash=D(1081000);e.alloc_open(dt,[seed('b'),seed('a')]);assert [t['sid'] for t in e.orders]==['b'];assert e.candidates[0]['decision']=='MIN_LOT_CAPITAL_REJECT:sector_cap';assert e.cash==D('1079994.5000');checks.append('independent_sector_reservations_shared_NAV')
 # Global lexical queue, genuinely shared cash: one sector cannot spend the same cash twice.
 e=Engine(Stub());a=attempt('old',107800);e.active['old']=a;e.archive[a['id']]=a;e.cash=D(122000);e.d.sid_sector=dict(Stub.sid_sector,old='OLD',a='A',b='B');e.alloc_open(dt,[seed('b'),seed('a')]);assert [t['sid'] for t in e.orders]==['a'];assert e.candidates[-1]['decision']=='MIN_LOT_CAPITAL_REJECT:cash_reserve';assert e.cash>=D(120000);checks.append('global_SEED_order_and_shared_cash_reserve')
 # ADD precedes SEED irrespective of code, consumes exactly the actual filled CP.
 e=Engine(Stub());a=attempt('b');a['cp']=cp();c=a['cp'];a['plan']=plan('b');e.active['b']=a;e.archive[a['id']]=a;e.alloc_open(dt,[seed('a')]);assert [t['side'] for t in e.orders]==['BUY_ADD','BUY_SEED'];assert c['consumed'] and a['cp'] is None;checks.append('global_ADD_before_SEED_unique_actual_CP_consumption')
 # Failed ADD does not consume CP, even with positive plan/OPEN liquidation net.
 e=Engine(Stub());a=attempt('b');a['cp']=cp();a['plan']=plan('b');e.active['b']=a;e.archive[a['id']]=a;e.cash=D(100);e.alloc_open(dt,[]);assert not e.orders and not a['cp']['consumed'];checks.append('failed_ADD_retains_CP')
 # Register actual quantity, old attempt claim survives exit and new attempt, pay only at CLOSE.
 e=Engine(Stub());e.d.events={('a',pd.Timestamp('2024-09-04')):dict(record_date='2024-09-03',ex_date='2024-09-04',pay_date='2024-09-05',d_cash='1',d_source='1')};old=attempt('a');e.active['a']=old;e.archive[old['id']]=old;e.register_pay(dt);del e.active['a'];e.accrue(pd.Timestamp('2024-09-04'));assert e.receivable==80 and e.cash==INITIAL and old['dividend']==80;new=attempt('a');new['id']='a|2';e.active['a']=new;e.archive[new['id']]=new;e.register_pay(pd.Timestamp('2024-09-05'));assert e.cash==INITIAL+80 and e.receivable==0 and new['dividend']==0;e.register_pay(pd.Timestamp('2024-09-05'));assert e.cash==INITIAL+80;checks.append('registered_entitlement_cross_round_pay_close_once')
 # Pending ex-day new position with no prior ownership gets no entitlement; bridge still checked.
 e=Engine(Stub());e.d.events={('a',dt):dict(record_date='2024-09-02',ex_date='2024-09-03',pay_date='2024-09-03',d_cash='1',factor_old='1',factor_new='1',economic_event_id_candidate='a|e')};e.economic_preflight(dt,[seed('a')]);e.accrue(dt);e.register_pay(dt);assert e.receivable==0 and e.cash==INITIAL and e.equity[0]['record_qty']==0;checks.append('pending_entry_zero_entitlement_with_bridge')
 # A complete day rollback includes partial orders, archive/active shared object identity and per-sector ledger.
 class Dated(Stub):
  events={};cal=pd.DatetimeIndex(['2024-09-02','2024-09-03']);days=cal[1:]
 class Fail(Engine):
  def economic_preflight(self,d,p):pass
  def accrue(self,d):pass
  def exit_open(self,d):pass
  def alloc_open(self,d,p):self.cash-=D(123);self.orders.append({'day':'2024-09-03','side':'BUY_SEED'})
  def close(self,d,p):self.sector_daily.append({'bad':True});raise Blocked('2024-09-03 a CLOSE_INVALID')
 e=Fail(Dated()).run();assert e.cash==INITIAL and not e.orders and not e.sector_daily and e.uncertified_day['partial_orders'];checks.append('atomic_uncertified_day_rollback')
 e=Engine(Stub());a=attempt('a');e.d.z=lambda s,d:{}
 try:e.qvalue(a,dt,'raw_close');assert False
 except Blocked as ex:assert 'RAW_CLOSE_MISSING' in str(ex)
 checks.append('missing_held_mark_is_explicit_blocker')
 return checks
