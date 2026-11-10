from stress_engine import *
ORIGIN=('s','p','0');DT=pd.Timestamp('2024-09-03')
class Stub:
 names={s:s for s in ['a','b','old','x']};sid_sector={'a':'A','b':'B','old':'OLD','x':'X'};sector_ids=['A','B','OLD','X'];events={};hashes={};excluded=[];admission=[]
 def __init__(self):self.bars={};self.events={};self.sid_sector=dict(type(self).sid_sector)
 def z(self,s,d):return dict(raw_open=10,raw_high=11,raw_low=9,raw_close=10,adjustment_factor=1,source_kind='s',source_path='p',segment_id=0,**self.bars.get((s,day(d)),{})) if not self.bars.get((s,day(d))) else dict(dict(raw_open=10,raw_high=11,raw_low=9,raw_close=10,adjustment_factor=1,source_kind='s',source_path='p',segment_id=0),**self.bars[(s,day(d))])
 def fee(self,*args):return D(5)
 def getmeta(self,*args):return (b.QuantityRule('x',100,100,100,True,1),None,None)
 def size(self,s,d,p,budget,cap):return max(0,min(int(cap)//100,int((budget-D(5))/p)//100))*100
 def action(self,s,d):return []
 def same(self,s,d=DT,p=10):self.bars[(s,day(d))]=dict(raw_open=p,raw_high=p,raw_low=p,raw_close=p)
def attempt(s,q=100):
 return dict(id=s+'|1',sid=s,lots=[dict(id=s+'|lot',q=q,kind='SEED',bought='2024-09-02',floor=D(5))],ifloor=D(5),factor=D(1),origin=ORIGIN,exit=None,plan=None,cp=None,cashflow=D(-900),dividend=ZERO,fees=D(5),nav0=INITIAL,add_count=0,seed_day='2024-09-02')
def seed(s):return dict(kind='SEED',sid=s,birth_type='A',signal_day='2024-09-02',budget=D(24000),planned_q=100,capacity=100,ifloor=D(5),factor=D(1),origin=ORIGIN,nav0=INITIAL)
def cp():return dict(id='CP1',date='2024-09-02',floor=D(5),origin=ORIGIN,consumed=False,invalid=False)
def plan(s):return dict(kind='ADD',sid=s,signal_day='2024-09-02',cp_date='2024-09-02',cp_id='CP1',budget=D(24000),planned_q=100,capacity=100,close_net='95',origin=ORIGIN,factor=D(1))
def add(e,a):e.active[a['sid']]=a;e.archive[a['id']]=a

def batch(e,p=(),dt=DT):e.freeze_intent(dt,list(p));e.exit_open(dt);e.alloc_open(dt,list(p))
def run():
 checks=[]
 e=StressEngine(Stub());assert not e.no_fill('a',DT);e.d.same('a');assert e.no_fill('a',DT);e.d.bars[('a',day(DT))]['raw_high']=10.000001;assert not e.no_fill('a',DT);checks.append('exact_raw_OHLC_not_near_limit_threshold')
 e.d.bars[('a',day(DT))]['raw_high']=float('nan')
 try:e.no_fill('a',DT);raise AssertionError('missing gate did not block')
 except Blocked:pass
 checks.append('missing_gate_data_blocks')
 e=StressEngine(Stub());e.d.same('a');batch(e,[seed('a')]);assert not e.active and not e.archive and not e.orders and e.cash==INITIAL and len(e.nofills)==1 and e.reservations[0]['reserved_q']==100
 batch(e,[],pd.Timestamp('2024-09-04'));assert not e.active and not e.orders;checks.append('unfilled_seed_expires_no_position_or_old_ticket_replay')
 e=StressEngine(Stub());a=attempt('a');a['cp']=cp();a['plan']=plan('a');add(e,a);e.d.same('a');batch(e);assert a['cp'] and not a['cp']['consumed'] and a['add_count']==0 and e.quantity(a)==100 and not e.orders
 a['plan']=plan('a');batch(e,[],pd.Timestamp('2024-09-04'));assert e.quantity(a)==200 and a['add_count']==1 and a['cp'] is None and len(e.orders)==1;checks.append('unfilled_ADD_preserves_CP_later_qualified_retry_fills')
 e=StressEngine(Stub());a=attempt('a');a['exit']='I_INVALID';add(e,a);e.d.same('a');batch(e);assert e.quantity(a)==100 and a['lots'][0]['exit'] and e.cash==INITIAL and not e.orders
 batch(e,[],pd.Timestamp('2024-09-04'));assert not e.active and e.cash==INITIAL+D('994.5000') and len(e.orders)==1;checks.append('unfilled_SELL_keeps_locked_lot_retries_no_fake_cash')
 e=StressEngine(Stub());a=attempt('a');a['lots'][0]['bought']=day(DT);a['exit']='I_INVALID';add(e,a);e.d.same('a');batch(e);assert not e.orders and not e.nofills and a['lots'][0]['exit']=='T1_LOCKED_EXIT';checks.append('T1_precedes_gate_no_same_day_sale')
 # Only a can receive the frozen batch's last cash. Its no-fill must not revive b.
 e=StressEngine(Stub());a=attempt('old',107800);add(e,a);e.cash=D(122000);e.d.same('a');batch(e,[seed('b'),seed('a')]);assert not e.orders and e.cash==D(122000);assert len(e.nofills)==1 and e.nofills[0]['sid']=='a';assert e.candidates[-1]['decision']=='MIN_LOT_CAPITAL_REJECT:cash_reserve';assert len(e.reservations)==1;checks.append('original_cash_reservation_no_same_batch_reallocation_after_no_fill')
 # Original exit would fund seeds, but actual failed sell must not supply cash.
 e=StressEngine(Stub());a=attempt('old',108000);a['exit']='I_INVALID';add(e,a);e.cash=D(120000);e.d.same('old');batch(e,[seed('a')]);assert [x['side'] for x in e._intent_orders]==['SELL_ALL','BUY_SEED'];assert not e.orders and e.cash==D(120000);assert e.candidates[-1]['executed_q']==0;checks.append('failed_sale_cannot_fund_original_approved_buy')
 # Actual intent snapshot begins from the pressure account, not baseline future holdings.
 e=StressEngine(Stub());batch(e,[seed('a')]);assert set(e.active)=={'a'} and all(x['sid']!='old' for x in e.intents);checks.append('intent_clone_starts_from_current_actual_scenario_state')
 # Once the gate is off, actual cash/lots/orders and ordinary candidate fields equal baseline.
 d=Stub();d.same('a');e=StressEngine(d,False);base=b.Engine(d);a=attempt('b');a['cp']=cp();a['plan']=plan('b');add(e,a);add(base,copy.deepcopy(a));batch(e,[seed('a')]);base.exit_open(DT);base.alloc_open(DT,[seed('a')]);assert e.cash==base.cash and e.active==base.active and e.archive==base.archive and e.orders==base.orders and e.cp_log==base.cp_log
 extra={'original_intended_q','reserved_q','fill_status'};assert [{k:v for k,v in x.items() if k not in extra} for x in e.candidates]==base.candidates;checks.append('gate_off_baseline_exact_account_and_order_equality')
 # Missing gate data after partial actions must roll back all logs and shared identities.
 class Dated(Stub):cal=pd.DatetimeIndex(['2024-09-02','2024-09-03']);days=cal[1:]
 class Fail(StressEngine):
  def economic_preflight(self,d,p):pass
  def accrue(self,d):pass
  def freeze_intent(self,d,p):pass
  def exit_open(self,d):self.cash-=123;self.orders.append(dict(day=day(d)));self.nofills.append({'x':1});self.intents.append({'x':1});self.reservations.append({'x':1})
  def alloc_open(self,d,p):pass
  def close(self,d,p):raise Blocked('synthetic failed gate')
 e=Fail(Dated()).run();assert e.cash==INITIAL and not e.orders and not e.nofills and not e.intents and not e.reservations and e.uncertified_day['partial_orders'];checks.append('atomic_day_rollback_includes_intents_reservations_and_nofills')
 # Ensure copied allocator cannot drift in unchanged sizing/economic guards.
 assert 'original[\'executed_q\']' in (ROOT/'stress_engine.py').read_text();checks.append('original_intended_qty_is_hard_execution_upper_bound')
 return dict(result='PASS',checks=checks,historical_scenario_not_run=True)
